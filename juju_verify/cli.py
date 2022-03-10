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
import asyncio
import logging
import os
import sys
import typing
from typing import Tuple, Union

from juju import errors
from juju.model import Model

from juju_verify import logger as juju_verify_logger
from juju_verify import stream_handler
from juju_verify.exceptions import CharmException, JujuVerifyError, VerificationError
from juju_verify.utils.unit import find_units, find_units_on_machine
from juju_verify.verifiers import SUPPORTED_CHARMS, BaseVerifier, get_verifiers
from juju_verify.verifiers.result import set_stop_on_failure

# set MAX_FRAME_SIZE to 64MB to connect python-libjuju to the model
JUJU_MAX_FRAME_SIZE = 2**26
logger = logging.getLogger(__name__)


async def connect_model(model_name: Union[str, None]) -> Model:
    """Connect to a custom or default Juju model.

    The Juju model can be identified by 'model_name' or the currently active
    model will be used if left unspecified.
    """
    model = Model()
    try:
        if model_name:
            logger.debug("Connecting to model '%s'.", model_name)
            await model.connect(
                model_name=model_name, max_frame_size=JUJU_MAX_FRAME_SIZE
            )
        else:
            logger.debug("Connecting to currently active model.")
            await model.connect(max_frame_size=JUJU_MAX_FRAME_SIZE)
    except errors.JujuError as exc:
        raise CharmException(
            f"Failed to connect to the model.{os.linesep}{exc}"
        ) from exc

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


def parse_charm_mapping(charm_map: str = "") -> Tuple[str, str]:
    """Parse value of --map-charm argument into a tuple (app_name, charm_name).

    Expected input format of mapping is two colon separated strings.

    :param charm_map: Colon separated pair <APP_NAME>:<CHARM_NAME>.
    :return: Input value parsed into tuple (app_name, charm_name)
    """
    if not isinstance(charm_map, str):
        raise ValueError("--map-charm arguments expects string type value.")

    try:
        app_name, charm_name = charm_map.split(":")
    except ValueError as exc:
        raise ValueError(
            "Unexpected format of --map-charm argument. For more info see --help."
        ) from exc

    return app_name, charm_name


def parse_args() -> argparse.Namespace:
    """Parse cli arguments."""
    description = (
        "Verify that it's safe to perform selected action on specified units."
        f"{os.linesep}Currently supported charms are:"
    )
    description += "".join(f"\n\t* {verifier}" for verifier in SUPPORTED_CHARMS)
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.register("action", "extend", ExtendAction)

    parser.add_argument(
        "--model", "-m", required=False, help="Connect to specific model."
    )
    parser.add_argument(
        "check",
        choices=BaseVerifier.supported_checks(),
        type=str.lower,
        help="Check to verify.",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        type=str.lower,
        help="Set amount of displayed information",
        default="info",
        choices=["trace", "debug", "info"],
    )
    parser.add_argument(
        "-s",
        "--stop-on-failure",
        action="store_true",
        help="Stop running checks after a failed one.",
    )
    parser.add_argument(
        "--map-charm",
        action="append",
        default=[],
        type=parse_charm_mapping,
        help="WARNING: This option can lead to failed verifications when used "
        "incorrectly. This option allows users to explicitly specify the charm used"
        " by an application. Typical use cases involve the usage of local charms or"
        " non-official charmhub repositories. Expected value format"
        " is <APP_NAME>:<CHARM_NAME>. For list of supported charms, see description"
        " in --help",
    )

    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--units", "-u", action="extend", nargs="+", type=str, help="Units to check."
    )
    target.add_argument(
        "--machines",
        "-M",
        action="extend",
        nargs="+",
        type=str,
        help="Check all units on the machine.",
    )
    return parser.parse_args()


def config_logger(log_level: str) -> None:
    """Configure logging options."""
    log_level = log_level.lower()
    root_logger = logging.getLogger()

    if log_level == "trace":
        # 'trace' level enables debugging in juju lib and other dependencies
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root_logger.setLevel(logging.DEBUG)
        juju_verify_logger.setLevel(logging.DEBUG)
    elif log_level == "debug":
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        root_logger.setLevel(logging.INFO)
        # set DEBUG level only for juju-verify logger
        juju_verify_logger.setLevel(logging.DEBUG)
    elif log_level == "info":
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.setLevel(logging.WARNING)
        # set INFO level only for juju-verify logger
        juju_verify_logger.setLevel(logging.INFO)
    else:
        raise JujuVerifyError(f"Unsupported log level requested: '{log_level}'")


def entrypoint() -> None:
    """Execute 'juju-verify' command."""
    try:
        args = parse_args()
        set_stop_on_failure(args.stop_on_failure)
        config_logger(args.log_level)  # update logging option
        loop = asyncio.get_event_loop()
        model = loop.run_until_complete(connect_model(args.model))

        if args.units:
            units = loop.run_until_complete(find_units(model, args.units))
        elif args.machines:
            units = loop.run_until_complete(find_units_on_machine(model, args.machines))
        else:
            raise JujuVerifyError(
                "juju-verify must target either juju units or juju machines"
            )

        for verifier in get_verifiers(units, args.map_charm):
            result = verifier.verify(args.check)
            logger.info("%s", result)
    except (
        JujuVerifyError,
        CharmException,
        VerificationError,
        NotImplementedError,
    ) as exc:
        logger.error(exc)
        sys.exit(1)
