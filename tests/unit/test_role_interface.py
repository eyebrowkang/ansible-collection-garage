# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) eyebrowkang
"""The values the roles share (docs/design.md, "Interface between the roles") stay equal."""
from __future__ import annotations

import os

import pytest

yaml = pytest.importorskip("yaml")

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def role_vars(role):
    with open(os.path.join(ROOT, "roles", role, "vars", "main.yml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_paths_are_the_node_roles():
    node, cluster = role_vars("node"), role_vars("cluster")
    assert cluster["garage_cluster_binary_path"] == node["garage_node_binary_path"]
    assert cluster["garage_cluster_config_path"] == node["garage_node_config_path"]


def test_the_role_variables_are_the_same_list():
    assert role_vars("cluster")["garage_cluster_role_variables"] == role_vars("node")["garage_node_role_variables"]


def test_no_variable_reuses_a_role_variable_name():
    """A variable of the collection with a name of the eyebrowkang.garage role would be
    reported as left over from the role."""
    old = set(role_vars("node")["garage_node_role_variables"])
    for role in ("node", "cluster"):
        with open(os.path.join(ROOT, "roles", role, "meta", "argument_specs.yml"), encoding="utf-8") as handle:
            options = yaml.safe_load(handle)["argument_specs"]["main"]["options"]
        assert not old & set(options), role
