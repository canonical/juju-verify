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
"""Configuration scripts for juju models related to ceph-osd and ceph-mon charm."""
import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional

import zaza
import zaza.model as model
from juju.model import Model

from juju_verify.utils.unit import find_unit_by_hostname

logger = logging.getLogger(__name__)


def _get_osd_map() -> Dict[str, List[str]]:
    """Get map between ceph-osd unit and osd."""
    juju_model = zaza.sync_wrapper(model.get_model)()
    action = model.run_action_on_leader(
        "ceph-mon", "show-disk-free", action_params={"format": "json"}
    )
    ceph_tree_json = action.data.get("results", {}).get("message")
    ceph_tree = {node["id"]: node for node in json.loads(ceph_tree_json)["nodes"]}

    osd_map = defaultdict(list)
    for node in ceph_tree.values():
        if node["type"] == "host":
            unit = find_unit_by_hostname(juju_model, node["name"], "ceph-osd")
            for child in node.get("children", []):
                logger.debug("found osd `%s` for unit `%s`", child, unit)
                osd_map[unit.entity_id].append(ceph_tree[child]["name"])

    zaza.sync_wrapper(juju_model.disconnect)()
    return osd_map


def _set_osd_device_class(osds: List[str], device_class: str):
    """Set device class for osds."""
    osds = " ".join(osds)
    # remove old device-class for osds
    model.run_on_unit(
        "ceph-mon/0",
        f"ceph --id admin osd crush rm-device-class {osds}",
        timeout=2 * 60,
    )
    # set new device-class for osds
    model.run_on_unit(
        "ceph-mon/0",
        f"ceph --id admin osd crush set-device-class {device_class} {osds}",
        timeout=2 * 60,
    )
    logger.info("Set device-class `%s` for osds %s", device_class, osds)


def set_up_devices_class():
    """Configure osd device classes."""
    osd_map = _get_osd_map()
    for device_class in ["hdd", "ssd", "nvme"]:
        try:
            units = model.get_units(f"ceph-osd-{device_class}")
        except KeyError:
            logger.info("application ceph-osd-%s was not found", device_class)
        else:
            logger.info(
                "start units %s configuration",
                " ".join(unit.entity_id for unit in units),
            )
            for unit in units:
                _set_osd_device_class(osd_map[unit.entity_id], device_class)


def _create_replication_rule(
    name: str,
    failure_domain: Optional[str] = None,
    device_class: Optional[str] = None,
):
    """Create replication rule."""
    crush_rule_info = {
        "name": name,
        "failure-domain": failure_domain,
        "device-class": device_class,
    }
    _ = zaza.model.run_action(
        "ceph-mon/0",
        "create-crush-rule",
        action_params={
            param: value for param, value in crush_rule_info.items() if value
        },
    )
    logger.info(
        "Create crush rule `%s` with failure-domain=%s and device-class=%s",
        name,
        failure_domain,
        device_class,
    )


def create_replication_rules():
    """Create replication rules."""
    crush_rules = [
        ("hdd", None, "hdd"),
        ("ssd", None, "ssd"),
        ("hdd-host", "host", "hdd"),
        ("ssd-host", "host", "ssd"),
        ("hdd-rack", "rack", "hdd"),
        ("ssd-rack", "rack", "ssd"),
    ]
    for name, failure_domain, device_class in crush_rules:
        _create_replication_rule(name, failure_domain, device_class)
