# Design

English | [简体中文](design.zh-CN.md)

> **In development.** The roles are written against this document. Until 1.0 it can still
> change, and the collection isn't meant for production.

What `eyebrowkang.garage` is for, the rules its roles follow, and what it doesn't do on
purpose. Read it before proposing a feature: most answers to "why doesn't it..." are here.

## Goal

Deploy, upgrade and remove a [Garage](https://garagehq.deuxfleurs.fr/) cluster on systemd
hosts, as the official static binary. Every run is predictable and safe to repeat.

The first release is deliberately small. It is done when:

1. A new user can deploy a cluster of a given, supported Garage version, and the cluster
   serves requests once the run ends.
2. A user of the `eyebrowkang.garage` role can take over the cluster the role deployed,
   then upgrade it, including from Garage v2 to v3.
3. A user can remove Garage from a host. (Optional for 1.0.)

**It manages** a Garage node on each host: the binary, its user, the systemd unit, the
configuration and its secrets, and their upgrades (`node`); and the steps that make a set
of nodes one cluster the first time: connecting them and applying the first layout
(`cluster`).

**It doesn't manage** what lives inside the cluster (buckets, keys, admin tokens created
through the API), any layout change after the first one, nor what the host must provide
(systemd, disks and mounts, the firewall, a reverse proxy, TLS).

The collection reaches 1.0 when Garage v3 is released, and 1.0 migrates clusters from v2
to v3. Before 1.0 it isn't published to Galaxy and isn't meant for production.

## Principles

1. **The inputs decide everything.**
   - The version is required and exact (`v2.6.0`). The collection ships no default version:
     upgrading the collection never upgrades Garage.
   - Running again with the same inputs is the explicit request: what failed is tried again.
   - Nothing is removed implicitly. A host taken out of the inventory keeps running.
     Removing is `state: absent`.
2. **Only a binary whose checksum the collection knows runs.**
   - Garage publishes neither signatures nor checksums. The collection ships the SHA256 of
     each supported release and architecture, measured when the release is added. This is
     the trust root, fixed by the collection, like a signing key.
   - The host verifies the download before anything is replaced. The download server, a
     mirror and the controller's cache aren't trusted.
   - A version the collection doesn't know is refused, unless the user gives its checksum
     (`garage_node_checksum`): that's still a verified binary, and it bridges a Garage
     release and the next collection release.
3. **Garage's own configuration format.**
   - `garage_node_settings` is `garage.toml`, as YAML. The role writes it as TOML.
   - It's merged over the role's few defaults, the role's former values: the bind addresses
     and the S3 region. A setting nobody sets isn't written: it's Garage's own default.
   - `replication_factor` has no default: the role's former 1 is wrong for a cluster.
   - `rpc_public_addr` has no default, as in Garage, which detects it.
   - Secrets are the one exception: `garage_node_rpc_secret`, `garage_node_admin_token`
     and `garage_node_metrics_token` are written to files of their own, and
     `garage.toml` points at them (`rpc_secret_file`, ...).
4. **The cluster stays available, except when Garage itself requires otherwise.**
   - A change that needs a restart (a binary of the same major version, the configuration,
     a secret, the unit) restarts the nodes one at a time. Each must be healthy before the
     next one stops.
   - A major upgrade is the one exception: Garage nodes of different major versions can't
     talk to each other, so every node stops, then every node starts on the new binary.
     See [Major upgrades](#major-upgrades).
5. **Check before changing.**
   - Every check, including across hosts, runs before anything changes. A failure says what
     and why, and keeps Garage's own message.
   - Prerequisites come from the host: the roles check them and never install them.
6. **The cluster's identity is never at stake.**
   - A node's identity and data live in `metadata_dir` and `data_dir`. Changing either on a
     node that already has data is refused: Garage would start as a new, empty node.
   - Nothing under `metadata_dir` or `data_dir` is ever removed, not even by `absent`.
7. **Secrets stay out of the logs.**
   - The secrets are never in `garage.toml`, a command line, task output or `--diff`.

## Guarantees and limits

Each section lists what's guaranteed, then the limits: what isn't done or can't be.

### Binary

Guarantees:

- The binary is `/usr/local/bin/garage`, the same path as the role's.
- A new binary is verified before it replaces anything: its checksum, then the version it
  reports.
- The replacement is atomic.
- A downgrade is refused: from v2.5.0 on, Garage's metadata can't go back to an older
  version.
- Skipping a major version (v1 to v3) is refused: Garage only migrates between
  contiguous major versions.
- The download comes from Garage's release server, from `garage_node_url` when set (a
  mirror needs no trust), and is fetched by the host or, with `garage_node_fetch:
  controller`, by the controller and copied over (hosts without internet access).

