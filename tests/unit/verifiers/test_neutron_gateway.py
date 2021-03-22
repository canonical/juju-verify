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
"""NeutronGateway verifier class test suite."""
from unittest.mock import MagicMock

from juju.unit import Unit

from juju_verify.verifiers import NeutronGateway

all_ngw_units = []
for i in range(3):
    ngw = MagicMock()
    ngw.entity_id = "neutron-gateway/{}".format(i)
    all_ngw_units.append(ngw)

mock_data = [
    {
        "host": "host0",
        "shutdown": True,
        "unit": all_ngw_units[0],
        "routers": [{"id": "router0", "ha": False, "status": "ACTIVE"},
                    {"id": "router1", "ha": False, "status": "ACTIVE"}]
    },
    {
        "host": "host1",
        "shutdown": False,
        "unit": all_ngw_units[1],
        "routers": [{"id": "router2", "ha": False, "status": "ACTIVE"}],
    },
    {
        "host": "host2",
        "shutdown": False,
        "unit": all_ngw_units[2],
        "routers": [{"id": "router3", "ha": False, "status": "ACTIVE"},
                    {"id": "router4", "ha": False, "status": "ACTIVE"}],
    },
]

all_ngw_host_names = [h["host"] for h in mock_data]

model = MagicMock()


def get_ngw_verifier():
    """Get new NeutronGateway verifier (used for applying changes in shutdown list)."""
    return NeutronGateway([Unit(h["unit"].entity_id, model)
                           for h in mock_data if h["shutdown"]])


def get_resource_lists():
    """Get all routers in mock data."""
    return [h["routers"] for h in mock_data]


def get_shutdown_host_name_list():
    """Get all hostnames of all hosts being shutdown."""
    return [h["host"] for h in mock_data if h["shutdown"]]


