# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
from wazo_bus.resources.common.event import TenantEvent

from .events import SttEvent


logger = logging.getLogger(__name__)


class SttNotifier:

    def __init__(self, bus_publisher):
        self.bus_publisher = bus_publisher

    def publish_stt(self, channel_id, tenant_uuid, transcription):
        event =  {
            "channel_id": channel_id,
            "transcription": transcription
        }
        bus_event = SttEvent(
            event,
            tenant_uuid
        )
        self.bus_publisher.publish(bus_event)
