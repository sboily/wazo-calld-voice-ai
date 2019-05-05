# Copyright 2019-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .notifier import SttNotifier
from .stasis import SttStasis
from .services import SttService
from .resources import (
    SttResource,
    SttCreateResource
)


class Plugin:

    def load(self, dependencies):
        ari = dependencies['ari']
        api = dependencies['api']
        config = dependencies['config']
        bus_publisher = dependencies['bus_publisher']

        notifier = SttNotifier(bus_publisher)
        stt_service = SttService(config, ari.client, notifier)
        stasis = SttStasis(config, ari.client, stt_service)

        api.add_resource(SttCreateResource, '/stt', resource_class_args=[stt_service])
        api.add_resource(SttResource, '/stt/<call_id>', resource_class_args=[stt_service])
