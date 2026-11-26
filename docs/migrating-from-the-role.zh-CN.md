# 从 role 迁移

[English](migrating-from-the-role.md) | 简体中文

> 本文译自英文版，两者不一致时以[英文版](migrating-from-the-role.md)为准。

如何把由 [`eyebrowkang.garage` role](https://github.com/eyebrowkang/ansible-role-garage)（1.x）部署的
主机迁移到本 collection。主机会被原地接管：不重装任何东西，每个节点保留它的身份、layout 和数据。具体保证见
[docs/design.zh-CN.md](design.zh-CN.md) 的「从 role 接管主机」。

## 开始之前

- 主机必须是用 role 的默认路径和名称部署的：`garage_user`、`garage_group`、`garage_home` 和
  `garage_config_dir` 没有改过。其他主机会在任何改动之前被 node role 拒绝，并说明哪个值不同。
- `metadata_dir` 和 `data_dir` 必须与 role 写在 `/etc/garage/garage.toml` 中的完全一致。在已有数据的节点上
  改变它们会被 node role 拒绝。
- 第一次运行会逐个重启每个节点一次：unit 会变化，密钥会从 `garage.toml` 移到单独的文件中。

## 步骤

1. 按下表转换 role 的变量，并删除它们。仍然设置着这些变量的 play 会在任何改动之前失败，并列出它们。
2. 在 play 中用 collection 的 role 替换原来的 role：
   - role 部署的集群已经有 layout：只用 [node role](../roles/node/README.zh-CN.md) 就够了；
   - [cluster role](../roles/cluster/README.zh-CN.md) 用于新集群。
3. 先预演：`ansible-playbook --check --diff`。它会显示新的 `garage.toml` 和 unit，以及哪些节点会重启。
4. 正式运行。接管和升级 Garage 可以在同一次运行中完成。

```yaml
# Before: the role
- hosts: garage
  become: true
  vars:
    garage_version: v2.6.0
    garage_rpc_secret: "{{ vault_garage_rpc_secret }}"
    garage_replication_factor: 3
  roles:
    - eyebrowkang.garage

# After: the collection
- hosts: garage
  become: true
  vars:
    garage_node_version: v2.6.0
    garage_node_rpc_secret: "{{ vault_garage_rpc_secret }}"
    garage_node_settings:
      metadata_dir: /var/lib/garage/meta
      data_dir: /var/lib/garage/data
      replication_factor: 3
      rpc_public_addr: "{{ ansible_default_ipv4.address }}:3901"
  roles:
    - eyebrowkang.garage.node
```

## role 的变量

`settings` 指 `garage_node_settings`，即以 YAML 书写的 Garage `garage.toml`。

| role 变量 | 在 collection 中 |
| --------- | ---------------- |
| `garage_version` | `garage_node_version`。必填：没有默认版本。 |
| `garage_user`、`garage_group`、`garage_home`、`garage_config_dir` | 固定为 `garage`、`garage`、`/var/lib/garage`、`/etc/garage`，即 role 的默认值。 |
| `garage_metadata_dir` | `settings.metadata_dir`。必填：role 的默认值是 `/var/lib/garage/meta`。 |
| `garage_data_dir` | `settings.data_dir`。必填：role 的默认值是 `/var/lib/garage/data`。 |
| `garage_data_dirs` | `settings.data_dir`，写成 `{path, capacity}` 或 `{path, read_only: true}` 的列表。 |
| `garage_db_engine` | `settings.db_engine`。Garage 的默认值是 `lmdb`，与 role 相同。 |
| `garage_replication_factor` | `settings.replication_factor`。必填：role 的默认值 1 对集群是错误的。 |
| `garage_rpc_secret` | `garage_node_rpc_secret`。 |
| `garage_rpc_secret_file` | 没有对应：在 `garage_node_rpc_secret` 中给出值，collection 会写入自己的文件。 |
| `garage_rpc_bind_addr` | `settings.rpc_bind_addr`。默认值相同。 |
| `garage_rpc_public_addr` | `settings.rpc_public_addr`。没有默认值：由 Garage 检测。role 的默认值是 `"{{ ansible_default_ipv4.address }}:3901"`，见上面的示例。 |
| `garage_bootstrap_peers` | `settings.bootstrap_peers`。 |
| `garage_s3_region` | `settings.s3_api.s3_region`。默认值相同。 |
| `garage_s3_api_bind_addr` | `settings.s3_api.api_bind_addr`。默认值相同。 |
| `garage_s3_root_domain` | `settings.s3_api.root_domain`。 |
| `garage_s3_public_endpoint` | `settings.s3_api.public_endpoint`。 |
| `garage_s3_web_bind_addr`、`garage_s3_web_root_domain` | `settings.s3_web.bind_addr`、`settings.s3_web.root_domain`。 |
| `garage_admin_api_bind_addr` | `settings.admin.api_bind_addr`。默认值相同。 |
| `garage_admin_token` | `garage_node_admin_token`。 |
| `garage_metrics_token` | `garage_node_metrics_token`。 |
| `garage_admin_token_file`、`garage_metrics_token_file` | 没有对应：在 `garage_node_admin_token` 和 `garage_node_metrics_token` 中给出值。 |
| `garage_admin_healthcheck_host`、`garage_healthcheck_enabled` | 没有对应：node role 总会经 RPC 检查启动或重启后节点的健康状态。 |
| `garage_cluster_connect`、`garage_layout_init` | cluster role：它总会连接节点，并在没有 layout 时应用首个 layout。 |
| `garage_cluster_hosts` | 没有对应：集群的节点就是 play 的主机。 |
| `garage_layout_zone`、`garage_layout_capacity`、`garage_layout_gateway`、`garage_layout_tags` | `garage_cluster_zone`、`garage_cluster_capacity`、`garage_cluster_gateway`、`garage_cluster_tags`。 |
| `garage_upgrade` | 没有对应：新的 `garage_node_version` 就是升级。 |
| `garage_upgrade_precheck` | 没有对应：节点逐个重启，每个恢复到重启前的健康程度后，下一个才会停止。 |
| `garage_checksum` | `garage_node_checksum`。 |
| `garage_download_url` | `garage_node_url`。 |
| `garage_download_local` | `garage_node_fetch: controller`。 |
| `garage_config_template` | `garage_node_settings`：转换模板的内容。 |
| `garage_no_log` | 没有对应：密钥从不出现在输出中，`garage.toml` 也不含密钥。 |
| `garage_env_variables` | `garage_node_systemd_override`，写成 `[Service]` 和 `Environment=` 行。`GARAGE_LOG_TO_JOURNALD=1` 由 unit 自带。 |

## 主机上会变化的内容

- `/etc/garage/garage.toml` 换成 collection 的：密钥移到 `/etc/garage/secrets/`，属于 `garage:garage`，
  权限 `0600`。
- `/etc/systemd/system/garage.service` 换成 collection 的。role 的 `/etc/garage/garage.env` 和
  `/usr/local/bin/garage.bak` 会被删除。
- 二进制、`garage` 用户以及元数据和数据目录保留。
