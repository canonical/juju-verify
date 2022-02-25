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
"""Cli test suite for entrypoint function and helpers."""
import importlib
import logging
import os
import pkgutil
from argparse import Namespace
from asyncio import Future
from unittest.mock import ANY, MagicMock

import pytest
from juju import errors
from juju.model import Model

from juju_verify import cli
from juju_verify.exceptions import CharmException, JujuVerifyError, VerificationError
from juju_verify.verifiers.base import Result, Severity


def test_all_loggers():
    """Test if all logger used in this project inherited from juju_verify.

    All logger should be defined as follow:
    logger = logging.getLogger(__name__)
    """
    for _, name, _ in pkgutil.walk_packages([__package__]):
        if name != "setup":
            juju_verify_module = importlib.import_module(name)
            if hasattr(juju_verify_module, "logger"):
                assert juju_verify_module.logger.name.startswith(
                    "juju_verify"
                ), "`{}.logger` does not inherit from juju_verify".format(name)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_name",
    [None, "NamedModel"],
)
async def test_connect_model(mocker, model_name):
    """Test that connect_model function connects to correct model.

    Based on the 'model_name' parameter of connect-model function, it should
    either call 'juju.model.Model().connect_current` if model_name is None,
    or `juju.model.Model().connect_model(model_name)` if model_name is provided
    """
    connection_method = mocker.patch.object(cli.Model, "connect")
    connection_method.return_value = Future()
    connection_method.return_value.set_result(None)

    model = await cli.connect_model(model_name)

    connection_method.assert_called_once()
    assert isinstance(model, Model)

    # Assert that fail is called if connection fails

    err_msg = "foo"
    connection_method.side_effect = errors.JujuError(err_msg)
    expected_msg = f"Failed to connect to the model.{os.linesep}{err_msg}"

    with pytest.raises(CharmException) as error:
        await cli.connect_model(model_name)
        assert expected_msg in str(error.value)


@pytest.mark.parametrize(
    "log_level, global_level, local_level",
    [
        ("trace", logging.DEBUG, logging.DEBUG),
        ("debug", logging.INFO, logging.DEBUG),
        ("DEBUG", logging.INFO, logging.DEBUG),
        ("info", logging.WARNING, logging.INFO),
        ("InFo", logging.WARNING, logging.INFO),
    ],
)
def test_config_logger(mocker, log_level, global_level, local_level):
    """Test setting basic log levels (debug/info)."""
    mock_get_logger = mocker.patch.object(cli.logging, "getLogger")
    mock_root_logger = mock_get_logger.return_value = MagicMock()
    mock_logger = mocker.patch.object(cli, "juju_verify_logger")
    mock_stream_handler = mocker.patch.object(cli, "stream_handler")

    cli.config_logger(log_level)

    mock_root_logger.setLevel.assert_called_once_with(global_level)
    mock_logger.setLevel.assert_called_once_with(local_level)
    mock_stream_handler.setFormatter.assert_called_once()


@pytest.mark.parametrize("log_level", ["warning", "error", "critical", "foo"])
def test_unsupported_log_levels(log_level):
    """juju-verify cli supports only info(default)/debug/trace log levels."""
    expected_msg = f"Unsupported log level requested: '{log_level}'"

    with pytest.raises(JujuVerifyError) as error:
        cli.config_logger(log_level)
        assert expected_msg in str(error.value)


@pytest.mark.parametrize(
    "arg_value, exp_result, exp_failure",
    [
        (
            ["ceph-osd:ceph-osd", "ceph-mon:ceph-mon"],
            [("ceph-osd", "ceph-osd"), ("ceph-mon", "ceph-mon")],
            False,
        ),  # Correct mapping of multiple applications
        (["ceph-osd-ssd:ceph-osd:foo"], [], True),  # too many colons in mapping
        (["ceph-osd-ssd"], [], True),  # application not mapped to charm
        ([42], [], True),  # bad type of argument. String expected
    ],
)
def test_parse_charm_mapping(arg_value, exp_result, exp_failure):
    """Test converting string values of --map-charms to List of Tuples."""
    args = Namespace(map_charm=arg_value)

    if exp_failure:
        with pytest.raises(ValueError):
            cli.parse_charm_mapping(args)
    else:
        cli.parse_charm_mapping(args)
        assert args.map_charm == exp_result


@pytest.mark.parametrize(
    "args, exp_args",
    [
        (
            ["reboot", "--units", "ceph-osd/0", "ceph-osd/1"],
            dict(
                check="reboot",
                machines=None,
                map_charm=[],
                units=["ceph-osd/0", "ceph-osd/1"],
                stop_on_failure=False,
            ),
        ),
        (
            ["reboot", "--machines", "0", "1"],
            dict(
                check="reboot",
                units=None,
                machines=["0", "1"],
                map_charm=[],
                stop_on_failure=False,
            ),
        ),
        (
            ["reboot", "--machines", "0", "--machines", "1"],
            dict(
                check="reboot",
                units=None,
                machines=["0", "1"],
                map_charm=[],
                stop_on_failure=False,
            ),
        ),
        (
            ["reboot", "--machine", "0", "--machine", "1"],
            dict(
                check="reboot",
                units=None,
                machines=["0", "1"],
                map_charm=[],
                stop_on_failure=False,
            ),
        ),
        (
            ["reboot", "--machine", "0", "--machine", "1", "2"],
            dict(
                check="reboot",
                units=None,
                machines=["0", "1", "2"],
                map_charm=[],
                stop_on_failure=False,
            ),
        ),
        (
            ["reboot", "--machine", "0", "--stop-on-failure", "--machine", "1", "2"],
            dict(
                check="reboot",
                units=None,
                machines=["0", "1", "2"],
                map_charm=[],
                stop_on_failure=True,
            ),
        ),
    ],
)
def test_parse_args(args, exp_args, mocker):
    """Test for argument parsing."""
    mocker.patch("sys.argv", ["juju-verify", *args])
    mapping_mock = mocker.patch.object(cli, "parse_charm_mapping")
    exp_result = Namespace(**exp_args, log_level="info", model=None)

    result = cli.parse_args()
    mapping_mock.assert_called_once_with(exp_result)
    assert result == exp_result


