<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN">
<context>
    <name>CommandInputPage</name>
    <message>
        <location filename="../template_wizard/_command_page.py" line="216"/>
        <source>Enter Command</source>
        <extracomment>试运行超时（毫秒）。由偏好面板控制；未传则沿用历史硬编码。</extracomment>
        <translation>输入命令</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="221"/>
        <source>Enter a real executable command; click “➕ Add pipe segment” to extend into a multi-segment pipeline.
Click “Try-run full pipeline” and proceed only after it succeeds.
Note: try-run actually executes the command; use side-effect-free arguments first.</source>
        <translation>请输入一条真实可执行的命令；可点「➕ 添加管道段」扩展为多段管道。
点「试运行整条管道」，确认通过后再进入下一步。
注意：试运行会真实执行该命令，请先用无副作用的参数验证。</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="228"/>
        <source>&lt;b&gt;Example:&lt;/b&gt; &lt;code&gt;{cmd}&lt;/code&gt;</source>
        <translation>&lt;b&gt;示例：&lt;/b&gt; &lt;code&gt;{cmd}&lt;/code&gt;</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="236"/>
        <source>Insert Example</source>
        <translation>填入示例</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="237"/>
        <source>Insert the example command into the first segment</source>
        <translation>将示例命令填入第一段输入框</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="249"/>
        <source>⚠ Each segment is executed via execv, &lt;b&gt;not through a shell&lt;/b&gt;: env vars &lt;code&gt;$VAR&lt;/code&gt;, pipes &lt;code&gt;|&lt;/code&gt;, redirects &lt;code&gt;&amp;gt;&lt;/code&gt;, globs &lt;code&gt;*&lt;/code&gt; are NOT expanded;
to chain pipelines use “➕ Add pipe segment” instead of writing &lt;code&gt;|&lt;/code&gt; inside a segment.</source>
        <translation>⚠ 每段直接 execv 执行，&lt;b&gt;不经 shell&lt;/b&gt;：环境变量 &lt;code&gt;$VAR&lt;/code&gt;、管道 &lt;code&gt;|&lt;/code&gt;、重定向 &lt;code&gt;&amp;gt;&lt;/code&gt;、通配符 &lt;code&gt;*&lt;/code&gt; 都不会展开；
管道拼接请用「➕ 添加管道段」而非在单段里写 &lt;code&gt;|&lt;/code&gt;。</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="271"/>
        <source>➕ Add pipe segment</source>
        <translation>➕ 添加管道段</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="278"/>
        <source>Try-run full pipeline</source>
        <translation>试运行整条管道</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="281"/>
        <source>Clear run result</source>
        <translation>清除运行结果</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="288"/>
        <source>Try-run stdout/stderr and exit code will appear here</source>
        <translation>此处显示试运行的 stdout/stderr 与退出码</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="298"/>
        <source>Command (multiple segments form a pipeline in order):</source>
        <translation>命令（多段按顺序串联为管道）：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="303"/>
        <source>Try-run output (stdout of last segment):</source>
        <translation>试运行输出（最后一段 stdout）：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="322"/>
        <source>Overwrite current command?</source>
        <translation>覆盖当前命令？</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="323"/>
        <source>The first segment already has content; inserting the example will overwrite it. Continue?</source>
        <translation>第一段输入框中已有命令，填入示例会覆盖现有内容。继续？</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="365"/>
        <source>Hard limit of {n} segments reached</source>
        <translation>已达硬上限 {n} 段</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="368"/>
        <source>Add a new pipe segment (currently {n}/{max})</source>
        <translation>添加新管道段（当前 {n}/{max}）</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="394"/>
        <source>⚠ {n} empty segment(s); please fill or remove</source>
        <translation>⚠ 存在 {n} 个空段，请填写或删除</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="401"/>
        <source>✓ {n}/{max} segments all valid; will be chained as pipeline</source>
        <translation>✓ {n}/{max} 段全部合法；将以管道串联试运行</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="405"/>
        <source>✓ {n}/{max} segments all valid</source>
        <translation>✓ {n}/{max} 段全部合法</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="412"/>
        <source>⚠ Invalid segment(s) exist; see red hints per segment</source>
        <translation>⚠ 存在非法段，请查看每段红色提示</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="439"/>
        <source>Confirm Try-Run</source>
        <translation>确认试运行</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="444"/>
        <source>About to actually execute this entire pipeline.
