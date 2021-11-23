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

"""Juju plugin to help verify the safety of maintenance operations.

The tool allows users to check whether it's safe to execute operations like
'shutdown' or 'reboot' on juju units without affecting availability and integrity.
"""
import logging

stream_handler = logging.StreamHandler()
logging.basicConfig(
    format="%(message)s", level=logging.WARNING, handlers=[stream_handler]
)
# This is the main logger for juju-verify from which all other loggers in this package
# should inherit. There is also a test that checks whether all loggers are defined as
# `logger = logging.getLogger(__ name __)`, ie whether they inherit from this logger.
logger = logging.getLogger(__package__)
# While the root logger is set to the WARNING level, the logger for jujju-verify is set
# to the INFO level.
logger.setLevel(logging.INFO)
