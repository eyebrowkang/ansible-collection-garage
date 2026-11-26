# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) eyebrowkang
from __future__ import annotations

import pytest

# The round trips read garage.toml back with tomllib (Python 3.11+); the filter that uses
# these functions runs on the controller, where ansible-core's Python always has it.
tomllib = pytest.importorskip("tomllib")

from ansible_collections.eyebrowkang.garage.plugins.module_utils import garage


# ---- versions ----------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("garage v2.6.0 [features: bundled-libs, k2v, lmdb, webadmin]", "v2.6.0"),
    ("garage v2.1.0 [features: k2v, lmdb, sqlite]", "v2.1.0"),
    ("garage v3.0.0-beta1 [features: lmdb]", "v3.0.0-beta1"),
    ("", None),
    ("command not found", None),
])
def test_parse_version(text, expected):
    assert garage.parse_version(text) == expected


@pytest.mark.parametrize("left, right, expected", [
    ("v2.6.0", "v2.6.0", 0),
    ("v2.5.0", "v2.6.0", -1),
    ("v2.10.0", "v2.9.1", 1),
    ("v3.0.0-beta1", "v3.0.0", -1),
    ("v3.0.0-beta1", "v3.0.0-beta2", -1),
    ("v3.0.0-beta2", "v3.0.0-rc1", -1),
    ("v3.0.0-beta.10", "v3.0.0-beta.9", 1),
    ("v2.6.0", "v3.0.0-beta1", -1),
])
def test_compare_versions(left, right, expected):
    assert garage.compare_versions(left, right) == expected


def test_version_key_refuses_garbage():
    with pytest.raises(ValueError):
        garage.version_key("2.6")


@pytest.mark.parametrize("current, target, expected", [
    (None, "v2.6.0", "install"),
    ("v2.6.0", "v2.6.0", "none"),
    ("v2.3.0", "v2.6.0", "minor"),
    ("v2.6.0", "v3.0.0", "major"),
    ("v2.6.0", "v3.0.0-beta1", "major"),
    ("v3.0.0-beta1", "v3.0.0", "minor"),
    ("v2.6.0", "v2.5.0", "downgrade"),
    ("v3.0.0", "v2.6.0", "downgrade"),
    ("v1.3.1", "v3.0.0", "skip-major"),
])
def test_upgrade_kind(current, target, expected):
    assert garage.upgrade_kind(current, target) == expected


# ---- garage.toml -------------------------------------------------------------------------

SETTINGS = {
    "metadata_dir": "/var/lib/garage/meta",
    "data_dir": "/var/lib/garage/data",
    "db_engine": "lmdb",
    "replication_factor": 3,
    "rpc_bind_addr": "[::]:3901",
    "s3_api": {"api_bind_addr": "[::]:3900", "s3_region": "garage"},
    "admin": {"api_bind_addr": "[::]:3903"},
}


def test_toml_round_trips():
    assert tomllib.loads(garage.toml_dumps(SETTINGS)) == SETTINGS


def test_toml_writes_scalars_before_tables():
    text = garage.toml_dumps({"s3_api": {"s3_region": "garage"}, "replication_factor": 1})
    assert text == 'replication_factor = 1\n\n[s3_api]\ns3_region = "garage"\n'


def test_toml_writes_data_dir_tables_inline():
    data = {"data_dir": [
        {"path": "/mnt/a", "capacity": "2T"},
        {"path": "/mnt/b", "read_only": True},
    ]}
    text = garage.toml_dumps(data)
    assert 'data_dir = [{ path = "/mnt/a", capacity = "2T" }, { path = "/mnt/b", read_only = true }]' in text
    assert tomllib.loads(text) == data


@pytest.mark.parametrize("value", [
    'quote " backslash \\ newline \n tab \t',
    "control \x01 \x7f",
    "unicode ü 漢字",
])
def test_toml_escapes_strings(value):
    assert tomllib.loads(garage.toml_dumps({"k": value})) == {"k": value}


def test_toml_quotes_keys_that_arent_bare():
    data = {"a key": 1, "table": {"dotted.key": "x"}}
    assert tomllib.loads(garage.toml_dumps(data)) == data


