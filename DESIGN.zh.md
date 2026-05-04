# cmdseal —— 设计文档

> *面向 AI 智能体时代的能力网关。*
> *让你的 AI 智能体**能调用**敏感命令，却**拿不到**背后的秘密。*

[English version](./DESIGN.md)

---

## 1. 这个工具为什么存在

在 AI 智能体时代，越来越多人会在家里部署一个常驻的个人智能体：能读本地
文件、能跑本地工具、能在主人外出时通过 IM / 邮件自动回复。

这些操作里有一部分需要用到**秘密**：离线密码管理器的主密码、一把私钥、
一个加密档案的口令……把这些秘密直接交给智能体是不可接受的——一次 prompt
injection、一次被留底的对话、一条被拦截的信道，就能全部泄露。

可我们仍然希望智能体能帮上忙。问题是：

> *怎样让智能体**调用**一项敏感操作，而**不让它知道**这项操作所需的秘密？*

`cmdseal` 的回答是：生成一个**经过签名、被 Keychain 绑定、单一用途的
二进制**——一个能力网关。智能体可以运行它，但看不到它的内部，也无法
提取它所使用的秘密。

---

## 2. 威胁模型

| 角色                     | 可信用途             | 不可信用途                         |
| ------------------------ | -------------------- | ---------------------------------- |
| 你（所有者）             | 一切                 | —                                  |
| 家庭 AI 智能体           | 调用程序             | 读取秘密、修改二进制               |
| 网络 / IM / 邮件         | 传输密文             | 承载明文秘密                       |
| 拿到二进制的攻击者       | —                    | 在另一台机器上运行                 |

假设：

- AI 智能体运行在所有者的 macOS 登录会话中。
- 智能体可以读文件系统、跑任意命令、调用 `security(1)`，可以把文件发往
  网络。
- 智能体**无法**响应交互式 GUI 弹窗（没有人坐在电脑前）。
- Keychain 处于「当前会话内已解锁」的常规状态。

v1 暂不考虑：

- 同机 root + debugger 的攻击者（可以 ptrace 正在运行的二进制、窥探
  内存）。
- macOS 系统更新被污染，或 Apple 签名根被攻破。
- 针对 Keychain 密码学实现的侧信道攻击。

---

## 3. 架构

```
        外出                          家里的机器
   ┌──────────────┐              ┌──────────────────────────┐
   │  所有者       │              │      AI 智能体            │
   │  （手机）     │              │  （可以调用程序）          │
   └──────┬───────┘              └──────────┬───────────────┘
          │ ① "帮我取一下 X 的密码"          │ 只能 exec，永远不能直接 read
          │──────────────IM──────────────►  │
          │                                  ▼
          │                   ┌──────────────────────────────┐
          │                   │  cmdseal 生成的二进制          │
          │                   │  （ad-hoc 签名 + ACL 绑定）    │
          │                   └──────────┬───────────────────┘
          │                              │ ② SecKeychainFind...()
          │                              ▼
          │                   ┌──────────────────────────────┐
          │                   │  macOS Keychain               │
          │                   │  ACL = { 只授权这个二进制 }    │
          │                   └──────────┬───────────────────┘
          │                              │ ③ 解密后的秘密
          │                              ▼
          │                   ┌──────────────────────────────┐
          │                   │  execvp(target_cmd, argv)     │
          │                   │  stdout → 加密后的产物         │
          │                   └──────────┬───────────────────┘
          │ ④ 加密产物                    │
          │◄────────────IM/邮件───────────┘
          ▼
   在手机上本地解密
   密码只存在于所有者脑子里
```

---

## 4. 安全机制

### 4.1 秘密不写进二进制

生成的 C 源码里只有**占位符**（`__SECRET__NAME`）和**服务名**
（`cmdseal.<hash>.NAME`）。实际秘密在生成时被写入 macOS Keychain。
`strings <binary>` 只能看到服务名——在 Keychain 没有解锁授权的前提下，
这个名字毫无价值。

### 4.2 Keychain ACL 绑定到这一个具体二进制

编译完成后，cmdseal 会：

1. 剥除符号并执行 ad-hoc 签名（`codesign -s - --force <bin>`）。
2. 新增 keychain 条目，并把该二进制加到 ACL 的信任列表：
   ```
   security add-generic-password \
     -a "$USER" -s "cmdseal.<hash>.NAME" \
     -w "<secret>" \
     -T "<binary_path>" \
     -U
   ```

效果：

