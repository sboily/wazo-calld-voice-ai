# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


class SttStasis:

    def __init__(self, config, ari, stt_service):
        self._ari = ari.client
        self._stt_service = stt_service

        if config["stt"]["stasis"]:
            self.initialize()

    def initialize(self):
        self._ari.on_channel_event('StasisStart', self._stasis_start)
        logger.debug('Stasis stt initialized')

    def _stasis_start(self, event_objects, event):
        logger.critical("event_objects: %s", event_objects)
        logger.critical("event: %s", event)
        self._stt_service.start(event_objects, event)
        logger.critical("thread started")
