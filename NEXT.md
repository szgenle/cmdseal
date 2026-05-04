# cmdseal — 会话续接档案

> 本文件是 AI 协作会话的**可移植续接档案**。
> 仓库在别的机器 / 别的 AI 工具 / 开源给别人时也能看到。
> 如果不想开源它，请在 `.gitignore` 加一行 `NEXT.md`。

最后更新：2026-05-04（v1 PoC 完成、ACL 非交互验证通过、目录已扁平化、老 zipany 代码已移除、已记录 Plan D 架构演进待决策）

---

## 1. 路径 / 布局

- workspace 根：`/Users/ws/Dev/cmdseal/`
- **已扁平化**：原 `cmdseal/cmdseal/*` 全部上提一级到仓库根，子目录
  `cmdseal/` 已删除。原因：老 zipany 代码被移除后，当初为了和老项目
  隔离而建立的子目录失去存在理由；扁平化后仓库布局匹配 GitHub 单工
  具项目的常见形态，且避免 `cmdseal/cmdseal/cmdseal.py` 这种三层重名。
- 未来若要改造为可 `pip install` 的 Python 包，再引入规范的
  `src/cmdseal/__init__.py` 布局，现阶段不需要。

---

## 2. 项目现状

v1 PoC 已跑通端到端。定位：**Capability gateways for the AI agent era**
—— 让家里的 AI 智能体能"调用"敏感命令（比如从离线密码管理器取某条
密码），但读不到底层秘密。

### 已交付文件（全部位于仓库根目录）

| 文件 | 作用 |
|------|------|
| `DESIGN.md` | 设计文档：威胁模型 §2、架构 §3、安全机制 §4、占位符语法 §5、实测结论 §8 |
| `README.md` | 使用指南，含签名模式对比表 |
| `cmdseal.py` | 生成器主程序（CLI 入口），支持 `--signing-identity` |
| `wrapper_template.c` | 生成 sealed 二进制用的 C 模板 |
| `cmdseal_helper.c` | 严格 ACL 钥匙串写入工具（独立二进制，用 SecAccessCreate 而非 security CLI，避免 security 被自动加进 ACL） |
| `reader_probe.c` | 负向测试探针：不同 ad-hoc 签名的 reader |
| `acl_test.py` | **非交互 5s timeout 测试 harness**（v1 回归工具） |
| `modify_acl_probe.py` | **modify / delete ACL 行为探针**（非交互，Plan D 前置，详见 §5.8） |
| `_build/` | 构建产物缓存（cmdseal_helper、reader_probe）—— 已加入 `.gitignore` |
| `.gitignore` | 忽略 `_build/`、`__pycache__/`、`.DS_Store` |

老 zipany 工具源码（`zipany.c` / `zhmm_zip.c` / `zipany.sh` / 老根目录
`README.md`）已从仓库清除。

---

## 3. 关键结论（**严禁回到错误结论**）

**ad-hoc 签名 + `SecAccessCreate` 的钥匙串 ACL 在 macOS 上真实执法。**

非交互 5s timeout 测试（`acl_test.py`）证实：对一条从未授权过任何
caller 的新钥匙串条目，以下非授权调用者**全部 5s timeout**（GUI 弹窗
等不到 AI 点 Allow）：

- `/usr/bin/security find-generic-password -w`
- 其他 ad-hoc 签名的二进制直接调 `SecKeychainFindGenericPassword`
- sealed 二进制的字节级副本（同 cdhash，不同路径）

### 曾经犯过的方法论错误（不要再犯）

早期"手动端到端测试"得到"ACL 不执法、必须 Developer ID"的结论是
**假阳性**。原因：测试期间操作者一直在点钥匙串弹窗的 Allow，导致
"被阻塞等待"被误读为"静默成功读取"。

**教训**：验证 macOS 钥匙串 ACL **必须使用非交互 harness**（固定超时
+ 判 timeout / exit），禁止人工响应弹窗。请用 `acl_test.py` 作为标准
回归工具。

### Developer ID 是可选加固，不是必需

`--signing-identity "Developer ID Application: ..."` 参数保留，面向
分发 / 共享构建场景（设计要求更紧）。对于"家里 AI 智能体取密码"这
一核心威胁模型，ad-hoc 已经够用。

### 已知 UX 问题（不是安全漏洞）

sealed 二进制**首次**运行时自己也会弹一次 partition-list 提示，用户
点一次 "Always Allow" 后后续静默访问。这是 macOS Sierra 引入的
partition-list 机制，`SecKeychainItemCreateFromContent` 创建的条目
partition-list 默认为空。修复方法见下面 v1.1 待办 #1。

---

## 4. v1.1 待办加固项（按 ROI 排序）

等作者决策是否启动。建议按此顺序做。

