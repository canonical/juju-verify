# Juju verify

This CLI tool is a Juju plugin that allows user to check whether it's safe
to perform some disruptive maintenance operations on Juju units, like `shutdown`
or `reboot`.

## Requirements

Juju-verify requires Juju 2.8.10 or higher.

## Supported charms

* nova-compute
* ceph-osd
* ceph-mon
* neutron-gateway

## Supported checks

* reboot
* shutdown

## Contribution and lifecycle

For more information on how to contribute and the lifecycle of ``juju-verify`` tools,
visit [CONTRIBUTING] page.

## Usage example

To verify that it is safe to stop/shutdown units `nova-compute/0` and
`nova-compute/1` without affecting the rest of the OpenStack cloud environment,
run the following.

```bash
$ juju-verify shutdown --units nova-compute/0 nova-compute/1
$ juju verify shutdown -u nova-compute/ nova-compute/1
```

To verify that it is safe to reboot all principal units from a Juju machine, run the following.

```bash
$ juju-verify reboot --machines 6
$ juju verify reboot -M 6
```

For more information, visit the [juju-verify-getting-started] page.

## Known limitations

1. argparse limitation with `nargs="+"` type of arguments. The core Juju client allows
   commands after options (e.g. `juju --run unit/0 ls`). ``juju-verify`` needs to pass the
   type of check (`reboot`, `shutdown`) at the beginning of the command, otherwise it will
   be parsed as a unit (or machine). `juju-verify -u unit/0 reboot` will fail.
   `juju-verify reboot -u unit/0` will succeed.

2. If you run a check on a unit which contains a subordinate unit, you will only get
   a warning message about the existence of the subordinate unit. In order to check if
   it is safe to reboot/shutdown this unit, juju-verify needs to be explicitly run
   against this subordinate unit, or the unit needs to be manually checked (if
   juju-verify does not support this charm yet)

   Example:
   ```bash
   $ juju-verify shutdown --units ceph-osd/0
   ===[ceph-osd/0]===
   Checks:
   [WARN] ceph-osd/0 has units running on child machines: ceph-mon/0*
   [OK] ceph-mon/0: Ceph cluster is healthy
   [OK] Minimum replica number check passed.
   [OK] Availability zone check passed.

   Result: OK (Checks passed with warnings)
   ```

## How to contribute

Is your favorite charm missing from the list of supported charm? Don't hesitate
to add it. This plugin is easily extensible.

All you need to do is create new class in `juju_verify.verifiers` package that
inherits from `juju_verify.verifiers.BaseVerifier` (see the class documentation for
more details) and implement the necessary logic.

Then, the charm name needs to be added to `SUPPORTED_CHARMS` dictionary in
`juju_verify/verifiers/__init__.py` *et voilà*, the charm is now supported.

### Testing

Don't forget to add unit and functional tests.

#### Unittests

Unit tests can be executed in these ways:

```bash
make unittest
# or
tox -e unit
```
However, it is recommended to run unit tests at the same time as lint tests as follows:

```bash
make tests
# or
tox
```

#### Functional tests

Functional tests can be run using:

```bash
make functional
# or
tox -e func
```

Functional tests require some applications to use a VIP. Please ensure the `OS_VIP00`
environment variable is set to a suitable VIP address before running functional tests.

During development, different variations of all the functional tests may be run.
Find some examples below:

1. `tox -e func` runs all bundles and does not keep any Juju model
2. `tox -e func -- --keep-faulty-model` runs all bundles and keeps the Juju models that
                                        failed
3. `tox -e func -- --keep-all-models --log DEBUG` runs all bundles w/ logging in debug
                                                  mode and keeping all the Juju models
4. `tox -e func-target -- ceph` runs only the Ceph bundle and not keep the Juju model
5. `tox -e func-target -- ceph --keep-model --log DEBUG` runs only the Ceph bundle w/
                                                         logging in debug mode and keep
                                                         the Juju model

## Code decisions

The main idea of `juju-verify` is to be used as a CLI tool with an entry point defined
in `juju verify/juju verify.py`. We use the `argparse` library to parse CLI arguments
and to provide help information, which can be accessed using `juju-verify --help`
command.

Despite the main purpose, it is possible to use `juju-verify` as python package. It
can be installed directly from [pypi.org].

### Verifiers

The basic structure of the verifier is defined in the `/juju_verify/verifiers/base.py`
file as the `BaseVerifier` class. Every other verifier must inherit from this class,
with the following variable and functions having to be overrided.

* `NAME` - name of verifier
* `verify_<action-with-unit>` - function to run all necessary checks when trying to
	                          perform "action" with the unit

Each verifier will contain these two variables:

* units - list of units we want to verify
* model - corresponding model containing units

The verifier should run a verification using the `verify` function, which will check
if the verification is supported and adds these pre-checks:

* check_affected_machines - Check if affected machines run other principal units.
* check_has_sub_machines - Check if the machine hosts containers or VMs.

For more information about the verifier, see [juju-verify-verifiers] page.

**NOTE**: There is a list of supported verifiers that corresponded to the list of
[supported charms](#supported-charms).

### Checks

The recommended way is to divide a unit check into several smaller checks with
self-explanatory names and a good docstring. Than all sub-checks should be run with
`checks_executor`, which aggregates the results from each check or provide default
result. It also catches any of the following errors `JujuActionFailed`,
`CharmException`, `KeyError` or `JSONDecodeError`, giving a FAIL result with a message
in the form "{check.__name__} check failed with error: {error}".

### Results

A `Result` is a class object that represents the output of any check that can be
aggregated together with other results. Each result consists of one or more sub-results
represented as a `Partial` class, the partial result consists of severity and meesage.

There are currently 4 severity tips:

* OK - representing a successful check
* WARN - the result ended successfully, but there was a possibility that may have
         an unexpected impact on the result
* UNSUPPORTED - result of check is not supported
* FAIL - check failed

The final result is successful if no partial result ends other than with the OK or
WARN severity. The string representation of results is an aggregation of partial
results, which are represented as severiny name and message.

In the following example, we can see four checks, one ending with a severity WARN
and three ending with a severity OK, but the overall result is OK.

```bash
$ juju-verify shutdown --unit ceph-osd/0
===[ceph-osd/0]===
Checks:
[WARN] ceph-osd/0 has units running on child machines: ceph-mon/0*
[OK] ceph-mon/0: Ceph cluster is healthy
[OK] Minimum replica number check passed.
[OK] Availability zone check passed.

Result: OK (Checks passed with warnings)
```

## Submit a bug

If you prefer, file a bug or feature request at:

* https://bugs.launchpad.net/juju-verify


---
[pypi.org]: https://pypi.org/
[juju-verify-getting-started]: https://juju-verify.readthedocs.io/en/latest/getting-started.html
[juju-verify-verifiers]: https://juju-verify.readthedocs.io/en/latest/verifiers.html
[CONTRIBUTING]: https://juju-verify.readthedocs.io/en/latest/contributing.html
