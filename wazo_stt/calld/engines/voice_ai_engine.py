# -*- coding: utf-8 -*-
# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import threading
from .engine_base import SttEngineBase
from ..voice_ai_client import VoiceAIClient

logger = logging.getLogger(__name__)


class VoiceAIEngine(SttEngineBase):
    """Voice AI service engine implementation"""

    def _initialize(self):
        """Initialize the Voice AI engine configuration"""
        self._clients = {}  # Store client instances for each channel
        self._uri = self._config["stt"]["voice_ai_uri"]
        self._language = self._config["stt"]["language"]
        self._use_ai = self._config["stt"].get("use_ai", False)

    def process_audio_chunk(self, channel, tenant_uuid, chunk):
        """Process an audio chunk through Voice AI service
        
        Args:
            channel: The channel object
            chunk: Binary audio data
        """
        if not chunk or channel.id not in self._clients:
            return
            
        # Send the audio chunk to the Voice AI service
        # Results will come back through the callback
        self._clients[channel.id].send_audio_chunk(chunk)

    def start(self, channel, tenant_uuid, **kwargs):
        """Start processing for a channel
        
        Args:
            channel: The channel to process
            **kwargs: Additional parameters (use_ai can be overridden)
        """
        logger.info(f"Starting Voice AI engine for channel: {channel.id}")
        
        # Get use_ai setting, allowing override per channel
        use_ai = kwargs.get("use_ai", self._use_ai)
        
        # Create a new client for this channel
        client = VoiceAIClient(
            uri=self._uri,
            language=self._language,
            use_ai=use_ai,
            sample_rate=16000
        )
        
        # Set up callbacks
        def on_transcription(text):
            self.publish_transcription(channel, tenant_uuid, text)
            
        # Start the client
        success = client.start(on_transcription)
        if success:
            self._clients[channel.id] = client
            return True
        else:
            logger.error(f"Failed to start Voice AI client for channel: {channel.id}")
            return False

    def stop(self, channel_id, tenant_uuid):
        """Stop processing for a channel
        
        Args:
            channel_id: ID of the channel to stop
        """
        logger.info(f"Stopping Voice AI engine for channel: {channel_id}")
        if channel_id in self._clients:
            client = self._clients.pop(channel_id)
            client.stop()
            return True
        return False
