# eyebrowkang.garage

[English](README.md) | 简体中文

> 本文译自英文版，两者不一致时以[英文版](README.md)为准。

在 systemd 主机上部署、升级和移除 [Garage](https://garagehq.deuxfleurs.fr/) 对象存储集群。

> **开发中。** 1.0 之前本 collection 不发布到 Galaxy，也不用于生产环境。它是
> [`eyebrowkang.garage` role](https://github.com/eyebrowkang/ansible-role-garage) 的继任者；在此之前，
> 部署 Garage 仍请使用该 role。

本 collection 做什么、有意不做什么：[docs/design.zh-CN.md](docs/design.zh-CN.md)。迁移 role 部署的主机：
[docs/migrating-from-the-role.zh-CN.md](docs/migrating-from-the-role.zh-CN.md)。

## 包含的 role

| Role | 管理的内容 |
| ---- | ---------- |
| [`eyebrowkang.garage.node`](roles/node/README.zh-CN.md) | 一个 Garage 节点：二进制、用户、systemd unit、`garage.toml` 及其密钥，以及它们的升级 |
| [`eyebrowkang.garage.cluster`](roles/cluster/README.zh-CN.md) | 让节点第一次成为一个集群：互相连接并应用首个 layout |

## 依赖

- 控制端：ansible-core 2.20 或更新。
- 主机：带 systemd 的 Linux，以及 ansible-core 能用的 Python。测试的发行版：Debian 12 和 13、
  Ubuntu 22.04 和 24.04、Rocky Linux 8、9 和 10、Fedora 43、openSUSE Leap 16 以及 Arch Linux。
- 架构：x86_64、aarch64、armv6l/armv7l 和 i686，即 Garage 发布的构建。

## 开发与测试

用 [copier](https://copier.readthedocs.io/) 和 [uv](https://docs.astral.sh/uv/) 管理：

```bash
uv sync          # install the dev toolchain
make lint        # yamllint + ansible-lint
make sanity      # ansible-test sanity (--venv)
make units       # ansible-test units (--venv)
make test        # molecule: one node in docker (MOLECULE_DISTRO and MOLECULE_IMAGE pick the distribution)
make test-vm     # molecule: one node on a VM (vagrant; needs KVM)
```

`ansible-test` 必须在 `ansible_collections/eyebrowkang/garage/` 路径下运行。CI 会把仓库检出到这个路径。

新 Garage 版本的 checksum：运行 `scripts/update-checksums.sh vX.Y.Z`，每周的工作流也会运行它。

## 许可证

GPL-3.0-or-later
