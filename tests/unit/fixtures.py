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
"""Available fixtures for juju_verify unit test suite."""
from string import digits
from unittest.mock import PropertyMock


from juju.client.connector import Connector
from juju.model import Model
from juju.unit import Unit

from juju_verify import juju_verify

import pytest


@pytest.fixture(scope='function')
def fail(session_mocker):
    """Mock fail function that otherwise causes process to exit."""
    return session_mocker.patch.object(juju_verify, 'fail')


@pytest.fixture(scope='session')
def all_units():
    """List of units that are present in the 'model' fixture."""
    return [
        'nova-compute/0',
        'nova-compute/1',
        'nova-compute/2',
        'ceph-osd/0',
        'ceph-osd/1',
        'ceph-mon/0',
        'ceph-mon/1',
        'ceph-mon/2',
    ]


@pytest.fixture(scope='session')
def model(session_mocker, all_units):
    """Fixture representing connected juju model."""
    session_mocker.patch.object(Connector, 'is_connected').return_value = True
    model = Model()
    session_mocker.patch.object(Model, 'connect_current')
    session_mocker.patch.object(Model, 'connect_model')
    session_mocker.patch.object(Unit, 'data')
    session_mocker.patch.object(Unit, 'machine')
    units = session_mocker.patch('juju.model.Model.units',
                                 new_callable=PropertyMock)

    unit_map = {}
    for unit_id in all_units:
        unit = Unit(unit_id, model)
        charm_name = unit_id.rstrip(digits + '/')
        unit.data = {'charm-url': 'cs:focal/{}-1'.format(charm_name)}
        unit_map[unit_id] = unit
    units.return_value = unit_map

    return model