Please verify current arguments cause no destructive side effects (deleting files, overwriting data, etc.).

$ {preview}

Continue?</source>
        <translation>即将真实执行该整条管道。
请确认命令当前参数不会产生破坏性副作用（删文件、覆盖数据等）。

$ {preview}

继续？</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="480"/>
        <source>⚠ Child process failed to start</source>
        <translation>⚠ 子进程启动失败</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="505"/>
        <source>⚠ QProcess error: {err}</source>
        <translation>⚠ QProcess 错误：{err}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="510"/>
        <source>⚠ Timeout ({s}s); pipeline terminated</source>
        <translation>⚠ 超时（{s}s），已终止整条管道</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="532"/>
        <source>✓ Pipeline verified; you can proceed</source>
        <translation>✓ 整条管道验证通过，可进入下一步</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="534"/>
        <source>✗ At least one segment failed; please fix and retry</source>
        <translation>✗ 管道中至少一段失败，请修正后重试</translation>
    </message>
</context>
<context>
    <name>CommandLineEdit</name>
    <message>
        <location filename="../template_wizard/_command_page.py" line="88"/>
        <source>⚠ No match: {token}</source>
        <extracomment>向页面报告补全提示文本；空串 = 清空提示 记录上一次 Tab 补全后的 token，用于检测“双 Tab 列出候选”</extracomment>
        <translation>⚠ 无匹配：{token}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="106"/>
        <source> … {n} total</source>
        <translation> … 共 {n} 个</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="107"/>
        <source>Candidates: </source>
        <translation>候选：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="110"/>
        <source>{n} candidates, press Tab again to list</source>
        <translation>{n} 个候选，再按 Tab 查看</translation>
    </message>
</context>
<context>
    <name>CommandPage</name>
    <message>
        <location filename="../seal_wizard.py" line="197"/>
        <source>Command Template</source>
        <translation>命令模板</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="203"/>
        <source>Write the command(s) to seal (up to {max} pipe segments).
• Literal passwords allowed; or use {{secret:NAME}} / {{arg:N}}
• With multiple segments, each consumes stdout of the previous segment
• {{arg:N}} numbers are globally unique and passed in order across all segments</source>
        <translation>填写要密封的命令（可多段管道，最多 {max} 段）。
• 可直接写字面量密码；或用 {{secret:NAME}} / {{arg:N}}
• 多段时，后一段的 stdin 为前一段的 stdout
• {{arg:N}} 编号跨段全局唯一、顺序连续传入</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="217"/>
        <source>➕  Add pipe segment</source>
        <translation>➕  添加管道段</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="225"/>
        <source>Command segments (shell-style; first field should be absolute path):</source>
        <translation>命令段（shell 风格，首字段建议绝对路径）：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="228"/>
        <source>Global parse result:</source>
        <translation>全局解析结果：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="275"/>
        <source>⚠ Failed to parse shell quoting: {err}</source>
        <translation>⚠ 无法解析 shell 引用：{err}</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="285"/>
        <source>; ⚠ First token is a placeholder; make sure to pass an absolute path at runtime</source>
        <translation>；⚠ 首 token 是占位符，请确保运行时传入绝对路径</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="288"/>
        <source>; ℹ First token &apos;{tok}&apos; will be resolved to absolute path at seal time</source>
        <translation>；ℹ 首 token &apos;{tok}&apos; 将在封存时解析为绝对路径</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="292"/>
        <location filename="../seal_wizard.py" line="317"/>
        <source>secrets={v}</source>
        <translation>secrets={v}</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="292"/>
        <location filename="../seal_wizard.py" line="293"/>
        <location filename="../seal_wizard.py" line="317"/>
        <location filename="../seal_wizard.py" line="319"/>
        <source>(none)</source>
        <translation>(无)</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="293"/>
        <location filename="../seal_wizard.py" line="319"/>
        <source>args={v}</source>
        <translation>args={v}</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="300"/>
        <source>⚠ Unwrapped secret:/arg: detected; use {{secret:NAME}} or {{arg:N}}</source>
        <translation>⚠ 检测到未包裹的 secret:/arg:，请用 {{secret:NAME}} 或 {{arg:N}}</translation>
    </message>