| # | 项目 | 类型 | 实施要点 | 预估耗时 |
|---|------|------|---------|---------|
| 1 | partition list 配置 | UX | 在 `cmdseal_helper.c` 里调用 `SecKeychainSetGenericPasswordPartitionList`（或等效私有 API），消除 sealed 二进制自己首次运行的 GUI 提示 | 1h |
| 2 | 禁止 PATH 查找 | 安全 | `wrapper_template.c` 把 `execvp` 改为 `execv`；`cmdseal.py` 在生成时强制命令第一个 token 必须是绝对路径（以 `/` 开头），否则拒绝生成 | 30m |
| 3 | 环境变量清理 | 安全 | exec 前 `clearenv()` + 重建最小 env（只保留 `PATH=/usr/bin:/bin`、`HOME`、`USER`），防 `DYLD_INSERT_LIBRARIES` 等 | 30m |
| 4 | hardened runtime | 安全 | codesign 加 `--options runtime`，配合 #3 让 DYLD 注入失效 | 30m |
| 5 | 密码走 pipe-fd 而非 argv | 安全 | sealed 二进制创建 pipe，fork 子进程把密码写进 pipe fd，子进程把 fd 号传给 target 命令的 `--password-fd` 参数；防同用户 `ps -E` 侧漏。target 命令不支持 fd 时退化为匿名内存文件 | 2-3h |

完成 #1 + #2 + #3 + #4 是"开源前最小可公开安全基线"，大约 3h。

---

## 5. 设计演进讨论：Plan D（AEAD 密封命令行）——待决策

> 本节记录一次架构讨论的最终结论，涵盖用户演进出来的几个替代方案、
> 为什么选 Plan D、以及在动工实现前需要跑的探针测试。不正式启动前请先读本
> 节，以免绕回已否决的分支。

### 5.1 动机

现状架构：`wrapper_template.c` 硬编码命令模板 + `{{secret:xxx}}` 占位
符 + keychain 存单条密码。作者希望化简代码，除掉模板 / 占位符逻辑。

### 5.2 考虑过的替代方案（均已评估）

| 方案 | 命令存放 | keychain 存什么 | runner 存什么 | 安全性 | 代码简单度 | 结论 |
|------|---------|----------------|----------------|--------|------------|------|
| A. 现状 | runner 模板 | 单条密码 | 命令模板 + 占位符 | 优 | 中（模板渲染） | 基线 |
| B. 整条命令进 keychain | keychain | 整条命令含密码 | 无业务内容 | **失去 codesign 封存** | 高 | **驳回** |
| C. B + runner 内副本对比 | keychain + runner | 整条命令 | 同副本用于比对 | 等效 A | 等同 A | 无收益，驳回 |
| C'. B + runner 内密钥加解密 | 密文在哪都行 | 密钥 | 密文自身 | 等效 A + 静态保密 | **高**（AEAD 自带完整性） | **采纳 → Plan D** |
| E. “runtime字符串当密钥” obfuscation | 密文在 keychain | 无 | 固定字符串做"密钥" | 安全剧场性 | 中 | 驳回（anti-pattern） |

### 5.3 Plan D 架构

```
设计时：cmdseal.py 随机生成 K（32 字节）
            ciphertext = AES-256-GCM(K, 平文命令行)
            ciphertext 硬编码进 runner.c 并编译 + ad-hoc 签名 → sealed_binary
            cmdseal_helper 把 K 写入 keychain，ACL 按 cdhash 授权

运行时：sealed_binary:
            ACL 守门 → K = read_keychain()
            plaintext = AES-GCM-decrypt(K, ciphertext)   ← tag 一承担完整性校验
            execv(tokenize(plaintext))
```

**两把锁互为钥匙**：K 给 keychain ACL 守读取，密文给 codesign 守篡改。

### 5.4 Plan D 的收益和代价

✅ **收益**
- 模板 / 占位符逻辑全部消失（Python 和 C 两边都减线）
- AEAD 内建完整性保护，无需额外 hash 比对
- 命令字符串静态加密，对 "keychain db 被泄 + runner 未泄" 的小概率场景多一层防御
- 增量代码约 40 行 CommonCrypto（macOS 系统自带，无新依赖）

⚠️ **代价**
- **密码轮换 = 重建 runner**（因密码封在密文里）。实际表现为用户跑一条
  `cmdseal rotate`，脚本内部删旧 item（弹一次登录密码框）+ 重编译签名 +
  写新 K。sealed binary 路径不变，AI agent 调用方式不变。
- 审计叙事需要在 DESIGN.md 里画图说清"两把锁"机制

### 5.5 ACL 的两层权限（重要前提）

keychain item 的 ACL 分两块，一直被混淆，在此写清楚：

