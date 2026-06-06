# cmdseal 使用指南

> **面向用户的完整操作手册** —— 从入门到高级用法

---

## 目录

- [1. 快速开始](#1-快速开始)
  - [1.1 GUI 用户（推荐）](#11-gui-用户推荐)
  - [1.2 CLI 用户（高级）](#12-cli-用户高级)
- [2. GUI 封存向导详解](#2-gui-封存向导详解)
  - [2.1 启动向导](#21-启动向导)
  - [2.2 第一步：命令模板](#22-第一步命令模板)
  - [2.3 第二步：Secret 采集](#23-第二步secret-采集)
  - [2.4 第三步：选项配置](#24-第三步选项配置)
  - [2.5 第四步：执行与预览](#25-第四步执行与预览)
  - [2.6 从命令生成模板（简化入口）](#26-从命令生成模板简化入口)
- [3. Runner 管理](#3-runner-管理)
  - [3.1 查看 Runner 列表](#31-查看-runner-列表)
  - [3.2 删除 Runner](#32-删除-runner)
- [4. CLI 命令参考](#4-cli-命令参考)
  - [4.1 seal - 封存命令](#41-seal---封存命令)
  - [4.2 rotate - 轮换密钥](#42-rotate---轮换密钥)
  - [4.3 list - 列出 Runner](#43-list---列出-runner)
  - [4.4 gc - 收割孤儿 Keychain 条目](#44-gc---收割孤儿-keychain-条目)
- [5. 占位符语法](#5-占位符语法)
  - [5.1 基本规则](#51-基本规则)
  - [5.2 示例场景](#52-示例场景)
  - [5.3 常见错误](#53-常见错误)
- [6. 安全模型](#6-安全模型)
  - [6.1 防护范围](#61-防护范围)
  - [6.2 不防护的场景](#62-不防护的场景)
  - [6.3 首次运行对话框](#63-首次运行对话框)
- [7. 日常维护](#7-日常维护)
  - [7.1 查看 Keychain 条目](#71-查看-keychain-条目)
  - [7.2 清理退役的 Runner](#72-清理退役的-runner)
  - [7.3 检查二进制元数据](#73-检查二进制元数据)
- [8. 故障排查](#8-故障排查)
  - [8.1 首次运行弹窗被拒绝](#81-首次运行弹窗被拒绝)
  - [8.2 运行时找不到程序](#82-运行时找不到程序)
  - [8.3 GUI 无法启动](#83-gui-无法启动)
- [9. 最佳实践](#9-最佳实践)
  - [9.1 命名规范](#91-命名规范)
  - [9.2 密钥轮换策略](#92-密钥轮换策略)
  - [9.3 团队协作](#93-团队协作)

---

## 1. 快速开始

### 1.1 GUI 用户（推荐）

**适用人群**：普通用户、不喜欢命令行的用户

```bash
# 1. 克隆仓库
git clone https://github.com/szgenle/cmdseal.git
cd cmdseal

# 2. 安装依赖
make sync

# 3. 构建 GUI 应用
make app

# 4. 启动应用
open dist/cmdseal.app
```

✅ **完成！** 现在你将看到封存向导的图形界面。

> 🔰 **初次使用建议：** 主窗口点 **「从命令生成模板…」**（详见 [§ 2.6](#26-从命令生成模板简化入口)）——
> 照着顶部示例 `echo hello world` 跑一遍全流程，认识运行时参数概念后再回头看密码味更重的封存向导。

---

### 1.2 CLI 用户（高级）

**适用人群**：开发者、CI/CD 管道、自动化脚本

```bash
# 1. 克隆仓库
git clone https://github.com/szgenle/cmdseal.git
cd cmdseal

# 2. 封存一个命令（交互式输入密码）
python3 cmdseal.py seal \
    --command 'sh -c "7zz a -tzip -mem=AES256 -p\"$1\" \"$2\" \"$3\"" _ {{secret:zippw}} {{arg:1}} {{arg:2}}' \
    --output ./my_sealed_zip

# 3. 使用封存的二进制
./my_sealed_zip /tmp/output.zip /path/to/secret_file.txt
```

> 💡 **提示**：GUI 用户请运行 `make app`；CLI 适用于脚本编写、CI 管道和审计。

---

## 2. GUI 封存向导详解

### 2.1 启动向导

```bash
# 开发模式（需要 Python 环境）
make run

# 或启动构建好的 .app
open dist/cmdseal.app
```

---

### 2.2 第一步：命令模板

**你要做什么**：输入要封存的命令模板

**支持的语法**：

| 类型 | 示例 | 说明 |
|------|------|------|
| **字面量密码** | `7zz a -tzip -mem=AES256 -pmypassword` | 直接写入命令（简单但不推荐用于高安全场景） |
| **Secret 占位符** | `{{secret:zippw}}` | 封存时采集，不暴露给 shell history |
| **运行时参数** | `{{arg:1}}` `{{arg:2}}` | 运行时由用户传入 |

**示例**：

```bash
# 示例 1：字面量密码（简单场景）
7zz a -tzip -mem=AES256 -pmypassword {{arg:1}} {{arg:2}}

# 示例 2：Secret 占位符（推荐）
zhmm-cli --pwd {{secret:master}} -s {{arg:1}}

# 示例 3：混合使用
openssl enc -aes-256-cbc -k {{secret:key}} -in {{arg:1}} -out {{arg:2}}
```

**多段管道（v1.2.1）**：

命令模板页允许点击 **➕ 添加管道段** 下拉出新的编辑框，最多 8 段。
运行时 runner 会自建 `pipe()` / `fork()` / `dup2()` 将前一段的 stdout
接到下一段的 stdin，**全程不经过 shell**。

- `{{arg:N}}` 跨段全局编号：首段用 `{{arg:1}}`、二段用 `{{arg:2}}`，
  运行时依次传递 `./bin a b` 即可。
- 退出码采用 pipefail 等价语义（**最左失败者胜**）。
- 页底摘要行会实时显示 `segments=N/8`、跨段总 tokens、合并后的 secret
  名与全局 arg 集，文稿级地验证你的设计。
- 首段不可删；其余段在段头点 `×` 删除。空段会被自动剔除后传给 CLI。

**智能警告**：

- ⚠️ 检测到未包裹的 `secret:`/`arg:` → 请用 `{{secret:NAME}}` 或 `{{arg:N}}`
- ℹ️ 首 token 非绝对路径 → 将在封存时解析为绝对路径
- ⚠️ 首 token 是占位符 → 请确保运行时传入绝对路径

> 💡 **想要 Tab 路径补全？** 封存向导暂未提供；若你是初学者或不需要 `{{secret:}}`，
> 请改用主窗口的「从命令生成模板…」入口（详见 [§ 2.6](#26-从命令生成模板简化入口)）。

---

### 2.3 第二步：Secret 采集

**何时出现**：仅当命令模板中包含 `{{secret:NAME}}` 时

**你要做什么**：为每个 secret 占位符输入实际值

**特性**：
- 🔒 密码输入框默认隐藏（点击"显示"可查看）
- ✅ 必填项，未填写时"下一步"按钮禁用
- 🚀 无 `{{secret:*}}` 时自动跳过此页

**示例**：

如果你的命令是：
```bash
zhmm-cli --pwd {{secret:master}} --api-key {{secret:apikey}}
```

此页将显示两个输入框：
1. `master` - 输入主密码
2. `apikey` - 输入 API 密钥

---

### 2.4 第三步：选项配置

**你要填写**：

| 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|
| **输出路径** | ✅ | 生成的二进制文件路径 | `~/bin/my_runner` |
| **标签** | ❌ | 便于识别的标签名 | `生产环境 ZIP 加密` |
| **签名身份** | ❌ | Developer ID（可选） | `Developer ID Application: ...` |

**默认行为**：
- 不填标签 → 使用输出文件名
- 不填签名 → 使用 ad-hoc 签名（足够安全）

---

### 2.5 第四步：执行与预览

**你将看到**：

1. **命令预览** - 最终封存的命令（含解析后的绝对路径）
2. **Secret 列表** - 已采集的 secret（值已隐藏）
3. **运行时参数** - 需要传入的参数数量

**操作**：
- 点击 **“执行”** → 后台运行 `cmdseal.py seal`
- 进度条显示构建状态
- 完成后显示成功消息和文件位置

---

### 2.6 从命令生成模板（简化入口）

**适用对象**：
- 初次使用、不了解 `{{secret:}}`/`{{arg:}}` 语法的用户
- 已有一条可直接执行的命令，只想点选“哪几个参数保留给运行时传入”

**入口**：主窗口 → **「从命令生成模板…」** 按钮

向导共 4 页，比 § 2.2 的封存向导更直观：用户先把命令写对并试跑成功，再点选运行时参数。

---

#### 2.6.1 第一步：命令输入 + 试运行

**顶部常驻示例**：`echo hello world`。点「填入示例」一键填充，然后「试运行」走通整条流程。

> ⚠ **不走 shell**：每段命令直接 `execv` 执行，环境变量 `$VAR`、重定向 `>`、通配符 `*` 都不会展开。需要 shell 特性请自己包 `sh -c`。
>
> ➕ **多段管道（v1.2.2）**：要拼接 `cmd1 | cmd2 | cmd3`，请点「➕ 添加管道段」而非在单段里写 `|`（管道不经 shell，与 runner 在封装后实际执行的路径一致）。硬上限 8 段。

**验证规则**：
- 静态检查（每段各自）：`shlex` 合法 + 首 token 在 PATH 中或为绝对可执行文件
- 动态验证：**必须**点「试运行整条管道」且所有段 exit code = 0，才能进入下一步
- 多段走 `QProcess.setStandardOutputProcess` 串联（`proc[i].stdout → proc[i+1].stdin`），与 v1.2 runner 在封装后的执行语义等价；pipefail 等价——任一段失败则整条验证失败
- 试运行有 10 秒超时；任一段被修改，“已验证”状态立即失效

**Tab 路径补全**（bash 风格）：

| 情形 | 行为 |
|------|------|
| 光标前 token 以 `/`、`~`、`./`、`../` 开头 | 触发路径补全 |
| 唯一匹配 | 直接补全，目录尾随 `/` |
| 多个匹配 | 先补到最长公共前缀；再按一次 Tab 列出候选 |
| 非路径 token | Tab 切焦点到下一个控件（和常规表单一致） |

`~/` 前缀会保留（不会被展开成绝对 `$HOME` 写回输入框）。

---

#### 2.6.2 第二步：选择运行时参数

命令的每个 token 被切片为可点选的“chip”：

- 白底 = 字面量（封入产物中）
- 蓝底 = 运行时参数（按出现顺序编号为 `{{arg:1}}`、`{{arg:2}}` …）
- 未选中的 token 会走 `shlex.quote` 保护，含空格/特殊字符的字面量不会被破坏
- 选中首 token 会给出警告：运行时需传入绝对可执行路径

**多段时（v1.2.2）**：每段单独一行 chip，但 `{{arg:N}}` 编号在**所有段**中全局递增。例如第一段选了 2 个 token，第二段的首个选中 token 就是 `{{arg:3}}`；运行时亦按 `seal_xxx arg1 arg2 arg3 …` 的顺序跨段分发。这策略与 seal 向导（高级模式）下的 `_scan_placeholders_many` 规则对齐。

下方实时展示每段的最终模板：

```text
段 1: /bin/echo {{arg:1}}
段 2: /usr/bin/tr a-z A-Z
段 3: /usr/bin/zip {{arg:2}} -
```

---

#### 2.6.3 第三步：保存位置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| **输出路径** | `~/cmdseal/bin/seal_<原命令名>` | 首次使用自动创建目录；文件名加 `seal_` 前缀区分原命令（与 demo 的 `seal_zip` 一致） |
| **Label** | 留空 | 留空则按输出文件名自动生成 |
| **Keychain 账号** | `$USER` | 存放 AEAD 密钥的账号名 |

若要全局调用，点「浏览…」手动改成 `/usr/local/bin/seal_xxx`（该目录写入可能需 sudo）。

---

#### 2.6.4 第四步：执行

点击 **「执行」** 后后台调用 `cmdseal.py seal`，日志实时输出到页面。完成后：

```bash
# 验证产物
~/cmdseal/bin/seal_echo hello world   # → 输出 hello world

# 在 Runner 管理窗里重新刷新，可看到新增的 seal_echo
```

> 💡 与§ 2 的差异：本入口不暴露 `{{secret:}}`。如你需要密码采集（避免出现在 history 里），请回头使用 [§ 2](#2-gui-封存向导详解) 的封存向导。

---

## 3. Runner 管理

### 3.1 查看 Runner 列表

**入口**：主窗口 → "管理 runner…"

**功能**：
- 📋 表格展示所有已封存的 runner
- 🔍 4 列信息：
  - **Label** - 标签名
  - **Service** - Keychain service 名称
  - **Template** - 命令模板（位置参数显示为 `***`）
  - **Created** - 创建时间

**操作**：
- 点击 "刷新" 按钮重新扫描 keychain
- 右键点击 runner 打开上下文菜单

---

### 3.2 删除 Runner

**操作步骤**：

1. 打开 Runner 管理窗
2. 右键选择目标 runner
3. 点击 **"删除…"**
4. 确认删除

**联动清理**：
- ✅ 删除 Keychain 条目（`cmdseal.<hash>.K`）
- ✅ 删除磁盘上的二进制文件
- ⚠️ 确认前请备份重要数据

---

## 4. CLI 命令参考

### 4.1 seal - 封存命令

**基本用法**：

```bash
python3 cmdseal.py seal \
    --command 'COMMAND_TEMPLATE' \
    --output OUTPUT_PATH \
    [--label LABEL] \
    [--user USERNAME] \
    [--sign IDENTITY]
```

**参数说明**：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--command` | ✅ | 命令模板（含占位符）。**可多次传入**，用于组装管道（v1.2）。 |
| `--output` | ✅ | 输出二进制路径 |
| `--label` | ❌ | 标签名（默认：输出文件名） |
| `--user` | ❌ | Keychain 所有者（默认：当前用户） |
| `--sign` | ❌ | 签名身份（默认：ad-hoc） |

**示例**：

```bash
# 示例 1：基本封存
python3 cmdseal.py seal \
    --command 'sh -c "7zz a -tzip -mem=AES256 -p\"$1\" \"$2\" \"$3\"" _ {{secret:zippw}} {{arg:1}} {{arg:2}}' \
    --output ./seal_zip

# 示例 2：带标签和用户
python3 cmdseal.py seal \
    --command 'openssl enc -aes-256-cbc -k {{secret:key}} -in {{arg:1}}' \
    --output ./encrypt_file \
    --label "生产加密工具" \
    --user $(whoami)

# 示例 3：Developer ID 签名
python3 cmdseal.py seal \
    --command 'my-command {{arg:1}}' \
    --output ./my_runner \
    --sign "Developer ID Application: Your Name (TEAM_ID)"

# 示例 4：多段管道（v1.2）—— 段与段之间以 stdout→stdin 相连。
# 每一段传一次 --command（最多 8 段）。管道由 runner 的 C 代码
# 实现，运行时完全不调用 shell。{{arg:N}} 编号跨段全局连续。
python3 cmdseal.py seal \
    --command '/usr/local/bin/zhmm_cmd -s {{arg:1}} --once' \
    --command '/usr/bin/zip query_result.zip -' \
    --output ./zhmm_pack

# sealed 二进制以**最左侧**失败段的退出码退出（pipefail 等价）；
# 后续段仍会执行完毕。
./zhmm_pack csj
```

---

### 4.2 rotate - 轮换密钥

**用途**：生成新密钥，无需重新构建模板

```bash
python3 cmdseal.py rotate ./seal_zip
```

**执行过程**：
1. 生成新的 AES-256 密钥
2. 重写 AEAD 密文
3. 重新签名二进制
4. 原子性替换 keychain 条目

**特性**：
- ⚡ 约 1 秒完成
- 🔇 完全静默，无需用户交互
- 🔒 原子性操作，无中间状态

---

### 4.3 list - 列出 Runner

**基本用法**：

```bash
# 表格输出
python3 cmdseal.py list

# JSON 输出（适合脚本处理）
python3 cmdseal.py list --json
```

**输出示例**：

```
Label              Service                          Template
────────────────── ──────────────────────────────── ─────────────────────────
生产加密工具       cmdseal.a1b2c3.K                 openssl enc -aes-256-cbc -k *** -in {{arg:1}}
ZIP 加密           cmdseal.d4e5f6.K                 sh -c "7zz a -tzip -mem=AES256 ..." {{secret:zippw}} {{arg:1}} {{arg:2}}
```

**字段说明**：
- **Label** - 标签名
- **Service** - Keychain service 名称
- **Template** - 命令模板（位置参数已掩码为 `***`）

---

### 4.4 gc - 收割孤儿 Keychain 条目

当某个封存二进制被从磁盘上删除（例如用 `rm`）时，
它对应的 `cmdseal.<hash>.K` keychain 条目会被留在原地——
这条 ACL 绑定的 `cdhash` 已经没有文件对应了。这些条目
无害（ACL 仍然拒绝任何 caller 读取），但会在「钥匙
串访问.app」中积累。`gc` 子命令用来回收它们。

**判定规则**：`cmdseal list` 返回的每条记录按 `kSecAttrComment`
元数据分类（读这条元数据不会触发 ACL 弹窗，见 DESIGN.md §9）：

| 分类      | 条件                                       | gc 动作             |
|-----------|--------------------------------------------|---------------------|
| **live**  | `output_path` 对应的文件存在               | 保留                |
| **orphan**| `output_path` 已填但文件已消失             | 提议删除            |
| **legacy**| 没有元数据（v1.1 之前的条目）              | 报告，由用户手工处理  |

legacy 条目永远不被自动删除——没有元数据我们无法知道它对应哪
个二进制，自动扫掉会有误杀仍在使用的 runner 的风险。

**基本用法**：

```bash
# 1. 先审计（只读，不确认不删除）：
python3 cmdseal.py gc --dry-run

# 2. 交互式回收（会问「Delete these N items? [y/N]」）：
python3 cmdseal.py gc

# 3. 非交互（脚本 / cron）：
python3 cmdseal.py gc --yes

# 4. 机读 JSON 审计输出（默认只读，除非同时传 --yes）：
python3 cmdseal.py gc --dry-run --json
```

**输出示例**（审计模式）：

```
scanned 3 sealed runner(s) with prefix 'cmdseal.':
  live      : 1
  orphaned  : 1
  legacy    : 1  (no metadata; not eligible for auto-gc)

orphaned keychain items (on-disk binary missing):
  • service     : cmdseal.abc123def456.K
    label       : cmdseal sealed: old_zip
    output_path : /Users/you/bin/old_zip
    template    : sh -c "7zz a -tzip -mem=AES256 ..." *** *** {{arg:1}}
    created     : 2026-03-01T10:00:00+00:00

--dry-run: would delete 1 keychain item(s). Re-run without --dry-run to proceed.
```

**退出码**：`0` 表示成功（包括 dry-run），`1` 表示至少一条调 helper
`delete` 失败。可以安全地从 CI 脚本（`set -e`）调用 `gc --yes`。

**GUI 用户**。*Manage Runners* 窗口（`cmdseal-gui → Runners →
Manage…`）把 `cmdseal gc` 看到的数据搬到了界面上：

- **Status** 列把每一行标为 🟢 *live* / 🟡 *orphan* / ⚫
  *legacy*，孤儿行以琥珀色前景高亮。
- 状态栏汇总（`N 条 · X live · Y orphan · Z legacy`）与 CLI
  的判定规则完全一致。
- **Garbage collect…** 按钮端到端跑 `cmdseal gc`，没有孤儿
  时自动禁用。确认对话框提供一个 **Dry run first** 复选框
  （默认勾选）：勾选后会先以 `--dry-run --json` 再查一次
  CLI，若期间 keychain 状态被并发修改则中止，防止误删。
- 若底层 `cmdseal gc --yes` 非零退出但仍输出合法
  JSON 报告（有的孤儿删成功、有的失败），GUI 会弹
  *批量回收部分失败* 的 warning 对话框，而不是误报
  成功。正规恢复动作：点 **Refresh** 刷新表格，看哪几
  条仍然残留。

GUI 从不直接访问 keychain，所有操作都通过 subprocess 调
`cmdseal.py gc --json`——CLI 和 GUI 对 live / orphan / legacy
的判定永远自动对齐。

---

## 5. 占位符语法

### 5.1 基本规则

**占位符必须独占一个 argv 位置**：

```bash
# ✅ 正确：独占 token
--pwd {{secret:mypass}}

# ❌ 错误：混合写法（会被拒绝）
--pwd={{secret:mypass}}

# ✅ 正确：拆成两个 token
--pwd {{secret:mypass}}
```

**占位符类型**：

| 占位符 | 解析时机 | 取值来源 |
|--------|----------|----------|
| `{{secret:NAME}}` | 封存时 | 交互式提示，嵌入 AEAD 密文 |
| `{{arg:N}}` | 运行时 | 生成二进制的 `argv[N]` |
| 其他 token | — | 原样透传 |

---

### 5.2 示例场景

**场景 1：密码管理的 CLI 工具**

```bash
zhmm-cli --pwd {{secret:master}} --search {{arg:1}}
```

运行时：
```bash
./sealed_runner "搜索关键词"
# master 密码已在封存时嵌入，无需传入
```

---

**场景 2：文件加密/解密**

```bash
openssl enc -aes-256-cbc -k {{secret:enc_key}} -in {{arg:1}} -out {{arg:2}}
```

运行时：
```bash
./sealed_runner /path/to/input.txt /path/to/output.enc
```

---

**场景 3：批量操作（字面量密码）**

```bash
# 简单场景：密码不敏感
7zz a -tzip -mem=AES256 -pmypassword {{arg:1}} {{arg:2}}
```

运行时：
```bash
./sealed_runner /tmp/output.zip /path/to/file.txt
```

---

### 5.3 常见错误

**错误 1：裸写占位符**

```bash
# ❌ 错误
zhmm-cli --pwd secret:master

# ✅ 正确
zhmm-cli --pwd {{secret:master}}
```

**错误 2：混合 token**

```bash
# ❌ 错误
--api-key={{secret:key}}

# ✅ 正确
--api-key {{secret:key}}
```

**错误 3：arg 索引从 0 开始**

```bash
# ❌ 错误：没有 {{arg:0}}
my-command {{arg:0}} {{arg:1}}

# ✅ 正确：从 1 开始
my-command {{arg:1}} {{arg:2}}
```

---

## 6. 安全模型

### 6.1 防护范围

✅ **cmdseal 保护你免受**：

1. **通过 argv 或 `ps` 的秘密窃取**
   - 秘密以 AEAD 密文形式嵌入二进制
   - 仅在内存中短暂解密（keychain 获取 → `execv`）

2. **其他进程读取 keychain 条目**
   - macOS ACL 绑定到确切的二进制 cdhash
   - 已验证拦截：`/usr/bin/security`、ad-hoc 签名探测器、位级相同副本

3. **基于 PATH 的程序替换**
   - 运行器使用 `execv` + 封存时的绝对路径
   - 无运行时 `$PATH` 查找

4. **通过环境变量的 Dylib 注入**
   - 运行器剥离 `DYLD_*` 和 `LD_*`
   - 使用 `codesign --options runtime` 签名

---

### 6.2 不防护的场景

❌ **cmdseal 不保护你免受**：

- **root 攻击者** - 可读取任何进程内存、任何 keychain
- **同用户的任意代码执行** - 可调试/转储运行中的二进制
- **构建前的生成机器篡改**
- **目标命令的侧信道攻击** - 例如 `zip` 本身写入日志
- **Linux 或 Windows 上的任何攻击**

> ⚠️ **重要**：cmdseal 是**能力网关**，不是保险库。请诚实地评估你的威胁模型。

---

### 6.3 首次运行对话框

**何时出现**：首次运行新生成的二进制时

**对话框内容**：
- 登录密码输入
- "始终允许" 按钮

**为什么需要**：
- macOS partition-list 握手过程
- 将 keychain 条目绑定到此二进制的 cdhash

**发生频率**：
- 每个封存的二进制 × 每个用户机器 = **仅一次**
- 后续运行完全静默，毫秒级快速

---

## 7. 日常维护

### 7.1 查看 Keychain 条目

```bash
# 查看元数据（不显示密钥值）
security find-generic-password -s cmdseal.<hash>.K

# 示例输出
keychain: "/Users/<you>/Library/Keychains/login.keychain-db"
version: 512
class: "genp"
attributes:
    0x00000007 <blob>="cmdseal.a1b2c3.K"
    "cdhash"<blob>=<SHA256 hash of binary>
```

---

### 7.2 清理退役的 Runner

**方式 1：GUI 删除**（推荐）
1. 打开 Runner 管理窗
2. 右键 → "删除…"
3. 自动清理 keychain + 二进制

**方式 2：手动清理**

```bash
# 1. 删除 keychain 条目
security delete-generic-password -s cmdseal.<hash>.K

# 2. 删除二进制文件
rm /path/to/sealed_binary
```

---

### 7.3 检查二进制元数据

```bash
# 查看嵌入的元数据（无秘密可见）
strings ./seal_zip | grep cmdseal

# 示例输出
cmdseal.a1b2c3.K
{"label":"生产加密工具","created":"2026-05-05T10:30:00"}
```

---

## 8. 故障排查

### 8.1 首次运行弹窗被拒绝

**症状**：运行封存的二进制时报错 "keychain access denied"

**原因**：首次运行时点击了"拒绝"而非"始终允许"

**解决方案**：

```bash
# 1. 删除旧的 keychain 条目
security delete-generic-password -s cmdseal.<hash>.K

# 2. 重新运行二进制
./sealed_binary arg1 arg2

# 3. 这次点击 "始终允许"
```

---

### 8.2 运行时找不到程序

**症状**：报错 "No such file or directory" 或 "command not found"

**原因**：封存时首 token 未解析为绝对路径

**解决方案**：

```bash
# 检查封存时的输出
python3 cmdseal.py seal --command 'my-command {{arg:1}}' --output ./runner
# 应该看到：resolved 'my-command' -> '/usr/local/bin/my-command'

# 如果没看到，确保程序在 PATH 中
which my-command
# 或使用绝对路径
python3 cmdseal.py seal --command '/usr/local/bin/my-command {{arg:1}}' --output ./runner
```

---

### 8.3 GUI 无法启动

**症状**：`make run` 或 `open dist/cmdseal.app` 无响应

**排查步骤**：

```bash
# 1. 检查 PySide6 是否安装
uv run python -c "import PySide6; print(PySide6.__version__)"

# 2. 重新安装依赖
make sync

# 3. 重新构建 .app
make clean
make app

# 4. 查看日志
cat ~/Library/Logs/cmdseal.app.log 2>/dev/null || echo "无日志文件"
```

---

## 9. 最佳实践

### 9.1 命名规范

**标签命名**：

```
{环境}_{用途}_{工具名}

示例：
- 生产_ZIP加密_快速备份
- 开发_API测试_临时工具
- 测试_数据脱敏_批量处理
```

**输出文件命名**：

```
seal_{工具名}_{环境}

示例：
- seal_zip_prod
- seal_encrypt_dev
- seal_decrypt_test
```

---

### 9.2 密钥轮换策略

**建议频率**：

| 场景 | 轮换频率 | 方法 |
|------|----------|------|
| 生产环境 | 每 90 天 | CLI: `rotate`（或 GUI: 删除后重新 seal） |
| 测试环境 | 每 30 天 | 同上 |
| 泄露应急 | 立即 | 同上 |

**轮换检查清单**：

- [ ] 通知所有使用该 runner 的用户
- [ ] 在低峰期执行轮换
- [ ] 验证轮换后二进制正常工作
- [ ] 更新文档中的 runner 信息

---

### 9.3 团队协作

**场景**：多个开发者需要封存相同的命令模板

**方案 1：共享模板文件**

```bash
# 1. 创建模板文件（command_template.txt）
zhmm-cli --pwd {{secret:master}} --search {{arg:1}}

# 2. 团队成员各自封存
python3 cmdseal.py seal \
    --command "$(cat command_template.txt)" \
    --output ./my_runner

# 3. 各自生成独立的二进制和密钥
```

**方案 2：CI/CD 管道集成**

```yaml
# .github/workflows/seal.yml
name: Seal Command
on:
  push:
    paths:
      - 'command_template.txt'

jobs:
  seal:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - run: |
          python3 cmdseal.py seal \
            --command "$(cat command_template.txt)" \
            --output ./sealed_runner
      - uses: actions/upload-artifact@v3
        with:
          name: sealed-runner
          path: ./sealed_runner
```

> ⚠️ **注意**：每个机器生成的二进制是独立的（cdhash 绑定），不能跨机器共享。

---

## 附录

### A. 完整命令参考

```bash
# 封存
python3 cmdseal.py seal --command CMD --output PATH [--label LABEL] [--user USER] [--sign IDENTITY]

# 轮换密钥
python3 cmdseal.py rotate BINARY

# 列出 runner
python3 cmdseal.py list [--json]

# 构建 GUI
make app

# 运行 GUI
make run
```

### B. 文件结构

```
cmdseal/
├── cmdseal.py              # CLI 主程序
├── runner_aead_template.c  # Runner 模板（C 代码）
├── gui/                    # GUI 模块
│   ├── main_window.py      # 主窗口
│   ├── seal_wizard.py      # 封存向导
│   ├── runner_list.py      # Runner 列表
│   └── backend.py          # 后端逻辑
├── demo/                   # 示例
├── tests/                  # 测试
└── local/                  # 个人配置（不提交）
```

### C. 相关文档

- [README.md](../README.md) - 项目介绍
- [DESIGN.md](../DESIGN.md) - 设计文档
- [LICENSE](../LICENSE) - MIT 许可证

---

**文档版本**: v1.1  
**最后更新**: 2026-05-05  
**维护者**: [lioesquieu](https://lioesquieu.github.io/)
