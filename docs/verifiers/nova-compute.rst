Nova-compute verifier
=====================

So far, the "reboot" and "shutdown" actions are supported and they both
perform the same set of checks.

* check running VMs
* check availability zones


check running VMs
-----------------

This simple check verifies that the unit(s) about to be shut down do not host
any virtual machines. If the VMs are present, the verifier will fail and user
has to manually migrate those VMs away from the unit(s) intended for
shutdown/reboot.

check availability zones
------------------------

This check verifies that after shutdown/restart of selected nova-compute units,
availability zones to which these units belong wont be left empty. This check
takes into consideration only availability zones that are affected by the unit
shutdown/restart, there may be other empty availability zones within the
cluster.
