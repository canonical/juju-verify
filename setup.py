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
"""Manage package and distribution."""
from setuptools import setup
import subprocess
from typing import List


def find_version(filename: str = "version") -> str:
    """Parse the version and build details stored in the 'version' file."""
    try:
        cmd: List[str] = ["git", "describe", "--tags", "--always", "HEAD"]
        gitversion: str = subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL
        ).decode().strip()
        build: List[str] = gitversion.split("-")
        # <tagname>-<ncommits-ahead>-<commit-id> (e.g. 0.2-8-adfebee)
        if len(build) > 1:
            return "{}.post{}".format(build[0], build[1])

        # tagged commit
        return gitversion
    except subprocess.CalledProcessError:
        # If .git does not exist, default to an old dev version
        return "0.1.dev0"


setup(version=find_version())
