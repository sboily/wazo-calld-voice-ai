# -*- coding: utf-8 -*-
# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
from .google_engine import GoogleSttEngine
from .voice_ai_engine import VoiceAIEngine

logger = logging.getLogger(__name__)


class SttEngineFactory:
    """Factory for creating STT engine instances"""

    @staticmethod
    def create_engine(engine_type, config, notifier):
        """Create an STT engine based on the configuration
        
        Args:
            engine_type: The type of engine to create (google, voice_ai)
            config: The configuration dictionary
            notifier: The notifier for publishing events
            
        Returns:
            SttEngineBase: An instance of the specified engine
            
        Raises:
            ValueError: If the engine type is not supported
        """
        if engine_type == "google":
            return GoogleSttEngine(config, notifier)
        elif engine_type == "voice_ai":
            return VoiceAIEngine(config, notifier)
        else:
            raise ValueError(f"Unsupported STT engine type: {engine_type}")
