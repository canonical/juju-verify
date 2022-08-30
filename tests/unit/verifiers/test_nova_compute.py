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
"""NovaCompute verifier class test suite."""
import json
from unittest.mock import MagicMock

import pytest
from juju.model import Model
from juju.unit import Unit
from pytest import param

from juju_verify.verifiers.nova_compute import NovaCompute
from juju_verify.verifiers.result import Partial, Result, Severity


@pytest.mark.parametrize(
    "vm_count, expect_severity", [("0", Severity.OK), ("1", Severity.FAIL)]
)
def test_nova_compute_no_running_vms(mocker, vm_count, expect_severity):
    """Test expected Result based on the number of VMs running on nova."""
    # Prepare Units for verifier
    unit_names = ["nova-compute/0", "nova-compute/1"]
    model = Model()
    units = [Unit(name, model) for name in unit_names]

    # Mock result of 'instance-count' action on all verified units.
    result_data = {"instance-count": vm_count}
    mock_result = MagicMock()
    mock_result.results = result_data
    action_results = {unit: mock_result for unit in unit_names}
    mocker.patch.object(NovaCompute, "run_action_on_all").return_value = action_results

    expected_result = Result()
    for unit in unit_names:
        expected_result.add_partial_result(
            expect_severity, f"Unit {unit} is running {vm_count} VMs."
        )

    # Create and run verifier
    verifier = NovaCompute(units)
    result = verifier.check_no_running_vms()

    # Assert expected results
    assert result == expected_result


@pytest.mark.parametrize(
    "all_hosts, remove_hosts, host_state, host_status, expect_severity",
    [
        param(2, 2, "up", "enabled", Severity.FAIL, id="fail-on-empty-az"),
        param(3, 2, "up", "enabled", Severity.OK, id="success-non-empty-az"),
        param(3, 2, "down", "enabled", Severity.FAIL, id="fail-down-host-left"),
        param(3, 2, "up", "disabled", Severity.FAIL, id="fail-disabled-host-left"),
        param(
            3, 2, "down", "disabled", Severity.FAIL, id="fail-down-disabled-host-left"
        ),
    ],
)
def test_nova_compute_empty_az(
    all_hosts, remove_hosts, host_state, host_status, expect_severity, mocker
):
    """Test expected Result when trying to remove all nodes from AZ.

    Following scenarios are tested:
        * fail-on-empty-az - Removing nodes would cause AZ to go empty.
                             Expected result is Fail.
        * success-non-empty-az - Removing nodes will leave at least one active
                                 node in AZ. Expected result is Pass.
        * fail-down-host-left - Removing nodes would leave AZ only with hosts
                                that are 'down'. Expected result is Fail.
        * fail-disabled-host-left - Removing nodes would leave AZ only with
                                    hosts that are 'disabled'. Expected result
                                    is Fail.
        * fail-down-disabled-host-left - Removing nodes would leave AZ only
                                         with hosts that are 'down' and
                                         disabled. Expected result is Fail.
    """
    unit_pool = ["nova-compute/0", "nova-compute/1", "nova-compute/2"]
    host_pool = ["compute.0", "compute.1", "compute.2"]

    # prepare Units for verifier. Number of units to remove is parametrized.
    unit_names = unit_pool[:remove_hosts]
    model = Model()
    units = [Unit(name, model) for name in unit_names]
    zone = "nova"

    if expect_severity == Severity.OK:
        expected_success = True
        expected_partial = Partial(Severity.OK, "Empty Availability Zone check passed.")
    else:
        expected_success = False
        expected_partial = Partial(
            Severity.FAIL,
            "Removing these units would leave following availability zones empty: "
            "{}".format({zone}),
        )

    # mock results of 'node-names' action on all verified units
    node_name_results = []
    for node in host_pool[:remove_hosts]:
        result_mock = MagicMock()
        result_mock.results = {"node-name": node}
        node_name_results.append(result_mock)
    action_results = dict(zip(unit_names, node_name_results))

    mocker.patch.object(NovaCompute, "run_action_on_all").return_value = action_results

    # mock result 'list-compute-nodes' action. Number of nodes in zone is parametrized.
    raw_compute_nodes = [
        {"host": host, "zone": zone, "state": host_state, "status": host_status}
        for host in host_pool[:all_hosts]
    ]

    compute_nodes_data = {"compute-nodes": json.dumps(raw_compute_nodes)}
    mock_compute_node_result = MagicMock()
    mock_compute_node_result.results = compute_nodes_data
    mocker.patch(
        "juju_verify.verifiers.nova_compute.run_action_on_unit"
    ).return_value = mock_compute_node_result

    # run verifier
    verifier = NovaCompute(units)
    result = verifier.check_no_empty_az()

    # assert expected results
    assert result.success == expected_success
    assert expected_partial in result.partials


@pytest.mark.parametrize(
    "vm_count_result, empty_az_result, final_result",
    [
        param(
            Result(Severity.OK, "foo"),
            Result(Severity.OK, "bar"),
            True,
            id="all-checks-Pass",
        ),
        param(
            Result(Severity.FAIL, "foo"),
            Result(Severity.OK, "bar"),
            False,
            id="only-empty_az-Pass",
        ),
        param(
            Result(Severity.OK, "foo"),
            Result(Severity.FAIL, "bar"),
            False,
            id="only-vm_count-Pass",
        ),
        param(
            Result(Severity.FAIL, "foo"),
            Result(Severity.FAIL, "bar"),
            False,
            id="all-checks-Failed",
        ),
    ],
)
def test_verify_reboot(mocker, vm_count_result, empty_az_result, final_result):
    """Test results of the verify_reboot method in NovaCompute."""
    mocker.patch.object(
        NovaCompute, "check_no_running_vms"
    ).return_value = vm_count_result
    mocker.patch.object(NovaCompute, "check_no_empty_az").return_value = empty_az_result

    verifier = NovaCompute([Unit("nova-compute/0", Model())])
    result = verifier.verify_reboot()
    assert result.success == final_result


def test_verify_shutdown(mocker):
    """Test that verify_shutdown links to verify_reboot."""
    mock_verify_reboot = mocker.patch.object(NovaCompute, "verify_reboot")
    unit = Unit("nova-compute/0", Model())

    verifier = NovaCompute([unit])
    verifier.verify_shutdown()

    mock_verify_reboot.assert_called_once()
