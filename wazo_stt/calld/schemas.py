# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.mallow import fields
from xivo.mallow_helpers import Schema


class CallSchema(Schema):
    call_id = fields.String()
    use_ai = fields.Boolean(missing=False)
