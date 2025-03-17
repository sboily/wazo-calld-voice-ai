# -*- coding: utf-8 -*-
# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
#from google.cloud import speech
#from google.cloud.speech import enums
#from google.cloud.speech import types

from .engine_base import SttEngineBase

logger = logging.getLogger(__name__)


class GoogleSttEngine(SttEngineBase):
    """Google Cloud Speech-to-Text engine implementation"""

    def _initialize(self):
        """Initialize the Google STT client"""
        self._speech_client = speech.SpeechClient.from_service_account_file(
            self._config["stt"]["google_creds"])
        self._streaming_config = types.StreamingRecognitionConfig(
            config=types.RecognitionConfig(
                encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self._config["stt"]["language"]))

    def process_audio_chunk(self, channel, tenant_uuid, chunk):
        """Process an audio chunk through Google STT
        
        Args:
            channel: The channel object
            tenant_uuid: The tenant UUID
            chunk: Binary audio data
        """
        if not chunk:
            return
            
        request = types.StreamingRecognizeRequest(audio_content=chunk)
        responses = list(self._speech_client.streaming_recognize(
            self._streaming_config, [request]))

        for response in responses:
            results = list(response.results)
            logger.debug("Google STT results: %d", len(results))
            for result in results:
                if result.is_final:
                    transcription = result.alternatives[0].transcript
                    self.publish_transcription(channel, tenant_uuid, transcription)

    def start(self, channel, tenant_uuid, **kwargs):
        """Start processing for a channel
        
        Args:
            channel: The channel to process
            **kwargs: Additional parameters (not used for Google STT)
        """
        logger.info(f"Google STT engine ready for channel: {channel.id}")
        # Google engine doesn't need special initialization per channel
        return True

    def stop(self, channel_id, tenant_uuid):
        """Stop processing for a channel
        
        Args:
            channel_id: ID of the channel to stop
        """
        logger.info(f"Stopping Google STT for channel: {channel_id}")
        # Google engine doesn't need special cleanup per channel
        return True
