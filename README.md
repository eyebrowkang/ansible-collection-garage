# eyebrowkang.garage

English | [简体中文](README.zh-CN.md)

Deploy, upgrade and remove a [Garage](https://garagehq.deuxfleurs.fr/) object storage
cluster on systemd hosts.

> **In development.** Until 1.0 the collection isn't published to Galaxy and isn't meant for
> production. It succeeds the
> [`eyebrowkang.garage` role](https://github.com/eyebrowkang/ansible-role-garage), which
> stays the way to deploy Garage until then.

What the collection does, and what it doesn't on purpose: [docs/design.md](docs/design.md).

## Roles

| Role | What it manages |
| ---- | --------------- |
| [`eyebrowkang.garage.node`](roles/node/README.md) | A Garage node: the binary, its user, the systemd unit, `garage.toml` and its secrets, and their upgrades |
| [`eyebrowkang.garage.cluster`](roles/cluster/README.md) | Makes the nodes one cluster the first time: connects them and applies the first layout |

## Requirements

- ansible-core 2.20 or newer on the controller.
- Hosts: Linux with systemd, and a Python ansible-core can use. The tested distributions are
  Debian 12 and 13, Ubuntu 22.04 and 24.04, Rocky Linux 8, 9 and 10, Fedora 43, openSUSE
  Leap 16 and Arch Linux.
- Architectures: x86_64, aarch64, armv6l/armv7l and i686, the builds Garage publishes.

## Development and testing

Managed with [copier](https://copier.readthedocs.io/) and [uv](https://docs.astral.sh/uv/):

```bash
uv sync          # install the dev toolchain
make lint        # yamllint + ansible-lint
make sanity      # ansible-test sanity (--venv)
make units       # ansible-test units (--venv)
make test        # molecule: one node in docker (MOLECULE_DISTRO and MOLECULE_IMAGE pick the distribution)
make test-vm     # molecule: one node on a VM (vagrant; needs KVM)
```

`ansible-test` must run from an `ansible_collections/eyebrowkang/garage/` path. CI checks
the repository out under that path.

A new Garage release's checksums: `scripts/update-checksums.sh vX.Y.Z`, which a weekly
workflow also runs.

## License

GPL-3.0-or-later
