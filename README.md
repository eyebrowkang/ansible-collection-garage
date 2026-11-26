# eyebrowkang.garage

Deploy, upgrade and remove a Garage object storage cluster on systemd hosts

## Included content

- `roles/example` — starter role; replace with your real roles.

## Requirements

- ansible-core >= 2.20.0
- [uv](https://docs.astral.sh/uv/) for local development
- Docker (for the molecule docker scenario; `ansible-test sanity` runs in a `--venv`)
- libvirt + Vagrant + KVM (for the vagrant molecule scenario)

## Installing

```bash
ansible-galaxy collection install eyebrowkang.garage
```

## Development and testing

Managed with [copier](https://copier.readthedocs.io/) + [uv](https://docs.astral.sh/uv/):

```bash
uv sync          # install dev toolchain
make lint        # yamllint + ansible-lint
make sanity      # ansible-test sanity (--venv)
make units       # ansible-test units (--venv)
make test        # molecule test for the example role (docker)
make test-vm     # molecule test for the example role (vagrant; needs KVM)
```

> `ansible-test` must run from an `ansible_collections/eyebrowkang/garage/`
> path. Developing under the meta-repo's `collections/` workspace satisfies this; CI checks
> the repo out under that path (see the generated CI workflow).

Pull future template improvements:

```bash
copier update --trust
```

## License

GPL-3.0-or-later
