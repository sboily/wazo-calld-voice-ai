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
    def start(self, channel, **kwargs):
        """Start processing for a channel
        
        Args:
            channel: The channel to process
            **kwargs: Additional parameters
        """
        pass

    @abc.abstractmethod
    def stop(self, channel_id):
        """Stop processing for a channel
        
        Args:
            channel_id: ID of the channel to stop
        """
        pass

    def publish_transcription(self, channel, transcription):
        """Publish a transcription to the Wazo bus
        
        Args:
            channel: The channel object
            transcription: The transcription text
        """
        logger.info(f"STT result for channel {channel.id}: {transcription}")
        
        from ari.exceptions import ARINotFound
        
        try:
            try:
                all_stt = (
                    channel.getChannelVar(variable="X_WAZO_STT")['value'] + " " +
                    transcription
                )
            except ARINotFound:
                all_stt = transcription
                
            channel.setChannelVar(variable="X_WAZO_STT",
                                value=all_stt[-1020:])
            self._notifier.publish_stt(channel.id, transcription)
        except Exception as e:
            logger.error(f"Error publishing transcription: {e}")
