# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
from wazo_bus.resources.common.event import TenantEvent


logger = logging.getLogger(__name__)


class SttEvent(TenantEvent):
    service = 'calld'
    name = 'stt'
    routing_key_fmt = 'applications.stt.event'
    required_acl_fmt = 'events.applications.stt'

    def __init__(self, content, tenant_uuid):
        super().__init__(content, tenant_uuid)
