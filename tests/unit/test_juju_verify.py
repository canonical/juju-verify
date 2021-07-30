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
"""Test suite for the entrypoint function and helpers."""

import logging
import os
import sys
from argparse import Namespace
from asyncio import Future
from unittest.mock import ANY, MagicMock

import pytest
from juju import errors
from juju.model import Model
from juju.unit import Unit

from juju_verify import juju_verify
from juju_verify.exceptions import CharmException, VerificationError
from juju_verify.verifiers.base import Result, Severity


def test_fail(mocker):
    """Test that fail function logs message and exits program."""
    mock_exit = mocker.patch.object(sys, 'exit')
    mocker.patch.object(juju_verify, 'logger')
    msg = 'test_fail'

    juju_verify.fail(msg)

    juju_verify.logger.error.assert_called_with(msg)
    mock_exit.assert_called_with(1)


@pytest.mark.asyncio
@pytest.mark.parametrize('model_name, func_name',
                         [(None, 'connect_current'),
                          ('NamedModel', 'connect_model')])
async def test_connect_model(mocker, fail, model_name, func_name):
    """Test that connect_model function connects to correct model.

    Based on the 'model_name' parameter of connect-model function, it should
    either call 'juju.model.Model().connect_current` if model_name is None,
    or `juju.model.Model().connect_model(model_name)` if model_name is provided
    """
    connection_method = mocker.patch.object(juju_verify.Model, func_name)
    connection_method.return_value = Future()
    connection_method.return_value.set_result(None)

    model = await juju_verify.connect_model(model_name)

    connection_method.assert_called_once()
    fail.assert_not_called()
    assert isinstance(model, Model)

    # Assert that fail is called if connection fails

    err_msg = 'foo'
    connection_method.side_effect = errors.JujuError(err_msg)
    expected_msg = 'Failed to connect to the model.{}{}'.format(os.linesep,
                                                                err_msg)

    await juju_verify.connect_model(model_name)

    fail.assert_called_once_with(expected_msg)


@pytest.mark.asyncio
async def test_find_units(model, all_units, fail):
    """Test that find_units returns correct list of Unit objects."""
    unit_list = await juju_verify.find_units(model, all_units)

    assert len(unit_list) == len(all_units)

    result = zip(all_units, unit_list)
    for (unit_name, unit_obj) in result:
        assert isinstance(unit_obj, Unit)
        assert unit_obj.entity_id == unit_name

    # fail if requested unit is not in the list of all units

    missing_unit = 'foo/0'
    expected_message = 'Unit "{}" not found in the model.'.format(missing_unit)

    await juju_verify.find_units(model, [missing_unit])

    fail.assert_called_once_with(expected_message)


@pytest.mark.asyncio
async def test_find_units_on_machine(model, all_units):
    """Test that find_units_on_machine function returns correct units."""
    machine_1_name = '0'
    machine_2_name = '1'

    machine_1 = MagicMock()
    machine_1.entity_id = machine_1_name
    machine_2 = MagicMock()
    machine_2.entity_id = machine_2_name

    machine_1_units = all_units[:3]
    machine_2_units = all_units[3:]

    for unit_name, unit in model.units.items():
        if unit_name in machine_1_units:
            unit.machine = machine_1
        elif unit_name in machine_2_units:
            unit.machine = machine_2

    found_units = await juju_verify.find_units_on_machine(model,
                                                          [machine_1_name])

    assert machine_1_units == [unit.entity_id for unit in found_units]


@pytest.mark.parametrize('log_level, log_constant',
                         [('debug', logging.DEBUG),
                          ('DEBUG', logging.DEBUG),
                          ('info', logging.INFO),
                          ('InFo', logging.INFO),
                          ])
def test_logger_setup_basic_levels(mocker, log_level, log_constant):
    """Test setting basic log levels (debug/info)."""
    logger = mocker.patch.object(juju_verify, 'logger')
    basic_config = mocker.patch.object(logging, 'basicConfig')
    log_format = '%(message)s'

    juju_verify.config_logger(log_level)

    logger.setLevel.assert_called_once_with(log_constant)
    basic_config.assert_called_once_with(format=log_format)


@pytest.mark.parametrize('log_level', ['trace', 'TRACE'])
def test_logger_setup_deep_logging(mocker, log_level):
    """Test setting up deep logging with 'trace' level."""
    basic_config = mocker.patch.object(logging, 'basicConfig')
    log_format = '%(message)s'

    juju_verify.config_logger(log_level)

    basic_config.assert_called_once_with(format=log_format,
                                         level=logging.DEBUG)


@pytest.mark.parametrize('log_level', ['warning', 'error', 'critical', 'foo'])
def test_unsupported_log_levels(fail, log_level):
    """juju-verify cli supports only info(default)/debug/trace log levels."""
    expected_msg = 'Unsupported log level requested: "{}"'.format(log_level)

    juju_verify.config_logger(log_level)

    fail.assert_called_with(expected_msg)


