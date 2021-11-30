Nova-compute verifier
=====================

So far, the "reboot" and "shutdown" actions are supported and they both
perform the same set of checks.

* check running VMs
* check availability zones

::

  $ juju-verify reboot --unit nova-compute/0
  ===[nova-compute/0]===
  Checks:
  [OK] check_affected_machines check passed
  [OK] check_has_sub_machines check passed
  [OK] Unit nova-compute/0 is running 0 VMs.
  [OK] Empty Availability Zone check passed.

  Result: OK (All checks passed)


check running VMs
-----------------

This simple check verifies that the unit(s) about to be reboot/shutdown do not host
any virtual machines. In this case, the following result message will be present.

::

  [OK] Unit nova-compute/0 is running 0 VMs.

If the VMs are present, the verifier will fail and user
has to manually migrate those VMs away from the unit(s) intended for
reboot/shutdown. The failure result message is basically the same as in the previous
case.

::

  [FAIL] Unit nova-compute/0 is running 2 VMs.


check availability zones
------------------------

This check verifies that after reboot/shutdown of selected nova-compute units,
availability zones to which these units belong wont be left empty. This is what the
result message looks like after a successful check.

::

  [OK] Empty Availability Zone check passed.

If availability zone remains empty after reboot/shutdown unit(s), the result message
will be as follows.

::

  [FAIL] Removing these units would leave following availability zones empty: {'nova'}


This check takes into consideration only availability zones that are affected by the
unit reboot/shutdown, there may be other empty availability zones within the
cluster.
