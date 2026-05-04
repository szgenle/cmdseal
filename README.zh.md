# cmdseal（PoC）

> *面向 AI 智能体时代的能力网关。*
> *让你的 AI 智能体**能调用**敏感命令，却**拿不到**背后的秘密。*

[English version](./README.md)

本仓库是对 [DESIGN.zh.md](./DESIGN.zh.md) 中描述的端到端安全链路的
**概念验证（Proof-of-Concept）实现**：

```
命令模板  →  生成的 C 源码  →  ad-hoc 签名后的二进制
                                       ↓
                            绑定到这个二进制的 Keychain ACL
```

仅支持 macOS。暂不提供 GUI —— GUI 会在 `cmdseal.py` 这条核心链路被验证
稳定后再基于它构建。

## 环境要求

- macOS（在 darwin 24+ 上测试）
- `cc`（来自 Xcode Command Line Tools）
- `codesign`
- `/usr/bin/security`
- Python 3.8+

## 快速上手

```bash
cd cmdseal

# 封装一个 echo 命令：接收 1 个秘密 + 1 个运行时参数。
python3 cmdseal.py \
    --output ./demo_sealed \
    --command 'echo {{secret:mypass}} {{arg:1}}'
# → 会提示你输入 `mypass` 的值（两次），然后编译出 ./demo_sealed

# 运行它：
./demo_sealed hello-from-caller
# 第一次运行会弹一次 keychain 提示，点「始终允许」。
# 之后就完全静默。
# 输出：<你输入的密码> hello-from-caller
```

## 占位符速查表

| 占位符              | 解析时机 | 取值来源                                 |
| ------------------- | -------- | ---------------------------------------- |
| `{{secret:NAME}}`   | 运行时   | Keychain 中的 `cmdseal.<hash>.NAME` 条目 |
| `{{arg:N}}`         | 运行时   | 生成二进制的 `argv[N]`                   |
| 其他 token          | —        | 原样透传                                 |

占位符必须**独占一个 argv 位置**——`"--pwd={{secret:x}}"` 这种混合写法
会被拒绝。请拆成两个 token：`--pwd {{secret:x}}`。

## 一个真实用例（最初的动机场景）

```bash
python3 cmdseal.py \
    --output ~/bin/zhmm_fetch \
    --command 'zhmm_cmd -i /Users/ws/szdoc/zhmm/zhmm.gl.gl \
               --openId olQ0e7SL_98gbj2lqV_zki-Vjxco \
               --pwd {{secret:master}} \
               --search {{arg:1}} \
               --once'
```

之后家里的 AI 智能体就可以这样调用：

```bash
~/bin/zhmm_fetch "gmail"
```

……主密码全程不出现在 argv 里，不以明文落盘，也不会通过网络传输。如果
智能体自己尝试直接读：

```bash
/usr/bin/security find-generic-password -s cmdseal.<hash>.master -w
# → 弹 GUI 提示框。智能体无法点「允许」。失败。
```

## 日常维护

```bash
# 查看 keychain 条目（只看元信息，不取值）：
security find-generic-password -s cmdseal.<hash>.master -g

# 删除条目（例如淘汰某个 sealed binary 时）：
security delete-generic-password -s cmdseal.<hash>.master

# 查看二进制里写死的占位符（里面没有秘密）：
strings ./demo_sealed | grep cmdseal
```

## 已知限制（v1 PoC）

- **sealed binary 自身首次运行仍会弹窗。** 受 macOS partition-list 机制
  的约束，所有者需要在 sealed binary 首次运行时手动点一次「始终允许」。
  之后的调用都是静默的——这正是 AI 智能体需要的状态。消除首次提示是
  v2 的工作。
- 尚无 sealed binary 的注册表 → 哪个服务前缀对应哪个二进制目前靠自己
  记（或用 `strings` 查）。
- 删除 sealed binary 时不会自动清理对应的 keychain 条目。
- 尚无 `cmdseal rotate <binary>` 轮换子命令（用于不重编译的情况下换密码）
  —— 已规划。
- 尚未提供参数白名单 / 正则校验 —— 已规划。
- 尚无审计日志 —— 已规划。
- 侧信道加固尚未进行：sealed binary 仍使用 `execvp`（会走 PATH 搜索）、
  并通过 argv 把秘密传给目标命令，同机同用户的攻击者如果能写 `$PATH`、
  或能用 `ps -E` 紧密轮询，仍可截获。计划在 v1.1 处理。
- 只支持 macOS。Linux（`libsecret`）和 Windows（DPAPI）是未来工作。

## 签名模式 vs. 执法强度

已通过非交互方式验证（见 `acl_test.py`）：**即便在 ad-hoc 签名下，
Keychain ACL 仍然拦截其他调用者** —— `/usr/bin/security`、另一个
ad-hoc 签名的二进制、以及 sealed binary 的字节级副本，都会触发一个
无人值守 AI 无法应答的 GUI 提示。

| 签名模式                              | 参数                                                             | 执法效果       | 适用场景                          |
| ------------------------------------- | ---------------------------------------------------------------- | -------------- | --------------------------------- |
| Ad-hoc（默认）                        | *（无）*                                                         | ✅ 生效         | 个人 / 单机使用                   |
| Developer ID（付费 Apple 开发者计划） | `--signing-identity "Developer ID Application: Name (TEAMID)"`   | ✅ 且更严格     | 分发 / 共享构建                   |

Developer ID 属于可选加固，并非必需。对于催生 cmdseal 的「家庭智能体」
威胁模型而言，ad-hoc 已经足够。

```bash
# Ad-hoc（默认）对大多数用户已足够。
python3 cmdseal.py --output ./fetch_pwd --command '...'

# 如果你有 Developer ID 且想让 ACL 的 designated requirement 更紧，
# 可以显式指定。
python3 cmdseal.py \
    --signing-identity "Developer ID Application: Jane Doe (ABCDE12345)" \
    --output ./fetch_pwd \
    --command '...'
```

完整实证结论与方法论纠偏（早期手动测试时由于操作者误点弹窗导致的假
阴性）见 [DESIGN.zh.md](./DESIGN.zh.md) 第 8 节。
