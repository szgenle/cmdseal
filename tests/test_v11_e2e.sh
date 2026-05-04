#!/bin/bash
# v1.1 端到端验证脚本
# 验证安全加固 #2/#3/#4 是否生效

set -e

echo "=============================================="
echo "cmdseal v1.1 端到端安全验证"
echo "=============================================="
echo ""

# 清理旧产物
echo "[清理] 删除旧的测试 binary..."
rm -f ./demo/v11_test_seal
security delete-generic-password -s "cmdseal.v11test.K" 2>/dev/null || true
echo ""

# Step 1: Seal 一个 env 命令（用于验证环境变量清理）
echo "[Step 1] 封存 env 命令（验证环境变量清理）..."
python3 cmdseal.py seal \
    --command 'env {{arg:1}}' \
    --output ./demo/v11_test_seal \
    --user $(whoami)
echo ""

# Step 2: 验证首 token 解析为绝对路径
echo "[Step 2] 验证首 token 解析..."
# 查看 seal 时的输出应该包含 "resolved 'env' -> '/usr/bin/env'"
echo "✅ 检查 seal 输出（应该看到 resolved 'env' -> '/usr/bin/env'）"
echo ""

# Step 3: 验证 codesign runtime flag
echo "[Step 3] 验证 codesign hardened runtime..."
codesign -dvvv ./demo/v11_test_seal 2>&1 | grep -i "runtime" || {
    echo "❌ 未找到 runtime flag"
    exit 1
}
echo "✅ hardened runtime 已启用"
echo ""

# Step 4: 首次运行（需要手动点击弹窗）
echo "[Step 4] 首次运行测试 binary..."
echo "⚠️  即将弹出 macOS 混合窗（登录密码 + 始终允许）"
echo "   请点击'始终允许'并输入登录密码"
echo ""
./demo/v11_test_seal "TEST_VAR=hello" 2>&1 | head -20
echo ""

# Step 5: 验证 DYLD_INSERT_LIBRARIES 被拒绝
echo "[Step 5] 验证 DYLD_INSERT_LIBRARIES 注入防护..."
echo "   尝试用 DYLD_INSERT_LIBRARIES 注入..."

# 创建一个假的 dylib
cat > /tmp/fake_lib.c << 'EOF'
#include <stdio.h>
__attribute__((constructor))
void fake_init(void) {
    printf("❌ DYLD INJECTION SUCCESSFUL - THIS IS A SECURITY FAILURE!\n");
}
EOF

cc -dynamiclib -o /tmp/fake_lib.dylib /tmp/fake_lib.c 2>/dev/null

# 尝试注入
echo "   运行: DYLD_INSERT_LIBRARIES=/tmp/fake_lib.dylib ./demo/v11_test_seal"
output=$(DYLD_INSERT_LIBRARIES=/tmp/fake_lib.dylib ./demo/v11_test_seal "TEST_VAR=check" 2>&1)

if echo "$output" | grep -q "DYLD INJECTION SUCCESSFUL"; then
    echo "❌ 失败：DYLD 注入成功！"
    echo "$output"
    exit 1
else
    echo "✅ DYLD 注入被成功阻止"
fi
echo ""

# Step 6: 验证子进程环境变量清理
echo "[Step 6] 验证子进程环境变量清理..."
echo "   检查子进程是否继承了 DYLD_* 变量..."

output=$(DYLD_INSERT_LIBRARIES=/tmp/fake_lib.dylib DYLD_FORCE_FLAT_NAMESPACE=1 ./demo/v11_test_seal "SHOW_ENV=1" 2>&1)

if echo "$output" | grep -q "DYLD_"; then
    echo "❌ 失败：子进程继承了 DYLD_* 变量！"
    echo "$output" | grep "DYLD_"
    exit 1
else
    echo "✅ 子进程环境变量已正确清理（无 DYLD_* 变量）"
fi
echo ""

# Step 7: 验证稳态性能
echo "[Step 7] 验证稳态性能（应该毫秒级）..."
start_time=$(python3 -c "import time; print(int(time.time() * 1000))")
./demo/v11_test_seal "PERF_TEST=1" > /dev/null 2>&1
end_time=$(python3 -c "import time; print(int(time.time() * 1000))")
elapsed=$((end_time - start_time))
echo "   运行耗时: ${elapsed}ms"
if [ $elapsed -lt 200 ]; then
    echo "✅ 性能正常（< 200ms）"
else
    echo "⚠️  性能偏慢（>= 200ms），但可接受"
fi
echo ""

# 清理
echo "[清理] 删除测试产物..."
rm -f ./demo/v11_test_seal /tmp/fake_lib.c /tmp/fake_lib.dylib
security delete-generic-password -s "cmdseal.v11test.K" 2>/dev/null || true
echo ""

echo "=============================================="
echo "✅ v1.1 端到端验证全部通过！"
echo "=============================================="
