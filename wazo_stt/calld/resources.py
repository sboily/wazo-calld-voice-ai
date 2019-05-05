# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request

from wazo_calld.auth import required_acl
from wazo_calld.rest_api import AuthResource

from .schemas import CallSchema


class SttCreateResource(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('calld.stt.create')
    def post(self):
        request_body = call_request_schema.load(request.get_json(force=True)).data
        channel = self._service.get_channel_by_id(request_body["call_id"])

        self._service.start(channel)

        return CallSchema().dump(request_body["call_id"]).data, 201


class SttResource(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('calld.stt.delete')
    def delete(self, call_id):
        self._service.stop(call_id)

        return '', 204
