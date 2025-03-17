# -*- coding: utf-8 -*-
# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import asyncio
import json
import logging
import threading
import websockets
import signal
import time
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

# Réduire le niveau de logging pour websockets
websockets_logger = logging.getLogger('websockets')
websockets_logger.setLevel(logging.WARNING)
websockets_protocol_logger = logging.getLogger('websockets.protocol')
websockets_protocol_logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class VoiceAIClient:
    """Client for Voice AI Service that provides speech-to-text and AI agent capabilities"""

    def __init__(self, uri, language='fr_FR', use_ai=False, sample_rate=16000):
        """Initialize the Voice AI client
        
        Args:
            uri: WebSocket URI of the Voice AI service
            language: Language code for transcription
            use_ai: Whether to use AI agent for responses
            sample_rate: Sample rate of the audio stream
        """
        self.uri = uri
        self.language = language
        self.use_ai = use_ai
        self.sample_rate = sample_rate
        self.websocket = None
        self.connected = False
        self.queue = Queue()
        self.transcription_callback = None
        self.ai_response_callback = None
        self.event_loop = None
        self.ws_task = None
        self.worker_thread = None
        self.is_running = False
        self._shutdown_event = threading.Event()
        self._tasks = []

    def start(self, transcription_callback, ai_response_callback=None):
        """Start the Voice AI client
        
        Args:
            transcription_callback: Callback function for transcription results
            ai_response_callback: Callback function for AI agent responses
            
        Returns:
            bool: True if successfully started, False otherwise
        """
        if self.is_running:
            logger.warning("Voice AI client already running")
            return self.connected
            
        self.transcription_callback = transcription_callback
        self.ai_response_callback = ai_response_callback
        self.is_running = True
        self._shutdown_event.clear()
        
        # Start worker thread for asyncio event loop
        self.worker_thread = threading.Thread(target=self._run_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        # Wait for connection to be established
        attempts = 0
        max_attempts = 10
        while not self.connected and self.is_running and attempts < max_attempts:
            logger.info("Waiting for Voice AI service connection...")
            if not self.worker_thread.is_alive():
                logger.error("Worker thread died unexpectedly")
                self.is_running = False
                return False
            threading.Event().wait(0.5)
            attempts += 1
            
        if not self.connected:
            logger.warning("Could not establish connection to Voice AI service after maximum attempts")
            self.is_running = False
            self._cleanup()
            
        return self.connected

    def stop(self):
        """Stop the Voice AI client and clean up all resources"""
        if not self.is_running:
            logger.debug("Voice AI client already stopped")
            return
            
        logger.info("Stopping Voice AI client")
        self.is_running = False
        self._shutdown_event.set()
        
        # Signal to the event loop that we want to stop
        if self.event_loop and not self.event_loop.is_closed():
            try:
                # Schedule a task to stop all running tasks
                if self.ws_task and not self.ws_task.done():
                    self.event_loop.call_soon_threadsafe(self.ws_task.cancel)
                
                # Signal to all running coroutines to clean up
                for task in self._tasks:
                    if not task.done():
                        self.event_loop.call_soon_threadsafe(task.cancel)
                
                # Attempt a clean stop of the event loop itself
                self.event_loop.call_soon_threadsafe(self.event_loop.stop)
            except Exception as e:
                logger.error(f"Error scheduling event loop shutdown: {e}")
        
        # Wait for the worker thread to finish (but not too long)
        if self.worker_thread and self.worker_thread.is_alive():
            try:
                self.worker_thread.join(timeout=2)
            except Exception as e:
                logger.error(f"Error joining worker thread: {e}")
        
        # Final cleanup
        self._cleanup()
        logger.info("Voice AI client successfully stopped")

    def _cleanup(self):
        """Clean up resources"""
        # Make sure the thread variables are reset
        self.connected = False
        self.queue = Queue()
        self.websocket = None
        self.worker_thread = None
        self._tasks = []

    def send_audio_chunk(self, chunk):
        """Send an audio chunk to the Voice AI service
        
        Args:
            chunk: Audio data bytes
        """
        if not self.connected or not self.is_running:
            logger.debug("Cannot send chunk - not connected to Voice AI service")
            return
            
        self.queue.put(chunk)

    def _run_worker(self):
        """Run the worker thread with asyncio event loop"""
        try:
            # Create new event loop for this thread
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            
            # Add signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                self.event_loop.add_signal_handler(
                    sig,
                    lambda: self.event_loop.call_soon_threadsafe(self.event_loop.stop)
                )
            
            # Create the main task
            self.ws_task = self.event_loop.create_task(self._websocket_client())
            self._tasks.append(self.ws_task)
            
            # Run the event loop until it's stopped
            self.event_loop.run_until_complete(self.ws_task)
            
        except Exception as e:
            if self.is_running:  # Only log if this wasn't an expected shutdown
                logger.error(f"Voice AI worker error: {e}")
        finally:
            # Clean up remaining tasks
            pending_tasks = [task for task in self._tasks if not task.done()]
            if pending_tasks and not self.event_loop.is_closed():
                logger.debug(f"Canceling {len(pending_tasks)} pending tasks")
                for task in pending_tasks:
                    task.cancel()
                    
                # Wait for tasks to finish with timeout
                try:
                    self.event_loop.run_until_complete(
                        asyncio.wait(pending_tasks, timeout=1.0)
                    )
                except Exception as e:
                    logger.debug(f"Error waiting for tasks to cancel: {e}")
            
            # Close the event loop
            try:
                self.event_loop.run_until_complete(self.event_loop.shutdown_asyncgens())
                self.event_loop.close()
            except Exception as e:
                logger.debug(f"Error closing event loop: {e}")
                
            # Reset state flags
            self.connected = False
            self.is_running = False
            logger.debug("Voice AI worker thread exited")

    async def _websocket_client(self):
        """Websocket client coroutine"""
        retry_count = 0
        max_retries = 5
        retry_delay = 2
        
        while self.is_running and retry_count < max_retries and not self._shutdown_event.is_set():
            try:
                logger.info(f"Connecting to Voice AI service at {self.uri}")
                async with websockets.connect(self.uri) as websocket:
                    self.websocket = websocket
                    retry_count = 0  # Reset retry counter on successful connection
                    
                    # Send configuration
                    config = {
                        "type": "config",
                        "language": self.language,
                        "use_ai": self.use_ai,
                        "sample_rate": self.sample_rate
                    }
                    
                    await websocket.send(json.dumps(config))
                    logger.info(f"Sent config to Voice AI service: {config}")
                    
                    # Wait for config acknowledgment
                    response = await websocket.recv()
                    data = json.loads(response)
                    logger.info(f"Config response from Voice AI service: {data}")
                    
                    # Set connected flag after successful config
                    self.connected = True
                    
                    # Start tasks for sending and receiving
                    sender_task = self.event_loop.create_task(self._sender())
                    receiver_task = self.event_loop.create_task(self._receiver())
                    self._tasks.extend([sender_task, receiver_task])
                    
                    # Wait for tasks to complete or for shutdown signal
                    while self.is_running and not self._shutdown_event.is_set():
                        # Check if either task is done
                        if sender_task.done() or receiver_task.done():
                            # Check for exceptions
                            for task in [sender_task, receiver_task]:
                                if task.done() and not task.cancelled():
                                    try:
                                        task.result()
                                    except Exception as e:
                                        logger.error(f"Task error: {e}")
                            break
                            
                        # Wait a short time
                        await asyncio.sleep(0.1)
                    
                    # Cancel tasks if still running
                    for task in [sender_task, receiver_task]:
                        if not task.done():
                            task.cancel()
                    
            except (websockets.exceptions.ConnectionClosed, 
                    websockets.exceptions.InvalidStatusCode,
                    ConnectionRefusedError) as e:
                if self._shutdown_event.is_set():
                    break
                    
                retry_count += 1
                logger.warning(f"Connection to Voice AI service failed ({retry_count}/{max_retries}): {e}")
                await asyncio.sleep(retry_delay)
            except asyncio.CancelledError:
                logger.debug("Websocket client cancelled")
                break
            except Exception as e:
                if self.is_running and not self._shutdown_event.is_set():
                    logger.error(f"Unexpected error in Voice AI websocket client: {e}")
                break
            finally:
                self.connected = False
                self.websocket = None
        
        logger.info("Voice AI websocket client stopped")

    async def _sender(self):
        """Send audio chunks from queue to websocket"""
        try:
            while self.is_running and self.websocket and not self._shutdown_event.is_set():
                try:
                    # Non-blocking queue check with timeout
                    try:
                        chunk = self.queue.get(block=True, timeout=0.1)
                        # Send the audio chunk
                        await self.websocket.send(chunk)
                        # Send EOF marker after each chunk as binary data
                        await self.websocket.send(b'EOF')
                        logger.debug("Sent audio chunk and EOF marker to Voice AI service")
                    except Empty:
                        # No data available, just continue
                        await asyncio.sleep(0.01)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if self.is_running and not self._shutdown_event.is_set():
                        logger.error(f"Error in Voice AI sender: {e}")
                    await asyncio.sleep(1)  # Wait before retrying
        except asyncio.CancelledError:
            logger.debug("Voice AI sender task cancelled")
            raise

    async def _receiver(self):
        """Receive messages from websocket and process them"""
        try:
            while self.is_running and self.websocket and not self._shutdown_event.is_set():
                try:
                    # Set a timeout for receive operations
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=0.5)
                    
                    # Process the message
                    data = json.loads(message)
                    
                    if data["type"] == "transcription" and self.transcription_callback:
                        self.transcription_callback(data["text"])
                        
                    elif data["type"] == "ai_response" and self.ai_response_callback:
                        self.ai_response_callback(data["text"])
                        
                    elif data["type"] == "error":
                        logger.error(f"Voice AI service error: {data['message']}")
                        
                except asyncio.TimeoutError:
                    # This is normal, just continue
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if self.is_running and not self._shutdown_event.is_set():
                        logger.error(f"Error in Voice AI receiver: {e}")
                    await asyncio.sleep(1)  # Wait before retrying
        except asyncio.CancelledError:
            logger.debug("Voice AI receiver task cancelled")
            raise
