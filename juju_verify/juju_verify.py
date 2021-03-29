#!/usr/bin/env python3

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

"""Entrypoint to the 'juju-verify' plugin."""
import argparse
import logging
import os
import sys
import typing
from typing import List, Union

from juju import errors, loop
from juju.model import Model
from juju.unit import Unit

from juju_verify.exceptions import CharmException, VerificationError
from juju_verify.verifiers import BaseVerifier, get_verifier

logger = logging.getLogger(__package__)


def fail(err_msg: str) -> None:
    """Log error message and exit."""
    logger.error(err_msg)
    sys.exit(1)


async def find_units(model: Model, units: List[str]) -> List[Unit]:
    """Return list of juju.Unit objects that match with names in 'units' parameter.

    This function will exit program with error message if any of units is not
    found in the juju model.

    :param model: Juju model to search units in.
    :param units: List of unit names to search
    :return: List of matching juju.Unit objects
    """
    selected_units: List[Unit] = []

    for unit_name in units:
        unit = model.units.get(unit_name)
        if unit is None:
            fail('Unit "{}" not found in the model.'.format(unit_name))
        selected_units.append(unit)
    return selected_units


async def find_units_on_machine(model: Model, machines: List[str]) -> List[Unit]:
    """Find all principal units that run on selected machines.

    :param model: Juju model to search units in
    :param machines: names of Juju machines on which to search units
    :return: List of juju.Unit objects that match units running on the machines
    """
    return [unit for _, unit in model.units.items()
            if unit.machine.entity_id in machines
            and not unit.data.get("subordinate")]


async def connect_model(model_name: Union[str, None]) -> Model:
    """Connect to a custom or default Juju model.

    The Juju model can be identified by 'model_name' or the currently active
    model will be used if left unspecified.
    """
    model = Model()
    try:
        if model_name:
            logger.debug('Connecting to model "%s".', model_name)
            await model.connect_model(model_name)
        else:
            logger.debug('Connecting to currently active model.')
            await model.connect_current()
    except errors.JujuError as exc:
        fail("Failed to connect to the model.{}{}".format(os.linesep, exc))
    return model


class ExtendAction(argparse.Action):  # pylint: disable=too-few-public-methods
    """Extend action for argparse.

    NOTE (rgildein): This action should be removed after python 3.6 support ends, because
                     since Python 3.8 the "extend" is available directly in stdlib.
    """

    @typing.no_type_check
    def __call__(self, parser, namespace, values, option_string=None):
        """Extend existing items with values."""
        items = getattr(namespace, self.dest) or []
        items = [*items, *values]  # extend list of items
        setattr(namespace, self.dest, items)


def parse_args() -> argparse.Namespace:
    """Parse cli arguments."""
    description = "Verify that it's safe to perform selected action on " \
                  "specified units"
    parser = argparse.ArgumentParser(description=description)
    parser.register("action", "extend", ExtendAction)

    parser.add_argument('--model', '-m', required=False,
                        help='Connect to specific model.')
    parser.add_argument('check', choices=BaseVerifier.supported_checks(),
                        type=str.lower, help='Check to verify.')
    parser.add_argument('-l', '--log-level', type=str.lower,
                        help='Set amount of displayed information',
                        default='info', choices=['trace', 'debug', 'info'])

    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--units', '-u', action="extend", nargs='+', type=str,
                        help='Units to check.')
    target.add_argument('--machines', '-M', action="extend", nargs='+', type=str,
                        help='Check all units on the machine.')
    return parser.parse_args()


def config_logger(log_level: str) -> None:
    """Configure logging options."""
    log_level = log_level.lower()

    if log_level == 'trace':
        # 'trace' level enables debugging in juju lib and other dependencies
        logging.basicConfig(format='%(message)s', level=logging.DEBUG)
    else:
        # other levels apply only to juju-verify logging
        logging.basicConfig(format='%(message)s')
        if log_level == 'debug':
            logger.setLevel(logging.DEBUG)
        elif log_level == 'info':
            logger.setLevel(logging.INFO)
        else:
            fail('Unsupported log level requested: "{}"'.format(log_level))


def main() -> None:
    """Execute 'juju-verify' command."""
    args = parse_args()
    config_logger(args.log_level)
    model = loop.run(connect_model(args.model))
    units: List[Unit] = []

    if args.units:
        units = loop.run(find_units(model, args.units))
    elif args.machines:
        units = loop.run(find_units_on_machine(model, args.machines))
    else:
        fail('juju-verify must target either juju units or juju machines')

    try:
        verifier = get_verifier(units)
        result = verifier.verify(args.check)
        logger.info(str(result))
    except (CharmException, VerificationError, NotImplementedError) as exc:
        fail(str(exc))


if __name__ == '__main__':  # pragma: no cover
    main()
