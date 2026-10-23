# 实施状态（Recovery Entry）

> 更新：2026-10-24。本文件是会话中断/上下文压缩后的恢复入口；以 Git、文件与测试输出为准，不采信未经证据的"已完成"叙述。

## 1. 当前阶段

- **Stage 0 — DONE / FROZEN（第 4 轮确认 + 冻结哈希抽查 PASS）**：T0.1 第 2 轮独立复核 PASS；T0.2–T0.6 与 M5 全部具备机器证据；292 项测试全绿。
- **Stage 1 — IN_PROGRESS**：T1.0 规则目录与 Rule ID 已冻结（20 条）；T1.1/T1.2/T1.3/T1.5/T1.6/T1.7 已完成；T1.4 为测量 JSON 模式（SIMULATED），真实探针转 T3.3。
- 分支：`v1.3.3-contract-closure`。
- 基线：`main` 上 `e7e921e`，tag `v1.3.2-baseline`，SHA256 `70f5f339…9411ea04`。
- 裁决：`CONTRACT_CLOSURE_READY_FOR_REVIEW` 已由第 2 轮 PASS 解除；Stage 0 Exit 以 `docs/STAGE0_ACCEPTANCE.md` 为准，**仍不是 Release**。

## 2. 已完成（有证据）

| 项 | 产物 | 证据 |
|---|---|---|
| 不可变基线 | commit `e7e921e` + tag | `git show e7e921e --stat`；SHA256 与执行令一致 |
| 契约字典与 14 份 Schema | `contracts/` | `tests/unit/test_schemas.py`、`test_enums.py` |
| Mode×Gate 机器策略 | `contracts/mode-gate-policy.v1.3.3.json` | `tests/unit/test_policy.py` |
| finalize/Gate 引擎 | `runtime/uiux_engine/` | `tests/integration/test_finalize.py`、`test_cli.py` |
| 正反 fixtures | `tests/fixtures/`（14 valid / 15 invalid / 5 semantic） | `_build_fixtures.py`、Schema 测试 |
| 契约+安装测试 | `tests/`（292 项） | `.venv\Scripts\python.exe -m pytest tests -q` |
| 契约测试证据 | `evidence/T0.1/contract-test-evidence.json` | 292/292 PASS（T0.1 证据仍为 160/160 冻结值），exit 0（以 evidence 为准） |
| 双 Skill 入口与启动器 | `skills/uiux`、`skills/uiux-verify` | `tests/integration/test_install.py`（launch enums） |
| 安装/卸载/升级/回滚 | `scripts/setup_skill.py`、`scripts/uninstall_skill.py` | 版本并存、删除源码后仍可启动、未知 Skill 不覆盖 |
| doctor | `scripts/setup_skill.py doctor` | `host-capability.v1.3.3` 校验、root/rank/shadowed_by |
| 任务登记 | `plan/tasks.v1.3.3.json`、`docs/TASK_PLAN.md` | `tests/unit/test_task_registry.py`（61 任务、M1–M18/m1–m8 全覆盖） |
| 规范 | `SPEC_V1.3.3.md` | 本文件与 `docs/V1.3.3_CHANGELOG.md` |

## 3. 进行中

| 任务 | 状态 | 阻塞点 |
|---|---|---|
| T0.1 | DONE（第 2 轮 PASS） | 第 3 轮增量确认（R-01..R-11） |
| T0.2–T0.6 | DONE | 证据见 `docs/STAGE0_ACCEPTANCE.md` |
| T1.0 规则/Rule ID 冻结 | READY（下一入口） | — |
| T1.5 Gate 引擎完整化 | IN_PROGRESS | 待 Stage 1 工具日志接入 |
| M5 UNC/junction/MAX_PATH | DONE | `tests/integration/test_paths.py` |

### 3.1 第 1 轮独立复核返修（2026-10-24）

