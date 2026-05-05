# cmdseal

> *面向 AI 智能体时代的能力网关。*
> *让你的 AI 智能体**能调用**敏感命令，却**拿不到**背后的秘密。*

[English version](./README.md) · [DESIGN.md](./DESIGN.md) · [使用指南](./USER_GUIDE.zh.md)

`cmdseal` 将命令模板和秘密值转换为一个独立的 macOS 二进制文件。该二进制文件可以执行它被封存时的确切命令——并且**只能**执行那个命令——即使对运行它的用户也不会泄露秘密。

```
命令模板  ─┐
秘密值   ────┼─►  AEAD 封存的运行器 (C)  ──►  ad-hoc 签名的二进制
           │                                 │
           └──  AES-256 密钥 K  ──►  login.keychain ACL 绑定到此二进制的 cdhash
```

使用场景：你希望设备上的 AI 智能体（或脚本管道）能够调用 `zhmm_cmd --pwd ... --search <term>`，而智能体永远看不到主密码。

## 状态

- ✅ CLI 端到端已可用（macOS 13+，已在 14 / 15 / 26 上测试）
- ✅ GUI（PySide6）封存向导 — 可选功能，从同一仓库启动
- ✅ 通过 `make app` 生成 `.app` 包（PyInstaller）
- ⚠️ 目前仅支持 macOS（Linux / Windows 是未来工作）
- ⚠️ 以**源码**形式分发；尚未提供 Developer ID 签名的发布版本

## 环境要求