@pytest.mark.parametrize(
    "args",
    [
        ["--units", "ceph-osd/0"],
        ["--machines", "0"],
        ["reboot", "--units", "ceph-osd/0", "--machines", "0"],
    ],
)
def test_parse_args_error(args, mocker):
    """Test for argument parsing raise error."""
    mocker.patch("sys.argv", ["juju-verify", *args])

    with pytest.raises(SystemExit):
        cli.parse_args()


def test_parse_args_charm_mapping_error(mocker):
    """Test behavior of arg parsing when --map-charms option has bad values."""
    mock_parser = MagicMock()
    parser_error = MagicMock()
    mock_parser.error = parser_error

    mocker.patch.object(cli.argparse, "ArgumentParser", return_value=mock_parser)
    mocker.patch.object(cli, "parse_charm_mapping", side_effect=ValueError)

    expected_error = (
        "Unexpected format of --map-charm argument. For more info see " "--help"
    )

    cli.parse_args()

    parser_error.assert_called_once_with(expected_error)


def test_main_cli_target_units(mocker):
    """Verify workflow of the main cli when script targets units."""
    args = MagicMock()
    args.log_level = "info"
    args.model = None
    args.check = "shutdown"
    args.units = ["nova-compute/0"]
    args.machines = None

    result = Result(Severity.OK, "Passed")
    verifier = MagicMock()
    verifier.verify.return_value = result

    mocker.patch.object(cli, "parse_args").return_value = args
    mocker.patch.object(cli, "get_verifiers").return_value = [verifier]
    mocker.patch.object(cli, "asyncio")
    mocker.patch.object(cli, "connect_model", new_callable=MagicMock())
    mocker.patch.object(cli, "find_units", new_callable=MagicMock())
    logger = mocker.patch.object(cli, "logger")

    cli.entrypoint()

    cli.connect_model.assert_called_with(args.model)
    cli.find_units.assert_called_with(ANY, args.units)
    verifier.verify.asssert_called_with(args.check)
    logger.info.assert_called_with("%s", result)


def test_main_cli_target_machine(mocker):
    """Verify workflow of the main cli when script targets machines."""
    args = MagicMock()
    args.log_level = "info"
    args.model = None
    args.check = "shutdown"
    args.machines = ["0"]
    args.units = None
    expected_units = ["nova-compute/0"]

    result = Result(Severity.OK, "Passed")
    verifier = MagicMock()
    verifier.verify.return_value = result

    mocker.patch.object(cli, "parse_args").return_value = args
    mocker.patch.object(cli, "get_verifiers").return_value = [verifier]
    mocker.patch.object(cli, "asyncio")
    mocker.patch.object(cli, "connect_model", new_callable=MagicMock())
    mocker.patch.object(
        cli, "find_units_on_machine", new_callable=MagicMock()
    ).return_value = expected_units
    logger = mocker.patch.object(cli, "logger")

    cli.entrypoint()

    cli.connect_model.assert_called_with(args.model)
    cli.find_units_on_machine.assert_called_with(ANY, args.machines)
    verifier.verify.asssert_called_with(args.check)
    logger.info.assert_called_with("%s", result)


def test_main_cli_no_target_fail(mocker):
    """Test that main fails if not target (units/machines) is specified."""
    args = MagicMock()
    args.log_level = "info"
    args.model = None
    args.check = "shutdown"
    args.machines = None
    args.units = None

    expected_msg = "juju-verify must target either juju units or juju machines"

    mocker.patch.object(cli, "parse_args").return_value = args
    mocker.patch.object(cli, "connect_model", new_callable=MagicMock())
    mocker.patch.object(cli, "asyncio")
    mock_logger = mocker.patch.object(cli, "logger")

    with pytest.raises(SystemExit):
        cli.entrypoint()
        mock_logger.error.assert_callled_once_with(expected_msg)


@pytest.mark.parametrize(
    "error, error_msg",
    [
        (CharmException, "Charm failure"),
        (VerificationError, "Verification Failure"),
        (NotImplementedError, "No Implementation"),
    ],
)
def test_main_expected_failure(mocker, error, error_msg):
    """Verify handling of expected exceptions."""
    mocker.patch.object(cli, "parse_args")
    mocker.patch.object(cli, "config_logger")
    mocker.patch.object(cli, "asyncio")
    mocker.patch.object(cli, "connect_model", new_callable=MagicMock())
    mocker.patch.object(cli, "find_units", new_callable=MagicMock())
    mocker.patch.object(cli, "get_verifiers").side_effect = [error(error_msg)]
    mock_logger = mocker.patch.object(cli, "logger")

    with pytest.raises(SystemExit):
        cli.entrypoint()
        mock_logger.error.assert_callled_once_with(error_msg)
