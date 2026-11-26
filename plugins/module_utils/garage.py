# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) eyebrowkang
"""Pure logic for a Garage node: garage.toml, versions and the checks on the settings.

No Ansible imports: the filters wrap these functions, and the unit tests call them directly.
"""
from __future__ import annotations

import math
import re

# Keys of garage.toml that hold a secret, by table ('' is the top level). The node role
# writes each secret to a file of its own and sets the matching *_file key itself.
SECRET_KEYS = {
    "": ("rpc_secret", "rpc_secret_file"),
    "admin": ("admin_token", "admin_token_file", "metrics_token", "metrics_token_file"),
}

# Settings that need a newer Garage than the oldest the collection supports: (table, key)
# -> the first version that reads it. An older Garage ignores an unknown key silently.
MIN_VERSION_OF_SETTING = {
    ("s3_api", "public_endpoint"): "v2.5.0",
    ("s3_api", "public_endpoint_path_style"): "v2.5.0",
}

_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.]+))?")
_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


# ---- versions ----------------------------------------------------------------------------


def parse_version(text):
    """The version in `garage --version` output ("garage v2.6.0 [features: ...]"), as
    "v2.6.0" or "v3.0.0-beta1"; None when there is none."""
    match = _VERSION_RE.search(text or "")
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return "v%s.%s.%s%s" % (major, minor, patch, "-" + pre if pre else "")


def version_key(version):
    """A sortable key: a pre-release sorts before its release (v3.0.0-beta1 < v3.0.0)."""
    match = _VERSION_RE.fullmatch(version or "")
    if not match:
        raise ValueError("not a Garage version: %r" % (version,))
    major, minor, patch, pre = match.groups()
    pre_key = (1,) if pre is None else (0,) + tuple(_pre_part(p) for p in pre.split("."))
    return (int(major), int(minor), int(patch)) + pre_key


def _pre_part(part):
    # Numbers before words, numbers compared as numbers.
    return (0, int(part), "") if part.isdigit() else (1, 0, part)


def compare_versions(left, right):
    """-1, 0 or 1."""
    a, b = version_key(left), version_key(right)
    return (a > b) - (a < b)


def major(version):
    return version_key(version)[0]


def upgrade_kind(current, target):
    """What going from the installed version to the requested one is.

    'install' (nothing installed), 'none', 'minor', 'major', 'downgrade' or
    'skip-major' (more than one major version at once).
    """
    if current is None:
        return "install"
    order = compare_versions(current, target)
    if order == 0:
        return "none"
    if order > 0:
        return "downgrade"
    step = major(target) - major(current)
    if step == 0:
        return "minor"
    if step == 1:
        return "major"
    return "skip-major"


# ---- garage.toml -------------------------------------------------------------------------


class TomlError(ValueError):
    pass


def toml_dumps(data):
    """garage.toml from a dict: scalars first, then one [table] per nested dict.

    Lists of tables (data_dir) are written as arrays of inline tables. None is refused:
    a setting nobody sets is left out, not written empty.
    """
    if not isinstance(data, dict):
        raise TomlError("the settings must be a mapping, not %s" % type(data).__name__)
    lines = []
    _dump_table(data, [], lines)
    return "\n".join(lines).strip("\n") + "\n"


def _dump_table(table, path, lines):
    scalars = [(k, v) for k, v in table.items() if not isinstance(v, dict)]
    tables = [(k, v) for k, v in table.items() if isinstance(v, dict)]
    if path and (scalars or not tables):
        if lines:
            lines.append("")
        lines.append("[%s]" % ".".join(_key(p) for p in path))
    for key, value in scalars:
        lines.append("%s = %s" % (_key(key), _value(value, path + [key])))
    for key, value in tables:
        _dump_table(value, path + [key], lines)


def _key(key):
    if not isinstance(key, str):
        raise TomlError("keys must be strings, not %r" % (key,))
    return key if _BARE_KEY_RE.match(key) else _string(key)


