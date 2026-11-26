# eyebrowkang.garage.node

English | [简体中文](README.zh-CN.md)

A Garage node: the official static binary, its user, the systemd unit, `garage.toml` and its
secrets, and their upgrades. One node per host. Why it works this way, and what it doesn't
do: [docs/design.md](../../docs/design.md).

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

## Variables

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `garage_node_state` | `present` | `present` installs or upgrades the node and starts it. `absent` removes it: see [Removing](#removing). |
| `garage_node_version` | (required) | The exact Garage version, such as `v2.6.0`. No default: upgrading the collection never upgrades Garage. |
| `garage_node_settings` | (required) | `garage.toml`, as YAML: see [Settings](#settings). |
| `garage_node_rpc_secret` | (required) | The cluster's RPC secret, 64 hex characters (`openssl rand -hex 32`). |
| `garage_node_admin_token` | `""` | The admin API token. Empty: none, the admin API takes only the tokens created through it. |
| `garage_node_metrics_token` | `""` | The token for `/metrics`. Empty: none. |
| `garage_node_checksum` | `""` | The SHA256 of the binary, for a version the collection doesn't know yet. |
| `garage_node_url` | Garage's release server | Where the binary is downloaded from. A mirror needs no trust: the checksum is verified on the host. |
| `garage_node_fetch` | `target` | Who downloads the binary: the host (`target`), or the controller (`controller`), which copies it over. |
| `garage_node_cache_dir` | `~/.cache/eyebrowkang.garage` | The controller's download cache, with `garage_node_fetch: controller`. |
| `garage_node_systemd_override` | `""` | A drop-in for `garage.service`, in systemd's own syntax. |
| `garage_node_major_upgrade` | `false` | Allows `garage_node_version` to cross a major version, which stops every node of the cluster at once. Not implemented yet. |

## Settings

`garage_node_settings` is Garage's
[configuration file](https://garagehq.deuxfleurs.fr/documentation/reference-manual/configuration/),
as YAML. The role writes it as TOML.

- It's merged over the role's defaults: `rpc_bind_addr` `[::]:3901`, `s3_api.api_bind_addr`
  `[::]:3900`, `s3_api.s3_region` `garage` and `admin.api_bind_addr` `[::]:3903`.
- `metadata_dir`, `data_dir` and `replication_factor` are required.
- The secrets aren't settings: `rpc_secret`, `admin.admin_token`, `admin.metrics_token` and
  their `*_file` keys are refused. The role writes the secrets to files and sets the
  `*_file` keys itself.
- A setting newer than `garage_node_version` is refused, such as `s3_api.public_endpoint`
  before v2.5.0: older releases ignore it silently.

## Files

| Path | Owner, mode | Content |
| ---- | ----------- | ------- |
| `/usr/local/bin/garage` | `root`, `0755` | The binary |
| `/etc/garage/garage.toml` | `root:garage`, `0640` | The settings |
| `/etc/garage/secrets/*` | `garage:garage`, `0600` | `rpc_secret`, `admin_token`, `metrics_token` |
| `/etc/systemd/system/garage.service` | `root`, `0644` | The unit |
| `/etc/systemd/system/garage.service.d/eyebrowkang-garage.conf` | `root`, `0644` | `garage_node_systemd_override` |
| `metadata_dir`, `data_dir` | `garage:garage`, `0750` | The node's identity and data |

## Restarts

A running node is restarted once for all its changes: the binary, the settings, a secret,
the unit. The nodes of the play restart one at a time, and each must be as healthy as it
was before the next one stops, as Garage reports it over RPC: connected to as many nodes,
with as many storage nodes up, and the cluster healthy if it was. See [docs/design.md](../../docs/design.md), "Restarts".

## Removing

`garage_node_state: absent` stops and disables Garage, and removes the binary, the unit,
`/etc/garage` and the `garage` user. The metadata and data directories stay, and so does
`/var/lib/garage`.
