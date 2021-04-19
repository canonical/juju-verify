# Juju verify

This CLI tool is a Juju plugin that allows user to check whether it's safe
to perform some disruptive maintenance operations on Juju units, like `shutdown`
or `reboot`.

## Supported charms

* nova-compute (WIP) (Usable with [this nova-compute charm](https://jaas.ai/u/martin-kalcok/nova-compute/0))
* ceph-osd (WIP)
* neutron-gateway (WIP)

## Supported checks

* reboot
* shutdown

**NOTE:** Final list of supported checks and what they represent is still WIP

## Usage example

To verify that it is safe to stop/shutdown units `nova-compute/0` and
`nova-compute/1` without affecting the rest of the OpenStack cloud environment,
run the following.

```bash
$ juju-verify shutdown --units nova-compute/0 nova-compute/1
```

**NOTE:** If you run check on multiple units at the same time, they must all run
the same charm. Trying, for example, `juju-verify shutdown --units nova-compute/1
ceph-osd/0` will result in error.

Alternatively, a machine can be targeted:

```bash
$ juju-verify shutdown --machines 0
```

## How to contribute

Is your favorite charm missing from the list of supported charm? Don't hesitate
to add it. This plugin is easily extensible.

All you need to do is create new class in `juju_verify.verifiers` package that
inherits from `juju_verify.verifiers.BaseVerifier` (see the class documentation for
more details) and implement the necessary logic.

Then, the charm name needs to be added to `SUPPORTED_CHARMS` dictionary in
`juju_verify/verifiers/__init__.py` *et voilà*, the charm is now supported.

Don't forget to add unit and functional tests, and run:

```bash
make test
```

Functional tests require some applications to use a VIP. Please ensure the `OS_VIP00`
environment variable is set to a suitable VIP address before running functional tests.

## Submit a bug

If you prefer, file a bug or feature request at:

* https://bugs.launchpad.net/juju-verify