def _value(value, path):
    where = ".".join(str(p) for p in path)
    if value is None:
        raise TomlError("%s is null: leave a setting out instead of setting it to null" % where)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise TomlError("%s is not a finite number" % where)
        return repr(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (list, tuple)):
        return "[%s]" % ", ".join(_value(item, path) for item in value)
    if isinstance(value, dict):
        return "{ %s }" % ", ".join(
            "%s = %s" % (_key(k), _value(v, path + [k])) for k, v in value.items()
        )
    raise TomlError("%s has a value of type %s, which TOML can't hold" % (where, type(value).__name__))


def _string(text):
    out = ['"']
    for char in text:
        code = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\t":
            out.append("\\t")
        elif char == "\r":
            out.append("\\r")
        elif code < 0x20 or code == 0x7F:
            out.append("\\u%04X" % code)
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


# ---- the node's settings -----------------------------------------------------------------


def data_dirs(settings):
    """The data directories' paths, whichever form data_dir takes."""
    value = settings.get("data_dir")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item["path"] if isinstance(item, dict) else item for item in value]
    return []


def node_paths(settings):
    """Every directory the node writes: metadata, data, and the snapshots' if apart."""
    paths = [settings.get("metadata_dir")] + data_dirs(settings)
    if settings.get("metadata_snapshots_dir"):
        paths.append(settings["metadata_snapshots_dir"])
    return [p for p in paths if p]


def settings_problems(settings, version):
    """What's wrong with the settings for this Garage version, as messages (empty: fine)."""
    if not isinstance(settings, dict):
        return ["garage_node_settings must be a mapping (garage.toml as YAML)."]
    problems = []

    for key in ("metadata_dir", "data_dir", "replication_factor", "rpc_bind_addr"):
        if key not in settings:
            problems.append("garage_node_settings.%s is required." % key)
    admin = settings.get("admin")
    if not isinstance(admin, dict) or "api_bind_addr" not in admin:
        problems.append(
            "garage_node_settings.admin.api_bind_addr is required: the role checks the"
            " node's health through it."
        )

    if "metadata_dir" in settings and not _absolute(settings["metadata_dir"]):
        problems.append("garage_node_settings.metadata_dir must be an absolute path.")
    problems.extend(_data_dir_problems(settings.get("data_dir")))

    factor = settings.get("replication_factor")
    if "replication_factor" in settings and (
        isinstance(factor, bool) or not isinstance(factor, int) or factor < 1
    ):
        problems.append("garage_node_settings.replication_factor must be a positive integer.")

    for table, keys in SECRET_KEYS.items():
        section = settings if table == "" else settings.get(table)
        if not isinstance(section, dict):
            continue
        for key in keys:
            if key in section:
                name = key if table == "" else "%s.%s" % (table, key)
                problems.append(
                    "garage_node_settings.%s is refused: secrets go in garage_node_rpc_secret,"
                    " garage_node_admin_token and garage_node_metrics_token, which the role"
                    " writes to files of their own." % name
                )

    if version:
        for (table, key), since in sorted(MIN_VERSION_OF_SETTING.items()):
            section = settings.get(table)
            if isinstance(section, dict) and key in section and compare_versions(version, since) < 0:
                problems.append(
                    "garage_node_settings.%s.%s needs Garage %s or later (garage_node_version is"
                    " %s): older releases silently ignore it." % (table, key, since, version)
                )
    return problems


def _absolute(path):
    return isinstance(path, str) and path.startswith("/")


def _data_dir_problems(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [] if _absolute(value) else ["garage_node_settings.data_dir must be an absolute path."]
    if isinstance(value, list) and value:
        problems = []
        for index, item in enumerate(value):
            path = item.get("path") if isinstance(item, dict) else None
            if not _absolute(path):
                problems.append(
                    "garage_node_settings.data_dir[%d] must be a table with an absolute path"
                    " (and a capacity, or read_only: true)." % index
                )
        return problems
    return ["garage_node_settings.data_dir must be a path or a list of tables with a path."]


def changed_identity_dirs(existing, settings):
    """The identity directories that differ from an existing garage.toml's ('metadata_dir',
    'data_dir'): changing them on a node with data would start an empty node."""
    changed = []
    if existing.get("metadata_dir") != settings.get("metadata_dir"):
        changed.append("metadata_dir")
    if sorted(data_dirs(existing)) != sorted(data_dirs(settings)):
        changed.append("data_dir")
    return changed
