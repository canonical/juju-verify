Neutron-gateway verifier
========================

So far, the "reboot" and "shutdown" actions are supported and they both
perform the same set of checks.

* check minimum Juju version
* check active HA router
* check LBaasV2 present
* check neutron-gateway redundant routers
* check neutron-gateway redundant DHCP


::

  $ juju-verify reboot --unit neutron-gateway/0
  Checks:
  [OK] check_affected_machines check passed
  [OK] check_has_sub_machines check passed
  [OK] Minimum juju version check passed.
  [OK] warn_router_ha check passed
  [OK] warn_lbaas_present check passed
  [OK] Redundancy check passed for: router-list
  [OK] Redundancy check passed for: dhcp-networks

  Overall result: OK (All checks passed)


check minimum Juju version
--------------------------

Neutron-gateway verification relies on Juju features introduced in 2.8.10. If this
minimum version requirement is not met, the verification will stop and return ``Failed``
result immediately. (same behavior as if juju-verify was run with the
``--stop-on-failure`` flag)

If the Juju version meets minimum expected version, this check will pass with:

::

  [OK] Minimum juju version check passed

If the minimum required version is not met and Juju is, for example, in version 2.7.5,
this check will fail with following message:

::

  [FAIL] Juju agent on unit neutron-gateway/0 has lower than minimum required version. 2.7.5 < 2.8.10


check active HA router
----------------------

In the case that ``neutron-gateway`` unit, that is being verified, hosts a
neutron router in HA mode, such router should be manually failed over to the
unit that is not going to be rebooted or shutdown. This is only a
recommendation and as such, generates only warning.

If the affected units do not host any routers, check will pass with the following
message.

::

  [OK] warn_router_ha check passed

If there are routers that should be failed over to other active
``neutron-gateway`` units, the following warning is displayed, listing router IDs
of affected neutron routers.

::

  [WARN] It's recommended that you manually failover the following routers: 22567d98-828e-4e7f-bdb2-2f1ea16fc979 (on neutron-gateway/0, hostname: juju-0c0b8f-openstack-0)


check LBaasV2 present
---------------------

LBaasV2 loadbalancer is HA technology that stopped being supported in Openstack
``Train`` and was replaced with project ``Octavia``. However since there are still
supported Openstack releases that have this feature, Juju-verify will show
warning if LBaasv2 is configured on the ``neutron-gateway`` unit that is being
rebooted or shutdown.

::

  [WARN] Following units have neutron LBaasV2 load-balancers that will be lost on unit reboot/shutdown: neutron-gateway/0, neutron-gateway/1

If there are no LbaasV2 services configured on the unit, check will pass with
the following message.

::

  [OK] warn_lbaas_present check passed


check neutron-gateway redundant routers
---------------------------------------

This check verifies that routers present on ``neutron-gateway`` unit, are in
HA mode and can be offloaded to a unit that is not being rebooted or shutdown.

If there above condition is true, the check will pass with the following
message:

::

  [OK] Redundancy check passed for: router-list

Otherwise, if there are non-redundant routers, the result message will show the
following message with the list of non-redundant routers IDs separated with comma.

::

  [FAIL] The following routers are non-redundant: 22567d98-828e-4e7f-bdb2-2f1ea16fc979


check neutron-gateway redundant DHCP
------------------------------------

This check verifies that DHCP agents present on ``neutron-gateway`` unit, are in
HA mode and can be offloaded to a unit that is not being rebooted or shutdown.

If there above condition is true, the check will pass with the following
message:

::

  [OK] Redundancy check passed for: dhcp-networks

Otherwise, if there are non-redundant DHCP agents, the result message will
show the following message with the list of non-redundant agent IDs separated with
commas.

::

  [FAIL] The following DHCP networks are non-redundant: 8b664fb1-df08-42ea-ba5d-63b513523628
