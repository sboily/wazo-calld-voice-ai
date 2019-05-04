# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


import logging

logger = logging.getLogger(__name__)


class SttEvent(object):
    name = 'stt'
    required_acl = "event.stt"

    def __init__(self, channel_id, result_stt):
        self.routing_key = 'stt.event'
        self.channel_id = channel_id
        self.result_stt = result_stt

    def marshal(self):
        return {
            "call_id": "%s" % self.channel_id,
            "result_stt": self.result_stt
        }


class SttNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def publish_stt(self, channel_id, result_stt):
        event = SttEvent(channel_id, result_stt)
        self._bus_producer.publish(event)