</context>
<context>
    <name>ExecutePage</name>
    <message>
        <location filename="../seal_wizard.py" line="572"/>
        <source>Execute Seal</source>
        <translation>执行密封</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="573"/>
        <source>After clicking “Run”, cmdseal.py will build the binary in a subprocess.</source>
        <translation>点击『运行』后，cmdseal.py 将在子进程中构建二进制。</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="591"/>
        <source>Run seal</source>
        <translation>运行 seal</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="595"/>
        <source>Preview (secrets redacted):</source>
        <translation>预览（secret 已脱敏）：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="598"/>
        <source>Log:</source>
        <translation>日志：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="613"/>
        <source>label   : {l}</source>
        <translation>label   : {l}</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="613"/>
        <source>(auto)</source>
        <translation>(auto)</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="670"/>
        <source>⚠ Child process failed to start
</source>
        <translation>⚠ 子进程启动失败
</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="681"/>
        <source>⚠ _run exception: {e}
{tb}
</source>
        <translation>⚠ _run 异常：{e}
{tb}
</translation>
    </message>
</context>
<context>
    <name>ExecutionPage</name>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="30"/>
        <source>Generate Sealed Binary</source>
        <translation>生成封装</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="31"/>
        <source>Click “Run”; cmdseal.py will build and sign the binary in a subprocess.</source>
        <translation>点击「运行」，cmdseal.py 将在子进程中构建并签名二进制。</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="50"/>
        <source>Run Generation</source>
        <translation>运行生成</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="54"/>
        <source>Configuration preview:</source>
        <translation>配置预览：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="57"/>
        <source>Log:</source>
        <translation>日志：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="73"/>
        <source>Template  : {t}</source>
        <translation>模板    : {t}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="76"/>
        <source>Template #{i}: {t}</source>
        <translation>模板段{i}  : {t}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="78"/>
        <source>Output    : {p}</source>
        <translation>输出    : {p}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="79"/>
        <source>Label     : {l}</source>
        <translation>label   : {l}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="79"/>
        <source>(auto)</source>
        <translation>(auto)</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="80"/>
        <source>User      : {u}</source>
        <translation>用户    : {u}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="81"/>
        <source>Signing   : ad-hoc</source>
        <translation>签名    : ad-hoc</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="129"/>
        <source>⚠ Child process failed to start</source>
        <translation>⚠ 子进程启动失败</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="137"/>
        <source>⚠ Exception: {e}
{tb}</source>
        <translation>⚠ 异常：{e}
{tb}</translation>
    </message>
    <message>
        <location filename="../template_wizard/_exec_page.py" line="149"/>
        <source>⚠ QProcess error: {err}</source>
        <translation>⚠ QProcess 错误：{err}</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../main_window.py" line="53"/>
        <source>Seal a command into an AEAD-encrypted binary;
the key lives only in the keychain and is bound to this binary.</source>
        <translation>把一条命令密封进 AEAD 加密的二进制；
密钥只存在于 keychain，且仅允许该二进制读取。</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="57"/>
        <source>Generate from Command…</source>
        <translation>从命令生成模板…</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="61"/>
        <source>Advanced Mode…</source>
        <translation>高级模式…</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="65"/>
        <source>Manage Runners…</source>
        <translation>管理 runner…</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="141"/>
        <source>Preferences…</source>
        <translation>偏好设置…</translation>
    </message>