| 调用者                                  | 结果                     |
| --------------------------------------- | ------------------------ |
| 生成的那个二进制本身                    | ✅ 静默成功              |
| 其他任意进程（包括 AI 智能体）          | ❌ GUI 弹窗 → 被拒绝     |
| 同一个二进制被挪到另一台机器            | ❌ 条目不存在 → 失败     |
| 重编译 / 被篡改过的二进制               | ❌ 签名不匹配 → 弹窗     |

关键洞察：macOS Security 框架在做 ACL 校验时，检查的是**调用进程的
code requirement**，而不仅仅是它的路径。ad-hoc 签名把身份钉死在了一个
具体的编译产物上。

### 4.3 运行时路径上没有 shell

生成的二进制使用 `execvp(argv[0], argv)` 直接执行预先拆好的 argv
数组，不会经过 `system()` 或 `/bin/sh`，因此参数值不可能借 shell
元字符逃逸。

### 4.4 参数透传只走位置

像 `{{arg:1}}` 这样的占位符只会被替换成调用时的 `argv[1]`，不做其他
处理。运行时不会展开 `~`、不做通配（glob）、也不会对透传值做环境变量
插值。

### 4.5 输出通道（推荐用法）

推荐 sealed 命令把**加密后的产物**（例如 `zip -P`、`gpg`、`age`）写到
一个文件路径，stdout 只打印一行简短的成功信息。AI 智能体把这个产物
原样转发；明文永远不会出现在 stdout、日志或网络数据包里。

---

## 5. 占位符语法（v1）

命令模板是一个 shell 风格的字符串，由 `shlex` 进行 token 化：

| 占位符              | 解析时机 | 取值来源                                |
| ------------------- | -------- | --------------------------------------- |
| `{{secret:NAME}}`   | 运行时   | Keychain 中的 `cmdseal.<hash>.NAME`     |
| `{{arg:N}}`         | 运行时   | 生成二进制的 `argv[N]`                  |
| 普通字面 token      | —        | 原样使用                                |

示例：

```
zhmm-cli -i /Users/ws/data.zmb \
  --account you@example.com \
  --pwd {{secret:master}} \
  -s {{arg:1}}
```

会生成一个可按如下方式调用的二进制：

```
./zhmm_fetch "某关键词"
```

---

## 6. 生成流程

```
cmdseal.py
  └─► 读取 --command 模板
  └─► 用 shlex 拆分成 tokens
  └─► 收集所有不同的 {{secret:NAME}} 占位符
  └─► 对每个秘密调用 getpass() 让用户输入
  └─► 生成服务名 hash（截短的 uuid4）
  └─► 渲染 wrapper_template.c → build/wrapper.c
  └─► cc -O2 -framework Security -framework CoreFoundation
         -o <output> build/wrapper.c
  └─► codesign -s - --force --timestamp=none <output>
  └─► 对每个秘密执行：
         security add-generic-password -U
             -s cmdseal.<hash>.NAME -a $USER -w <value>
             -T <output>
  └─► 打印摘要（服务名、安装路径、使用示例）
```

---

## 7. 非目标（v1）

- 跨平台。v1 只做 macOS，Linux / Windows 将来再通过 `libsecret` /
  DPAPI 适配。
- GUI。GUI 会作为一层薄薄的前端去 shell 调用 `cmdseal.py`，等核心流程
  真正稳定再做，是 v2 的事。
- 自动参数消毒。使用者应在编写 sealed 命令时把 `{{arg:N}}` 的值当作
  不可信数据（以引用方式放在 argv 位置，不要拼接成路径）。

---

## 8. v1 PoC 的实证结论

PoC 已在 darwin 24+（macOS）上端到端跑通。下文数据来自一个**非交互
5 秒硬超时的负向测试 harness**（见 `cmdseal/acl_test.py`）：每个候选
调用者都在 5 秒硬超时下运行，这样一旦 Keychain 弹出 GUI（无人值守的
AI 永远不会去点），它就会表现为 timeout，而不是被误判为「成功」。

> ⚠️ 本文档的早期版本曾得出「ad-hoc 签名下 ACL 不执法」的结论，那是
> **错的**。因为操作者在手工测试期间一直在点弹窗的「允许」，把「每次
> 都在被弹窗提示」这一事实完全掩盖了。换用非交互 harness 后，真相
> 才浮现出来——而且比之前以为的好得多。

✅ **生成流水线可用。** `cmdseal.py` 会解析模板、渲染 C 源码，用 `cc
-framework Security` 编译，`codesign -s -` 做 ad-hoc 签名，然后通过
专用的 `cmdseal_helper`（使用 `SecAccessCreate`，从而刻意把
`/usr/bin/security` 排除在 ACL 信任列表之外）写入秘密。

