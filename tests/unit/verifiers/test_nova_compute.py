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

from juju_verify.verifiers import NovaCompute
from juju_verify.verifiers import Result


@pytest.mark.parametrize('vm_count, expect_result',
                         [('0', Result(True)),
                          ('1', Result(False))])
def test_nova_compute_no_running_vms(mocker, vm_count, expect_result):
    """Test expected Result based on the number of VMs running on nova."""
    # Prepare Units for verifier
    unit_names = ['nova-compute/0', 'nova-compute/1']
    model = Model()
    units = [Unit(name, model) for name in unit_names]

    # Mock result of 'instance-count' action on all verified units.
    result_data = {'results': {'instance-count': vm_count}}
    mock_result = MagicMock()
    mock_result.data = result_data
    action_results = {unit: mock_result for unit in unit_names}
    mocker.patch.object(NovaCompute,
                        'run_action_on_all').return_value = action_results

    fail_reason = ''
    for unit in unit_names:
        fail_reason += 'Unit {} is running {} VMs.\n'.format(unit, vm_count)

    # Create and run verifier
    verifier = NovaCompute(units)
    result = verifier.check_no_running_vms()

    # Assert expected results
    assert result.success == expect_result.success
    if not result.success:
        assert result.reason == fail_reason


@pytest.mark.parametrize('all_hosts, remove_hosts, host_state, host_status, '
                         'expect_result', [
                             param(2, 2, 'up', 'enabled', Result(False),
                                   id='fail-on-empty-az'),
                             param(3, 2, 'up', 'enabled', Result(True),
                                   id='success-non-empty-az'),
                             param(3, 2, 'down', 'enabled', Result(False),
                                   id='fail-down-host-left'),
                             param(3, 2, 'up', 'disabled', Result(False),
                                   id='fail-disabled-host-left'),
                             param(3, 2, 'down', 'disabled', Result(False),
                                   id='fail-down-disabled-host-left'),
                         ])
def test_nova_compute_empty_az(all_hosts, remove_hosts, host_state,
                               host_status, expect_result, mocker):
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
    unit_pool = ['nova-compute/0', 'nova-compute/1', 'nova-compute/2']
    host_pool = ['compute.0', 'compute.1', 'compute.2']

    # prepare Units for verifier. Number of units to remove is parametrized.
    unit_names = unit_pool[:remove_hosts]
    model = Model()
    units = [Unit(name, model) for name in unit_names]
    zone = 'nova'

    fail_reason = 'Removing these units would leave these availability zones' \
                  ' empty: {}'.format({zone})

    # mock results of 'node-names' action on all verified units
    node_name_results = []
    for node in host_pool[:remove_hosts]:
        result_mock = MagicMock()
        result_mock.data = {'results': {'node-name': node}}
        node_name_results.append(result_mock)
    action_results = dict(zip(unit_names, node_name_results))

    mocker.patch.object(NovaCompute,
                        'run_action_on_all').return_value = action_results

    # mock result 'list-compute-nodes' action. Number of nodes in zone
    # is parametrized.
    raw_compute_nodes = [{'host': host,
                          'zone': zone,
                          'state': host_state,
                          'status': host_status}
                         for host in host_pool[:all_hosts]]

    compute_nodes_data = {'results': {
        'compute-nodes': json.dumps(raw_compute_nodes)}}
    mock_compute_node_result = MagicMock()
    mock_compute_node_result.data = compute_nodes_data
    mocker.patch.object(NovaCompute,
                        'run_action_on_unit'
                        ).return_value = mock_compute_node_result

    # run verifier
    verifier = NovaCompute(units)
    result = verifier.check_no_empty_az()

    # assert expected results
    assert result.success == expect_result.success
    if not result.success:
        assert result.reason == fail_reason


@pytest.mark.parametrize('vm_count_result, empty_az_result, final_result', [
    param(Result(True), Result(True), Result(True), id="all-checks-Pass"),
    param(Result(False), Result(True), Result(False), id="only-empty_az-Pass"),
    param(Result(True), Result(False), Result(False), id="only-vm_count-Pass"),
    param(Result(False), Result(False), Result(False), id="all-checks-Failed"),
])
def test_verify_reboot(mocker, vm_count_result, empty_az_result, final_result):
    """Test results of the verify_reboot method in NovaCompute."""
    mocker.patch.object(NovaCompute, 'check_no_running_vms'
                        ).return_value = vm_count_result
    mocker.patch.object(NovaCompute, 'check_no_empty_az'
                        ).return_value = empty_az_result

    verifier = NovaCompute([Unit('nova-compute/0', Model())])
    result = verifier.verify_reboot()
    assert result.success == final_result.success


def test_verify_shutdown(mocker):
    """Test that verify_shutdown links to verify_reboot."""
    mocker.patch.object(NovaCompute, 'verify_reboot')
    unit = Unit('nova-compute/0', Model())

    verifier = NovaCompute([unit])
    verifier.verify_shutdown()

    verifier.verify_reboot.assert_called_once()
