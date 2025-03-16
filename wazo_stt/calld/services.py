# -*- coding: utf-8 -*-
# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os
import functools
import logging
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

    def start(self, channel, use_ai=None):
        """Start STT processing for a channel
        
        Args:
            channel: The channel to process
            use_ai: Override use_ai setting for this channel (only for voice_ai engine)
        """
        logger.info(f"Starting STT for channel: {channel.id}")
        
        kwargs = {}
        if use_ai is not None:
            kwargs["use_ai"] = use_ai
            
        # Initialize the engine for this channel
        self._engine.start(channel, **kwargs)
        
        # Start a thread to handle audio for this channel
        call_thread = self._threadpool.submit(self._handle_call, channel)
        self._current_calls.update({channel.id: call_thread})

    def stop(self, call_id):
        """Stop STT processing for a call
        
        Args:
            call_id: The call ID to stop processing for
        """
        logger.info(f"Stopping STT for channel: {call_id}")
        call = self._current_calls.get(call_id)
        if call:
            call.cancel()
            # Stop the engine for this channel
            self._engine.stop(call_id)
            return call.done()
        return False

    def get_channel_by_id(self, channel_id):
        """Get a channel by ID
        
        Args:
            channel_id: The channel ID to get
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

    def _handle_call(self, channel):
        """Handle a call with STT
        
        Args:
            channel: The channel to handle
        """
        dump = self._open_dump(channel)
        
        # Connect to ARI websocket for audio stream
        ws = WebSocketApp(self._config["stt"]["ari_websocket_stream"],
                          header={"Channel-ID": channel.id},
                          subprotocols=["stream-channel"],
                          on_error=self._on_error,
                          on_message=functools.partial(self._on_message,
                                                       channel=channel,
                                                       dump=dump),
                          on_close=functools.partial(self._on_close,
                                                     channel=channel,
                                                     dump=dump)
                          )
        logger.info(f"Websocket client started for channel: {channel.id}")
        ws.run_forever()

    def _on_error(self, ws, error):
        """Handle websocket errors
        
        Args:
            ws: The websocket
            error: The error
        """
        logger.error(f"STT websocket error: {error}")

    def _on_close(self, ws, channel, dump):
        """Handle websocket close
        
        Args:
            ws: The websocket
            channel: The channel
            dump: The dump file
        """
        self._send_buffer(channel, dump)
        if dump:
            dump.close()

    def _on_message(self, ws, message, channel=None, dump=None):
        """Handle websocket messages
        
        Args:
            ws: The websocket
            message: The message
            channel: The channel
            dump: The dump file
        """
        chunk = self._buffers.setdefault(channel.id, b'') + message
        self._buffers[channel.id] = chunk

        if len(chunk) < 1024 * 64:
            return

        self._send_buffer(channel, dump)

    def _send_buffer(self, channel, dump):
        """Send a buffer to the speech service
        
        Args:
            channel: The channel
            dump: The dump file
        """
        chunk = self._buffers.pop(channel.id, None)
        if not chunk:
            return

        if dump:
            dump.write(chunk)
            
        # Process the chunk with the engine
        self._engine.process_audio_chunk(channel, chunk)