def test_toml_nested_tables():
    data = {"consul_discovery": {"api": "agent", "meta": {"zone": "dc1"}}}
    assert tomllib.loads(garage.toml_dumps(data)) == data


def test_toml_scalar_types():
    data = {"i": 0, "f": 1.5, "b": False, "l": [1, 2], "e": []}
    assert tomllib.loads(garage.toml_dumps(data)) == data


@pytest.mark.parametrize("data", [{"k": None}, {"k": float("nan")}, {"k": object()}, {1: "x"}, []])
def test_toml_refuses(data):
    with pytest.raises(garage.TomlError):
        garage.toml_dumps(data)


# ---- the node's settings -----------------------------------------------------------------

def test_settings_fine():
    assert garage.settings_problems(SETTINGS, "v2.6.0") == []


def test_settings_require_the_basics():
    problems = garage.settings_problems({}, "v2.6.0")
    for key in ("metadata_dir", "data_dir", "replication_factor", "rpc_bind_addr"):
        assert any("garage_node_settings.%s is required" % key in p for p in problems), key


def test_settings_not_a_mapping():
    assert garage.settings_problems("x", "v2.6.0") == ["garage_node_settings must be a mapping (garage.toml as YAML)."]


@pytest.mark.parametrize("change, needle", [
    ({"metadata_dir": "meta"}, "metadata_dir must be an absolute path"),
    ({"data_dir": "data"}, "data_dir must be an absolute path"),
    ({"data_dir": [{"capacity": "1T"}]}, "data_dir[0] must be a table with an absolute path"),
    ({"data_dir": []}, "data_dir must be a path or a list"),
    ({"replication_factor": 0}, "replication_factor must be a positive integer"),
    ({"replication_factor": "3"}, "replication_factor must be a positive integer"),
    ({"replication_factor": True}, "replication_factor must be a positive integer"),
    ({"rpc_secret": "x"}, "garage_node_settings.rpc_secret is refused"),
    ({"rpc_secret_file": "/x"}, "garage_node_settings.rpc_secret_file is refused"),
    ({"admin": {"api_bind_addr": "[::]:3903", "admin_token": "x"}}, "admin.admin_token is refused"),
    ({"admin": {"api_bind_addr": "[::]:3903", "metrics_token_file": "/x"}}, "admin.metrics_token_file is refused"),
])
def test_settings_problems(change, needle):
    settings = dict(SETTINGS, **change)
    assert any(needle in p for p in garage.settings_problems(settings, "v2.6.0")), needle


def test_settings_newer_than_the_version():
    settings = dict(SETTINGS, s3_api={"api_bind_addr": "[::]:3900", "public_endpoint": "https://s3.example.com"})
    assert garage.settings_problems(settings, "v2.6.0") == []
    problems = garage.settings_problems(settings, "v2.4.1")
    assert problems == [
        "garage_node_settings.s3_api.public_endpoint needs Garage v2.5.0 or later"
        " (garage_node_version is v2.4.1): older releases silently ignore it."
    ]


def test_node_paths():
    settings = dict(SETTINGS, data_dir=[{"path": "/a", "capacity": "1T"}, {"path": "/b", "read_only": True}],
                    metadata_snapshots_dir="/snap")
    assert garage.node_paths(settings) == ["/var/lib/garage/meta", "/a", "/b", "/snap"]


def test_changed_identity_dirs():
    existing = {"metadata_dir": "/m", "data_dir": [{"path": "/a", "capacity": "1T"}, {"path": "/b", "capacity": "1T"}]}
    assert garage.changed_identity_dirs(existing, {"metadata_dir": "/m", "data_dir": [{"path": "/b"}, {"path": "/a"}]}) == []
    assert garage.changed_identity_dirs(existing, {"metadata_dir": "/n", "data_dir": "/a"}) == ["metadata_dir", "data_dir"]


# ---- the cluster ---------------------------------------------------------------------------

# Measured with garage v2.0.0's CLI: `layout assign -c <size>`, then GetClusterLayout.
@pytest.mark.parametrize("value, expected", [
    ("1T", 1000000000000),
    ("1TB", 1000000000000),
    ("1TiB", 1099511627776),
    ("1t", 1000000000000),
    ("500G", 500000000000),
    ("500M", 500000000),
    ("1.5T", 1500000000000),
    ("2048", 2048),
    ("10KiB", 10240),
    ("10K", 10000),
    ("1PB", 1000000000000000),
    ("1Gb", 1000000000),
    (2048, 2048),
])
def test_parse_capacity(value, expected):
    assert garage.parse_capacity(value) == expected


