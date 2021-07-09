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
"""Functional tests for neutron-gateway verifier."""

import logging
from typing import Optional


from juju import loop
from neutronclient.v2_0.client import Client
from tests.base import OpenstackBaseTestCase
import zaza.openstack.utilities.openstack as openstack_utils

from juju_verify import juju_verify
from juju_verify.verifiers import get_verifier
from juju_verify.verifiers.result import Partial, Severity

logger = logging.getLogger()


class NeutronTests(OpenstackBaseTestCase):
    """Functional tests of neutron-gateway verifier."""

    CHECK = 'shutdown'
    APPLICATION_NAME = 'neutron-gateway'

    NEUTRON: Optional[Client] = None

    @classmethod
    def setUpClass(cls):
        """Set up neutron client."""
        super(NeutronTests, cls).setUpClass()
        keyston_session = openstack_utils.get_overcloud_keystone_session()
        cls.NEUTRON = openstack_utils.get_neutron_session_client(keyston_session)

    def tearDown(self):
        """Cleanup loadbalancers if there are any left over."""
        super(NeutronTests, self).tearDown()
        load_balancers = self.NEUTRON.list_loadbalancers().get('loadbalancers', [])
        for lbaas in load_balancers:
            self.NEUTRON.delete_loadbalancer(lbaas['id'])

    def test_single_unit(self):
        """Test that shutdown of a single unit returns OK."""
        units = ['neutron-gateway/0']
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)
        result = verifier.verify(self.CHECK)
        logger.info("result: %s", result)

        self.assertTrue(result.success)

    def test_redundancy_fail(self):
        """Test that stopping all neutron gateway returns failure."""
        units = ['neutron-gateway/0', 'neutron-gateway/1']
        unit_objects = loop.run(juju_verify.find_units(self.model, units))
        verifier = get_verifier(unit_objects)

        # expected router redundancy error
        routers = self.NEUTRON.list_routers().get('routers', [])
        router_list = ", ".join({router['id'] for router in routers})
        router_message = 'The following routers are non-redundant: {}'.format(
            router_list)
        router_error = Partial(Severity.FAIL, router_message)

        # expected network redundancy error
        networks = self.NEUTRON.list_networks().get('networks', [])
        network_list = ', '.join({network['id'] for network in networks})
        network_message = 'The following DHCP networks are non-redundant: {}'.format(
            network_list)
        network_error = Partial(Severity.FAIL, network_message)

        # run verifier
        result = verifier.verify(self.CHECK)
        logger.info("result: %s", result)

        self.assertFalse(result.success)
        self.assertIn(router_error, result.partials)
        self.assertIn(network_error, result.partials)

    def test_lbaas_warning(self):
        """Test that juju-verify reports if loadbalancers are present on target units."""
        lbaas_name = 'test_lbaas'

        # create LBaasV2 loadbalancer
        subnet_list = self.NEUTRON.list_subnets(name='private_subnet').get('subnets', [])

        if not subnet_list:
            raise RuntimeError('Expected subnet "private_subnet" not configured.')

        subnet = subnet_list[0]
        loadbalancer_data = {'loadbalancer': {'name': lbaas_name,
                                              'vip_subnet_id': subnet['id']}}
        self.NEUTRON.create_loadbalancer(body=loadbalancer_data)

        # store the loadbalancer's data
        lbaas_list = self.NEUTRON.list_loadbalancers(name=lbaas_name).get(
            'loadbalancers', [])
        lbaas = lbaas_list[0]

        # get nuetron-gateway unit hosting lbaas
        lbaas_agent = self.NEUTRON.get_lbaas_agent_hosting_loadbalancer(lbaas['id'])
        lbaas_host = lbaas_agent['agent']['host']
        juju_machine_id = lbaas_host.split('-')[-1]
        units = loop.run(juju_verify.find_units_on_machine(self.model,
                                                           [juju_machine_id]))

        # expected_result
        affected_untis = ", ".join([unit.entity_id for unit in units])
        message = "Following units have neutron LBaasV2 load-balancers that will be " \
                  "lost on unit shutdown: {}".format(affected_untis)
        expected_result = Partial(Severity.WARN, message)

        verifier = get_verifier(units)
        result = verifier.verify_shutdown()
        logger.info("result: %s", result)

        self.assertIn(expected_result, result.partials)
