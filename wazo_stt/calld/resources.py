# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+


from wazo_calld.auth import required_acl
from wazo_calld.rest_api import AuthResource


class SttCreateResource(AuthResource):

    def __init__(self):
        pass

    @required_acl('calld.stt.create')
    def post(self):
        pass