- macOS（Apple Silicon 或 Intel；在 darwin 24+ 上测试）
- Xcode Command Line Tools（`cc`, `codesign`）
- `/usr/bin/security`（macOS 自带）
- Python 3.11+（CLI 仅使用标准库）
- [`uv`](https://github.com/astral-sh/uv) — 用于 GUI / `.app` 构建
  （如果仅使用 CLI 可跳过）

## 快速上手（GUI）

如果你喜欢图形界面：

```bash
git clone https://codeup.aliyun.com/szgenle/cmdseal.git
cd cmdseal

make sync            # 在本地 uv 虚拟环境中安装 PySide6
make app             # 生成 dist/cmdseal.app
open dist/cmdseal.app
```

这将启动封存向导 —— 一个四步图形界面：
1. **命令** — 输入你的命令（例如：`zip -j -P mypassword {{arg:1}}`）
2. **Secret** — 如果使用了 `{{secret:NAME}}`，在这里填写（否则跳过）
3. **选项** — 输出路径、标签、签名身份
4. **执行** — 预览并在后台运行 `cmdseal.py`

GUI 是 `cmdseal.py` 的一层薄封装；没有重复的加密代码。
封存完成后，你会得到一个独立的二进制文件，可以交给 AI 智能体或脚本管道使用。

### 首次运行对话框

首次运行新生成的二进制时，macOS 会显示**一次**系统对话框
（登录密码 + “始终允许”）。这是将 keychain 条目绑定到此二进制
cdhash 的 partition-list 握手过程。每个封存的二进制在每个用户机器
上只发生一次；`cmdseal` 本身此后不再要求输入密码。后续所有运行
都是静默且毫秒级快速的。

## 高级：CLI 与脚本

对于 CI 管道、AI 智能体构建脚本，或者你更喜欢终端，`cmdseal.py`
提供完整的 CLI 访问：

```bash
# 封存一个带密码的 zip 命令。`zippw` 通过交互方式收集
# 并嵌入 AEAD 密文中；它永远不会以明文形式存储。
python3 cmdseal.py seal \
    --command 'zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}' \
    --output  ./seal_zip
# → 两次密码提示（输入 + 确认），然后生成 ./seal_zip

# 使用它 — 现在只需要两个位置参数，命令行上不再有密码。
./seal_zip  out.zip  /path/to/secret.txt
```

> **GUI 用户：** 请运行 `make app`；此 CLI 适用于脚本编写、
> CI 管道和审计。

## 占位符参考

| 占位符              | 解析时机 | 取值来源                                 |
| ------------------- | -------- | ---------------------------------------- |
| `{{secret:NAME}}`   | 封存时   | 交互式提示，嵌入 AEAD 密文中   |
| `{{arg:N}}`         | 运行时   | 生成二进制的 `argv[N]`                   |
| 其他 token          | —        | 原样透传                                 |

占位符必须**独占一个 argv 位置**——`"--pwd={{secret:x}}"` 这种混合写法
会被拒绝。请拆成两个 token：`--pwd {{secret:x}}`。

如果你写的是裸程序名（例如 `zip`），`cmdseal seal` 会在封存时通过
`shutil.which` 解析为绝对路径并嵌入其中。运行器拒绝使用 `$PATH` 查找
（见 §安全模型）。

## 一个可复现的完整示例

仓库已备好 [`demo/demo_zip_input.txt`](./demo/demo_zip_input.txt)
作为输入素材，以下流程可直接复制粘贴到你本机跑：

```bash
# 1）封存一个加密压缩命令为 demo/seal_zip。交互式输入自定义密码：
python3 cmdseal.py seal \
    --command 'zip -j -P {{secret:zippw}} {{arg:1}} {{arg:2}}' \
    --output  ./demo/seal_zip
# → 两次提示输入 zippw 的值，比如 'hunter2'

# 2）用它把 demo/demo_zip_input.txt 压成有密码保护的 out.zip：
./demo/seal_zip /tmp/out.zip ./demo/demo_zip_input.txt
# 首次运行：弹一次 macOS partition-list 系统框
#  （登录密码 + “始终允许”）— 这是绑定 cdhash 的一次性开销
# 后续运行：完全静默，约毫秒级返回

# 3）验证压缩包真的被密码保护：
unzip /tmp/out.zip -d /tmp/out
# → [/tmp/out.zip] demo_zip_input.txt password: ← 必须输 hunter2 才能解出

# 4）验证密码未被明文烘进二进制：
strings ./demo/seal_zip | grep -F 'hunter2' && echo FAIL || echo 'PASS: 密码未泄露'
```

核心卖点：第 2 步拿到的 `./demo/seal_zip` 可以交给设备上的 AI
智能体或脚本管道任意调用，而它们既看不到 `zippw` 的值，也
绕不过 keychain ACL 直接读取它：

```bash
# 智能体尝试绕过封存二进制直接拿密码：
/usr/bin/security find-generic-password -s cmdseal.<hash>.K -w
# → 弹出 GUI 授权框，智能体无法点击。拒绝访问。
```

> 如果你找不到封存时打出的 `cmdseal.<hash>.K`，可以用
> `strings ./demo/seal_zip | grep cmdseal` 重新拿到完整名称。

## 无需重新构建模板即可轮换密钥

```bash
python3 cmdseal.py rotate ./seal_zip
# 生成新的 AES-256 密钥，重写 AEAD 密文，
# 重新签名二进制，原子性替换 keychain 条目。
# 无需用户交互 — 约 1 秒内静默完成。
```

## GUI 快速参考

```bash
make sync            # 在本地 uv 虚拟环境中安装 PySide6
make run             # 启动封存向导（开发模式）
make app             # 生成 dist/cmdseal.app（独立应用）
open dist/cmdseal.app
```

GUI 是 `cmdseal.py` 的一层薄封装；没有重复的加密代码。
参见 [`gui/`](./gui/) 获取源码。

## 安全模型

### cmdseal 防范什么

- **通过被封存二进制的 argv 或 `ps` 进行的秘密窃取** —
  秘密以嵌入在二进制中的 AEAD 密文形式存在；它仅在
  keychain 获取和 `execv` 之间短暂的窗口期内以解密形式
  存在于运行器的地址空间中。
- **其他进程（即使是同一用户）读取 keychain 条目** —
  macOS partition-list / ACL 将条目绑定到此确切的二进制
  cdhash。已通过 `/usr/bin/security`、无关的 ad-hoc 签名
  探测器和位级完全相同的副本进行验证 — 全部被拦截。
- **基于 PATH 的程序替换** — 运行器使用 `execv` 和封存时
  嵌入的绝对路径（v1.1 #2）；运行时没有 `$PATH` 查找。
- **通过环境变量的 Dylib 注入** — 运行器在 `execv` 之前从
  其环境中剥离 `DYLD_*` 和 `LD_*`（v1.1 #3），并且使用
  `codesign --options runtime`（v1.1 #4）进行签名，因此
  dyld 本身会忽略此二进制的那些变量。

### cmdseal **不**防范什么

- **root** 攻击者，或以 root 运行的任何代码（可以读取任何
  进程内存、任何 keychain）。
- 以**同一用户**运行并获得任意代码执行权限以调试 / 转储
  运行中的被封存二进制的进程。
- 在构建二进制之前对生成机器的篡改。
- 对目标命令的快照 / 侧信道攻击（例如 `zip` 本身将密码
  写入某些日志；这是 `zip` 的责任，不是我们的）。
- Linux 或 Windows 上的任何内容。

在依赖 `cmdseal` 之前，请诚实地评估你的威胁模型。它是一个
**能力网关**，而不是保险库。

完整威胁模型、partition-list 实证发现和 Plan D（当前方案）
的基本原理，参见 [DESIGN.md](./DESIGN.md)。

## 日常维护

```bash
# 检查被封存二进制的 keychain 条目（仅元数据）：
security find-generic-password -s cmdseal.<hash>.K

# 删除条目（例如退役某个二进制时）：
security delete-generic-password -s cmdseal.<hash>.K

# 检查被封存二进制的元数据（无秘密可见）：
strings ./seal_zip | grep cmdseal
```

## 分发策略

我们**不**提供预构建的二进制文件。封存模型是
每台机器（cdhash + 你的登录 keychain），所以在别人的机器上
构建的二进制对你来说无论如何都是无用的。要使用
`cmdseal`：

1. `git clone` 仓库，
2. 审计你想审计的内容，
3. 如果你想要 GUI 可以 `make app`，或者直接使用 `cmdseal.py` 进行脚本编写。

如果你想要在 GitHub 上提供 Developer-ID 签名并公证的 `.app` 发布版本，
[开启一个 issue](https://codeup.aliyun.com/szgenle/cmdseal/issues) —
这取决于维护者加入 Apple Developer Program。

## 已知限制

- **每个封存二进制首次运行提示。** 见 §快速上手。
- **没有注册表** 来记录哪个 `cmdseal.<hash>.K` 服务对应
  哪个二进制，除了 `strings <binary> | grep cmdseal`。
- **删除被封存二进制时不会自动清理** keychain 条目。
  计划中：一个 `cmdseal gc` 子命令。
- **没有参数白名单** — `{{arg:N}}` 会原样传递给目标
  命令。如果目标命令对接受的值有严格要求，那是目标的责任。
- **仅 macOS。** Linux（`libsecret`）/ Windows（DPAPI）是
  未来工作；暂无时间表。

## 许可证

[MIT](./LICENSE) — 做你想做的，署名 appreciated，无保修。

## 第三方组件

`cmdseal` 使用了 [**PySide6**](https://pypi.org/project/PySide6/) 和
[**Qt 6**](https://www.qt.io/)，两者均采用
[LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.txt) 许可证。
Qt 是 The Qt Company Ltd. 的商标；`cmdseal` 与 The Qt Company
无附属关系，也未获其背书。

完整的第三方组件清单和 LGPL 合规说明见
[`THIRD_PARTY_LICENSES.md`](./THIRD_PARTY_LICENSES.md)。

## 相关

- [DESIGN.md](./DESIGN.md) — 架构和设计决策
- [DESIGN.zh.md](./DESIGN.zh.md) — 中文设计说明
- 作者：[szgenle.com](https://szgenle.com)
