# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) eyebrowkang
from __future__ import annotations

DOCUMENTATION = r"""
name: garage
short_description: Filters for a Garage node's configuration and versions
description:
  - C(to_toml) writes a mapping as C(garage.toml).
  - C(from_toml) reads C(garage.toml) into a mapping.
  - C(garage_version) is the version in C(garage --version) output, such as C(v2.6.0).
  - C(garage_compare_versions) compares two versions - -1, 0 or 1.
  - C(garage_upgrade_kind) is what going from one version to another is - C(install), C(none),
    C(minor), C(major), C(downgrade) or C(skip-major).
  - C(garage_settings_problems) lists what's wrong with C(garage_node_settings) for a version.
  - C(garage_node_paths) lists the directories a node writes.
  - C(garage_changed_identity_dirs) lists the identity directories that differ from an
    existing C(garage.toml).
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


def garage_version(text):
    return garage.parse_version(str(text) if text is not None else "")


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


def garage_changed_identity_dirs(existing, settings):
    return garage.changed_identity_dirs(_plain(existing), _plain(settings))


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
            "garage_changed_identity_dirs": garage_changed_identity_dirs,
        }
