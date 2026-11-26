# Local dev targets (mirror CI). Requires uv: https://docs.astral.sh/uv/
.PHONY: help install deps lint sanity units changelog test converge check destroy test-vm destroy-vm
help:
	@echo "install   - uv sync (dev toolchain)"
	@echo "lint      - yamllint + ansible-lint"
	@echo "deps      - install Galaxy collections that ansible-lint needs"
	@echo "sanity    - ansible-test sanity (--venv, no docker)"
	@echo "units     - ansible-test units (plugin unit tests, --venv)"
	@echo "changelog - antsibull-changelog release (fold fragments; bump galaxy.yml first)"
	@echo "test      - molecule test: one node (docker; MOLECULE_DISTRO and MOLECULE_IMAGE pick the distribution)"
	@echo "converge  - molecule converge (one node, docker)"
	@echo "check     - molecule converge --check (dry-run, on converged instances)"
	@echo "destroy   - molecule destroy (one node, docker)"
	@echo "test-vm    - molecule test (one node, vagrant; needs 'uv sync --group vagrant' + libvirt/KVM)"
	@echo "destroy-vm - molecule destroy (one node, vagrant)"

install:
	uv sync

# ansible-lint resolves the active molecule scenario's collections (e.g. community.docker,
# used by the docker scenario's create.yml) from the Galaxy install path, so install them
# first — the same step CI runs before linting. molecule's own test sequence installs these
# via dependency:galaxy.
deps:
	uv run ansible-galaxy collection install -r extensions/molecule/default/collections.yml

lint: deps
	uv run yamllint .
	uv run ansible-lint

# ansible-test must run from within ansible_collections/<ns>/<name>/ — which this
# directory's path already satisfies in the workspace. --venv isolates the sanity
# test deps in their own venv (no docker needed; works under the Forgejo DooD runner,
# where --docker's sibling-container bind mounts would miss the checked-out collection).
sanity:
	uv run ansible-test sanity --venv --color
# Plugin unit tests under tests/unit/ (--venv, no docker; runs from the collection path).
units:
	uv run ansible-test units --venv --color
# Fold changelogs/fragments/*.yml into changelogs/changelog.yaml + regenerate CHANGELOG.md.
# Bump galaxy.yml's version first, then commit the generated files before tagging.
# antsibull-changelog lives in the opt-in `changelog` dependency-group (off the default sync).
changelog:
	uv run --group changelog antsibull-changelog release
# The scenarios live under extensions/molecule/; the default one is a node on the
# distribution MOLECULE_DISTRO names (debian13 unless set).
test:
	uv run molecule test

converge:
	uv run molecule converge

# Dry-run: everything after `--` is passed through to ansible-playbook, so this previews
# changes via check mode. On
# converged instances only: the scenario's create.yml and prepare.yml get --check too, and
# molecule would record them as done. See docs/molecule-testing.md.
check:
	uv run molecule converge -- --check

destroy:
	uv run molecule destroy
# molecule-plugins#301: the vagrant module/filter aren't on Ansible's default search
# path. Compute the package paths at runtime (no hardcoded python version) and export
# them so molecule can find the vagrant module. See docs/molecule-301-workaround.md
test-vm:
	ANSIBLE_LIBRARY="$$(uv run python -c 'import os, molecule_plugins.vagrant as m; print(os.path.join(os.path.dirname(m.__file__), "modules"))')" \
	ANSIBLE_FILTER_PLUGINS="$$(uv run python -c 'import os, molecule as m; print(os.path.join(os.path.dirname(m.__file__), "provisioner", "ansible", "plugins", "filter"))')" \
	uv run molecule test -s vagrant

# Cleanup for the vagrant scenario — same molecule-plugins#301 env workaround as test-vm.
destroy-vm:
	ANSIBLE_LIBRARY="$$(uv run python -c 'import os, molecule_plugins.vagrant as m; print(os.path.join(os.path.dirname(m.__file__), "modules"))')" \
	ANSIBLE_FILTER_PLUGINS="$$(uv run python -c 'import os, molecule as m; print(os.path.join(os.path.dirname(m.__file__), "provisioner", "ansible", "plugins", "filter"))')" \
	uv run molecule destroy -s vagrant