</context>
<context>
    <name>OptionsPage</name>
    <message>
        <location filename="../seal_wizard.py" line="453"/>
        <source>Output &amp; Signing</source>
        <translation>输出与签名</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="454"/>
        <source>Choose the output path and signing method. ad-hoc means codesign -s -.</source>
        <translation>选择生成路径与签名方式。ad-hoc 即 codesign -s -。</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="466"/>
        <source>Browse…</source>
        <translation>浏览…</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="477"/>
        <source>Default file name is &lt;code&gt;{prefix}&amp;lt;orig-command-name&amp;gt;&lt;/code&gt;, default save location: {dir}/ (created automatically on first use).</source>
        <translation>默认文件名为 &lt;code&gt;{prefix}&amp;lt;原命令名&amp;gt;&lt;/code&gt;，默认保存到 {dir}/（首次使用会自动创建）。</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="482"/>
        <source>Auto-generated from output file name if empty</source>
        <translation>留空则按输出文件名自动生成</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="486"/>
        <source>- (ad-hoc, dev only)</source>
        <translation>- （ad-hoc，仅开发调试）</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="490"/>
        <source>Skip codesign (debug only; loses Plan D protection)</source>
        <translation>跳过 codesign（仅调试用，会失去 Plan D 保护）</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="496"/>
        <source>Output binary:</source>
        <translation>输出二进制：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="498"/>
        <source>Label (optional):</source>
        <translation>Label（可选）：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="499"/>
        <source>Keychain account:</source>
        <translation>Keychain 账号：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="500"/>
        <source>Signing identity:</source>
        <translation>签名身份：</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="544"/>
        <source>Choose output path</source>
        <translation>选择输出路径</translation>
    </message>
</context>
<context>
    <name>OutputConfigPage</name>
    <message>
        <location filename="../template_wizard/_output_page.py" line="39"/>
        <source>Save Location</source>
        <extracomment>默认输出目录；由偏好面板控制（带 mkdir 延迟到实际使用时） 文件名前缀；仅用于提示文案。实际拼名在 ParameterSelectionPage.program_name() 完成</extracomment>
        <translation>保存位置</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="40"/>
        <source>Choose where to save the sealed binary.</source>
        <translation>选择封装后的二进制保存到哪里。</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="46"/>
        <source>Browse…</source>
        <translation>浏览…</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="59"/>
        <source>Default file name is &lt;code&gt;{prefix}&amp;lt;orig-command-name&amp;gt;&lt;/code&gt;, to distinguish from the original command.
Default save location: {dir}/ (created automatically on first use).
For global access, manually choose a directory on PATH like /usr/local/bin/, or create a symlink yourself.</source>
        <translation>默认文件名为 &lt;code&gt;{prefix}&amp;lt;原命令名&amp;gt;&lt;/code&gt;，用以与原命令区分。
默认保存到 {dir}/（首次使用会自动创建）。
若要全局调用，可手动指定 /usr/local/bin/ 等 PATH 中的目录，或自建软链接。</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="64"/>
        <source>Auto-generated from output file name if empty</source>
        <translation>留空则按输出文件名自动生成</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="70"/>
        <source>Output path:</source>
        <translation>输出路径：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="72"/>
        <source>Label (optional):</source>
        <translation>Label（可选）：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="73"/>
        <source>Keychain account:</source>
        <translation>Keychain 账号：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_output_page.py" line="91"/>
        <source>Choose output path</source>
        <translation>选择输出路径</translation>
    </message>
</context>
<context>
    <name>ParameterSelectionPage</name>
    <message>
        <location filename="../template_wizard/_param_page.py" line="49"/>
        <source>Select Runtime Arguments</source>
        <extracomment>文件名前缀；供 program_name() 拼默认输出名。由偏好面板控制。</extracomment>
        <translation>选择运行时参数</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="53"/>
        <source>Click tokens in the command to toggle “literal / runtime argument”.
With multiple segments, argN numbers increase globally across segments: first selected token is arg1, second is arg2…</source>
        <translation>点击命令中的 token 切换「字面量 / 运行时参数」。
多段时 argN 编号跨段全局递增：第一个选中的 token 是 arg1，第二个是 arg2……</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="83"/>
        <source>Command breakdown (blue = runtime argument, white = literal):</source>
        <translation>命令分解（蓝色 = 运行时参数，白色 = 字面量）：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="85"/>
        <source>Template preview (one line per segment):</source>
        <translation>模板预览（每段一行）：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="126"/>
        <source>Segment 1:</source>
        <translation>段 1：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="127"/>
        <source>main command</source>
        <translation>主命令</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="128"/>
        <source>reads stdout of previous segment</source>
        <translation>读上段 stdout</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="128"/>
        <source>Segment {i} ({tag}):</source>
        <translation>段 {i}（{tag}）：</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="140"/>
        <source>Segment {s} token #{i}: click to toggle into runtime argument</source>
        <translation>段 {s} token #{i}：点击切换为运行时参数</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="180"/>
        <source>Seg {i}: </source>
        <translation>段 {i}: </translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="189"/>
        <source>⚠ Select at least one token in any segment as runtime argument</source>
        <translation>⚠ 至少在任意一段选择一个 token 作为运行时参数</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="192"/>
        <source>Selected {n} runtime argument(s) → passed at runtime as arg1/arg2/…</source>
        <translation>已选 {n} 个运行时参数 → 运行时按 arg1/arg2/… 顺序传入</translation>
    </message>
    <message>
        <location filename="../template_wizard/_param_page.py" line="198"/>
        <source>; ⚠ First token (program path) is parameterized; at runtime you must pass an executable absolute path</source>
        <translation>；⚠ 首 token（程序路径）被参数化，运行时必须传入可执行的绝对路径</translation>
    </message>
