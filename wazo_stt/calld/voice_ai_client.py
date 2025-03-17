# -*- coding: utf-8 -*-
# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import asyncio
import json
import logging
import threading
import websockets
from queue import Queue

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

    def start(self, transcription_callback, ai_response_callback=None):
        """Start the Voice AI client
        
        Args:
            transcription_callback: Callback function for transcription results
            ai_response_callback: Callback function for AI agent responses
            
        Returns:
            bool: True if successfully started, False otherwise
        """
        self.transcription_callback = transcription_callback
        self.ai_response_callback = ai_response_callback
        self.is_running = True
        
        # Start worker thread for asyncio event loop
        self.worker_thread = threading.Thread(target=self._run_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        # Wait for connection to be established
        attempts = 0
        max_attempts = 10
        while not self.connected and self.is_running and attempts < max_attempts:
            logging.info("Waiting for Voice AI service connection...")
            if not self.worker_thread.is_alive():
                raise RuntimeError("Worker thread died unexpectedly")
            threading.Event().wait(0.5)
            attempts += 1
            
        if not self.connected:
            logger.warning("Could not establish connection to Voice AI service after maximum attempts")
            
        return self.connected

    def stop(self):
        """Stop the Voice AI client"""
        logger.info("Stopping Voice AI client")
        self.is_running = False
        
        # Close websocket if it's open
        if self.event_loop and self.websocket:
            try:
                # Create a task to close the websocket
                async def close_ws():
                    if self.websocket:
                        await self.websocket.close()
                        logger.info("Voice AI websocket closed")
                
                # Run the close task
                if not self.event_loop.is_closed():
                    future = asyncio.run_coroutine_threadsafe(close_ws(), self.event_loop)
                    # Wait for the future to complete with a timeout
                    future.result(timeout=3)
            except Exception as e:
                logger.error(f"Error closing Voice AI websocket: {e}")
        
        # Wait for the worker thread to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
            if self.worker_thread.is_alive():
                logger.warning("Voice AI worker thread did not terminate gracefully")
        
        # Clear resources
        self.queue = Queue()  # Clear the queue
        self.websocket = None
        self.connected = False
        
        logger.info("Voice AI client successfully stopped")

    def send_audio_chunk(self, chunk):
        """Send an audio chunk to the Voice AI service
        
        Args:
            chunk: Audio data bytes
        """
        if not self.connected:
            logger.warning("Cannot send chunk - not connected to Voice AI service")
            return
            
        self.queue.put(chunk)

    def _run_worker(self):
        """Run the worker thread with asyncio event loop"""
        try:
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.ws_task = self.event_loop.create_task(self._websocket_client())
            self.event_loop.run_until_complete(self.ws_task)
        except Exception as e:
            logger.error(f"Voice AI worker error: {e}")
        finally:
            self.connected = False
            self.is_running = False
            if self.event_loop and self.event_loop.is_running():
                self.event_loop.close()

    async def _websocket_client(self):
        """Websocket client coroutine"""
        retry_count = 0
        max_retries = 5
        retry_delay = 2
        
        while self.is_running and retry_count < max_retries:
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
                    sender_task = asyncio.create_task(self._sender())
                    receiver_task = asyncio.create_task(self._receiver())
                    
                    # Wait for any task to complete or for stop signal
                    done, pending = await asyncio.wait(
                        [sender_task, receiver_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Cancel remaining tasks
                    for task in pending:
                        task.cancel()
                        
                    # Handle any exceptions
                    for task in done:
                        try:
                            await task
                        except Exception as e:
                            logger.error(f"Task error: {e}")
                    
            except (websockets.exceptions.ConnectionClosed, 
                    websockets.exceptions.InvalidStatusCode,
                    ConnectionRefusedError) as e:
                retry_count += 1
                logger.warning(f"Connection to Voice AI service failed ({retry_count}/{max_retries}): {e}")
                await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error in Voice AI websocket client: {e}")
                break
            finally:
                self.connected = False
                self.websocket = None
        
        logger.info("Voice AI websocket client stopped")

    async def _sender(self):
        """Send audio chunks from queue to websocket"""
        try:
            while self.is_running and self.websocket:
                # Non-blocking queue check
                if not self.queue.empty():
                    chunk = self.queue.get()
                    # Send the audio chunk
                    await self.websocket.send(chunk)
                    # Send EOF marker after each chunk as binary data
                    await self.websocket.send(b'EOF')
                    logger.debug("Sent audio chunk and EOF marker to Voice AI service")
                else:
                    # Short sleep to prevent CPU spinning
                    await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in Voice AI sender: {e}")

    async def _receiver(self):
        """Receive messages from websocket and process them"""
        try:
            while self.is_running and self.websocket:
                try:
                    message = await self.websocket.recv()
                    # Process the message
                    data = json.loads(message)
                    
                    if data["type"] == "transcription" and self.transcription_callback:
                        self.transcription_callback(data["text"])
                        
                    elif data["type"] == "ai_response" and self.ai_response_callback:
                        self.ai_response_callback(data["text"])
                        
                    elif data["type"] == "error":
                        logger.error(f"Voice AI service error: {data['message']}")
                        
                except asyncio.TimeoutError:
                    continue
        except Exception as e:
            logger.error(f"Error in Voice AI receiver: {e}")