| 编号 | 问题 | 修复 | 负向测试 |
|---|---|---|---|
| F-01 | production-code 的 L4 未强制独立 | `policy.l4_independent_required()` 按 `deliverable_tier` 派生；策略拆为 `review_policy` 与 `design_review_policy` | `test_production_code_l4_selftest_reviewer_is_rejected` |
| F-02 | coverage 可自报层级 | coverage 与 manifest provenance/tool-log 交叉校验；gate observed 不得超过证据层级 | `test_coverage_claiming_native_without_native_provenance_is_rejected`、`test_gate_observed_level_above_evidence_is_rejected` |
| F-03 | WARN 处置未 Schema 校验/未绑 HEAD | CLI 文件走同一 `warn_review` Schema；`reviewed_head` 必须等于冻结指纹 | `test_warn_review_missing_fields_is_rejected`、`test_warn_review_bound_to_wrong_head_is_rejected` |
| F-04 | 文档计数漂移 | 计数统一为 172；evidence 输入集加入 SPEC/docs/plan | `run_contract_tests.py` |
| F-05 | 顶层 `g6` 未被拒 | 删除顶层 `g6` property | `test_top_level_g6_is_rejected` |
| F-06 | AVAILABLE 字节校验口径 | 明确 T3.5 实现；T0.1 只做清单/引用哈希 | SPEC §3.6/§15 |
| F-07 | ISOLATED_REVIEW_VERIFIED 不可达 | 有效 ISOLATED_SESSION 审查可产生该状态 | `test_isolated_session_delivery_is_reachable` |
| F-08 | 枚举/状态集硬编码 | rank 全部读字典；review-only 状态读策略；移除 `RANKED_ENUMS` | `test_every_schema_enum_belongs_to_one_dictionary_namespace` |
| F-09 | FAILED 与策略不一致 | MANDATORY/REVIEW_ONLY FAIL、L4 FAIL → FAILED | `test_design_review_fail_yields_failed_status` |
| F-10 | REJECTED 成死枚举 | 允许 REJECTED + 反证 | `test_warn_rejected_with_counter_evidence_can_complete` |
| F-11 | date-time 未校验/解析崩溃 | 自定义 date-time checker；`parse_time` 安全返回 None；坏 `--now` 退出 2 | `test_malformed_datetime_is_rejected`、`test_cli_rejects_invalid_now_timestamp` |
| F-12 | 测试与 ReasonCode 闭集弱 | 命名空间校验、outcome 形状断言、gate/unverified reason code 闭集 | `test_gate_reason_codes_must_be_registered` 等 |
| F-13 | repair_cycles 恒 0 | `finalize --repair-cycles` 回填并校验 0..2 | CLI happy path |
| F-14 | runtime_targets 可事后调低 | `request_digest` 必填并交叉校验 | `test_request_digest_mismatch_blocks_complete`、`test_cli_rejects_request_digest_mismatch` |
| F-15 | 死代码 | 删除 `derive_runtime_targets`/`_unused`；删除 `contracts.schema_path` | compileall |
| F-16 | 审核输入不可复核 | 新增 `docs/audits/V1.3.2_DSH_REVIEW_SUMMARY.md` | 仓库内可追溯 |

### 3.2 第 2 轮独立复核（2026-10-24）

- 结论：**T0.1 PASS**（针对 commit `13a222e` / 代码 `597b71d`）。
- 证据：133/133、exit 0；101 项输入哈希全匹配；复跑两次一致；无新 BLOCKER/MAJOR。
- 3 项 MAJOR 均判 FIXED，且负向测试在旧实现下会失败。
- R-01..R-11 已处置：fixtures/ReasonCode 计数、审核记录落库、policy fact 声明与冗余标注、删除死代码、RFC3339 收紧、coverage 证据状态、WARN 证据可用性、FAILED 负向测试、字段命名空间映射、ISOLATED 语义确认（D-023）。
- 第 2 轮结论全文与处置表：`docs/audits/V1.3.3_CONTRACT_REVIEW.md`。

## 4. 下一批 READY（按依赖）

1. **R-01..R-11 增量确认**（同一 Reviewer 只读确认并重建证据）。
2. **T0.3** DSH 实机安装与双入口发现（已完成用户级安装与发现，待落库证据）。
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