| 权限 | 保护什么 | 当前 cmdseal 策略 |
|------|---------|--------------------|
| **decrypt / read** | 读明文 value | **严格**：只信任 sealed runner 的 cdhash |
| **modify / delete** | 改 value、删 item | **默认宽松**：macOS 弹登录密码框验证用户 |

威胁模型关注的是 **read**（不让 AI 读到）；modify/delete 给用户自己用，放宽
反而方便轮换。

### 5.6 密码轮换的三种流程对比

| # | 方式 | 代码量 | 用户动作 | 动 read-ACL |
|---|------|-------|---------|-------------|
| A | "钥匙串访问.app" GUI | 0 | GUI 操作若干步 + 输登录密码 | 否 |
| B | `cmdseal rotate` （方案 A 下） | ~50 行 helper | 一条命令 + 输登录密码 | 否 |
| C | `cmdseal rotate` （Plan D 下） | ~50 行 | 一条命令 + 输登录密码 | 旧 ACL 删 → 新 ACL 建 |

用户摩擦基本等价。C 多的只是 2s 编译 + 重新 cdhash 绑定，对安全性无影响。

### 5.7 决策

**采纳 Plan D + 新增 `cmdseal rotate` 子命令**，但动工前必须完成 §5.8 探针测试。

### 5.8 前置工作：modify-ACL 行为探针测试

**状态**：代码已就绪，待作者手动跑一次收集结果。

- `cmdseal_helper.c` 已扩展 `delete` / `update` 子命令（编译+签名已验证）
- `modify_acl_probe.py` 已落盘，风格和 `acl_test.py` 对齐（5s timeout / 验证
  四个场景）

**跑法**：

```bash
cc -O2 -Wno-deprecated-declarations -o _build/cmdseal_helper \
   cmdseal_helper.c -framework Security -framework CoreFoundation
codesign -s - --force _build/cmdseal_helper
python3 modify_acl_probe.py --trusted ./demo_sealed
# 若没有 demo_sealed，先跑 cmdseal.py 生成一个 demo；
# 或 --trusted 传任意已签名的二进制路径
```

探针验证的四个场景：

1. `cmdseal_helper delete` （helper 本身不在 ACL trusted-apps 里）
2. `cmdseal_helper update` （同上，`SecKeychainItemModifyContent`）
3. `/usr/bin/security delete-generic-password`
4. `/usr/bin/security add-generic-password -U` （等价 update）

每个场景归类为：`silent`（静默成功，<1s）、`prompted`（timeout）、
`refused`（非零退出）。最后脚本自动开列决策表。

**结果应引导后续设计**：

- 如果 **helper_delete / helper_update 均 silent** → 轮换流程真正完全
  非交互，`cmdseal rotate` 实现最简单
- 如果 出现 `prompted` → `cmdseal rotate` 运行时应明确提示用户
  "系统将要求你输登录密码"，不要默默卡住
- 若需要 helper 免弹框，考虑在 SecAccessCreate 时显式把 helper 的 cdhash 加入
  modify-ACL 的 trusted-apps（**但保持 read-ACL 仅信 sealed runner**）

---

## 6. v2 / 未来构想

- 换用加密文件 + Secure Enclave 作为 vault（需要用户在线出席）
- 跨平台：Linux `libsecret`、Windows DPAPI
- 审计日志（append-only，AI 不可写）
- 速率限制 / 调用频次 → 手机推送审批
- sealed binary 注册表（`~/Library/Application Support/cmdseal/`），
  支持 `cmdseal list` / `cmdseal rotate` / `cmdseal revoke`
- 老 `zipany.c` 用的是 ZipCrypto（弱），换成 AES-256（7z 或 zipcloak）

---

## 7. 作者背景

- 一人公司 szgenle（szgenle.com）
- 计划把 cmdseal 开源到 GitHub
- 命名已定：`cmdseal`（GitHub 无冲突）
- 相关项目：作者另有一个开源的离线密码管理器 `zhmm`，cmdseal
  常见用例之一就是封装 `zhmm_cmd` 调用

---

## 8. 给下一个 AI 协作者的 tips

- 读完本文件 + `DESIGN.md`，就掌握了项目 90% 的上下文
- 任何"ACL 安全性"相关的论断都**必须跑 `acl_test.py` 非交互验证**
  后再下结论，禁止凭手动操作下结论
- 不要擅自删除 `reader_probe.c`，它是未来回归测试的关键探针
- 不要把老 `zipany.c` 和新 `cmdseal` 代码混为一谈 —— 老工具只是
  cmdseal 的一个**被调用者**，不是它的前身
- 遇到作者问"我们做到哪了"/"上次是什么来着"，回答时请引用本文件
  §2 现状 + §4 待办 + §5 Plan D 决策
- 任何关于架构的"我想改成 XXX"提议，先核对§5.2 揭示的替代方案表，避免
  绕回已否决的分支（特别是方案 B / C / E）
