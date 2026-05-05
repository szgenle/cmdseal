#!/bin/bash
# v1.2 端到端管道验证脚本
# 覆盖 research/DESIGN.pipe.md §4：两段/三段管道、跨段 {{arg:N}}、退出码语义。
#
# ⚠️  首次运行每个 sealed binary 都会弹出 macOS 授权窗口
#     （登录密码 + "始终允许"），请逐个完成授权。
#     脚本在末尾会清理所有测试产物（sealed binary + keychain item）。

set -u  # 注意：不用 -e；脚本自己判定 exit code 矩阵

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TEST_DIR="$ROOT/local/v12_pipe_e2e"
mkdir -p "$TEST_DIR"

# 清理列表：脚本结束时删除这些 sealed binary 对应的 keychain item
declare -a CLEANUP_SERVICES=()
declare -a CLEANUP_BINARIES=()

cleanup() {
    echo ""
    echo "[清理] 删除测试产物..."
    for svc in "${CLEANUP_SERVICES[@]:-}"; do
        [ -n "$svc" ] && security delete-generic-password -s "$svc" >/dev/null 2>&1 || true
    done
    for bin in "${CLEANUP_BINARIES[@]:-}"; do
        rm -f "$bin"
    done
    rmdir "$TEST_DIR" 2>/dev/null || true
    echo "[清理] 完成"
}
trap cleanup EXIT

FAIL_COUNT=0
PASS_COUNT=0

