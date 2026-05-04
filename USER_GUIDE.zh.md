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
- [3. Runner 管理](#3-runner-管理)
  - [3.1 查看 Runner 列表](#31-查看-runner-列表)
  - [3.2 修改模板（密钥轮换）](#32-修改模板密钥轮换)
  - [3.3 删除 Runner](#33-删除-runner)
- [4. CLI 命令参考](#4-cli-命令参考)
  - [4.1 seal - 封存命令](#41-seal---封存命令)
  - [4.2 rotate - 轮换密钥](#42-rotate---轮换密钥)
  - [4.3 list - 列出 Runner](#43-list---列出-runner)
  - [4.4 edit-template - 修改模板](#44-edit-template---修改模板)
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

---

### 1.2 CLI 用户（高级）

**适用人群**：开发者、CI/CD 管道、自动化脚本

```bash
# 1. 克隆仓库
git clone https://github.com/szgenle/cmdseal.git
cd cmdseal

# 2. 封存一个命令（交互式输入密码）
python3 cmdseal.py seal \
    --command 'zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}' \
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
| **字面量密码** | `zip -j -P mypassword` | 直接写入命令（简单但不推荐用于高安全场景） |
| **Secret 占位符** | `{{secret:zippw}}` | 封存时采集，不暴露给 shell history |
| **运行时参数** | `{{arg:1}}` `{{arg:2}}` | 运行时由用户传入 |

**示例**：

```bash
# 示例 1：字面量密码（简单场景）
zip -j -P mypassword {{arg:1}} {{arg:2}}

# 示例 2：Secret 占位符（推荐）
zhmm-cli --pwd {{secret:master}} -s {{arg:1}}

# 示例 3：混合使用
openssl enc -aes-256-cbc -k {{secret:key}} -in {{arg:1}} -out {{arg:2}}
```

**智能警告**：

- ⚠️ 检测到未包裹的 `secret:`/`arg:` → 请用 `{{secret:NAME}}` 或 `{{arg:N}}`
- ℹ️ 首 token 非绝对路径 → 将在封存时解析为绝对路径
- ⚠️ 首 token 是占位符 → 请确保运行时传入绝对路径

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
- 点击 **"执行"** → 后台运行 `cmdseal.py seal`
- 进度条显示构建状态
- 完成后显示成功消息和文件位置

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

### 3.2 修改模板（密钥轮换）

**使用场景**：
- 想更换密钥但不想重新构建二进制
- 想修改命令模板

**操作步骤**：

1. 打开 Runner 管理窗
2. 右键选择目标 runner
3. 点击 **"修改模板…"**
4. 输入新的命令模板
5. 如果有 `{{secret:*}}`，会提示重新输入
6. 点击 "保存" → 自动完成：
   - ✅ 重新编译二进制
   - ✅ 生成新密钥 K
   - ✅ 删除旧 service
   - ✅ 轮换 cdhash + ACL

**优势**：
- 🚀 无需用户交互，约 1 秒完成
- 🔒 原子性操作，不会出现中间状态
- ✅ 零授权弹窗（owner 身份操作）

---

### 3.3 删除 Runner

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
| `--command` | ✅ | 命令模板（含占位符） |
| `--output` | ✅ | 输出二进制路径 |
| `--label` | ❌ | 标签名（默认：输出文件名） |
| `--user` | ❌ | Keychain 所有者（默认：当前用户） |
| `--sign` | ❌ | 签名身份（默认：ad-hoc） |

**示例**：

```bash
# 示例 1：基本封存
python3 cmdseal.py seal \
    --command 'zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}' \
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
ZIP 加密           cmdseal.d4e5f6.K                 zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}
```

**字段说明**：
- **Label** - 标签名
- **Service** - Keychain service 名称
- **Template** - 命令模板（位置参数已掩码为 `***`）

---

### 4.4 edit-template - 修改模板

**用途**：CLI 方式的模板修改（等同于 GUI 的"修改模板…"）

```bash
python3 cmdseal.py edit-template ./seal_zip --new-command 'NEW_COMMAND'
```

**参数**：

| 参数 | 必填 | 说明 |
|------|------|------|
| `BINARY` | ✅ | 要修改的二进制路径 |
| `--new-command` | ✅ | 新命令模板 |

**示例**：

```bash
python3 cmdseal.py edit-template ./seal_zip \
    --new-command 'zip -j -P {{secret:newzippw}} {{arg:1}} {{arg:2}}'
```

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
zip -j -P mypassword {{arg:1}} {{arg:2}}
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
keychain: "/Users/ws/Library/Keychains/login.keychain-db"
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
| 生产环境 | 每 90 天 | GUI: 右键 → 修改模板 / CLI: `rotate` |
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

# 修改模板
python3 cmdseal.py edit-template BINARY --new-command CMD

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
**维护者**: szgenle
