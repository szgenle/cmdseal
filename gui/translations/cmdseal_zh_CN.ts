<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN">
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
</TS>