record_result() {
    local name="$1"
    local ok="$2"
    if [ "$ok" = "1" ]; then
        echo "✅ $name"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "❌ $name"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# ---------------------------------------------------------------
# 辅助：封装一个管道模板（可变数量的 --command），并登记清理
# 用法: seal_pipe <out_name> <cmd1> [cmd2 ...]
# 结果 sealed binary 路径存入 $SEALED_BIN，service 名存入 $SEALED_SVC
# ---------------------------------------------------------------
seal_pipe() {
    local out_name="$1"
    shift
    local out_path="$TEST_DIR/$out_name"
    local args=()
    for cmd in "$@"; do
        args+=(--command "$cmd")
    done

    # 运行 seal（可能失败，由调用者判断）
    python3 cmdseal.py seal "${args[@]}" \
        --output "$out_path" \
        --user "$(whoami)" \
        >"$TEST_DIR/${out_name}.seal.log" 2>&1
    local rc=$?
    if [ $rc -ne 0 ]; then
        SEALED_BIN=""
        SEALED_SVC=""
        return $rc
    fi

    # 从 binary 中提取 service 名用于后续清理
    local svc
    svc=$(strings "$out_path" 2>/dev/null | grep -E '^cmdseal\.[a-f0-9]{12}\.K$' | head -1)

    SEALED_BIN="$out_path"
    SEALED_SVC="$svc"
    CLEANUP_BINARIES+=("$out_path")
    [ -n "$svc" ] && CLEANUP_SERVICES+=("$svc")
    return 0
}

# ---------------------------------------------------------------
echo "=================================================="
echo "cmdseal v1.2 管道功能端到端验证"
echo "=================================================="
echo ""
echo "测试目录: $TEST_DIR"
echo ""

# ---------------------------------------------------------------
# Case 1: 单段快路径（v1.1 兼容回归）
# ---------------------------------------------------------------
echo "[Case 1] 单段快路径（--command 只有一个，不触发 fork/pipe）"
seal_pipe "c1_single" "/bin/echo single {{arg:1}}" || {
    record_result "Case 1 seal 失败" 0
    exit 1
}
out=$("$SEALED_BIN" hello 2>&1)
rc=$?
if [ "$out" = "single hello" ] && [ $rc -eq 0 ]; then
    record_result "Case 1 单段：stdout=\"single hello\", exit=0" 1
else
    record_result "Case 1 单段（got stdout=\"$out\", exit=$rc）" 0
fi
echo ""

# ---------------------------------------------------------------
# Case 2: 两段管道（基础）
# ---------------------------------------------------------------
echo "[Case 2] 两段管道：echo | tr"
seal_pipe "c2_two" \
    "/bin/echo hello" \
    "/usr/bin/tr a-z A-Z" || {
    record_result "Case 2 seal 失败" 0
    exit 1
}
out=$("$SEALED_BIN" 2>&1)
rc=$?
if [ "$out" = "HELLO" ] && [ $rc -eq 0 ]; then
    record_result "Case 2 两段：stdout=\"HELLO\", exit=0" 1
else
    record_result "Case 2 两段（got stdout=\"$out\", exit=$rc）" 0
fi
echo ""

# ---------------------------------------------------------------
# Case 3: 跨段 {{arg:N}} 替换
# ---------------------------------------------------------------
echo "[Case 3] 跨段 arg：echo hello {{arg:1}} | tr a-z A-Z"
seal_pipe "c3_crossarg" \
    "/bin/echo hello {{arg:1}}" \
    "/usr/bin/tr a-z A-Z" || {
    record_result "Case 3 seal 失败" 0
    exit 1
}
out=$("$SEALED_BIN" world 2>&1)
rc=$?
if [ "$out" = "HELLO WORLD" ] && [ $rc -eq 0 ]; then
    record_result "Case 3 跨段 arg：stdout=\"HELLO WORLD\", exit=0" 1
else
    record_result "Case 3 跨段 arg（got stdout=\"$out\", exit=$rc）" 0
fi
echo ""

# ---------------------------------------------------------------
# Case 4: 三段管道
# ---------------------------------------------------------------
echo "[Case 4] 三段管道：echo a b c | tr ' ' '\\n' | sort -r"
seal_pipe "c4_three" \
    "/bin/echo a b c" \
    "/usr/bin/tr ' ' '\n'" \
    "/usr/bin/sort -r" || {
    record_result "Case 4 seal 失败" 0
    exit 1
}
out=$("$SEALED_BIN" 2>&1)
rc=$?
expected=$'c\nb\na'
if [ "$out" = "$expected" ] && [ $rc -eq 0 ]; then
    record_result "Case 4 三段：stdout=\"c\\nb\\na\", exit=0" 1
else
    record_result "Case 4 三段（got stdout=\"$out\", exit=$rc）" 0
fi
echo ""

# ---------------------------------------------------------------
# Case 5: 退出码 — 上游失败，下游成功 → 上游码胜出
# ---------------------------------------------------------------
echo "[Case 5] 退出码：上游 false | 下游 echo → exit 1（上游）"
seal_pipe "c5_upstream_fail" \
    "/usr/bin/false" \
    "/bin/echo downstream-still-runs" || {
    record_result "Case 5 seal 失败" 0
    exit 1
}
out=$("$SEALED_BIN" 2>&1)
rc=$?
# 下游 echo 仍应执行（shell 默认行为），但 exit 应为上游的 1
if [ "$out" = "downstream-still-runs" ] && [ $rc -eq 1 ]; then
    record_result "Case 5 上游失败：下游仍执行，exit=1" 1
else
    record_result "Case 5 上游失败（got stdout=\"$out\", exit=$rc, want exit=1）" 0
fi
echo ""

# ---------------------------------------------------------------
# Case 6: 退出码 — 下游失败 → 下游码胜出
# ---------------------------------------------------------------
echo "[Case 6] 退出码：上游 echo | 下游 false → exit 1（下游）"
seal_pipe "c6_downstream_fail" \
    "/bin/echo ok" \
    "/usr/bin/false" || {
    record_result "Case 6 seal 失败" 0
    exit 1
}
"$SEALED_BIN" >/dev/null 2>&1
rc=$?
if [ $rc -eq 1 ]; then
    record_result "Case 6 下游失败：exit=1" 1
else
    record_result "Case 6 下游失败（got exit=$rc, want 1）" 0
fi
echo ""

# ---------------------------------------------------------------
# Case 7: 退出码 — 多段失败，取最左（pipefail 等价）
# ---------------------------------------------------------------
echo "[Case 7] 退出码：sh -c 'exit 42' | false → exit 42（最左失败）"
seal_pipe "c7_leftmost_fail" \
    '/bin/sh -c "exit 42"' \
    "/usr/bin/false" || {
    record_result "Case 7 seal 失败" 0
    exit 1
}
"$SEALED_BIN" >/dev/null 2>&1
rc=$?
if [ $rc -eq 42 ]; then
    record_result "Case 7 最左失败者胜：exit=42（非 1）" 1
else
    record_result "Case 7 最左失败者胜（got exit=$rc, want 42）" 0
fi
echo ""

# ---------------------------------------------------------------
# 结果汇总
# ---------------------------------------------------------------
echo "=================================================="
echo "结果：$PASS_COUNT 通过 / $FAIL_COUNT 失败"
echo "=================================================="
if [ $FAIL_COUNT -eq 0 ]; then
    echo "✅ v1.2 管道端到端验证全部通过"
    exit 0
else
    echo "❌ 有测试失败，请检查上面的输出"
    exit 1
fi
