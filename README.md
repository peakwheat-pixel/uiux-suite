# Universal UI/UX Engineering Suite

面向 DSH（DeepSeek Harness）的 UI/UX 工程能力包：双 Skill 入口、7 模式契约、G0–G6 门禁、原生/模拟证据分层、L4 设计评审与可复核的安装/验收链路。

> 当前版本：**1.3.3（Contract Closure）**
> 状态：Stage 0 DONE（T0.1 独立复核 PASS；T0.2–T0.6 与 M5 均有机器证据）；Stage 3 进行中，按 `docs/TASK_PLAN.md` 推进。
> 基线：`SPEC_V1.3.2.md`（不可变，SHA256 `70f5f339…9411ea04`），修订规范 `SPEC_V1.3.3.md`。

## 快速开始

```powershell
# 1. 安装依赖（已有 .venv 可跳过）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. 用户级安装（默认 <USERPROFILE>/.agents；DSH_AGENTS_HOME 可覆盖）
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh install --scope user --version 1.3.3

# 3. doctor
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh doctor --scope user

# 4. 运行入口
$env:USERPROFILE\.agents\skills\uiux\scripts\launch.py enums
$env:USERPROFILE\.agents\skills\uiux-verify\scripts\launch.py enums
```

更多：`docs/INSTALL.md`、`docs/CLI.md`、`docs/STAGE0_ACCEPTANCE.md`。

## 目录

| 路径 | 内容 |
|---|---|
| `contracts/` | 14 份 JSON Schema、枚举字典、Mode×Gate 机器策略 |
| `runtime/uiux_engine/` | 契约加载、策略、Gate/finalize、证据、CLI |
| `skills/uiux`、`skills/uiux-verify` | 双 Skill 入口与启动器 |
| `scripts/` | 安装/doctor/卸载/证据/任务登记脚本 |
| `tests/` | 405 项契约、Gate、安装与宿主测试 |
| `evidence/` | T0.1/T0.3 机器可复核证据 |
| `docs/` | 规范、任务计划、审核记录、交付文档 |
| `dist/` | 本地发行包与离线 wheels（不入 Git） |

## 验证

```powershell
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\run_contract_tests.py
```

## 许可证

见 `LICENSE` 与 `THIRD_PARTY_NOTICES.md`；不随包分发第三方字体。
