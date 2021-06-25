Verifier design and architecture
================================

This section describes in detail the concept of each verifier and shows each check
used in individual actions. At the same time, you will find here the individual steps
for each check.

All checks of the action are performed in sequence and their results are aggregated
into one. For the result to be successful, all checks must be successful.

.. toctree::
   :caption: List of supported verifiers:

   verifiers/ceph-mon
   verifiers/ceph-osd


If you find that a check does not take into account all possible circumstances or its
assumption is wrong, do not hesitate to `report a bug`_.

.. _report a bug: https://bugs.launchpad.net/juju-verify
