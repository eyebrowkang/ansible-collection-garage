# eyebrowkang.garage.cluster

English | [简体中文](README.zh-CN.md)

Makes Garage nodes one cluster the first time: connects every node of the play to every
other, and applies the first layout when the cluster has none. A cluster that has a layout
is never changed: later layout changes are the admin's, with `garage layout`. Why: see
[docs/design.md](../../docs/design.md), "Cluster bootstrap".

It runs after [the node role](../node/README.md), on running nodes. The play's hosts are
the cluster's nodes.

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

## Variables

Each is per node: set them in `host_vars`, or `group_vars` for nodes alike.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `garage_cluster_zone` | (required) | The zone of this node's layout role. |
| `garage_cluster_capacity` | `""` | The capacity of this storage node: bytes, or a size as Garage's CLI reads it (`1T`, `500G`, `1.5TiB`). |
| `garage_cluster_gateway` | `false` | This node is a gateway: it serves the APIs and stores nothing. |
| `garage_cluster_tags` | `[]` | The tags of this node's layout role. |

A node is either a storage node (`garage_cluster_capacity`) or a gateway
(`garage_cluster_gateway: true`), not both.

## How it talks to Garage

Through `garage json-api` on each node: the admin API over RPC. It needs only the RPC
secret the node role wrote, no admin token. Each node is reached at the address it reports
for itself: set `rpc_public_addr` in `garage_node_settings` when Garage can't detect it.
