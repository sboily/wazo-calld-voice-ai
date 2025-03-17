# -*- coding: utf-8 -*-
# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os
import functools
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from websocket import WebSocketApp

from .engines.factory import SttEngineFactory

logger = logging.getLogger(__name__)


class SttService(object):

    def __init__(self, config, ari, notifier):
        self._config = config
        self._notifier = notifier
        self._ari = ari
        self._threadpool = ThreadPoolExecutor(max_workers=self._config["stt"]["workers"])
        self._engine_type = config["stt"]["engine"]
        self._buffers = {}
        self._current_calls = {}
        self._websockets = {}  # Store websocket instances for each call
        self._shutdown_lock = threading.RLock()  # Lock for thread-safe shutdown
        
        if self._config["stt"].get("dump_dir"):
            try:
                os.makedirs(self._config["stt"]["dump_dir"])
            except OSError:
                pass

        # Create the STT engine using the factory
        self._engine = SttEngineFactory.create_engine(
            self._engine_type, 
            self._config, 
            self._notifier
        )

    def start(self, channel, tenant_uuid, use_ai=None):
        """Start STT processing for a channel
        
        Args:
            channel: The channel to process
            tenant_uuid: The tenant UUID
            use_ai: Override use_ai setting for this channel (only for voice_ai engine)
        """
        logger.info(f"Starting STT for channel: {channel.id}")
        
        kwargs = {}
        if use_ai is not None:
            kwargs["use_ai"] = use_ai
            
        # Initialize the engine for this channel
        self._engine.start(channel, tenant_uuid, **kwargs)
        
        # Start a thread to handle audio for this channel
        call_thread = self._threadpool.submit(self._handle_call, channel, tenant_uuid)
        self._current_calls[channel.id] = {
            "thread": call_thread,
            "tenant_uuid": tenant_uuid
        }

    def stop(self, call_id, tenant_uuid):
        """Stop STT processing for a call
        
        Args:
            call_id: The call ID to stop processing for
            tenant_uuid: The tenant UUID
        """
        with self._shutdown_lock:
            logger.info(f"Stopping STT for channel: {call_id}")
            
            # Close ARI websocket if it exists
            if call_id in self._websockets:
                try:
                    ws = self._websockets.pop(call_id)
                    ws.close()
                    logger.info(f"Closed ARI websocket for channel: {call_id}")
                except Exception as e:
                    logger.error(f"Error closing ARI websocket for channel {call_id}: {e}")
            
            # Cancel the thread
            call_data = self._current_calls.pop(call_id, None)
            if call_data and "thread" in call_data:
                call = call_data["thread"]
                try:
                    call.cancel()
                except Exception as e:
                    logger.error(f"Error canceling thread for channel {call_id}: {e}")
                
                # Stop the engine for this channel (will close Voice AI websocket)
                try:
                    self._engine.stop(call_id, tenant_uuid)
                except Exception as e:
                    logger.error(f"Error stopping engine for channel {call_id}: {e}")
                
                # Clean up any remaining buffers
                if call_id in self._buffers:
                    del self._buffers[call_id]
                    
                return True
            
            return False
    
    def stop_all(self):
        """Stop all active STT sessions
        
        This method is called during shutdown to ensure all resources are released.
        """
        with self._shutdown_lock:
            logger.info(f"Stopping all STT sessions ({len(self._current_calls)} active)")
            
            # Make a copy of the keys to avoid modifying during iteration
            call_ids = list(self._current_calls.keys())
            
            # Stop each call
            for call_id in call_ids:
                try:
                    call_data = self._current_calls.get(call_id)
                    if call_data and "tenant_uuid" in call_data:
                        tenant_uuid = call_data["tenant_uuid"]
                        self.stop(call_id, tenant_uuid)
                    else:
                        logger.warning(f"Missing tenant_uuid for call {call_id} during shutdown")
                        # Attempt to stop anyway with None for tenant_uuid
                        self.stop(call_id, None)
                except Exception as e:
                    logger.error(f"Error stopping call {call_id} during shutdown: {e}")
            
            # Shutdown the thread pool
            logger.info("Shutting down STT threadpool")
            try:
                self._threadpool.shutdown(wait=False)
            except Exception as e:
                logger.error(f"Error shutting down threadpool: {e}")
            
            logger.info("All STT sessions stopped")

    def get_channel_by_id(self, channel_id, tenant_uuid):
        """Get a channel by ID
        
        Args:
            channel_id: The channel ID to get
            tenant_uuid: The tenant UUID # Not implemented
        """
        return self._ari.channels.get(channelId=channel_id)

    def _open_dump(self, channel):
        """Open a dump file for a channel
        
        Args:
            channel: The channel to open a dump for
        """
        if self._config["stt"].get("dump_dir"):
            return open("%s/wazo-stt-dump-%s.pcm" % (
                self._config["stt"]["dump_dir"],
                channel.id), "wb+")
        return None

    def _handle_call(self, channel, tenant_uuid):
        """Handle a call with STT
        
        Args:
            channel: The channel to handle
            tenant_uuid: The tenant UUID
        """
        dump = self._open_dump(channel)
        
        # Connect to ARI websocket for audio stream
        ws = WebSocketApp(self._config["stt"]["ari_websocket_stream"],
                          header={"Channel-ID": channel.id},
                          subprotocols=["stream-channel"],
                          on_error=self._on_error,
                          on_message=functools.partial(self._on_message,
                                                       channel=channel,
                                                       tenant_uuid=tenant_uuid,
                                                       dump=dump),
                          on_close=functools.partial(self._on_close,
                                                     channel=channel,
                                                     tenant_uuid=tenant_uuid,
                                                     dump=dump)
                          )
        
        # Store the websocket instance for potential early closure
        self._websockets[channel.id] = ws
        
        logger.info(f"Websocket client started for channel: {channel.id}")
        
        try:
            ws.run_forever()
        except Exception as e:
            logger.error(f"Error in websocket for channel {channel.id}: {e}")
        finally:
            # Clean up when the websocket exits
            with self._shutdown_lock:
                if channel.id in self._websockets and self._websockets[channel.id] is ws:
                    del self._websockets[channel.id]
                if channel.id in self._current_calls:
                    del self._current_calls[channel.id]

    def _on_error(self, ws, error):
        """Handle websocket errors
        
        Args:
            ws: The websocket
            error: The error
        """
        logger.error(f"STT websocket error: {error}")

    def _on_close(self, ws, channel, tenant_uuid, dump):
        """Handle websocket close
        
        Args:
            ws: The websocket
            channel: The channel
            tenant_uuid: The tenant UUID
            dump: The dump file
        """
        # Process any remaining audio
        try:
            self._send_buffer(channel, tenant_uuid, dump)
        except Exception as e:
            logger.error(f"Error sending final buffer for channel {channel.id}: {e}")
        
        # Close the dump file if it exists
        if dump:
            try:
                dump.close()
            except Exception as e:
                logger.error(f"Error closing dump file for channel {channel.id}: {e}")
            
        # Clean up this channel's entry in the websockets dict
        with self._shutdown_lock:
            if channel.id in self._websockets and self._websockets[channel.id] is ws:
                del self._websockets[channel.id]
            
        logger.info(f"ARI websocket closed for channel: {channel.id}")

    def _on_message(self, ws, message, channel=None, tenant_uuid=None, dump=None):
        """Handle websocket messages
        
        Args:
            ws: The websocket
            message: The message
            channel: The channel
            tenant_uuid: The tenant UUID
            dump: The dump file
        """
        chunk = self._buffers.setdefault(channel.id, b'') + message
        self._buffers[channel.id] = chunk

        if len(chunk) < 1024 * 64:
            return

        self._send_buffer(channel, tenant_uuid, dump)

    def _send_buffer(self, channel, tenant_uuid, dump):
        """Send a buffer to the speech service
        
        Args:
            channel: The channel
            tenant_uuid: The tenant UUID
            dump: The dump file
        """
        chunk = self._buffers.pop(channel.id, None)
        if not chunk:
            return

        if dump:
            dump.write(chunk)
            
        # Process the chunk with the engine
        try:
            self._engine.process_audio_chunk(channel, tenant_uuid, chunk)
        except Exception as e:
            logger.error(f"Error processing audio chunk for channel {channel.id}: {e}")
