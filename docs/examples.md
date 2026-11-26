# Examples

English | [简体中文](examples.zh-CN.md)

How to do the common things with the collection. What each variable means is in the roles'
READMEs ([node](../roles/node/README.md), [cluster](../roles/cluster/README.md)); why the
roles work this way is in [design.md](design.md).

## A new cluster

Three storage nodes in three zones. The secret comes from a vault.

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

The run ends when the cluster is healthy and every node has saved the others as its peers.
Create buckets and keys with Garage's CLI, admin API or web UI.

## A single node

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

## Several disks

`data_dir` as Garage's list: each disk with its capacity, or read-only.

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

The unit waits for the mounts of every directory (`RequiresMountsFor=`). Mounting the disks
is the host's.

## A minor upgrade

Change the version. The nodes restart one at a time, each as healthy as before the next
one stops.

```yaml
garage_node_version: v2.6.1
```

Preview it first: `ansible-playbook site.yml --check --diff`.

## A major upgrade

v2 to v3. Read Garage's release notes and upgrade guide first, and stop the traffic. The
whole cluster must be in the play, without `serial`.

```yaml
garage_node_version: v3.0.0
garage_node_major_upgrade: true
```

The run checks the cluster, repairs the tables and takes a snapshot of every node's
metadata, then stops every node and starts every node on v3. Copy the snapshots
(`metadata_dir/snapshots`) elsewhere if you want to keep them. Then remove
`garage_node_major_upgrade`, so the next major version is a decision again.

## A version the collection doesn't know yet

Give the binary's SHA256, measured yourself. It's one architecture's: set it per group of
hosts when they differ.

```yaml
garage_node_version: v2.7.0
garage_node_checksum: "<sha256 of the x86_64-unknown-linux-musl binary>"
```

## Hosts without internet access

The controller downloads the binary and copies it over. A mirror works too: the checksum is
verified on the host.

```yaml
garage_node_fetch: controller
# or
garage_node_url: "https://mirror.example.com/garage/{{ garage_node_version }}/x86_64-unknown-linux-musl/garage"
```

## Tokens and the admin API

```yaml
garage_node_admin_token: "{{ vault_garage_admin_token }}"
garage_node_metrics_token: "{{ vault_garage_metrics_token }}"
garage_node_settings:
  # ...
  admin:
    api_bind_addr: "10.0.0.1:3903"
```

Since v2.6.0 the admin API's address also serves the web UI: bind it to a private address.

## Logs and other systemd settings

A drop-in, in systemd's own syntax:

```yaml
garage_node_systemd_override: |
  [Service]
  Environment=RUST_LOG=garage=debug
  MemoryMax=8G
```

## Removing a node

Take it out of the layout first, with `garage layout remove` and `garage layout apply`.
Then:

```yaml
- name: Remove Garage
  hosts: garage3
  become: true
  roles:
    - role: eyebrowkang.garage.node
      vars:
        garage_node_state: absent
```

The metadata and data directories stay.

## Moving from the eyebrowkang.garage role

See [migrating-from-the-role.md](migrating-from-the-role.md).
