# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) eyebrowkang
from __future__ import annotations

DOCUMENTATION = r"""
name: garage
short_description: Filters for a Garage node's configuration and versions
description:
  - C(to_toml) writes a mapping as C(garage.toml).
  - C(from_toml) reads C(garage.toml) into a mapping.
  - C(garage_version) is the version in C(garage --version) output, such as C(v2.6.0); a
    pre-release that reports its commit is named by the mapping given (version to commit).
  - C(garage_compare_versions) compares two versions - -1, 0 or 1.
  - C(garage_upgrade_kind) is what going from one version to another is - C(install), C(none),
    C(minor), C(major), C(downgrade) or C(skip-major).
  - C(garage_settings_problems) lists what's wrong with C(garage_node_settings) for a version.
  - C(garage_node_paths) lists the directories a node writes.
  - C(garage_changed_identity) lists what of a node's identity (C(metadata_dir),
    C(data_dir), C(db_engine)) differs from an existing C(garage.toml).
  - C(garage_node_id) is the node ID in C(garage node id -q) output.
  - C(garage_node_address) is the RPC address a node reports for itself in C(GetClusterStatus).
  - C(garage_nodes_to_connect) lists the C(<id>@<addr>) of the wanted nodes a status doesn't see up.
  - C(garage_nodes_not_up) lists the wanted node IDs a status doesn't see up.
  - C(garage_layout_roles) is the C(UpdateClusterLayout) request for the first layout.
  - C(garage_role_problems) lists what's wrong with a node's layout role.
  - C(garage_peer_list_count) is how many peers a node's saved peer list holds, from its
    base64 content (slurp).
  - C(garage_health_regressions) lists how a C(GetClusterHealth) result is worse than an earlier one.
options:
  _input:
    description: The mapping, the text, or the version the filter works on.
    type: raw
    required: true
author:
  - "eyebrowkang (@eyebrowkang)"
"""

EXAMPLES = r"""
- name: The configuration file's content
  ansible.builtin.debug:
    msg: "{{ garage_node_settings | eyebrowkang.garage.to_toml }}"
"""

RETURN = r"""
_value:
  description: The text, the mapping, the version or the list, depending on the filter.
  type: raw
"""

import base64
import tomllib

from ansible.errors import AnsibleFilterError
from ansible_collections.eyebrowkang.garage.plugins.module_utils import garage


def _plain(value):
    # Ansible hands over its own str/dict/list subclasses; TOML only knows the plain ones.
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, str):
        return str(value)
    return value


def to_toml(data):
    try:
        return garage.toml_dumps(_plain(data))
    except garage.TomlError as error:
        raise AnsibleFilterError("garage_node_settings: %s" % error) from error


def from_toml(text):
    try:
        return tomllib.loads(str(text))
    except tomllib.TOMLDecodeError as error:
        raise AnsibleFilterError("not valid TOML: %s" % error) from error


def garage_version(text, prereleases=None):
    return garage.parse_version(str(text) if text is not None else "", _plain(prereleases or {}))


def garage_compare_versions(left, right):
    try:
        return garage.compare_versions(str(left), str(right))
    except ValueError as error:
        raise AnsibleFilterError(str(error)) from error


def garage_upgrade_kind(current, target):
    try:
        return garage.upgrade_kind(current or None, str(target))
    except ValueError as error:
        raise AnsibleFilterError(str(error)) from error


def garage_settings_problems(settings, version=None):
    return garage.settings_problems(_plain(settings), str(version) if version else None)


def garage_node_paths(settings):
    return garage.node_paths(_plain(settings))


def garage_changed_identity(existing, settings):
    return garage.changed_identity(_plain(existing), _plain(settings))


def garage_node_id(text):
    return garage.node_id(str(text) if text is not None else "")


def garage_node_address(status, node):
    return garage.node_address(_plain(status), str(node))


def garage_nodes_to_connect(status, wanted):
    return garage.nodes_to_connect(_plain(status), _plain(wanted))


def garage_nodes_not_up(status, wanted):
    return garage.nodes_not_up(_plain(status), _plain(wanted))


def garage_layout_roles(nodes):
    try:
        return garage.layout_roles(_plain(nodes))
    except ValueError as error:
        raise AnsibleFilterError(str(error)) from error


def garage_role_problems(zone, capacity, gateway, tags):
    return garage.role_problems(_plain(zone), _plain(capacity), bool(gateway), _plain(tags))


def garage_health_regressions(health, floor):
    return garage.health_regressions(_plain(health), _plain(floor or {}))


def garage_peer_list_count(content):
    try:
        return garage.peer_list_count(base64.b64decode(str(content or "")))
    except ValueError as error:
        raise AnsibleFilterError(str(error)) from error


class FilterModule:
    """Filters for a Garage node."""

    def filters(self):
        return {
            "to_toml": to_toml,
            "from_toml": from_toml,
            "garage_version": garage_version,
            "garage_compare_versions": garage_compare_versions,
            "garage_upgrade_kind": garage_upgrade_kind,
            "garage_settings_problems": garage_settings_problems,
            "garage_node_paths": garage_node_paths,
            "garage_changed_identity": garage_changed_identity,
            "garage_node_id": garage_node_id,
            "garage_node_address": garage_node_address,
            "garage_nodes_to_connect": garage_nodes_to_connect,
            "garage_nodes_not_up": garage_nodes_not_up,
            "garage_layout_roles": garage_layout_roles,
            "garage_role_problems": garage_role_problems,
            "garage_health_regressions": garage_health_regressions,
            "garage_peer_list_count": garage_peer_list_count,
        }