</context>
<context>
    <name>PreferencesDialog</name>
    <message>
        <location filename="../preferences.py" line="42"/>
        <source>Preferences</source>
        <translation>偏好设置</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="53"/>
        <source>Browse…</source>
        <translation>浏览…</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="68"/>
        <source> s</source>
        <translation> 秒</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="82"/>
        <source>Default output directory:</source>
        <translation>默认输出目录：</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="83"/>
        <source>File-name prefix:</source>
        <translation>文件名前缀：</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="84"/>
        <source>Try-run timeout:</source>
        <translation>试运行超时：</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="85"/>
        <source>Language:</source>
        <translation>语言：</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="93"/>
        <source>These defaults take effect the next time you open the “Generate from Command” wizard. The wizard itself can still override them temporarily without changing the global defaults.
Language changes take effect after restarting the app.</source>
        <translation>这些默认值在下一次打开「从命令生成模板」向导时生效。向导内仍可以临时改写，不影响此处的全局默认。
语言更改需要重启应用后生效。</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="121"/>
        <source>Choose default output directory</source>
        <translation>选择默认输出目录</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="129"/>
        <source>Restore Defaults</source>
        <translation>恢复默认</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="130"/>
        <source>Restore all four settings to their defaults?</source>
        <translation>确定要把这四项设置都恢复为默认值吗？</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="152"/>
        <location filename="../preferences.py" line="158"/>
        <location filename="../preferences.py" line="164"/>
        <location filename="../preferences.py" line="174"/>
        <source>Invalid</source>
        <translation>无效</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="153"/>
        <source>Default output directory cannot be empty.</source>
        <translation>默认输出目录不能为空。</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="159"/>
        <source>File-name prefix cannot be empty.</source>
        <translation>文件名前缀不能为空。</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="166"/>
        <source>File-name prefix cannot contain / or \.</source>
        <translation>文件名前缀不能包含 / 或 \。</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="175"/>
        <source>Failed to parse directory: {e}</source>
        <translation>目录路径解析失败：{e}</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="190"/>
        <source>Language Changed</source>
        <translation>语言已更改</translation>
    </message>
    <message>
        <location filename="../preferences.py" line="194"/>
        <source>The UI language preference has been saved.
It will take effect after you restart the app.</source>
        <translation>界面语言偏好已保存。
重启应用后生效。</translation>
    </message>
</context>
<context>
    <name>RunnerListWindow</name>
    <message>
        <location filename="../runner_list.py" line="138"/>
        <source>cmdseal · Sealed Runners</source>
        <translation>cmdseal · 已 seal 的 runner</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="144"/>
        <source>Refresh</source>
        <translation>刷新</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="153"/>
        <source>Label</source>
        <translation>标签</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="154"/>
        <source>Service</source>
        <translation>服务</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="155"/>
        <source>Template</source>
        <translation>模板</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="156"/>
        <source>Created</source>
        <translation>创建时间</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="174"/>
        <source>Close</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="193"/>
        <source>Loading…</source>
        <translation>加载中…</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="199"/>
        <location filename="../runner_list.py" line="204"/>
        <location filename="../runner_list.py" line="212"/>
        <source>Load failed</source>
        <translation>加载失败</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="207"/>
        <source>cmdseal.py list failed (rc={rc})

{err}</source>
        <translation>cmdseal.py list 失败（rc={rc}）

