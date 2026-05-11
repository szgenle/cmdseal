# 变更日志

> 英文版：[CHANGELOG.md](./CHANGELOG.md)

本文件记录 `cmdseal` 所有值得关注的变更。

格式大致遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，
版本号在 `cmdseal`（CLI + runner）层面遵循
[语义化版本](https://semver.org/lang/zh-CN/spec/v2.0.0.html)。
[`pyproject.toml`](./pyproject.toml) 中的 `cmdseal-gui`（PySide6
前端包）拥有独立的版本号，不需要与之保持同步。

## [Unreleased]

### 新增

- **`cmdseal gc` 子命令**。回收磁盘上已不存在的 sealed binary
  所对应的孤儿 `cmdseal.*` keychain 条目，避免它们在「钥匙
  串访问.app」中积累。命令按 `kSecAttrComment` 元数据将每条
  条目分类为 **live** / **orphan** / **legacy**（零 ACL 弹窗）。
  孤儿条目会被报告，并在用户确认后删除（`--dry-run`
  仅审计，`--yes` 跳过确认用于 CI）。legacy 条目（v1.1 及
  更早版本封存时还没写入元数据）永不被自动删除，会列
  出以供用户手工处理。输出模式：交互式表格（默认），
  `--json` 适合脚本（默认只读，除非同时传 `--yes`）。
  兑现了 README 「已知限制」中长期挂账的一项。
- **测试**。`tests/test_gc.py`（纯 Python、CI 友好；7 个用例
  涵盖分类、dry-run、交互式 `--yes`、JSON 只读/破坏性分发路径
  以及「无孤儿」快路径）。

### 文档

- **USER_GUIDE §4.4**。新增章节记录 `cmdseal gc` 的判定规则、
  输出示例、退出码契约。双语同步。
- **README 「已知限制」**。原本「计划中：一个 `cmdseal gc`
  子命令」的条目现已指向已交付的命令。双语同步。

## [1.2.1] - 2026-05-05

v1.2 的 GUI 配套版本。将 CLI 端已具备的多段管道能力带到
**两个** PySide6 向导，允许用户可视化地编排管道。

### 新增

- **seal 向导多段编辑器（高级模式）**。*命令模板* 页现已改为
  最多 8 段的编辑框堆叠，配备 `[➕ 添加管道段]` 按钮与
  每段的 `[×]` 删除按钮。每段独立展示 tokens / secrets / args
  解析结果，页底的全局摘要合并段数、跨段 `{{arg:N}}` 集
  和去重后的 secret 名。
- **模板向导多段 chip 编辑器（简化模式）**。*输入命令* 页接受
  最多 8 段管道；*选择运行时参数* 页按段渲染一行 chip，
  `{{arg:N}}` 编号在所有段中全局递增。「试运行整条管道」
  按钮以 `QProcess.setStandardOutputProcess` 串联所有段，
  与 runner 在封装后实际执行的管道语义等价。
- **跨段 secret 合并**。`SecretsPage` 会扫描所有段并去重
  secret 名，与 CLI 的全局编号语义完全一致。
- **按段预览 argv**。`ExecutePage` 将每一段以 `seg N :` 的
  形式单独渲染，secret 统一脱敏为 `***`。
- **`SealRequest.commands: list[str]`**。`gui/backend.py` 在构造
  `cmdseal.py` 命令行时，会以每段一个 `--command` 的方式追加，
  与 CLI 的 `action="append"` 语义对齐。

### 变更

- **命令模板现在在存储层就已打码**。`do_seal` 不再
  将原始命令模板写入 keychain item 的 `kSecAttrComment` 元
  数据，而是先经新增的 `mask_template()` helper 逐段打码，
  在 `template` 与 `segments` 字段里存与 `cmdseal list` 展示完
  全一致的 `***` 脱敏后形式。未脱敏的模板仅存在于 AEAD
  密文内部（只有 sealed binary 能读到）。效果：`cmdseal
  list` / `cmdseal list --json` 不再暴露任何明文 secret，
  无论模板原本如何书写。幂等：对已打码的输入再调一次
  仅返回相同结果，因此旧数据后续如被重新 seal 会自然收敛
  到同一形式。
- **`mask_template()` 打码规则**（权威规范见
  [tests/test_mask_template.py](./tests/test_mask_template.py)
  的 28 个用例）：首 token 保留；`{{arg:N}}` /
  `{{secret:NAME}}` 占位符保留；GNU 长选项（`--foo`）保留，
  `--key=val` 脱敏为 `--key=***`；POSIX 短选项保留精确 2
  字符形式（`-p`）但将 Unix 粘连形式（`-pPass`、`-xzvf`）
  折叠为 `前两字符 + ***`；其他裸 token（包括会泄露文件
  系统布局的绝对路径）脱敏为 `***`。

### 文档

- **第三方许可双语覆盖**。新增
  [`THIRD_PARTY_LICENSES.zh.md`](./THIRD_PARTY_LICENSES.zh.md)
  作为 `THIRD_PARTY_LICENSES.md` 的中文对照版，两份文件
  顶部加上语言切换提示；`README.zh.md` 现在链接到中文版。

### 移除

- **`edit-template` 全链路移除**。按照更严格的“CLI 永远看不到
  明文，GUI 查看明文前必须有一道授权关卡”策略，edit-template
  被整个拿掉：`cmdseal.py` 删除 `do_edit_template()`、
  其 subparser、shim 白名单条目和 main dispatch 分支；
  `gui/backend.py::edit_template()` 与 Runner 管理窗的右键
  “修改模板…”菜单项 / 对话框同步移除；`tests/test_edit_template.py`
  删除；USER_GUIDE 的 §3.2、§4.4、§9.2 与附录 A 的
  cheatsheet 一并清理。今后如需改模板，请删除 runner 后重新
  seal。这种做法维持安全模型最简洁，也消除了 AEAD 不可逆
  导致的 secret 名集合不容多改等隐患。

### 修复

- **模板向导的悬挂引用**。v1.2.1 把 `SealRequest.command` 重命名为
  `commands: list[str]` 后，`template_wizard.ExecutionPage._build_request`
  仍然在以 `command=` 关键字传参，导致简化模式向导最后
  一步抛 `TypeError`。现改为 `commands=param_page.templates()`，
  走多段路径重新对齐。
- **`cmdseal.py edit-template` 子命令真正落地**。Runner 管理窗口的
  右键“修改模板…”与 [`gui/backend.py::edit_template`](./gui/backend.py)
  一直在调用 `python3 cmdseal.py edit-template …`，但 CLI 只声明了
  `seal / rotate / list / delete` 四个子命令。更隐蔽的是，
  `parse_args` 的向后兼容 shim 会把未识别的首 token 默默改写为
  `seal` 的参数，产生“`seal`: the following arguments are required:
  --output”这样的误导性报错，而非“invalid choice”。本次修复：
    - 新增 `do_edit_template(args)`：按 `--service` 定位旧 item，
      从其 `kSecAttrComment` 元数据读出 `output_path / label /
      account / secret_names`；强制新模板的 `{{secret:NAME}}` 集合
      与旧集合一致；然后委托 `do_seal(old_service_to_delete=…)`
      完成一次原子的“生成新 K → 重编译 → 重签名 → 替换 keychain
      item”流程。
    - Legacy 条目（无 comment 元数据）直接按确定性错误信息拒绝。
    - shim 白名单补上 `"edit-template"`，未来任何拼写错误会触发
      `argparse: invalid choice`，而不是被吞入 `seal` 解析。

### 安全

- **安全姿态无变化**。GUI 仍仅作为 `cmdseal.py` 的薄包装，
  不复制任何加密 / 分发逻辑。与 CLI 之间的 `--command` 契约
  严格保持，v1.2 runner 侧的所有保障（无 shell、绝对路径、
  `DYLD_*` 剥离、hardened runtime）在多段场景下数值不变。
- **管道试运行不经 shell**。模板向导的「试运行整条管道」
  按钮走 `QProcess` 串联图；在单段里写的 `|` 字符不会被当作
  管道分隔符（顶部警示条会提醒用户改用 `[➕ 添加管道段]`）。

### 兼容性

- 任一模式的单段向导会话产出的 CLI 调用字节级等价 v1.1。
- `SealRequest.command` 保留为只读兼容属性（返回首段），
  避免破坏现有的日志 / 预览调用链。
- `build_template(tokens, selected)` 保留为 `build_template_many(
  [tokens], [selected])` 的薄封装；原有单元测试套件无需改动即全部通过。

## [1.2.0] - 2026-05-05

管道支持版本。在保留 v1.1 全部安全模型（运行时完全不经 shell、
绝对路径、剥离 `DYLD_*`、hardened runtime）的前提下，为 sealed 二进制
新增多段管道能力。设计文档：[research/DESIGN.pipe.md](./research/DESIGN.pipe.md)。

### 新增

- **多段 `--command`。** `cmdseal seal` 现在允许多次传入该参数，
  组装成 `cmd_A | cmd_B | ... | cmd_N` 的管道（最多 8 段）。
  `{{arg:N}}` 占位符跨段**全局连续编号**，调用方仍然只看到一份位置
  参数列表。
- **runner 内置管道执行器。** 生成的 runner 在 C 代码里用
  `pipe()`+`fork()`+`dup2()` 自建调度（见 `runner_aead_template.c`
  中的 `run_pipeline()`）。**运行时完全不调用 shell**；每段仍走
  `execv()`，并继承 v1.1 的安全加固（绝对路径校验、fork 前剥离
  `DYLD_*` / `LD_*`）。
- **pipefail 等价退出码语义。** 任一段非零退出，sealed 二进制
  便以**最左侧**失败段的退出码退出；后续段仍会执行完毕，与 shell 的
  `set -o pipefail` 一致。安全工具应当大声失败。
- **v1.1 字节级兼容。** 单个 `--command` 产出的明文 blob 与 v1.1
  字节一致，runner 走不 `fork` 的快路径。现有用户零回归风险。
- **测试。** 新增 `tests/test_pipe_serialize.py`（纯 Python，CI 友好；
  12 个 case 覆盖字节布局、v1.1 兼容、跨段 `{{arg:N}}`）与
  `tests/test_v12_pipe_e2e.sh`（交互式 e2e；7 个 case 覆盖单/双/三段
  管道及完整退出码矩阵）。

### 安全

- 管道功能完全由 runner 的 C 代码实现。用户在 `{{arg:N}}` 值里注入的
  任何 shell 元字符（`;`、`$(...)`、反引号、`>` 等）仍然**无效**，
  因为运行时没有任何字符串会经过 `/bin/sh` —— 它们只是某一段 `argv`
  槽位里的字节串。

### 明确不做（v1.2）

- 不支持 shell 重定向（`>`、`<`）、逻辑串联（`&&`、`||`、`;`）、
  stderr 合并（`2>&1`）、变量/命令替换、glob 展开。这些特性**永久
  拒绝**，因为它们会重新打开管道设计刻意规避的注入面。
- 多段模板的 GUI 可视化编辑推迟到 v1.2.1，独立跟踪。

## [1.1.0] - 2026-05-04

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
- **第三方许可披露**：`THIRD_PARTY_LICENSES.md` / `THIRD_PARTY_LICENSES.zh.md`，用于 PySide6
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

[1.2.0]: https://github.com/szgenle/cmdseal/releases/tag/v1.2.0
[1.1.0]: https://github.com/szgenle/cmdseal/releases/tag/v1.1.0
