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
"""Verifiers __init__ test suite."""
import os

import pytest
from juju.unit import Unit

from juju_verify.exceptions import CharmException
from juju_verify.verifiers import SUPPORTED_CHARMS, CephOsd, NovaCompute, get_verifier


@pytest.mark.parametrize(
    "charm, verifier_type",
    [
        ("nova-compute", NovaCompute),
        ("ceph-osd", CephOsd),
    ],
)
def test_get_verifier_supported_charms(model, charm, verifier_type):
    """Test creating correct verifiers from supported charm names."""
    units = []
    for name, unit in model.units.items():
        if name.startswith(charm):
            units.append(unit)
    assert units, f"Expected units for charm {charm} not found in 'model' fixture"

    verifier = get_verifier(units)
    assert isinstance(verifier, verifier_type)
    assert verifier.units == units


def test_get_verifier_unsupported_charm(mocker, model):
    """Raise exception if unsupported charm is requested."""
    charm_name = "unsupported-charm"
    unit_name = f"{charm_name}/0"
    charm_url = f"cs:focal/{charm_name}-1"
    supported_charms = os.linesep.join(SUPPORTED_CHARMS.keys())
    expected_msg = (
        f"Charm '{charm_name}' is not supported by juju-verify. Supported "
        f"charms:{os.linesep}{supported_charms}"
    )

    mocker.patch.object(Unit, "data")

    unit = Unit(unit_name, model)
    unit.data = {"charm-url": charm_url}

    with pytest.raises(CharmException) as exc:
        get_verifier([unit])

    assert str(exc.value) == expected_msg


@pytest.mark.parametrize("charm_url", ["cs:nova-compute-1", "cs:focal/nova-compute-1"])
def test_get_verifier_parse_urls(mocker, model, charm_url):
    """Successfully parse various chrm url formats."""
    mocker.patch.object(Unit, "data")
    unit = Unit("nova-compute/0", model)
    unit.data = {"charm-url": charm_url}

    # no exception raised
    get_verifier([unit])


def test_get_verifier_fail_parse_charm_url(mocker, model):
    """Raise exception if parsing of charm-url fails."""
    mocker.patch.object(Unit, "data")
    bad_url = "foo"
    expected_msg = f"Failed to parse charm-url: '{bad_url}'"
    unit = Unit("nova-compute", model)
    unit.data = {"charm-url": "foo"}

    with pytest.raises(CharmException) as exc:
        get_verifier([unit])

    assert str(exc.value) == expected_msg


def test_get_verifier_mixed_charms(mocker, model):
    """Fail if verifier is requested for units with different charms."""
    mocker.patch.object(Unit, "data")
    nova_url = "cs:nova-compute-0"
    ceph_url = "cs:ceph-osd-0"
    expected_msg = "Units are not running same charm. Detected types: {}".format(
        {"nova-compute", "ceph-osd"}
    )

    nova = Unit("nova-compute/0", model)
    nova.data = {"charm-url": nova_url}

    ceph = Unit("ceph-osd/0", model)
    ceph.data = {"charm-url": ceph_url}

    with pytest.raises(CharmException) as exc:
        get_verifier([nova, ceph])

    assert str(exc.value) == expected_msg


def test_get_verifier_empty_list():
    """Fail if list of units is empty."""
    expected_msg = "List of units can not be empty when creating verifier"

    with pytest.raises(CharmException) as exc:
        get_verifier([])

    assert str(exc.value) == expected_msg
