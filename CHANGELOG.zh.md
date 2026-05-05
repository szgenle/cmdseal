# 变更日志

> 英文版：[CHANGELOG.md](./CHANGELOG.md)

本文件记录 `cmdseal` 所有值得关注的变更。

格式大致遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，
版本号在 `cmdseal`（CLI + runner）层面遵循
[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。
[`pyproject.toml`](./pyproject.toml) 中的 `cmdseal-gui`（PySide6
前端包）拥有独立的版本号，不需要与之保持同步。

## [1.1.0] - 未发布

首个公开开源发布。v1.1 是在 v1.0 私有基线之上的一次安全加固
里程碑。

### 新增

- **运行时程序路径绑定。** `cmdseal seal` 会在封装时通过
  `shutil.which` 把裸程序名（如 `zip`）解析为绝对路径，并把
  结果烘焙进 AEAD 密文；runner 完全拒绝任何 `$PATH` 查找。
- **`cmdseal rotate`** 子命令：生成一把新的 AES-256 密钥，
  重写 AEAD 密文，重新签名 sealed 二进制，并原子地替换
  keychain item。无交互、每个 runner 约 1 秒。
- **GUI 中的 runner 管理**：列出所有 sealed runner 及其
  keychain item，支持删除（keychain 条目与磁盘文件会同步清理）。
- **模板向导**（「从一条能跑的命令构建模板」）以及带路径识别
  的参数可视化。
- **偏好设置面板**（`⌘,`），基于 `QSettings` 持久化默认输出
  目录、文件名前缀和 dry-run 超时；模板向导在初始化时
  读取这些默认值。
- **双语文档**：`README.md` / `README.zh.md`、
  `DESIGN.md` / `DESIGN.zh.md`、
  `USER_GUIDE.md` / `USER_GUIDE.zh.md`。
- **`tests/`** 目录：包含无头 GUI 测试
  （`QT_QPA_PLATFORM=offscreen`）和 `test_v11_e2e.sh` 端到端
  安全验证脚本（7 项指标）。
- **第三方许可披露**：`THIRD_PARTY_LICENSES.md`，用于 PySide6
  / Qt LGPL 合规。
- **MIT 协议**文件（`LICENSE`）。

### 安全

- **#2 `execvp` → `execv`。** 生成的 runner 不再在运行时做任何
  `PATH` 查找；底层程序路径是在封装时解析并烘焙进去的绝对
  路径。可防御基于 `PATH` 的程序替换。
- **#3 `DYLD_*` / `LD_*` 环境变量剥离。** `execv` 之前会调用
  `strip_dangerous_env`，因此无论是 sealed 二进制的子进程，
  还是 `cmdseal` 自己 fork 的子进程，都不会继承 dylib 注入
  变量。
- **#4 Hardened runtime。** sealed runner 与 `cmdseal_helper`
  都使用 `codesign --options runtime`（ad-hoc 身份）签名，
  即便 `DYLD_*` 变量被以某种方式重新引入，`dyld` 自身也会
  针对这个二进制忽略它们。
- **Plan D AEAD。** 密钥以 AES-GCM 密文的形式嵌在二进制里，
  仅在 runner 从 keychain 取到密钥到 `execv` 之间的极短
  窗口内，以明文存在于 runner 的地址空间中。
- **Keychain ACL 绑定。** 存储密钥的 partition-list / ACL
  被绑定到 sealed 二进制的 cdhash 上。已经通过位等同副本、
  ad-hoc 签名的探针、`security` 命令直接调用等多种方式验证
  拒绝生效。

### 变更

- GUI seal 向导简化（步骤更少、参数可视化更清晰）；README
  的叙事重心调整为「以开发者自行源码构建」为主要分发模型。
- 仓库主页迁移至 <https://github.com/szgenle/cmdseal>（原先
  的内部镜像已停用）。

### 文档

- README（英文 + 中文）重写，新增明确的 `Security model` 小节，
  说明 cmdseal 保护什么、**不**保护什么。
- 新增 `SECURITY.md` / `SECURITY.zh.md`，包含漏洞报告渠道和
  响应 SLA。

### 已知限制

- 仅以源码形式分发。尚未发布 Developer-ID 签名并公证的
  `.app`；这取决于维护者是否加入 Apple Developer Program
  （通过 GitHub Issue 跟踪）。
- 仅支持 macOS。Linux / Windows 明确不在支持范围内，因为安全
  模型依赖 macOS 的 keychain ACL + cdhash 绑定。

## [1.0.0] - 从未公开打 tag 的预发布基线

早期私有基线，仅作为历史上下文列出。

- AEAD-sealed runner 生成（`cmdseal seal`）。
- 存储于 keychain 的 AES-256 密钥，使用 cdhash 绑定的 ACL。
- 对生成的 runner 做 ad-hoc codesign。
- 首版 PySide6 GUI 及 seal 向导。
- 基于 PyInstaller 的 `.app` 打包流水线。

[1.1.0]: https://github.com/szgenle/cmdseal/releases/tag/v1.1.0