{err}</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="214"/>
        <location filename="../runner_list.py" line="358"/>
        <source>Unexpected error: {e}</source>
        <translation>意外错误：{e}</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="221"/>
        <source>{n} total · {ok} with metadata · {legacy} legacy</source>
        <translation>共 {n} 条 · {ok} 条带元数据 · {legacy} 条 legacy</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="244"/>
        <location filename="../runner_list.py" line="288"/>
        <source>(legacy)</source>
        <translation>(legacy)</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="246"/>
        <source>(legacy, metadata unknown)</source>
        <translation>(legacy，元数据未知)</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="275"/>
        <source>Delete…</source>
        <translation>删除…</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="302"/>
        <source>Delete runner “{label}”?

</source>
        <translation>确认删除 runner 「{label}」？

</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="303"/>
        <source>service : {svc}
</source>
        <translation>service : {svc}
</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="304"/>
        <source>account : {acct}
</source>
        <translation>account : {acct}
</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="307"/>
        <source>binary  : {out}
</source>
        <translation>binary  : {out}
</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="318"/>
        <source>
The following actions will run (not reversible):
① Remove K from the keychain (ciphertext becomes undecryptable)
② Also delete the sealed binary file from disk

No system authorization prompt will appear.If the file cannot be removed (e.g. permissions), we will warn; K is already deleted and cannot be rolled back.</source>
        <translation>
将执行以下操作（不可恢复）：
① 删除钥匙串中的 K（密文将无法再被解密）
② 同步删除磁盘上的 sealed binary 文件

此操作不触发系统授权弹窗。若文件删除失败（如权限不足），会提示但 K 已删除无法回滚。</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="325"/>
        <source>
The following actions will run (not reversible):
① Remove K from the keychain
② The binary file is already gone from disk (no cleanup needed)

No system authorization prompt will appear.</source>
        <translation>
将执行以下操作（不可恢复）：
① 删除钥匙串中的 K
② binary 文件已不在磁盘上（无需清理）

此操作不触发系统授权弹窗。</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="334"/>
        <source>
The following actions will run (not reversible):
① Remove K from the keychain
⚠️ Legacy runner without output_path metadata; we cannot
   automatically delete the sealed binary. If you still know
   its location, please remove it manually.

No system authorization prompt will appear.</source>
        <translation>
将执行以下操作（不可恢复）：
① 删除钥匙串中的 K
⚠️ legacy runner 没有 output_path 元数据，无法联动删除磁盘上
   对应的 sealed binary。若还知道位置，请手动清理。

此操作不触发系统授权弹窗。</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="338"/>
        <source>Delete Runner</source>
        <translation>删除 runner</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="340"/>
        <source>Delete</source>
        <translation>删除</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="341"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="353"/>
        <source>Delete failed (rc={rc})

{err}</source>
        <translation>删除失败（rc={rc}）

{err}</translation>
    </message>
    <message>
        <location filename="../runner_list.py" line="372"/>
        <source>K was deleted but removing the binary failed:
{path}

{err}

Please delete this file manually (it can no longer be run).</source>
        <translation>K 已删除，但磁盘文件删除失败：
{path}

{err}

请手动删除该文件（已不能再解密运行）。</translation>
    </message>
</context>
<context>
    <name>SealWizard</name>
    <message>
        <location filename="../seal_wizard.py" line="722"/>
        <source>cmdseal — New Seal</source>
        <translation>cmdseal — 新建 seal</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="746"/>
        <source>Finish</source>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="747"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="748"/>
        <source>Next &gt;</source>
        <translation>下一步 &gt;</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="749"/>
        <source>&lt; Back</source>
        <translation>&lt; 上一步</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="750"/>
        <source>Confirm and Run</source>
        <translation>确认进入执行</translation>
    </message>
</context>
<context>
    <name>SecretsPage</name>
    <message>
        <location filename="../seal_wizard.py" line="357"/>
        <source>Secret Collection</source>
        <translation>Secret 采集</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="360"/>
        <source>Collected once at seal time and stored in AEAD ciphertext; never prompted again at runtime.</source>
        <translation>生成时一次性采集，封入 AEAD 密文；运行时不会再问。</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="366"/>
        <source>This command uses no {{secret:*}}; simply proceed.</source>
        <translation>本次命令未使用 {{secret:*}}，直接下一步即可。</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="393"/>
        <source>value: {name}</source>
        <translation>值：{name}</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="396"/>
        <location filename="../seal_wizard.py" line="404"/>
        <source>Show</source>
        <translation>显示</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="404"/>
        <source>Hide</source>
        <translation>隐藏</translation>
    </message>
