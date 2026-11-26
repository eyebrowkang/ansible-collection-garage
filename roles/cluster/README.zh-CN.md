# eyebrowkang.garage.cluster

[English](README.md) | 简体中文

> 本文译自英文版，两者不一致时以[英文版](README.md)为准。

让 Garage 节点第一次成为一个集群：把 play 中的每个节点连接到其他每个节点，并在集群还没有 layout 时应用
首个 layout。已有 layout 的集群永远不会被改动：之后的 layout 变更由管理员用 `garage layout` 完成。原因见
[docs/design.zh-CN.md](../../docs/design.zh-CN.md) 的「集群引导」。

它在 [node role](../node/README.zh-CN.md) 之后、在运行中的节点上运行。play 的主机就是集群的节点。

```yaml
- name: A Garage cluster
  hosts: garage
  become: true
  roles:
    - role: eyebrowkang.garage.node
    - role: eyebrowkang.garage.cluster
```

```yaml
# host_vars/garage1.yml
garage_cluster_zone: dc1
garage_cluster_capacity: 1T
```

## 变量

每个变量都是针对单个节点的：写在 `host_vars` 中，节点相同时也可以写在 `group_vars` 中。

| 变量 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `garage_cluster_zone` | （必填） | 该节点 layout 角色的 zone。 |
| `garage_cluster_capacity` | `""` | 该存储节点的容量：字节数，或者 Garage CLI 能读的大小写法（`1T`、`500G`、`1.5TiB`）。 |
| `garage_cluster_gateway` | `false` | 该节点是 gateway：提供 API，不存储数据。 |
| `garage_cluster_tags` | `[]` | 该节点 layout 角色的标签。 |

一个节点要么是存储节点（`garage_cluster_capacity`），要么是 gateway（`garage_cluster_gateway: true`），
不能两者都是。

## 如何与 Garage 通信

在每个节点上通过 `garage json-api` 调用：经 RPC 访问 admin API。只需要 node role 写入的 RPC 密钥，不需要
admin token。每个节点通过它自己报告的地址访问：Garage 检测不到时，在 `garage_node_settings` 中设置
`rpc_public_addr`。
