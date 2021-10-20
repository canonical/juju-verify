Neutron-gateway verifier
========================

So far, the "reboot" and "shutdown" actions are supported and they both
perform the same set of checks.

* check router HA
* check LBaasV2 present
* check minimum Juju version
* check ceph-mon redundant routers
* check ceph-mon redundant DHCP


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


check router HA
---------------

.. todo:: add description `LP#1946027`_

If there are no routers, the check will provide the following result message.

::

  [OK] warn_router_ha check passed

Conversely, if a router is present that needs to be removed manually, the warning result
message should be as follows.

::

  [WARN] It's recommended that you manually failover the following routers: 22567d98-828e-4e7f-bdb2-2f1ea16fc979 (on neutron-gateway/0, hostname: juju-0c0b8f-openstack-0)


check LBaasV2 present
---------------------

.. todo:: add description `LP#1946027`_


If shutdown/restart the unit(s) causes the loss of the LBaasV2 loadbalancer, than the
following warning message will be present.

::

  [WARN] Following units have neutron LBaasV2 load-balancers that will be lost on unit shutdown/restart: neutron-gateway/0, neutron-gateway/1

Otherwise, only the successful result message.

::

  [OK] warn_lbaas_present check passed


check minimum Juju version
--------------------------

Ceph-mon verification relies on Juju features introduced in 2.8.10. If this minimum
version requirement is not met, the verification will stop and return ``Failed`` result
immediately. So it works as if the juju-verify was run with the ``--stop-on-failure``
flag.

Example of response when check failed, due to Juju client version 2.7.5:

::

  [FAIL] Juju agent on unit neutron-gateway/0 has lower than minimum required version. 2.7.5 < 2.8.10

on the contrary, if the client is met the minimum version:

::

  [OK] Minimum juju version check passed.


check ceph-mon redundant routers
--------------------------------

.. todo:: add description `LP#1946027`_

The check successful passed with the following result message.

::

  [OK] Redundancy check passed for: router-list

Otherwise, if there is a non-redundant router(s), then the result message will be
as follows with routers IDs separated with comma.

::

  [FAIL] The following routers are non-redundant: 22567d98-828e-4e7f-bdb2-2f1ea16fc979


check ceph-mon redundant DHCP
-----------------------------

.. todo:: add description `LP#1946027`_


The check successful passed with similar result message as previous check.

::

  [OK] Redundancy check passed for: dhcp-networks

Also the failed result message looks similar to the previous check.

::

  [FAIL] The following DHCP networks are non-redundant: 8b664fb1-df08-42ea-ba5d-63b513523628


.. _LP#1946027: https://bugs.launchpad.net/juju-verify/+bug/1946027
