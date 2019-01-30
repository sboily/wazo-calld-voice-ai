#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from setuptools import setup
from setuptools import find_packages


setup(
    name='wazo-stt',
    version='2.0',
    description='Wazo STT',
    author='Wazo Authors',
    url='http://wazo.community',
    packages=find_packages(),
    entry_points={
        'xivo_ctid_ng.plugins': [
            'stt = wazo_stt.ctid_ng.plugin:Plugin',
        ]
    }
)
