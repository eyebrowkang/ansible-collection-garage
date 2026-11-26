# eyebrowkang.garage.node

[English](README.md) | 简体中文

> 本文译自英文版，两者不一致时以[英文版](README.md)为准。

一个 Garage 节点：官方静态二进制、它的用户、systemd unit、`garage.toml` 及其密钥，以及它们的升级。
每台主机一个节点。为什么这样做、有哪些不做：[docs/design.zh-CN.md](../../docs/design.zh-CN.md)。

```yaml
- name: Garage nodes
  hosts: garage
  become: true
  roles:
    - role: eyebrowkang.garage.node
      vars:
        garage_node_version: v2.6.0
        garage_node_rpc_secret: "{{ vault_garage_rpc_secret }}"
        garage_node_settings:
          metadata_dir: /var/lib/garage/meta
          data_dir: /var/lib/garage/data
          replication_factor: 3
```

## 变量

| 变量 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `garage_node_state` | `present` | `present` 安装或升级节点并启动它。`absent` 移除它：见[移除](#移除)。 |
| `garage_node_version` | （必填） | 精确的 Garage 版本，例如 `v2.6.0`。没有默认值：升级 collection 永远不会升级 Garage。 |
| `garage_node_settings` | （必填） | `garage.toml`，以 YAML 书写：见[配置](#配置)。 |
| `garage_node_rpc_secret` | （必填） | 集群的 RPC 密钥，64 个十六进制字符（`openssl rand -hex 32`）。 |
| `garage_node_admin_token` | `""` | admin API 的 token。为空：没有，admin API 只接受通过它创建的 token。 |
| `garage_node_metrics_token` | `""` | `/metrics` 的 token。为空：没有。 |
| `garage_node_checksum` | `""` | 二进制的 SHA256，用于 collection 还不认识的版本。 |
| `garage_node_url` | Garage 的发布服务器 | 下载二进制的地址。镜像不需要被信任：checksum 在主机上校验。 |
| `garage_node_fetch` | `target` | 由谁下载二进制：主机（`target`），或者控制端（`controller`），再复制过去。 |
| `garage_node_cache_dir` | `~/.cache/eyebrowkang.garage` | 控制端的下载缓存，用于 `garage_node_fetch: controller`。 |
| `garage_node_systemd_override` | `""` | `garage.service` 的 drop-in，使用 systemd 自己的语法。 |
| `garage_node_major_upgrade` | `false` | 允许 `garage_node_version` 跨越大版本，这会同时停止集群的所有节点。尚未实现。 |

## 配置

`garage_node_settings` 就是 Garage 的
[配置文件](https://garagehq.deuxfleurs.fr/documentation/reference-manual/configuration/)，以 YAML 书写，由
role 写成 TOML。

- 它合并在 role 的默认值之上：`rpc_bind_addr` `[::]:3901`、`s3_api.api_bind_addr` `[::]:3900`、
  `s3_api.s3_region` `garage` 和 `admin.api_bind_addr` `[::]:3903`。
- `metadata_dir`、`data_dir` 和 `replication_factor` 必填。
- 密钥不是配置项：`rpc_secret`、`admin.admin_token`、`admin.metrics_token` 以及它们的 `*_file` 键都会被
  拒绝。role 把密钥写入文件，并自己设置 `*_file` 键。
- 比 `garage_node_version` 更新的配置项会被拒绝，例如 v2.5.0 之前的 `s3_api.public_endpoint`：旧版本会
  静默忽略它。

## 文件

| 路径 | 属主与权限 | 内容 |
| ---- | ---------- | ---- |
| `/usr/local/bin/garage` | `root`，`0755` | 二进制 |
| `/etc/garage/garage.toml` | `root:garage`，`0640` | 配置 |
| `/etc/garage/secrets/*` | `garage:garage`，`0600` | `rpc_secret`、`admin_token`、`metrics_token` |
| `/etc/systemd/system/garage.service` | `root`，`0644` | unit |
| `/etc/systemd/system/garage.service.d/eyebrowkang-garage.conf` | `root`，`0644` | `garage_node_systemd_override` |
| `metadata_dir`、`data_dir` | `garage:garage`，`0750` | 节点的身份和数据 |

## 重启

运行中的节点为它所有的变更只重启一次：二进制、配置、密钥、unit。play 中的节点一次重启一个，每个节点
恢复到重启前的健康程度后，下一个节点才会停止（以 Garage 通过 RPC 报告的为准：连接的节点数、在线的存储
节点数都不少于重启前，重启前集群健康的，现在也要健康）。见
[docs/design.zh-CN.md](../../docs/design.zh-CN.md) 的「重启」。

## 移除

`garage_node_state: absent` 停止并禁用 Garage，删除二进制、unit 和 `/etc/garage`。元数据和数据目录保留，
`/var/lib/garage` 以及拥有它们的 `garage` 用户和用户组也保留：重新安装的节点仍能读取它的数据。
