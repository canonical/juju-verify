#!/usr/bin/env python3
"""Entrypoint to the 'juju verify' plugin"""
import argparse
import sys

from typing import Dict, List, Union

from juju import loop
from juju import errors
from juju.model import Model
from juju.unit import Unit

from juju_verify.verifiers import get_verifier
from juju_verify.exceptions import CharmException, VerificationError

SUPPORTED_CHECKS = [
    'reboot',
    'shutdown'
]


def fail(err_msg: str) -> None:
    """Print error message and exit"""
    print("Error. {}".format(err_msg))
    sys.exit(1)


async def find_units(model: Model, units: List[str]) -> List[Unit]:
    """Returns list of juju.Unit objects that match with names in 'units'
    parameter.

    This function will exit program with error message if any of units is not
    found in the juju model.

    :param model: Juju model to search units in.
    :param units: List of unit names to search
    :return: List of matching juju.Unit objects
    """
    all_units: Dict[str, Unit] = {}
    selected_units: List[Unit] = []

    for _, app in model.applications.items():
        for unit in app.units:
            all_units[unit.entity_id] = unit

    for unit_name in units:
        unit = all_units.get(unit_name)
        if unit is None:
            fail('Unit "{}" not found in the model.'.format(unit_name))
        selected_units.append(unit)
    return selected_units


async def connect_model(model_name: Union[str, None]) -> Model:
    """Connect to Juju model identified by 'model_name' or currently active
    model if the name is not specified."""
    model = Model()
    try:
        if model_name:
            await model.connect_model(model_name)
        else:
            await model.connect_current()
    except errors.JujuError as exc:
        fail("Failed to connect to the model.\n{}".format(exc))
    return model


def parse_args() -> argparse.Namespace:
    """Parse cli arguments"""
    description = "Verify that it's safe to perform selected action on " \
                  "specified units"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--model', '-m', required=False,
                        help='Connect to specific model')
    parser.add_argument('check', choices=SUPPORTED_CHECKS,
                        help='Check to verify')
    parser.add_argument('units', nargs='+', help='Units to check')

    return parser.parse_args()


def main() -> None:
    """Execute 'juju-verify' command"""
    args = parse_args()
    model = loop.run(connect_model(args.model))
    units = loop.run(find_units(model, args.units))
    try:
        verifier = get_verifier(units)
        verifier.verify(args.check)
    except (CharmException, VerificationError) as exc:
        fail(str(exc))


if __name__ == '__main__':
    main()
