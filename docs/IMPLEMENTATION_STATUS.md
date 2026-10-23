# 实施状态（Recovery Entry）

> 更新：2026-10-24。本文件是会话中断/上下文压缩后的恢复入口；以 Git、文件与测试输出为准，不采信未经证据的"已完成"叙述。

## 1. 当前阶段

- **Stage 0 / T0.1 — IN_PROGRESS**（契约已实现并通过 111 项机器测试，等待独立只读复核签发）。
- **T0.2/T0.4 — IN_PROGRESS**（安装器、启动器、doctor、升级/回滚、卸载已实现并通过集成测试；等待 T0.1 复核后完成 Stage 0 验收）。
- 分支：`v1.3.3-contract-closure`。
- 基线：`main` 上 `e7e921e`，tag `v1.3.2-baseline`，SHA256 `70f5f339…9411ea04`。
- 裁决：`CONTRACT_CLOSURE_READY_FOR_REVIEW`，**不是** Stage 0 PASS，也不是 Release。

## 2. 已完成（有证据）

| 项 | 产物 | 证据 |
|---|---|---|
| 不可变基线 | commit `e7e921e` + tag | `git show e7e921e --stat`；SHA256 与执行令一致 |
| 契约字典与 14 份 Schema | `contracts/` | `tests/unit/test_schemas.py`、`test_enums.py` |
| Mode×Gate 机器策略 | `contracts/mode-gate-policy.v1.3.3.json` | `tests/unit/test_policy.py` |
| finalize/Gate 引擎 | `runtime/uiux_engine/` | `tests/integration/test_finalize.py`、`test_cli.py` |
| 正反 fixtures | `tests/fixtures/`（14 valid / 14 invalid / 5 semantic） | `_build_fixtures.py`、Schema 测试 |
| 契约+安装测试 | `tests/`（111 项） | `.venv\Scripts\python.exe -m pytest tests -q` |
| 契约测试证据 | `evidence/T0.1/contract-test-evidence.json` | 102/102（当时），exit 0；安装测试后总 111 |
| 双 Skill 入口与启动器 | `skills/uiux`、`skills/uiux-verify` | `tests/integration/test_install.py`（launch enums） |
| 安装/卸载/升级/回滚 | `scripts/setup_skill.py`、`scripts/uninstall_skill.py` | 版本并存、删除源码后仍可启动、未知 Skill 不覆盖 |
| doctor | `scripts/setup_skill.py doctor` | `host-capability.v1.3.3` 校验、root/rank/shadowed_by |
| 任务登记 | `plan/tasks.v1.3.3.json`、`docs/TASK_PLAN.md` | `tests/unit/test_task_registry.py`（61 任务、M1–M18/m1–m8 全覆盖） |
| 规范 | `SPEC_V1.3.3.md` | 本文件与 `docs/V1.3.3_CHANGELOG.md` |

## 3. 进行中

| 任务 | 状态 | 阻塞点 |
|---|---|---|
| T0.1 | IN_PROGRESS | 独立只读复核未完成 |
| T0.2 | IN_PROGRESS | 安装闭环已实现；待 T0.1 复核与 T0.3 实机安装 |
| T0.4 | IN_PROGRESS | doctor 已实现；待 DSH 实机根/遮蔽验证 |
| T1.5 Gate 引擎完整化 | IN_PROGRESS | 待 Stage 1 工具日志接入 |
| M2/M5/M9 | IN_PROGRESS | DSH 实机、UNC/长路径、Stage Exit 三列化 |

## 4. 下一批 READY（按依赖）

1. **独立 T0.1 复核**（只读 Reviewer，检查契约、测试证据与 Spec 一致性）。
2. **T0.3** DSH 实机安装与双入口发现。
3. **T0.5** 许可证与离线依赖锁定（M4）。
4. **T0.6** 删除开发仓回归。
5. **M2/M5/M9 收尾**（实机根/遮蔽、UNC/长路径、Stage Exit 表）。

## 5. 恢复步骤

```powershell
cd G:\AI\universal-uiux-engineering
git status
git log --oneline -5
.\.venv\Scripts\python.exe scripts\run_contract_tests.py
.\.venv\Scripts\python.exe scripts\build_task_registry.py
```

判定规则：

- 若 `evidence/T0.1/contract-test-evidence.json` 的 `exit_code != 0` 或 `summary.failures > 0`，先修复测试，不得进入 T0.2。
- 若 Git 工作区有未提交改动，先提交或记录 WIP 再继续。
- 若 `plan/tasks.v1.3.3.json` 与渲染不一致，先重跑 `build_task_registry.py`。

## 6. 关键路径与限制

- T0.3 需要真实 DSH 宿主；当前环境可用用户级安装验证。
- Stage 3 原生 GUI 依赖交互式 Windows 桌面；缺失时记 `UNVERIFIED`。
- Stage 5 真实项目只允许在独立副本/独立 worktree 操作，禁止改 `G:\CODEX\New Manga` 真实工作目录。
- 外部编排器不存在不影响任何主路径。

## 7. 最新可靠恢复点

- Commit：`e7e921e`（基线）；V1.3.3 契约提交见 `git log`（本轮提交）。
- 证据：`evidence/T0.1/contract-test-evidence.json`（含输入文件 SHA256 与 stdout 哈希）。
