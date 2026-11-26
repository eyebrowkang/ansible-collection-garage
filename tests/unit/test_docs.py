# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) eyebrowkang
"""The documentation's checkable rules (docs/design-principles in the scaffold): each English
document has a Chinese one with the same structure and the same code, relative links point
at files that exist, and the roles' variable tables are their argument specs."""
from __future__ import annotations

import glob
import os
import re

import pytest

yaml = pytest.importorskip("yaml")

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENGLISH = sorted(
    p for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True)
    if not p.endswith(".zh-CN.md") and "/tests/output/" not in p and "/.venv/" not in p
    and os.path.exists(p[:-3] + ".zh-CN.md")
)
ALL = sorted(
    p for p in glob.glob(os.path.join(ROOT, "**", "*.md"), recursive=True)
    if "/tests/output/" not in p and "/.venv/" not in p and "/.ansible/" not in p
)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


def headings(text):
    return [len(m.group(1)) for m in re.finditer(r"^(#+) ", strip_code(text), flags=re.M)]


def code_blocks(text):
    return re.findall(r"```.*?```", text, flags=re.S)


def rel(path):
    return os.path.relpath(path, ROOT)


def test_there_are_translations():
    assert ENGLISH, "no English document with a Chinese translation found"
    for path in ALL:
        if not path.endswith(".zh-CN.md") and not path.endswith("CHANGELOG.md"):
            assert os.path.exists(path[:-3] + ".zh-CN.md"), "%s has no .zh-CN.md" % rel(path)


@pytest.mark.parametrize("path", ENGLISH, ids=rel)
def test_same_headings(path):
    assert headings(read(path)) == headings(read(path[:-3] + ".zh-CN.md"))


@pytest.mark.parametrize("path", ENGLISH, ids=rel)
def test_same_code(path):
    assert code_blocks(read(path)) == code_blocks(read(path[:-3] + ".zh-CN.md"))


@pytest.mark.parametrize("path", ALL, ids=rel)
def test_relative_links_resolve(path):
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", strip_code(read(path))):
        if re.match(r"^[a-z]+:", target):
            continue
        assert os.path.exists(os.path.join(os.path.dirname(path), target)), "%s: %s" % (rel(path), target)


@pytest.mark.parametrize("role", ["node", "cluster"])
def test_variable_tables_are_the_argument_specs(role):
    with open(os.path.join(ROOT, "roles", role, "meta", "argument_specs.yml"), encoding="utf-8") as handle:
        options = set(yaml.safe_load(handle)["argument_specs"]["main"]["options"])
    for name in ("README.md", "README.zh-CN.md"):
        text = read(os.path.join(ROOT, "roles", role, name))
        table = set(re.findall(r"^\| `(%s_[a-z_]+)` \|" % "garage_%s" % role, text, flags=re.M))
        assert table == options, "%s/%s: %s" % (role, name, table ^ options)
