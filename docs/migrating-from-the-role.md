# Migrating from the role

English | [简体中文](migrating-from-the-role.zh-CN.md)

How to move hosts deployed by the [`eyebrowkang.garage` role](https://github.com/eyebrowkang/ansible-role-garage)
(1.x) to this collection. The hosts are taken over in place: nothing is reinstalled, and each
node keeps its identity, layout and data. What's guaranteed:
[docs/design.md](design.md), "Taking over a host from the role".

## Before you start

- The hosts must have been deployed with the role's default paths and names: `garage_user`,
  `garage_group`, `garage_home` and `garage_config_dir` unchanged. The node role refuses
  other hosts before changing anything, and says which value differs.
- Keep `metadata_dir` and `data_dir` exactly as the role wrote them in
  `/etc/garage/garage.toml`. The node role refuses to change them on a node that has data.
- The first run restarts each node once, one at a time: the unit changes, and the secrets
  move out of `garage.toml` into files.

## Steps

1. Translate the role's variables with the table below, and remove them. A play that still
   sets one fails before changing anything, listing them.
2. Replace the role with the collection's roles in the play:
   - a cluster the role deployed already has its layout: the
     [node role](../roles/node/README.md) is enough;
   - the [cluster role](../roles/cluster/README.md) is for a new cluster.
3. Check the run first: `ansible-playbook --check --diff`. It shows the new `garage.toml`
   and unit, and which nodes would restart.
4. Run it. Taking over and upgrading Garage can be the same run.

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

## The role's variables

`settings` is `garage_node_settings`, Garage's `garage.toml` as YAML.

| Role variable | In the collection |
| ------------- | ----------------- |
| `garage_version` | `garage_node_version`. Required: there's no default version. |
| `garage_user`, `garage_group`, `garage_home`, `garage_config_dir` | Fixed: `garage`, `garage`, `/var/lib/garage`, `/etc/garage`, the role's defaults. |
| `garage_metadata_dir` | `settings.metadata_dir`. Required: the role's default was `/var/lib/garage/meta`. |
| `garage_data_dir` | `settings.data_dir`. Required: the role's default was `/var/lib/garage/data`. |
| `garage_data_dirs` | `settings.data_dir`, as a list of `{path, capacity}` or `{path, read_only: true}`. |
| `garage_db_engine` | `settings.db_engine`. Garage's default is `lmdb`, the role's too. |
| `garage_replication_factor` | `settings.replication_factor`. Required: the role's default 1 is wrong for a cluster. |
| `garage_rpc_secret` | `garage_node_rpc_secret`. |
| `garage_rpc_secret_file` | None: give the value in `garage_node_rpc_secret`. The collection writes its own file. |
| `garage_rpc_bind_addr` | `settings.rpc_bind_addr`. Same default. |
| `garage_rpc_public_addr` | `settings.rpc_public_addr`. No default: Garage detects it. The role's default was `"{{ ansible_default_ipv4.address }}:3901"`, as in the example above. |
| `garage_bootstrap_peers` | `settings.bootstrap_peers`. |
| `garage_s3_region` | `settings.s3_api.s3_region`. Same default. |
| `garage_s3_api_bind_addr` | `settings.s3_api.api_bind_addr`. Same default. |
| `garage_s3_root_domain` | `settings.s3_api.root_domain`. |
| `garage_s3_public_endpoint` | `settings.s3_api.public_endpoint`. |
| `garage_s3_web_bind_addr`, `garage_s3_web_root_domain` | `settings.s3_web.bind_addr`, `settings.s3_web.root_domain`. |
| `garage_admin_api_bind_addr` | `settings.admin.api_bind_addr`. Same default. |
| `garage_admin_token` | `garage_node_admin_token`. |
| `garage_metrics_token` | `garage_node_metrics_token`. |
| `garage_admin_token_file`, `garage_metrics_token_file` | None: give the values in `garage_node_admin_token` and `garage_node_metrics_token`. |
| `garage_admin_healthcheck_host`, `garage_healthcheck_enabled` | None: the node role always checks a started or restarted node's health, over RPC. |
| `garage_cluster_connect`, `garage_layout_init` | The cluster role, which always connects the nodes and applies the first layout when there's none. |
| `garage_cluster_hosts` | None: the cluster's nodes are the play's hosts. |
| `garage_layout_zone`, `garage_layout_capacity`, `garage_layout_gateway`, `garage_layout_tags` | `garage_cluster_zone`, `garage_cluster_capacity`, `garage_cluster_gateway`, `garage_cluster_tags`. |
| `garage_upgrade` | None: a new `garage_node_version` is the upgrade. |
| `garage_upgrade_precheck` | None: nodes restart one at a time, each as healthy as before the next one stops. |
| `garage_checksum` | `garage_node_checksum`. |
| `garage_download_url` | `garage_node_url`. |
| `garage_download_local` | `garage_node_fetch: controller`. |
| `garage_config_template` | `garage_node_settings`: translate the template's content. |
| `garage_no_log` | None: the secrets are never in the output, and `garage.toml` holds none. |
| `garage_env_variables` | `garage_node_systemd_override`, as `[Service]` and `Environment=` lines. `GARAGE_LOG_TO_JOURNALD=1` is the unit's own. |

## What changes on the hosts

- `/etc/garage/garage.toml` is the collection's: the secrets move to
  `/etc/garage/secrets/`, `garage:garage`, mode `0600`.
- `/etc/systemd/system/garage.service` is the collection's. The role's
  `/etc/garage/garage.env` and `/usr/local/bin/garage.bak` are removed.
- The binary, the `garage` user and the metadata and data directories stay.