Limits:

- The installed binary is compared by the version it reports. A new URL for the same
  version installs nothing.
- No rollback. A failed minor upgrade stops at the node that failed, which keeps the old
  binary if the new one didn't verify, or runs the new one if it did.
- Architectures: x86_64, aarch64, armv6l/armv7l and i686, the builds Garage publishes.

### Configuration

Guarantees:

- Before anything is written, the role checks what it relies on: `metadata_dir`,
  `data_dir`, `replication_factor`, `rpc_bind_addr` and the `[admin]` `api_bind_addr` are
  set; the RPC secret is 32 bytes of hex; settings that need a newer Garage than
  `garage_node_version` (such as `[s3_api] public_endpoint` before v2.5.0) are refused,
  because older releases silently ignore them.
- `garage.toml` is `root:garage`, mode `0640`. The secret files are `garage:garage`, mode
  `0600`: Garage refuses to start on a secret file others can read.
- The unit's writable paths and required mounts follow `metadata_dir` and `data_dir`.

Limits:

- The rest of the configuration is Garage's to check, when it starts: a setting it refuses
  fails the start, and the rolling restart stops at that node.
- `db_engine = "fjall"` is refused for a major upgrade to v3: Fjall's v3 files aren't
  compatible. Converting with `garage node convert-db` first is the admin's step.

### Restarts

Guarantees:

- A node that isn't running is started.
- A change to a running node restarts it, one node at a time across the play. The next
  node stops only when the restarted one reports itself healthy to the cluster.
- A configuration change and a binary change in one run restart a node once.

Limits:

- The one-at-a-time order is across the hosts of the play. A node of the cluster that isn't
  in the play isn't restarted, and isn't waited for.
- `serial` batches work, but each batch is its own rolling restart.
- A restart Garage refuses (a bad setting) leaves that node down and stops the run: the
  other nodes keep running the old configuration.

### Major upgrades

Garage v2 to v3 (and later majors the same way). The steps follow Garage's
[upgrade guide](https://garagehq.deuxfleurs.fr/documentation/operations/upgrading/).

Guarantees:

- A major upgrade runs only when `garage_node_version` crosses a major version *and*
  `garage_node_major_upgrade: true`. Otherwise it's refused before anything changes.
- Before anything changes, it checks: every node of the cluster is in the play and none is
  left out by `serial`; every node runs the same version; the cluster is healthy; no node
  uses `db_engine = "fjall"`.
- Then: `garage repair --all-nodes --yes tables`, `garage meta snapshot --all`, every node
  stops, every node gets the new binary, every node starts, and the run waits for the
  cluster to be healthy. Any migration Garage's guide for that version requires runs then.
- Downtime is the time for every node to stop and start, under a minute on a healthy
  cluster.

Limits:

- The snapshot is Garage's (`metadata_dir/snapshots`, the last two kept). Backing it up
  elsewhere, and restoring it after a failed upgrade, is the admin's.
- Stopping traffic first (a reverse proxy, the clients) is the admin's.
- A failed major upgrade isn't rolled back: the guide for that version decides how.

### Cluster bootstrap

Guarantees:

- Every node of the play connects to every other node.
- The first layout is applied only when the cluster has none (layout version 0). Every
  node of the play must be connected first, and each must have a zone and a capacity, or
  be a gateway.
- A cluster that has a layout is never changed.
- `cluster` runs the `garage` CLI on the nodes, over RPC: it needs only the RPC secret, no
  admin token. Plugins parse the CLI's output, with unit tests for each supported major
  version.

Limits:

- Every later layout change (capacity, adding or removing a node, rebalancing) is the
  admin's, with `garage layout`.
- The cluster's nodes are the play's hosts. A node outside the play isn't connected.

### Taking over a host from the role

A host deployed by the `eyebrowkang.garage` role (1.x) is taken over in place: no reinstall,
no data copied.

Guarantees:

- The collection uses the role's default paths and names: `/usr/local/bin/garage`,
  `/etc/garage/garage.toml`, `garage.service`, the `garage` user and group, `/var/lib/garage`.
- A host deployed with other values (`garage_user`, `garage_config_dir`, ... changed from
  their defaults) is refused, saying which value differs.
- `metadata_dir` and `data_dir` must equal the ones in the existing `garage.toml`, otherwise
  the run is refused (see principle 6). The node keeps its identity, layout and data.
- Variables of the role still set in the inventory (`garage_version`, `garage_rpc_secret`,
  ...) make the run fail, listing them and pointing at the migration guide (to be written:
  each role variable and what replaces it). A variable the collection doesn't read would
  otherwise be ignored silently.
- The takeover removes what the role left that the collection doesn't use:
  `/etc/garage/garage.env` and `/usr/local/bin/garage.bak`.
- The first run restarts each node once, one at a time: the unit and `garage.toml` change
  (the secrets move to files).
- Taking over and upgrading can happen in the same run. Tests cover both orders.

Limits:

- Hosts deployed by the role before 1.0 of the role, or by hand, aren't supported.
- A custom `garage_config_template` is translated by hand into `garage_node_settings`.

### Removal

Guarantees:

- `node` with `absent` stops and disables Garage, and removes the binary, the unit,
  `/etc/garage/` (`garage.toml` and the secret files) and the `garage` user.
- `metadata_dir` and `data_dir` stay.

Limits:

- Removing a node that still has a role in the layout leaves the cluster without it. Taking
  it out of the layout first is the admin's.

### Security

Guarantees:

- The secrets are in their own files, never in `garage.toml`, a command line or task
  output.
- Garage runs as the `garage` system user, with the unit's hardening (`ProtectSystem=strict`,
  `NoNewPrivileges=`, ...).

