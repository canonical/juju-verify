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

import sys
import argparse
import logging
from unittest.mock import MagicMock, ANY

import pytest

from juju import errors
from juju.model import Model
from juju.unit import Unit
from juju_verify import juju_verify
from juju_verify.exceptions import VerificationError, CharmException
from juju_verify.verifiers.base import Result


def test_fail(mocker):
    """Test that fail function logs message and exits program."""
    exit = mocker.patch.object(sys, 'exit')
    mocker.patch.object(juju_verify, 'logger')
    msg = 'test_fail'

    juju_verify.fail(msg)

    juju_verify.logger.error.assert_called_with(msg)
    exit.assert_called_with(1)


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
    connection_method = mocker.patch.object(Model, func_name)

    model = await juju_verify.connect_model(model_name)

    connection_method.assert_called_once()
    fail.assert_not_called()
    assert isinstance(model, Model)

    # Assert that fail is called if connection fails

    err_msg = 'foo'
    connection_method.side_effect = errors.JujuError(err_msg)
    expected_msg = 'Failed to connect to the model.\n{}'.format(err_msg)

    await juju_verify.connect_model(model_name)

    fail.assert_called_once_with(expected_msg)


@pytest.mark.asyncio
async def test_find_units(model, all_units, fail):
    """Test that find_units returns correct list of Unit objects"""
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


@pytest.mark.parametrize('log_level, log_constant',
                         [('debug', logging.DEBUG),
                          ('DEBUG', logging.DEBUG),
                          ('info', logging.INFO),
                          ('InFo', logging.INFO),
                          ])
def test_logger_setup_basic_levels(mocker, log_level, log_constant):
    """Test setting basic log levels (debug/info)"""
    logger = mocker.patch.object(juju_verify, 'logger')
    basic_config = mocker.patch.object(logging, 'basicConfig')
    log_format = '%(message)s'

    juju_verify.config_logger(log_level)

    logger.setLevel.assert_called_once_with(log_constant)
    basic_config.assert_called_once_with(format=log_format)


@pytest.mark.parametrize('log_level', ['trace', 'TRACE'])
def test_logger_setup_deep_logging(mocker, log_level):
    """Test setting up deep logging with 'trace' level"""
    basic_config = mocker.patch.object(logging, 'basicConfig')
    log_format = '%(message)s'

    juju_verify.config_logger(log_level)

    basic_config.assert_called_once_with(format=log_format,
                                         level=logging.DEBUG)


@pytest.mark.parametrize('log_level', ['warning', 'error', 'critical', 'foo'])
def test_unsupported_log_levels(fail, log_level):
    """juju-verify cli supports only info(default)/debug/trace log levels"""
    expected_msg = 'Unsupported log level requested: "{}"'.format(log_level)

    juju_verify.config_logger(log_level)

    fail.assert_called_with(expected_msg)


def test_parse_args(mocker):
    """Rudimentary test for argument parsing"""
    parser = mocker.patch.object(argparse.ArgumentParser, 'parse_args')

    juju_verify.parse_args()

    parser.assert_called_once()


def test_main_entrypoint(mocker):
    """Verify workflow if the main entrypoint"""
    args = MagicMock()
    args.log_level = 'info'
    args.model = None
    args.check = 'shutdown'
    args.units = ['nova-compute/0']

    result = Result(True, 'Passed')
    verifier = MagicMock()
    verifier.verify.return_value = result

    mocker.patch.object(juju_verify, 'parse_args').return_value = args
    mocker.patch.object(juju_verify, 'get_verifier').return_value = verifier
    mocker.patch.object(juju_verify, 'connect_model')
    mocker.patch.object(juju_verify, 'find_units')
    logger = mocker.patch.object(juju_verify, 'logger')

    juju_verify.main()

    juju_verify.connect_model.assert_called_with(args.model)
    juju_verify.find_units.assert_called_with(ANY, args.units)
    verifier.verify.asssert_called_with(args.check)
    logger.info.assert_called_with(result.format())


@pytest.mark.parametrize('error, error_msg',
                         [(CharmException, 'Charm failure'),
                          (VerificationError, 'Verification Failure'),
                          (NotImplementedError, 'No Implementation'),
                          ])
def test_main_expected_failure(mocker, fail, error, error_msg):
    """Verify handling of expected exceptions"""
    mocker.patch.object(juju_verify, 'parse_args')
    mocker.patch.object(juju_verify, 'config_logger')
    mocker.patch.object(juju_verify, 'connect_model')
    mocker.patch.object(juju_verify, 'find_units')
    mocker.patch.object(juju_verify,
                        'get_verifier').side_effect = error(error_msg)

    juju_verify.main()

    fail.assert_called_once_with(error_msg)