@pytest.mark.parametrize("args, exp_args", [
    (["reboot", "--units", "ceph-osd/0", "ceph-osd/1"],
     dict(check="reboot", machines=None, units=["ceph-osd/0", "ceph-osd/1"],
          stop_on_failure=False)),
    (["reboot", "--machines", "0", "1"],
     dict(check="reboot", units=None, machines=["0", "1"], stop_on_failure=False)),
    (["reboot", "--machines", "0", "--machines", "1"],
     dict(check="reboot", units=None, machines=["0", "1"], stop_on_failure=False)),
    (["reboot", "--machine", "0", "--machine", "1"],
     dict(check="reboot", units=None, machines=["0", "1"], stop_on_failure=False)),
    (["reboot", "--machine", "0", "--machine", "1", "2"],
     dict(check="reboot", units=None, machines=["0", "1", "2"], stop_on_failure=False)),
    (["reboot", "--machine", "0", "--stop-on-failure", "--machine", "1", "2"],
     dict(check="reboot", units=None, machines=["0", "1", "2"], stop_on_failure=True)),
])
def test_parse_args(args, exp_args, mocker):
    """Test for argument parsing."""
    mocker.patch("sys.argv", ["juju-verify", *args])
    exp_result = Namespace(**exp_args, log_level="info", model=None)

    result = juju_verify.parse_args()
    assert result == exp_result


@pytest.mark.parametrize("args", [
    ["--units", "ceph-osd/0"],
    ["--machines", "0"],
    ["reboot", "--units", "ceph-osd/0", "--machines", "0"]
])
def test_parse_args_error(args, mocker):
    """Test for argument parsing raise error."""
    mocker.patch("sys.argv", ["juju-verify", *args])

    with pytest.raises(SystemExit):
        juju_verify.parse_args()


def test_main_entrypoint_target_units(mocker):
    """Verify workflow of the main entrypoint when script targets units."""
    args = MagicMock()
    args.log_level = 'info'
    args.model = None
    args.check = 'shutdown'
    args.units = ['nova-compute/0']
    args.machines = None

    result = Result(Severity.OK, 'Passed')
    verifier = MagicMock()
    verifier.verify.return_value = result

    mocker.patch.object(juju_verify, 'parse_args').return_value = args
    mocker.patch.object(juju_verify, 'get_verifier').return_value = verifier
    mocker.patch.object(juju_verify, 'loop')
    mocker.patch.object(juju_verify, 'connect_model', new_callable=MagicMock())
    mocker.patch.object(juju_verify, 'find_units', new_callable=MagicMock())
    logger = mocker.patch.object(juju_verify, 'logger')

    juju_verify.main()

    juju_verify.connect_model.assert_called_with(args.model)
    juju_verify.find_units.assert_called_with(ANY, args.units)
    verifier.verify.asssert_called_with(args.check)
    logger.info.assert_called_with(str(result))


def test_main_entrypoint_target_machine(mocker):
    """Verify workflow of the main entrypoint when script targets machines."""
    args = MagicMock()
    args.log_level = 'info'
    args.model = None
    args.check = 'shutdown'
    args.machines = ['0']
    args.units = None
    expected_units = ['nova-compute/0']

    result = Result(Severity.OK, 'Passed')
    verifier = MagicMock()
    verifier.verify.return_value = result

    mocker.patch.object(juju_verify, 'parse_args').return_value = args
    mocker.patch.object(juju_verify, 'get_verifier').return_value = verifier
    mocker.patch.object(juju_verify, 'loop')
    mocker.patch.object(juju_verify, 'connect_model', new_callable=MagicMock())
    mocker.patch.object(juju_verify, 'find_units_on_machine',
                        new_callable=MagicMock()).return_value = expected_units
    logger = mocker.patch.object(juju_verify, 'logger')

    juju_verify.main()

    juju_verify.connect_model.assert_called_with(args.model)
    juju_verify.find_units_on_machine.assert_called_with(ANY, args.machines)
    verifier.verify.asssert_called_with(args.check)
    logger.info.assert_called_with(str(result))


def test_main_entrypoint_no_target_fail(mocker, fail):
    """Test that main fails if not target (units/machines) is specified."""
    args = MagicMock()
    args.log_level = 'info'
    args.model = None
    args.check = 'shutdown'
    args.machines = None
    args.units = None

    expected_msg = 'juju-verify must target either juju units or juju machines'

    mocker.patch.object(juju_verify, 'parse_args').return_value = args
    mocker.patch.object(juju_verify, 'connect_model', new_callable=MagicMock())
    mocker.patch.object(juju_verify, 'loop')

    juju_verify.main()

    fail.assert_any_call(expected_msg)


@pytest.mark.parametrize('error, error_msg',
                         [(CharmException, 'Charm failure'),
                          (VerificationError, 'Verification Failure'),
                          (NotImplementedError, 'No Implementation'),
                          ])
def test_main_expected_failure(mocker, fail, error, error_msg):
    """Verify handling of expected exceptions."""
    mocker.patch.object(juju_verify, 'parse_args')
    mocker.patch.object(juju_verify, 'config_logger')
    mocker.patch.object(juju_verify, 'loop')
    mocker.patch.object(juju_verify, 'connect_model', new_callable=MagicMock())
    mocker.patch.object(juju_verify, 'find_units', new_callable=MagicMock())
    mocker.patch.object(juju_verify,
                        'get_verifier').side_effect = error(error_msg)

    juju_verify.main()

    fail.assert_called_once_with(error_msg)
