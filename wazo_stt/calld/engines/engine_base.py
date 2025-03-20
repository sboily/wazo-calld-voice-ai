# -*- coding: utf-8 -*-
# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import abc
import logging

logger = logging.getLogger(__name__)


class SttEngineBase(metaclass=abc.ABCMeta):
    """Base class for all STT engines"""

    def __init__(self, config, notifier):
        self._config = config
        self._notifier = notifier
        self._initialize()

    @abc.abstractmethod
    def _initialize(self):
        """Initialize the STT engine with configuration parameters"""
        pass

    @abc.abstractmethod
    def process_audio_chunk(self, channel, chunk):
        """Process an audio chunk and extract transcription
        
        Args:
            channel: The channel object
            chunk: Binary audio data
        """
        pass

    @abc.abstractmethod
    def start(self, channel, tenant_uuid, **kwargs):
        """Start processing for a channel
        
        Args:
            channel: The channel to process
            tenant_uuid: The tenant UUID
            **kwargs: Additional parameters
        """
        pass

    @abc.abstractmethod
    def stop(self, channel_id, tenant_uuid):
        """Stop processing for a channel
        
        Args:
            channel_id: ID of the channel to stop
            tenant_uuid: The tenant UUID
        """
        pass

    def publish_transcription(self, channel, tenant_uuid, transcription):
        """Publish a transcription to the Wazo bus
        
        Args:
            channel: The channel object
            tenant_uuid: The tenant UUID
            transcription: The transcription text
        """
        logger.info(f"STT result for channel {channel.id}/{tenant_uuid}: {transcription}")
        
        try:
            self._notifier.publish_stt(channel.id, tenant_uuid, transcription)
        except Exception as e:
            logger.error(f"Error publishing transcription: {e}")