</context>
<context>
    <name>TemplateWizard</name>
    <message>
        <location filename="../template_wizard/_wizard.py" line="18"/>
        <source>cmdseal — Generate from Command</source>
        <translation>cmdseal — 从命令生成模板</translation>
    </message>
    <message>
        <location filename="../template_wizard/_wizard.py" line="46"/>
        <source>Finish</source>
        <extracomment>默认输出目录：用户专属，避免 /usr/local/bin 的 sudo 依赖 试运行超时（秒）。太短会误杀正常命令；太长体验差 默认输出文件名前缀。用来与原始命令区分，避免放入 PATH 后遮蔽同名系统命令。 与项目自带 demo ``seal_zip`` 的命名风格保持一致。 顶部常驻示例命令。故意用不含任何 shell 元字符的形式： sealed 产物以 execv 运行，试运行用 QProcess.start，两者都不走 shell。 如果示例写 $VAR / | / &gt; / *，用户会误以为它们会展开，产生与封装后不一致的预期。 管道段数硬上限。与 cmdseal.py CLI / seal_wizard 高级模式保持一致。 Tab 补全触发前缀：只有当前 token 以这些字符开头才当作“路径”处理</extracomment>
        <translation>完成</translation>
    </message>
    <message>
        <location filename="../template_wizard/_wizard.py" line="47"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../template_wizard/_wizard.py" line="48"/>
        <source>Next &gt;</source>
        <translation>下一步 &gt;</translation>
    </message>
    <message>
        <location filename="../template_wizard/_wizard.py" line="49"/>
        <source>&lt; Back</source>
        <translation>&lt; 上一步</translation>
    </message>
    <message>
        <location filename="../template_wizard/_wizard.py" line="50"/>
        <source>Run</source>
        <translation>进入执行</translation>
    </message>
</context>
<context>
    <name>_PipeSegment</name>
    <message>
        <location filename="../template_wizard/_command_page.py" line="137"/>
        <source>Segment 1</source>
        <translation>段 1</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="143"/>
        <location filename="../template_wizard/_command_page.py" line="193"/>
        <source>Remove this segment</source>
        <translation>删除此段</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="156"/>
        <source>Path tokens (starting with /, ~, ./) can be Tab-completed</source>
        <translation>路径 token（以 /、~、./ 开头）可按 Tab 补全</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="186"/>
        <source>Segment 1 — main command</source>
        <translation>第一段 — 主命令</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="187"/>
        <source>Segment {i} — reads stdout of previous segment</source>
        <translation>第 {i} 段 — 从上段 stdout 读取</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="188"/>
        <source>Segment {i} ({tag})</source>
        <translation>段 {i}（{tag}）</translation>
    </message>
    <message>
        <location filename="../template_wizard/_command_page.py" line="195"/>
        <source>First segment cannot be removed</source>
        <translation>首段不可删除</translation>
    </message>
</context>
<context>
    <name>_SegmentEditor</name>
    <message>
        <location filename="../seal_wizard.py" line="127"/>
        <source>Remove this segment</source>
        <translation>删除此段</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="167"/>
        <source>Segment {i} (receives stdout of previous segment)</source>
        <translation>段 {i}　（第 {i} 段 — 获得上一段 stdout）</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="171"/>
        <source>Segment {i} (first segment — main command)</source>
        <translation>段 {i}　（第一段 — 主命令）</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="178"/>
        <source>e.g.: /usr/bin/zip -j -P {{secret:pw}} {{arg:1}}</source>
        <translation>例如：/usr/bin/zip -j -P {{secret:pw}} {{arg:1}}</translation>
    </message>
    <message>
        <location filename="../seal_wizard.py" line="181"/>
        <source>e.g.: /usr/bin/zip {{arg:2}} -    (&apos;-&apos; means read stdin)</source>
        <translation>例如：/usr/bin/zip {{arg:2}} -    （&apos;-&apos; 表示读 stdin）</translation>
    </message>
</context>
</TS>
