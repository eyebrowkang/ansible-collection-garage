# 设计理念

[English](design.md) | 简体中文

> 本文译自英文版，两者不一致时以[英文版](design.md)为准。

> **开发中。** 各个 role 按本文编写。1.0 之前本文仍可能变化，collection 也不用于生产环境。

本文说明 `eyebrowkang.garage` 的定位、各个 role 遵循的原则，以及有意不做的事情。提出新功能之前请先读一读：
大多数「为什么不支持……」的答案都在这里。

## 目标

在 systemd 主机上部署、升级和移除 [Garage](https://garagehq.deuxfleurs.fr/) 集群，使用官方的静态二进制。
每次运行都可预期，可以安全地重复。

第一个版本刻意保持克制。做到以下几点就算完成：

1. 新用户能部署一个指定的、受支持版本的 Garage 集群，运行结束时集群即可提供服务。
2. `eyebrowkang.garage` role 的用户能接管 role 部署的集群，然后升级它，包括从 Garage v2 升级到 v3。
3. 用户能从主机上移除 Garage。（1.0 可选。）

**它管理**每台主机上的一个 Garage 节点：二进制、用户、systemd unit、配置及其密钥，以及它们的升级
（`node`）；以及让一组节点第一次成为一个集群的步骤：互相连接、应用首个 layout（`cluster`）。

**它不管理**集群里面的内容（bucket、key、通过 API 创建的 admin token）、首个之后的任何 layout 变更，以及
主机要自备的东西（systemd、磁盘和挂载、防火墙、反向代理、TLS）。

Garage v3 正式发布时，collection 发布 1.0，并且 1.0 能把集群从 v2 迁移到 v3。1.0 之前不发布到 Galaxy，
也不用于生产环境。

## 原则

1. **输入决定一切。**
   - 版本必填且精确（`v2.6.0`）。collection 不自带默认版本：升级 collection 永远不会升级 Garage。
   - 用相同的输入再运行一次，本身就是显式的请求：失败过的会再试一次。
   - 不隐式删除任何东西。从 inventory 中去掉的主机继续运行。删除用 `state: absent`。
2. **只运行 collection 知道 checksum 的二进制。**
   - Garage 既不发布签名，也不发布 checksum。collection 自带每个受支持版本、每种架构的 SHA256，在加入该
     版本时实测得到。这就是信任根，由 collection 固定，作用相当于签名密钥。
   - 主机在替换任何东西之前校验下载的文件。下载服务器、镜像和控制端的缓存都不被信任。
   - collection 不认识的版本会被拒绝，除非用户提供它的 checksum（`garage_node_checksum`）：这仍然是
     校验过的二进制，并且能衔接 Garage 发布新版本与 collection 发布新版本之间的空档。
3. **使用 Garage 自己的配置格式。**
   - `garage_node_settings` 就是 `garage.toml`，以 YAML 书写，由 role 写成 TOML。
   - 它合并在 role 的少数默认值之上，即 role 原来的值：各监听地址和 S3 region。没人设置的选项不写入，
     即使用 Garage 自己的默认值。
   - `replication_factor` 没有默认值：role 原来的 1 对集群是错误的。
   - `rpc_public_addr` 没有默认值，和 Garage 一致，由它自动检测。
   - 密钥是唯一的例外：`garage_node_rpc_secret`、`garage_node_admin_token` 和
     `garage_node_metrics_token` 各自写入单独的文件，`garage.toml` 引用它们（`rpc_secret_file` 等）。
4. **集群保持可用，除非 Garage 本身要求停机。**
   - 需要重启的变更（同一大版本的二进制、配置、密钥、unit）逐个重启节点，每个节点恢复健康后才停下一个。
   - 大版本升级是唯一的例外：不同大版本的 Garage 节点无法互相通信，所以所有节点先停止，再全部用新二进制
     启动。见[大版本升级](#大版本升级)。
5. **检查在前。**
   - 所有检查（包括跨主机的）都在任何改动之前完成。失败时说明什么失败了、为什么，并保留 Garage 自己的信息。
   - 前置条件由主机提供：role 只检查，从不安装。
6. **集群的身份永远不受威胁。**
   - 节点的身份和数据在 `metadata_dir` 和 `data_dir` 里。在已有数据的节点上改变其中任何一个都会被拒绝：
     否则 Garage 会作为一个新的空节点启动。
   - `metadata_dir` 和 `data_dir` 下的任何东西都不会被删除，`absent` 也不会。
7. **密钥不进日志。**
   - 密钥不出现在 `garage.toml`、命令行、任务输出和 `--diff` 中。

## 保证与限制

每一节先列出保证的内容，再列出限制：不做或做不到的事。

### 二进制

保证：

- 二进制是 `/usr/local/bin/garage`，与 role 的路径相同。
- 新二进制在替换任何东西之前先校验：先校验 checksum，再校验它报告的版本。
- 替换是原子的。
- 拒绝降级：从 v2.5.0 起，Garage 的元数据无法回到旧版本。
- 拒绝跳过大版本（v1 到 v3）：Garage 只支持相邻大版本之间的迁移。
- 下载来自 Garage 的发布服务器，设置了 `garage_node_url` 时来自该地址（镜像不需要被信任）；由主机
  下载，或者在 `garage_node_fetch: controller` 时由控制端下载再复制过去（用于无法访问互联网的主机）。

限制：

- 已安装的二进制按它报告的版本比较。同一版本换一个 URL 不会安装任何东西。
- 没有回滚。小版本升级失败时停在失败的节点上：新二进制没通过校验，节点保留旧二进制；通过了，节点运行
  新二进制。
- 架构：x86_64、aarch64、armv6l/armv7l 和 i686，即 Garage 发布的构建。

### 配置

保证：

- 写入任何东西之前，role 检查它依赖的内容：`metadata_dir`、`data_dir`、`replication_factor`、
  `rpc_bind_addr` 和 `[admin]` 的 `api_bind_addr` 已设置；RPC 密钥是 32 字节的十六进制；需要比
  `garage_node_version` 更新的 Garage 才支持的选项（例如 v2.5.0 之前的 `[s3_api] public_endpoint`）
  会被拒绝，因为旧版本会静默忽略它们。
- `garage.toml` 属于 `root:garage`，权限 `0640`。密钥文件属于 `garage:garage`，权限 `0600`：密钥文件能被
  其他用户读取时，Garage 拒绝启动。
- unit 的可写路径和依赖的挂载点跟随 `metadata_dir` 和 `data_dir`。

限制：

- 其余配置由 Garage 在启动时检查：它拒绝的选项会导致启动失败，逐个重启会停在这个节点上。
- 大版本升级到 v3 时拒绝 `db_engine = "fjall"`：Fjall 在 v3 的文件不兼容。先用
  `garage node convert-db` 转换是管理员的步骤。

### 重启

保证：

- 没在运行的节点会被启动。
- 对运行中节点的变更会重启它，在整个 play 范围内一次一个节点。只有重启的节点向集群报告健康后，下一个
  节点才会停止。
- 同一次运行中配置和二进制都有变更时，节点只重启一次。

限制：

- 逐个重启的顺序只在 play 的主机之间。集群中不在 play 里的节点不会被重启，也不会被等待。
- `serial` 分批可以用，但每一批各自是一轮逐个重启。
- Garage 拒绝的重启（错误的选项）会让该节点停着并中止运行：其他节点继续运行旧配置。

### 大版本升级

Garage v2 到 v3（以后的大版本同理）。步骤遵循 Garage 的
[升级指南](https://garagehq.deuxfleurs.fr/documentation/operations/upgrading/)。

保证：

- 只有当 `garage_node_version` 跨越大版本，**并且** `garage_node_major_upgrade: true` 时，才会
  执行大版本升级。否则在任何改动之前就拒绝。
- 改动之前先检查：集群的每个节点都在 play 中，没有被 `serial` 漏掉；所有节点运行同一版本；集群健康；
  没有节点使用 `db_engine = "fjall"`。
- 然后：`garage repair --all-nodes --yes tables`、`garage meta snapshot --all`，所有节点停止，所有节点
  换上新二进制，所有节点启动，运行等待集群恢复健康。该版本的 Garage 指南要求的迁移步骤在此时执行。
- 停机时间就是所有节点停止再启动的时间，健康的集群一分钟以内。

限制：

- 快照是 Garage 自己的（`metadata_dir/snapshots`，保留最近两个）。把它备份到别处、升级失败后恢复，
  是管理员的事。
- 事先停掉流量（反向代理、客户端）是管理员的事。
- 大版本升级失败不会回滚：如何处理由该版本的指南决定。

### 集群引导

保证：

- play 中的每个节点都连接到其他每个节点。
- 只有当集群还没有 layout（layout 版本为 0）时才应用首个 layout。play 中的每个节点都必须先连接上，
  并且每个节点都要有 zone 和 capacity，或者是 gateway。
- 已有 layout 的集群永远不会被改动。
- `cluster` 在节点上经 RPC 运行 `garage` CLI：只需要 RPC 密钥，不需要 admin token。CLI 的输出由插件解析，
  插件针对每个受支持的大版本做单元测试。

限制：

- 之后的 layout 变更（容量、增删节点、重新平衡）都是管理员用 `garage layout` 完成的事。
- 集群的节点就是 play 的主机。不在 play 中的节点不会被连接。

### 从 role 接管主机

由 `eyebrowkang.garage` role（1.x）部署的主机会被原地接管：不重装，不复制数据。

保证：

- collection 使用 role 的默认路径和名称：`/usr/local/bin/garage`、`/etc/garage/garage.toml`、
  `garage.service`、`garage` 用户和用户组、`/var/lib/garage`。
- 用其他值部署的主机（改过默认值的 `garage_user`、`garage_config_dir` 等）会被拒绝，并说明哪个值不同。
- `metadata_dir` 和 `data_dir` 必须与现有 `garage.toml` 中的相同，否则拒绝运行（见原则 6）。节点保留
  它的身份、layout 和数据。
- inventory 中仍然设置着的 role 变量（`garage_version`、`garage_rpc_secret` 等）会让运行失败，列出这些
  变量，并指向迁移指南（待编写：每个 role 变量及其替代写法）。否则 collection 不读取的变量会被静默忽略。
- 接管会删除 role 留下而 collection 不用的东西：`/etc/garage/garage.env` 和
  `/usr/local/bin/garage.bak`。
- 第一次运行会逐个重启每个节点一次：unit 和 `garage.toml` 会变化（密钥移到单独的文件）。
- 接管和升级可以在同一次运行中进行。测试覆盖两种顺序。

限制：

- 不支持 role 1.0 之前的版本部署的主机，或者手动部署的主机。
- 自定义的 `garage_config_template` 需要手动转换为 `garage_node_settings`。

### 移除

保证：

- `node` 的 `absent` 停止并禁用 Garage，删除二进制、unit 和 `/etc/garage/`（`garage.toml` 和密钥文件）。
- `metadata_dir` 和 `data_dir` 保留，拥有它们的 `garage` 用户和用户组也保留：重新创建的用户可能得到不同的
  ID，重装后的节点就读不了保留下来的数据。

限制：

- 移除一个在 layout 中仍有角色的节点，集群就会失去它。先把它移出 layout 是管理员的事。

### 安全

保证：

- 密钥在单独的文件中，从不出现在 `garage.toml`、命令行或任务输出中。
- Garage 以 `garage` 系统用户运行，带有 unit 的加固设置（`ProtectSystem=strict`、`NoNewPrivileges=` 等）。

限制：

- 从 v2.6.0 起，admin API 的监听地址同时提供 Web 管理界面。谁能访问它是管理员的事：把 `[admin]
  api_bind_addr` 绑定到内网地址，或用防火墙限制。

## role 之间的接口

- 固定的路径和名称：`/usr/local/bin/garage`、`/etc/garage/`（`garage.toml`、`secrets/`）、
  `garage.service`、`garage` 用户和用户组、`/var/lib/garage`。
- 以上全部归 `node` 所有。一个节点是一个 role，因为它的二进制和配置一起变化：大版本升级要在同一次停机中
  用新配置启动新二进制，一次运行也只为所有变更重启节点一次。
- `cluster` 从运行中的节点读取节点身份。它从不重启节点，依赖 `node` role 的路径和一个运行中的节点。
- 在同一个 play 中：先 `node`，再 `cluster`。

改变其中任何一项都是破坏性变更（1.0 之后：主版本号升级）。

## 支持的平台与测试

- 任何带 systemd 的 Linux。测试的发行版与 role 声明的一致：Debian、Ubuntu、Enterprise Linux 8/9/10、
  Fedora、Arch Linux、openSUSE。
- 主机要提供 ansible-core 能用的 Python：在 Enterprise Linux 8 上，平台自带的 Python 3.6 不行。
- 所有场景都在 Docker（systemd 容器）中运行，所以都能在 CI 中运行：每个发行版一个单节点；一个三节点
  集群；从 role 接管；小版本升级；v2 到 v3 的大版本升级；移除；非法输入。
- 一个 Vagrant 场景在发布前于本地运行：在真实虚拟机上的三节点集群。
- 解析 Garage 的输出和生成 `garage.toml` 用插件实现，并有单元测试。

## 升级本 collection

- 1.0 之前的版本都是开发版本，版本之间不做任何迁移：主机重新安装。
- 从 1.0 开始，改变磁盘上内容的版本负责从上一个版本迁移主机，并保留这个迁移直到下一个主版本。
- 支持新的 Garage 大版本由新的 collection 版本完成；放弃支持某个大版本是 collection 的主版本升级。

## 不在范围内的

### 不管 bucket、key 和 admin token

它们是集群的内容，不是集群的部署。用 CLI、admin API 和 Web 界面管理它们。

### 首个之后不改 layout

改变容量或成员会移动数据。何时做、做多少由管理员用 `garage layout` 决定。

### 不做备份和恢复

大版本升级会做 Garage 自己的元数据快照。备份和恢复数据与元数据是管理员的事。

### 不支持软件包、容器和 Kubernetes

只支持 systemd 下的官方静态二进制。Kubernetes 由 Garage 的 Helm chart 覆盖。

### 不管防火墙、反向代理和 TLS

Garage 的 API 使用明文 HTTP。前面放什么由主机决定。
