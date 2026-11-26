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


def parse_version(text, prereleases=None):
    """The version in `garage --version` output ("garage v2.6.0 [features: ...]"), as
    "v2.6.0" or "v3.0.0-beta1"; None when there is none.

    A pre-release built from a commit reports the commit instead of a version:
    prereleases ({version: commit}) names it.
    """
    match = _VERSION_RE.search(text or "")
    if match:
        major_, minor, patch, pre = match.groups()
        return "v%s.%s.%s%s" % (major_, minor, patch, "-" + pre if pre else "")
    commits = {commit: version for version, commit in (prereleases or {}).items()}
    for word in re.findall(r"\b[0-9a-f]{40}\b", text or ""):
        if word in commits:
            return commits[word]
    return None


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


def changed_identity(existing, settings):
    """What of a node's identity and data differs from an existing garage.toml:
    'metadata_dir', 'data_dir', 'db_engine'. Changing them on a node with data would start
    an empty node (a new metadata database needs `garage node convert-db` first)."""
    changed = []
    if existing.get("metadata_dir") != settings.get("metadata_dir"):
        changed.append("metadata_dir")
    if sorted(data_dirs(existing)) != sorted(data_dirs(settings)):
        changed.append("data_dir")
    # Garage's default engine is lmdb.
    if existing.get("db_engine", "lmdb") != settings.get("db_engine", "lmdb"):
        changed.append("db_engine")
    return changed


# ---- the cluster ---------------------------------------------------------------------------

# bytesize's units, as Garage's CLI reads a capacity: decimal, or binary with "i"; any case;
# "b" alone is bytes.
_CAPACITY_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?)(i?)(b?)\s*$", re.IGNORECASE)
_CAPACITY_POWER = {"": 0, "k": 1, "m": 2, "g": 3, "t": 4, "p": 5}


def parse_capacity(value):
    """A layout capacity in bytes: an integer, or a size such as "1T", "500GB", "1.5TiB"."""
    if isinstance(value, bool):
        raise ValueError("a capacity is a size, not %r" % (value,))
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("a capacity must be positive, not %d" % value)
        return value
    match = _CAPACITY_RE.match(str(value))
    if not match:
        raise ValueError("%r is not a size such as 1T, 500G or 1.5TiB" % (value,))
    number, prefix, binary, _bytes = match.groups()
    if binary and not prefix:
        raise ValueError("%r is not a size such as 1T, 500G or 1.5TiB" % (value,))
    base = 1024 if binary else 1000
    size = int(float(number) * base ** _CAPACITY_POWER[prefix.lower()])
    if size <= 0:
        raise ValueError("a capacity must be positive, not %r" % (value,))
    return size


def node_id(text):
    """The full node ID in `garage node id -q` output ("<64 hex>[@<addr>]")."""
    match = re.search(r"\b([0-9a-f]{64})\b", text or "")
    return match.group(1) if match else None


def node_address(status, node):
    """The RPC address a node reports for itself in GetClusterStatus, or None."""
    for entry in status.get("nodes", []):
        if entry.get("id") == node:
            return entry.get("addr")
    return None


def nodes_to_connect(status, wanted):
    """The "<id>@<addr>" of the wanted nodes ({id: addr}) this node doesn't see up."""
    up = {entry.get("id") for entry in status.get("nodes", []) if entry.get("isUp")}
    return ["%s@%s" % (node, addr) for node, addr in sorted(wanted.items()) if node not in up]


def nodes_not_up(status, wanted):
    """The wanted node IDs this node doesn't see up."""
    up = {entry.get("id") for entry in status.get("nodes", []) if entry.get("isUp")}
    return sorted(node for node in wanted if node not in up)


def layout_roles(nodes):
    """The UpdateClusterLayout roles for the first layout.

    nodes: [{id, zone, capacity, gateway, tags}] - a gateway has no capacity.
    """
    roles = []
    for node in nodes:
        roles.append({
            "id": node["id"],
            "zone": node["zone"],
            "capacity": None if node.get("gateway") else parse_capacity(node["capacity"]),
            "tags": list(node.get("tags") or []),
        })
    return {"roles": sorted(roles, key=lambda role: role["id"])}


def role_problems(zone, capacity, gateway, tags):
    """What's wrong with a node's layout role, as messages (empty: fine)."""
    problems = []
    if not isinstance(zone, str) or not zone:
        problems.append("garage_cluster_zone is required: the zone of this node's layout role.")
    has_capacity = capacity not in (None, "")
    if bool(gateway) == has_capacity:
        problems.append(
            "Set either garage_cluster_capacity (a storage node) or garage_cluster_gateway:"
            " true (a gateway node), not both and not neither."
        )
    elif has_capacity:
        try:
            parse_capacity(capacity)
        except ValueError as error:
            problems.append("garage_cluster_capacity: %s." % error)
    if not isinstance(tags, (list, tuple)) or not all(isinstance(t, str) and t for t in tags):
        problems.append("garage_cluster_tags must be a list of non-empty strings.")
    return problems


def health_regressions(health, floor):
    """How a GetClusterHealth result is worse than an earlier one (the floor), as messages
    (empty: at least as healthy). An empty floor asks only for an answer."""
    regressions = []
    for key, what in (("connectedNodes", "connected nodes"), ("storageNodesUp", "storage nodes up")):
        if key in floor and health.get(key, 0) < floor[key]:
            regressions.append("%d %s, %d before" % (health.get(key, 0), what, floor[key]))
    if floor.get("status") == "healthy" and health.get("status") != "healthy":
        regressions.append("the cluster is %s, it was healthy" % health.get("status"))
    return regressions


def peer_list_count(data):
    """How many peers a node's saved peer list (metadata_dir/peer_list) holds.

    Garage saves it as a MessagePack array of (node ID, address), every minute: a node
    restarted before its peers are saved doesn't find them again.
    """
    if not data:
        return 0
    head = data[0]
    if 0x90 <= head <= 0x9F:
        return head & 0x0F
    if head == 0xDC and len(data) >= 3:
        return int.from_bytes(data[1:3], "big")
    if head == 0xDD and len(data) >= 5:
        return int.from_bytes(data[1:5], "big")
    raise ValueError("not a saved peer list (first byte 0x%02x)" % head)
