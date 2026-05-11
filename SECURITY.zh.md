# 安全策略

> 英文版：[SECURITY.md](./SECURITY.md)

`cmdseal` 是一个 macOS 安全工具，其全部价值就在于防止密钥材料
泄漏给 AI 编码代理、同机上的其他进程，以及被篡改的副本二进制。
因此安全问题的报告会被作为一等公民来处理。

## 支持的版本

只有 `main` 分支上的最新发布线会收到安全修复。从 git 固定下来
的旧快照不在支持范围内，报告前请先升级。

| 版本    | 是否支持           |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |
| < 1.1   | :x:                |

## 漏洞报告方式

**请不要通过公开的 GitHub issue 报告安全问题。**

请通过 **GitHub Security Advisories** 私密上报：在仓库的
*Security* 标签页点击 *Report a vulnerability*
(<https://github.com/szgenle/cmdseal/security/advisories/new>)，
标题请以 `[cmdseal security]` 作为前缀。

一份有用的报告通常包含：

- cmdseal 版本 / commit SHA、macOS 版本、Xcode Command Line Tools 版本。
- 最小复现：`seal` 所用的命令模板、触发问题的调用方式、
  实际行为与预期行为。
- 该问题是否会泄漏明文密钥、绕过 keychain ACL 绑定、绕过
  `DYLD_*` 剥离 / hardened runtime，或允许替换底层被封装的程序。

## 响应 SLA

下列是一名独立维护者能做到的最大努力，**不是合同级 SLA**：

| 阶段                             | 目标                         |
| -------------------------------- | ---------------------------- |
| 确认收到                         | 3 个工作日以内               |
| 初步分诊 + 严重等级判定           | 7 个工作日以内               |
| 发布修复或缓解措施（高危 / 严重）  | 30 天以内                    |
| 如果一周内你没有收到任何回复      | 请再发一次（邮件偶尔会丢）   |

## 范围

大致属于处理范围的问题：

- 破坏 sealed runner 的 cdhash 与 keychain AES 密钥之间的绑定
  （ACL 绕过）。
- 在没有对应 keychain item 的情况下，从 sealed 二进制中恢复
  明文密钥（AEAD 绕过、侧信道等）。
- 在 `execv` 之前向 sealed runner 地址空间注入代码（例如通过
  环境变量、`DYLD_*`、路径替换）。
- 通过滥用 `cmdseal` 本身（CLI 或 GUI）实现的权限提升或持久化。

不在处理范围：

- 要求攻击者已经在同用户下取得代码执行权 **且** 具备交互式
  keychain 解锁权限的攻击 —— 这属于已经写入威胁模型的内容，
  参见 README 的 [Security model](./README.md#security-model) 小节。
- 社会工程用户去运行一个完全无关的恶意二进制。
- 上游依赖（PySide6、Qt、CPython、macOS 本身）中的问题 ——
  请报告给对应的上游项目。

## 协调披露

我们倾向于协调披露。请给出合理的窗口（视严重度而定，通常
30–90 天）再公开细节。除非你另有声明，否则我们会在发布说明
/ CHANGELOG 中致谢。