Limits:

- Since v2.6.0 the admin API listener also serves the web administration UI. Who can reach
  it is the admin's: bind `[admin] api_bind_addr` to a private address, or firewall it.

## Interface between the roles

- Fixed paths and names: `/usr/local/bin/garage`, `/etc/garage/` (`garage.toml`,
  `secrets/`), `garage.service`, the `garage` user and group, `/var/lib/garage`.
- `node` owns all of them. A node is one role because its binary and its configuration
  change together: a major upgrade starts the new binary on the new configuration in the
  same downtime, and a run restarts a node once for all its changes.
- `cluster` reads the node identities from the running nodes. It never restarts them, and
  needs the `node` role's paths and a running node.
- In one play: `node`, then `cluster`.

Changing any of them is a breaking change (after 1.0: a major version).

## Supported platforms and tests

- Any Linux with systemd. The tested distributions are the ones the role declares:
  Debian, Ubuntu, Enterprise Linux 8/9/10, Fedora, Arch Linux, openSUSE.
- The host provides a Python ansible-core can use: on Enterprise Linux 8 that's not the
  platform Python 3.6.
- Every scenario runs in Docker (systemd containers), so it runs in CI: one node per
  distribution; a three-node cluster; taking over from the role; minor upgrade; major
  upgrade v2 to v3; removal; invalid input.
- One Vagrant scenario runs before a release, locally: a three-node cluster on real VMs.
- Parsing Garage's output and building `garage.toml` are plugins with unit tests.

## Upgrading the collection

- Releases before 1.0 are development versions. Nothing is carried over between them:
  hosts are reinstalled.
- From 1.0 on, a release that changes what's on disk migrates hosts from the previous one.
  It keeps that migration until the next major version.
- A new Garage major version is supported by a new collection release; dropping one is a
  major version of the collection.

## Out of scope

### No buckets, keys or admin tokens

They are the cluster's content, not its deployment. The CLI, the admin API and the web UI
manage them.

### No layout changes after the first

Changing capacity or membership moves data. When and how much is the admin's decision,
with `garage layout`.

### No backup or restore

The major upgrade takes Garage's own metadata snapshot. Backing up data and metadata, and
restoring them, is the admin's.

### No packages, containers or Kubernetes

Only the official static binary under systemd. Garage's Helm chart covers Kubernetes.

### No firewall, reverse proxy or TLS

Garage's APIs speak plain HTTP. What fronts them is the host's.