@pytest.mark.parametrize("value", ["1e3", "", "T", "1X", "-1T", "0", 0, True, "1iB"])
def test_parse_capacity_refuses(value):
    with pytest.raises(ValueError):
        garage.parse_capacity(value)


NODE_A = "a" * 64
NODE_B = "b" * 64
NODE_C = "c" * 64


@pytest.mark.parametrize("text, expected", [
    (NODE_A + "@10.0.0.1:3901\n", NODE_A),
    (NODE_A + "\n", NODE_A),
    ("nothing", None),
])
def test_node_id(text, expected):
    assert garage.node_id(text) == expected


# GetClusterStatus as garage v2.0.0's json-api prints it (fields trimmed).
STATUS = {
    "layoutVersion": 0,
    "nodes": [
        {"id": NODE_A, "addr": "10.0.0.1:3901", "isUp": True, "role": None},
        {"id": NODE_B, "addr": "10.0.0.2:3901", "isUp": False, "role": None},
    ],
}


def test_node_address():
    assert garage.node_address(STATUS, NODE_A) == "10.0.0.1:3901"
    assert garage.node_address(STATUS, NODE_C) is None


def test_nodes_to_connect_skips_the_nodes_up():
    wanted = {NODE_A: "10.0.0.1:3901", NODE_B: "10.0.0.2:3901", NODE_C: "10.0.0.3:3901"}
    assert garage.nodes_to_connect(STATUS, wanted) == [NODE_B + "@10.0.0.2:3901", NODE_C + "@10.0.0.3:3901"]
    assert garage.nodes_not_up(STATUS, wanted) == [NODE_B, NODE_C]


def test_layout_roles():
    nodes = [
        {"id": NODE_B, "zone": "dc2", "capacity": "1T", "gateway": False, "tags": ["x"]},
        {"id": NODE_A, "zone": "dc1", "capacity": None, "gateway": True, "tags": []},
    ]
    assert garage.layout_roles(nodes) == {"roles": [
        {"id": NODE_A, "zone": "dc1", "capacity": None, "tags": []},
        {"id": NODE_B, "zone": "dc2", "capacity": 1000000000000, "tags": ["x"]},
    ]}


@pytest.mark.parametrize("zone, capacity, gateway, tags, needle", [
    ("dc1", "1T", False, [], None),
    ("dc1", "", True, [], None),
    ("", "1T", False, [], "garage_cluster_zone is required"),
    ("dc1", "1T", True, [], "not both and not neither"),
    ("dc1", "", False, [], "not both and not neither"),
    ("dc1", "1X", False, [], "garage_cluster_capacity"),
    ("dc1", "1T", False, "x", "garage_cluster_tags"),
    ("dc1", "1T", False, [""], "garage_cluster_tags"),
])
def test_role_problems(zone, capacity, gateway, tags, needle):
    problems = garage.role_problems(zone, capacity, gateway, tags)
    if needle is None:
        assert problems == []
    else:
        assert any(needle in p for p in problems), problems


# GetClusterHealth as garage v2's json-api prints it.
HEALTHY = {"status": "healthy", "knownNodes": 4, "connectedNodes": 4, "storageNodes": 3,
           "storageNodesUp": 3, "partitions": 256, "partitionsQuorum": 256, "partitionsAllOk": 256}


def test_health_regressions_none():
    assert garage.health_regressions(HEALTHY, HEALTHY) == []
    assert garage.health_regressions({"status": "unavailable"}, {}) == []


def test_health_regressions():
    after = dict(HEALTHY, status="degraded", connectedNodes=2, storageNodesUp=2)
    assert garage.health_regressions(after, HEALTHY) == [
        "2 connected nodes, 4 before",
        "2 storage nodes up, 3 before",
        "the cluster is degraded, it was healthy",
    ]


def test_health_regressions_from_a_degraded_cluster():
    before = dict(HEALTHY, status="degraded", storageNodesUp=2, connectedNodes=3)
    assert garage.health_regressions(dict(before), before) == []
