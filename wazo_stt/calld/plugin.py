# Copyright 2019-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from .notifier import SttNotifier
from .stasis import SttStasis

logger = logging.getLogger(__name__)


class Plugin:

    def load(self, dependencies):
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        ari = dependencies['ari']
        config = dependencies['config']

        notifier = SttNotifier(bus_publisher)
        stasis = SttStasis(config, ari, notifier)
        stasis.initialize()
