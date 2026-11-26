# 示例

[English](examples.md) | 简体中文

> 本文译自英文版，两者不一致时以[英文版](examples.md)为准。

如何用本 collection 完成常见的事。每个变量的含义见各 role 的 README（[node](../roles/node/README.zh-CN.md)、
[cluster](../roles/cluster/README.zh-CN.md)）；role 为什么这样做见 [design.zh-CN.md](design.zh-CN.md)。

## 新集群

三个存储节点，分布在三个 zone。密钥来自 vault。

```yaml
# group_vars/garage.yml
garage_node_version: v2.6.0
garage_node_rpc_secret: "{{ vault_garage_rpc_secret }}"
garage_node_settings:
  metadata_dir: /var/lib/garage/meta
  data_dir: /var/lib/garage/data
  replication_factor: 3
  rpc_public_addr: "{{ ansible_default_ipv4.address }}:3901"
```

```yaml
# host_vars/garage1.yml (and garage2 in dc2, garage3 in dc3)
garage_cluster_zone: dc1
garage_cluster_capacity: 1T
```

```yaml
# site.yml
- name: A Garage cluster
  hosts: garage
  become: true
  roles:
    - role: eyebrowkang.garage.node
    - role: eyebrowkang.garage.cluster
```

集群健康、并且每个节点都把其他节点保存为 peer 之后，运行才结束。bucket 和 key 用 Garage 的 CLI、admin API
或 Web 界面创建。

## 单节点

```yaml
- name: A single Garage node
  hosts: garage1
  become: true
  vars:
    garage_node_version: v2.6.0
    garage_node_rpc_secret: "{{ vault_garage_rpc_secret }}"
    garage_node_settings:
      metadata_dir: /var/lib/garage/meta
      data_dir: /var/lib/garage/data
      replication_factor: 1
    garage_cluster_zone: dc1
    garage_cluster_capacity: 1T
  roles:
    - role: eyebrowkang.garage.node
    - role: eyebrowkang.garage.cluster
```

## 多块磁盘

`data_dir` 写成 Garage 的列表形式：每块磁盘带上容量，或者设为只读。

```yaml
garage_node_settings:
  metadata_dir: /var/lib/garage/meta
  data_dir:
    - path: /mnt/disk1/garage
      capacity: 4T
    - path: /mnt/disk2/garage
      capacity: 4T
  replication_factor: 3
```

unit 会等待每个目录所在的挂载点（`RequiresMountsFor=`）。挂载磁盘是主机的事。

## 小版本升级

改版本号即可。节点逐个重启，每个恢复到重启前的健康程度后，下一个才会停止。

```yaml
garage_node_version: v2.6.1
```

可以先预演：`ansible-playbook site.yml --check --diff`。

## 大版本升级

v2 到 v3。先读 Garage 的发布说明和升级指南，并停掉流量。整个集群都必须在 play 中，不能用 `serial`。

```yaml
garage_node_version: v3.0.0
garage_node_major_upgrade: true
```

运行会先检查集群，修复表并给每个节点的元数据做快照，然后停止所有节点，再用 v3 启动所有节点。需要保留快照的话，
把它们（`metadata_dir/snapshots`）复制到别处。之后删掉 `garage_node_major_upgrade`，让下一个大版本重新成为一次
明确的决定。

## collection 还不认识的版本

给出你自己测得的二进制 SHA256。它只对应一种架构：架构不同时按主机组分别设置。

```yaml
garage_node_version: v2.7.0
garage_node_checksum: "<sha256 of the x86_64-unknown-linux-musl binary>"
```

## 无法访问互联网的主机

由控制端下载二进制再复制过去。也可以用镜像：checksum 在主机上校验。

```yaml
garage_node_fetch: controller
# or
garage_node_url: "https://mirror.example.com/garage/{{ garage_node_version }}/x86_64-unknown-linux-musl/garage"
```

## token 与 admin API

```yaml
garage_node_admin_token: "{{ vault_garage_admin_token }}"
garage_node_metrics_token: "{{ vault_garage_metrics_token }}"
garage_node_settings:
  # ...
  admin:
    api_bind_addr: "10.0.0.1:3903"
```

从 v2.6.0 起，admin API 的地址同时提供 Web 界面：把它绑定到内网地址。

## 日志及其他 systemd 设置

用 drop-in，使用 systemd 自己的语法：

```yaml
garage_node_systemd_override: |
  [Service]
  Environment=RUST_LOG=garage=debug
  MemoryMax=8G
```

## 移除节点

先用 `garage layout remove` 和 `garage layout apply` 把它移出 layout。然后：

```yaml
- name: Remove Garage
  hosts: garage3
  become: true
  roles:
    - role: eyebrowkang.garage.node
      vars:
        garage_node_state: absent
```

元数据和数据目录保留。

## 从 eyebrowkang.garage role 迁移

见 [migrating-from-the-role.zh-CN.md](migrating-from-the-role.zh-CN.md)。
