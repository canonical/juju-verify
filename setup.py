# Copyright 2021 Canonical Limited.
#
# This file is part of juju-verify.
#
# juju-verify is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# juju-verify is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see https://www.gnu.org/licenses/.
"""Manage package and distribution."""
from setuptools import find_packages, setup

requirements = [
    'juju'
]

dev_requirements = [
    'pylint',
    'mypy',
    'pytest',
    'pytest_mock',
    'pytest-asyncio',
    'coverage',
]

setup(
    name='juju_verify',
    version='0.1',
    description='Juju plugin to verify if it\'s safe to perform action on the '
                'unit',
    packages=find_packages(exclude=['tests']),
    entry_points={'console_scripts': ['juju-verify = juju_verify:main']},
    install_requires=requirements,
    extras_require={
        'dev': dev_requirements
    }
)