✅ **ACL 执法是真实的——哪怕在 ad-hoc 签名下。** 针对一条全新的、
没有授权过任何调用者的 keychain 条目，实测如下：

| 攻击者场景                                              | 结果（5 秒超时）         |
| ------------------------------------------------------- | ------------------------ |
| `/usr/bin/security find-generic-password -w`            | ⏸ 超时——弹窗，无读取   |
| *另一个* ad-hoc 签名的二进制调用相同的 API              | ⏸ 超时——弹窗，无读取   |
| sealed 二进制的**字节级副本**                           | ⏸ 超时——弹窗，无读取   |

三种未授权调用者全部触发 GUI 确认弹窗。无人值守的 AI 智能体在所有者
的会话里没有任何办法去点那个弹窗。**能力网关这条性质成立。**

### 已知 UX 问题：sealed binary 自己首次运行会弹窗

sealed binary 第一次运行时*也*会弹一次提示（用户需要点一次「始终
允许」）。原因在于 macOS Sierra 引入的 **partition-list** 机制：通过
`SecKeychainItemCreateFromContent` 创建的条目，partition-list 默认
为空，所以即便调用者已经在 ACL 信任列表上，也要等用户一次性「祝福」
这个组合之后才能静默通过。

这是 UX 瑕疵，不是安全漏洞：

- 弹窗只对每个 (keychain 条目, 调用者二进制) 组合**出现一次**。用户
  点过「始终允许」之后，后续调用完全静默——这正是 AI 智能体需要的
  状态。
- partition-list 弹窗仍然会拦住*非信任*调用者（它们会先在 ACL 检查
  那一步就被拒绝）。
- 正确配置 partition list 需要
  `SecKeychainSetGenericPasswordPartitionList`（或 `/usr/bin/security
  -T` 在内部使用的等价私有 API）。v2 应在 `cmdseal_helper` 创建条目
  时就把它设好，从根本上消除首次弹窗。

### v1 阶段的威胁模型结论

针对「AI 能 `exec`，AI 不能 `read secret`」这一目标，在 ad-hoc 签名
下，只要所有者完成过一次性的「始终允许」授权，**PoC 已经达到设计
门槛**。

### 可选加固：Developer ID 签名

付费的 Developer ID 证书（Apple Developer Program，每年 99 美元）
可以给 ACL 提供更紧的 designated requirement，使用方式：

```bash
python3 cmdseal.py \
    --signing-identity "Developer ID Application: Jane Doe (ABCDE12345)" \
    ...
```

启用 Developer ID 后，designated requirement 会把 Team ID 和 cdhash
一起钉死，这会进一步收窄某些极端情况下可能绕过 ACL 的攻击面（比如
Gatekeeper 被豁免的特权上下文）。对于一般的家庭智能体威胁模型，
ad-hoc 已经够用；Developer ID 只建议在需要分发 / 共享构建时启用。

### v1 结束后仍然悬而未决的问题

1. 在创建条目时直接设置 partition list，消除 sealed 二进制自身首次
   运行的弹窗（私有 API 路径已知，需在 macOS 14+/15+ 上验证）。
2. 当一个 sealed binary 被删除时，如何让对应的 keychain 条目一同失效
   —— 需要在 `~/Library/Application Support/cmdseal/` 下维护一个
   注册表文件。
3. sealed binary 自身的侧信道加固：放弃 PATH 查找（改用 `execv` +
   强制绝对路径）、清空环境变量、启用 hardened runtime 阻止
   `DYLD_INSERT_LIBRARIES`、把秘密从 argv 改走 pipe-fd，从而让
   `ps -E` 之类的轮询无法抢到。
4. 是否在 v2 提供另一种 vault（加密文件 + Secure Enclave 解锁），
   让愿意接受「需要用户在场」条件的用户换取更强的执法？

---

## 9. 附：核心要点速览

- **目标**：让家里的 AI 智能体在你外出时「能调用」敏感操作（比如从
  离线密码管理器取某条密码），但「读不到」底层秘密。
- **核心机制**：
  1. 秘密不写进二进制，而是写进 macOS Keychain。
  2. Keychain 条目的 ACL 被绑定到**这个经过 ad-hoc 签名的二进制**。
  3. AI 调用二进制 → 静默拿到密码 → 执行命令 → 输出密文压缩包。
  4. AI 自己直接读 Keychain → 弹 GUI 弹窗 → 无人值守 → 失败。
- **AI 能力**：`exec` ✔  `read secret` ✘
- **网络传输**：只走密文。
- **解密方**：只有你的手机 + 只在你脑子里的密码。
