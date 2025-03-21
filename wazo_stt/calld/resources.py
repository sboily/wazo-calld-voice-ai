# -*- coding: utf-8 -*-
# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schemas import CallSchema


stt_request_schema = CallSchema()


class SttCreateResource(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('calld.stt.create')
    def post(self):
        tenant = Tenant.autodetect()
        request_body = stt_request_schema.load(request.get_json(force=True))
        channel = self._service.get_channel_by_id(request_body["call_id"], tenant.uuid)

        # Pass use_ai parameter to start method
        use_ai = request_body.get("use_ai", False)
        self._service.start(channel, tenant.uuid, use_ai=use_ai)

        return CallSchema().dump({"call_id": request_body["call_id"], "tenant_uuid": tenant.uuid}), 201


class SttResource(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('calld.stt.delete')
    def delete(self, call_id):
        tenant = Tenant.autodetect()
        self._service.stop(call_id, tenant.uuid)

        return '', 204
