# cmdseal — 开发任务入口
#
# 常用：
#   make             查看所有目标
#   make sync        安装运行时依赖（PySide6）
#   make run         启动 GUI
#   make smoke       无头烟囱测试（CI/本地自检）
#   make helper      编译 cmdseal_helper（CLI 首次运行会自动触发，这里供手动）
#   make app         使用 pyinstaller 打包 .app（需 make sync-pkg 先拉依赖）
#   make clean       清构建产物（_build/、dist/、build/）
#   make distclean   清 .venv 与锁缓存（重装前用）

SHELL := /bin/zsh
PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

UV       ?= uv
PY       := $(UV) run python
QT_HEADLESS := QT_QPA_PLATFORM=offscreen

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------
.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*##"; printf "目标：\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

# ---------------------------------------------------------------------------
# 依赖管理（uv）
# ---------------------------------------------------------------------------
.PHONY: sync sync-pkg lock upgrade
sync: ## 安装运行时依赖（PySide6）
	$(UV) sync

sync-pkg: ## 安装运行时依赖 + 打包分组（pyinstaller）
	$(UV) sync --group packaging

lock: ## 刷新 uv.lock（不升级）
	$(UV) lock

upgrade: ## 升级所有依赖并同步 venv
	$(UV) lock --upgrade
	$(UV) sync

# ---------------------------------------------------------------------------
# 运行 / 自检
# ---------------------------------------------------------------------------
.PHONY: run smoke
run: ## 启动 GUI（python -m gui）
	$(PY) -m gui

smoke: ## 无头自检：构造主窗口 + seal 向导后立刻退出
	$(QT_HEADLESS) $(PY) -c "from PySide6.QtCore import QTimer; \
from PySide6.QtWidgets import QApplication; \
from gui.main_window import MainWindow; \
from gui.seal_wizard import SealWizard; \
from gui import backend; \
app=QApplication([]); w=MainWindow(); w.show(); \
wz=SealWizard(); wz.show(); \
QTimer.singleShot(200, app.quit); \
rc=app.exec(); \
print('smoke: exit=', rc, 'backend_ok=', backend.CMDSEAL_PY.is_file())"

# ---------------------------------------------------------------------------
# 国际化（i18n）
#   UI 字符串以英文为 source；.qm 翻到 zh_CN。
#   代码里新增/改动 self.tr("...") 后：
#     1. make i18n-update   # 扫出最新 source 到 .ts（保留已填翻译）
#     2. 手工编辑 gui/translations/cmdseal_zh_CN.ts 填 <translation>
#     3. make i18n-release   # 编译 .qm
# ---------------------------------------------------------------------------
.PHONY: i18n-update i18n-release
I18N_TS := gui/translations/cmdseal_zh_CN.ts
I18N_QM := gui/translations/cmdseal_zh_CN.qm
I18N_SRC := gui/main_window.py gui/runner_list.py gui/preferences.py \
            gui/seal_wizard.py \
            gui/template_wizard/_core.py \
            gui/template_wizard/_wizard.py \
            gui/template_wizard/_command_page.py \
            gui/template_wizard/_param_page.py \
            gui/template_wizard/_output_page.py \
            gui/template_wizard/_exec_page.py

# pyside6-lupdate / pyside6-lrelease 在 uv venv 里没有暴露为 console
# script；它们以裸可执行文件存在于 PySide6 包目录下。用 Python 运
# 行时在 recipe 里定位——不要用顶层 $(shell ...)，否则每次 make
# 加载（连 `make help` / `make smoke`）都会启动一次 uv + import
# PySide6，白白增加 0.3-0.5s 开销。
PYSIDE6_DIR_CMD = $(UV) run python3 -c "import PySide6, pathlib; print(pathlib.Path(PySide6.__file__).parent)"

i18n-update: ## 从源码扫出最新 UI 字符串到 .ts
	@mkdir -p gui/translations
	@PYSIDE6_DIR=$$($(PYSIDE6_DIR_CMD)) && \
		"$$PYSIDE6_DIR/lupdate" $(I18N_SRC) -ts $(I18N_TS)

i18n-release: ## 编译 .ts -> .qm（GUI 运行时加载）
	@PYSIDE6_DIR=$$($(PYSIDE6_DIR_CMD)) && \
		"$$PYSIDE6_DIR/lrelease" $(I18N_TS) -qm $(I18N_QM)

# ---------------------------------------------------------------------------
# C helper（供 cmdseal.py 调用；日常无需手动）
# ---------------------------------------------------------------------------
.PHONY: helper
helper: ## 手动编译 + ad-hoc 签名 cmdseal_helper
	@mkdir -p _build
	cc -O2 -Wall -Wno-deprecated-declarations \
		-o _build/cmdseal_helper cmdseal_helper.c \
		-framework Security -framework CoreFoundation
	codesign -s - --force --timestamp=none --options runtime _build/cmdseal_helper

# ---------------------------------------------------------------------------
# 打包（pyinstaller，骨架，后续再补 spec 文件）
# ---------------------------------------------------------------------------
.PHONY: app
app: sync-pkg ## 打包 .app（需 packaging 依赖）
	$(UV) run pyinstaller \
		--name cmdseal \
		--windowed \
		--noconfirm \
		--paths $(PROJECT_ROOT) \
		--collect-submodules gui \
		--add-data cmdseal.py:assets \
		--add-data cmdseal_helper.c:assets \
		--add-data runner_aead_template.c:assets \
		--add-data gui/translations/cmdseal_zh_CN.qm:gui/translations \
		run_gui.py

# ---------------------------------------------------------------------------
# 清理
# ---------------------------------------------------------------------------
.PHONY: clean distclean
clean: ## 删除构建产物（_build/ build/ dist/ __pycache__/）
	rm -rf _build build dist
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +

distclean: clean ## 额外清 .venv（重装前用）
	rm -rf .venv uv.lock
