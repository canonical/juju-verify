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
from unittest.mock import MagicMock, PropertyMock

import pytest
import yaml
from juju.action import Action
from juju.client.connector import Connector
from juju.model import Model
from juju.unit import Unit

from juju_verify.verifiers.ovn_central import ClusterStatus


@pytest.fixture(scope="session")
def model_units():
    """Definition of the units (with data) that are part of the 'model' fixture."""

    def unit_data(charm_name: str, application: str, workload_status: str):
        """Create unit data."""
        return {
            "charm-url": f"cs:focal/{charm_name}-1",
            "application": application,
            "workload-status": {"current": workload_status},
        }

    return {
        "nova-compute/0": unit_data("nova-compute", "nova-compute", "active"),
        "nova-compute/1": unit_data("nova-compute", "nova-compute", "active"),
        "nova-compute/2": unit_data("nova-compute", "nova-compute", "active"),
        "ceph-osd/0": unit_data("ceph-osd", "ceph-osd", "active"),
        "ceph-osd/1": unit_data("ceph-osd", "ceph-osd", "active"),
        "ceph-osd/2": unit_data("ceph-osd", "ceph-osd", "active"),
        "ceph-osd-hdd/0": unit_data("ceph-osd", "ceph-osd-hdd", "active"),
        "ceph-osd-hdd/1": unit_data("ceph-osd", "ceph-osd-hdd", "active"),
        "ceph-osd-hdd/2": unit_data("ceph-osd", "ceph-osd-hdd", "active"),
        "ceph-osd-ssd/0": unit_data("ceph-osd", "ceph-osd-ssd", "active"),
        "ceph-osd-ssd/1": unit_data("ceph-osd", "ceph-osd-ssd", "active"),
        "ceph-osd-ssd/2": unit_data("ceph-osd", "ceph-osd-ssd", "active"),
        "ceph-mon/0": unit_data("ceph-mon", "ceph-mon", "active"),
        "ceph-mon/1": unit_data("ceph-mon", "ceph-mon", "active"),
        "ceph-mon/2": unit_data("ceph-mon", "ceph-mon", "active"),
        "neutron-gateway/0": unit_data("neutron-gateway", "neutron-gateway", "active"),
        "neutron-gateway/1": unit_data("neutron-gateway", "neutron-gateway", "active"),
        "ovn-central/0": unit_data("ovn-central", "ovn-central", "active"),
        "ovn-central/1": unit_data("ovn-central", "ovn-central", "active"),
        "ovn-central/2": unit_data("ovn-central", "ovn-central", "active"),
    }


@pytest.fixture(scope="session")
def all_units(model_units):
    """List of units that are present in the 'model' fixture."""
    return list(model_units.keys())


@pytest.fixture(scope="session")
def model(session_mocker, model_units):
    """Fixture representing connected juju model."""
    session_mocker.patch.object(Connector, "is_connected").return_value = True
    mock_model = Model()
    session_mocker.patch.object(Model, "connect_current")
    session_mocker.patch.object(Model, "connect_model")
    session_mocker.patch.object(Unit, "data")
    session_mocker.patch.object(Unit, "machine")
    session_mocker.patch.object(Unit, "run_action", new_callable=MagicMock)
    session_mocker.patch.object(Action, "wait", new_callable=MagicMock)
    session_mocker.patch.object(Action, "status").return_value = "pending"
    session_mocker.patch.object(Action, "data")
    units = session_mocker.patch("juju.model.Model.units", new_callable=PropertyMock)
    applications = session_mocker.patch(
        "juju.model.Model.applications", new_callable=PropertyMock
    )

    unit_map, app_map = {}, {}
    for unit_id, unit_data in model_units.items():
        unit = Unit(unit_id, mock_model)
        unit.data = unit_data
        unit_map[unit_id] = unit

        # add unit to model.applications
        if unit_data["application"] not in app_map:
            app_map[unit_data["application"]] = MagicMock()
            app_map[unit_data["application"]].units = []

        app_map[unit_data["application"]].units.append(unit)

    units.return_value = unit_map
    applications.return_value = app_map

    return mock_model


@pytest.fixture()
def ovn_cluster_status_dict():
    """Fixture representing sample of an ovn-cluster status in the for of dict."""
    return {
        "Cluster ID": "567e7225-369e-40d6-abf8-9b442bbcd18b",
        "Server ID": "16335def-c21e-404c-b123-8337b3013c07",
        "Address": "ssl:10.5.2.232:6644",
        "Status": "cluster member",
        "Role": "follower",
        "Term": 34,
        "Leader": "dbdb",
        "Vote": "dbdb",
        "Log": "[66, 66]",
        "Entries not yet committed": 0,
        "Entries not yet applied": 0,
        "Servers": {
            "dbdb": {
                "Address": "ssl:10.5.0.144:6644",
                "Unit": "ovn-central/7",
            },
            "f1a2": {
                "Address": "ssl:10.5.3.200:6644",
                "Unit": "ovn-central/10",
            },
            "1633": {
                "Address": "ssl:10.5.2.232:6644",
                "Unit": "ovn-central/6",
            },
        },
    }


@pytest.fixture()
def ovn_cluster_status_raw(ovn_cluster_status_dict):
    """Fixture representing sample of an ovn-cluster status serialized an YAML string."""
    return yaml.dump(ovn_cluster_status_dict, indent=2)


@pytest.fixture()
def ovn_cluster_status(ovn_cluster_status_raw):
    """Fixture returning ClusterStatus instance with sample data."""
    return ClusterStatus(ovn_cluster_status_raw)
