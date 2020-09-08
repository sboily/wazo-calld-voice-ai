#!/usr/bin/env python3
# Copyright 2019-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import yaml

from setuptools import setup
from setuptools import find_packages


with open('wazo/plugin.yml') as file:
    metadata = yaml.load(file)

setup(
    name=metadata['name'],
    version=metadata['version'],
    description=metadata['display_name'],
    author=metadata['author'],
    url=metadata['homepage'],

    packages=find_packages(),
    include_package_data=True,
    package_data={'wazo_stt': ['*/api.yml']},
    entry_points={
        'wazo_calld.plugins': [
            'stt = wazo_stt.calld.plugin:Plugin',
        ]
    }
)
