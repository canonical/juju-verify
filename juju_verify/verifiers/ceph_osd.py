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
"""ceph-osd verification."""
import logging
from typing import Set

from juju.unit import Unit

from juju_verify.utils.ceph import check_cluster_health
from juju_verify.verifiers.base import BaseVerifier
from juju_verify.verifiers.result import aggregate_results, Result

logger = logging.getLogger()


class CephOsd(BaseVerifier):
    """Implementation of verification checks for the ceph-osd charm."""

    NAME = 'ceph-osd'

    def get_ceph_mon_units(self) -> Set[Unit]:
        """Get Ceph-mon units related to verified units.

        1. get all distinct ceph-osd applications from provides units
        2. get all relationships based on found apps or ceph-mon
        3. get the first unit from the application providing the relation
        """
        # get all affected ceph-osd applications
        applications = {unit.application for unit in self.units}
        logger.debug("affected applications %s", map(str, applications))
        applications.add("ceph-osd")

        # get all relation between ceph-osd and ceph-mon
        relations = [relation for relation in self.model.relations
                     if any(relation.matches(f"{application}:mon")
                            for application in applications)]
        logger.debug("found relations %s", map(str, relations))

        # get first ceph-mon unit from relation
        ceph_mon_units = {relation.provides.application.units[0]
                          for relation in relations}
        logger.debug("found units %s", map(str, ceph_mon_units))

        return ceph_mon_units

    def verify_reboot(self) -> Result:
        """Verify that it's safe to reboot selected nova-compute units."""
        return aggregate_results(check_cluster_health(*self.get_ceph_mon_units()))

    def verify_shutdown(self) -> Result:
        """Verify that it's safe to shutdown selected nova-compute units."""
        return self.verify_reboot()
