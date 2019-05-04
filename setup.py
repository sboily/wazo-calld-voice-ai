#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from setuptools import setup
from setuptools import find_packages


setup(
    name='wazo-stt',
    version='0.2.0',
    description='Wazo STT',
    author='Wazo Authors',
    url='http://wazo.community',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'wazo_calld': ['*/api.yml'],
    },
    entry_points={
        'wazo_calld.plugins': [
            'stt = wazo_stt.calld.plugin:Plugin',
        ]
    }
)
