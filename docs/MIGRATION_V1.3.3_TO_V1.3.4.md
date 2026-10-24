# V1.3.3 → V1.3.4 契约迁移与兼容矩阵

> 本文件是 TASK-00 的正式交付物。原则：**V1.3.3 契约冻结只读；V1.3.4 追加式扩展；无静默混用。**

## 1. 版本策略

| 项 | 规则 |
|---|---|
| 契约文件 | `contracts/*.v1.3.3.schema.json` 原样保留；新增 `contracts/*.v1.3.4.schema.json`（26 份全套，自包含，`$id`/`$ref` 只指向同版本） |
| 枚举字典 | `enums.v1.3.3.json` 保留；新增 `enums.v1.3.4.json`（只增不改） |
| 策略文件 | `mode-gate-policy.v1.3.3.json` 保留；新增 `mode-gate-policy.v1.3.4.json`（内容相同，版本号 1.3.4） |
| 版本推断 | 输入含 `schema_version` → 用该版本；不含 → 用当前版本但必然因 `required` 失败（fail-closed） |
| 未知版本 | 返回 `SCHEMA_VERSION_UNSUPPORTED`，不回退 |
| 混合版本 | finalize/校验返回 `SCHEMA_VERSION_MISMATCH`，不静默选择 |
| 分派入口 | `contracts.validation_errors(name, instance, version=None)`；`uiux-engine validate --schema-version`；`uiux-engine finalize --schema-version`（必须与 request 一致） |

## 2. 字段级迁移矩阵

### 2.1 `coverage-matrix`（record）

| 字段 | V1.3.3 | V1.3.4 | 说明 |
|---|---|---|---|
| `test_state` | 5 枚举（PASS/FAIL/UNVERIFIED/BLOCKED/NOT_APPLICABLE） | **不变** | 不得替换或新增值 |
| `disposition` | — | 可选，9 枚举 | 未通过项的处置原因 |
| `scope_ref` | — | 可选 string | 关联 declared scope 项 |
| `risk_ref` | — | 可选 string | 关联高风险清单项；用于风险门禁 |
| 其余字段 | 不变 | 不变 | `required_runtime_level`、`observed_runtime_level`、`evidence_refs` 等 |

`disposition` 枚举：`ENVIRONMENT_UNAVAILABLE`、`AUDITOR_OMISSION`、`TOOL_UNAVAILABLE`、`FIXTURE_INVALID`、`NATIVE_INTERACTION_UNAVAILABLE`、`NOT_APPLICABLE`、`PRODUCT_FAILURE`、`EVIDENCE_MISSING`、`INDEPENDENCE_UNVERIFIED`。

### 2.2 `task-result`

| 字段 | V1.3.3 | V1.3.4 | 说明 |
|---|---|---|---|
| `status` / `delivery_status` / `independent_review_status` / `design_review_status` | 不变 | 不变 | 顶层语义保持 |
| `delivery_dimensions` | — | 可选对象（6 维度 + notes） | execution/scope/evidence/risk/independence/delivery |
| `scope_summary` | — | 可选对象（11 计数） | declared scope 映射统计；TASK-02 提供 inventory 后完整 |
| 其余字段 | 不变 | 不变 | `gates`、`derived_g6`、`coverage_matrix` 等 |

### 2.3 其他 Schema

| Schema | 变化 |
|---|---|
| `common` | 新增 `$defs/disposition`（9 枚举）；其余不变 |
| `gate-results` | 新增可选 `gate_result.dispositions` 数组；其余不变 |
| 其余 23 份 | 版本重写（`$id`/`$ref`/`title`/`schema_version`），语义不变 |

### 2.4 枚举字典

新增：`Disposition`、`DeliveryDimensionStatus`、`ScopeCoverageStatus`、`RiskCoverageStatus`、`EvidenceIntegrityStatus`、`DeliveryDimension`。
`DeliveryStatus` 追加 `PARTIAL_SCOPED`（仅用于 `delivery_dimensions.delivery_status`；顶层 `delivery_status` 输出仍为 `PARTIAL_VERIFIED`）。
新增 reason code：`SCHEMA_VERSION_MISSING`、`SCHEMA_VERSION_MISMATCH`、`SCHEMA_VERSION_UNSUPPORTED`、`SCOPE_MANIPULATION`、`SCOPE_MAPPING_INCOMPLETE`、`SCOPE_REF_UNKNOWN`、`DISPOSITION_REQUIRED`、`RISK_GATE_BLOCKED`、`DELIVERY_DIMENSION_MISMATCH`、`FIXTURE_INVALID`、`FIXTURE_ENVIRONMENT_ERROR`、`AUDITOR_OMISSION`、`ENVIRONMENT_UNAVAILABLE`。

## 3. 聚合规则对照（G6 / runtime level）

| 记录状态 | V1.3.3（legacy） | V1.3.4（新） |
|---|---|---|
| PASS | 计入 observed level | 计入 observed level |
| FAIL / BLOCKED | 视为 NONE | 视为 NONE |
| UNVERIFIED（无 disposition） | 视为 NONE | 视为 NONE |
| UNVERIFIED + `ENVIRONMENT_UNAVAILABLE` / `NATIVE_INTERACTION_UNAVAILABLE` / `TOOL_UNAVAILABLE` / `FIXTURE_INVALID` | 视为 NONE | **排除出 aggregate**，但保留在 `unverified_paths`（reason_code=disposition） |
| UNVERIFIED + `AUDITOR_OMISSION` / `PRODUCT_FAILURE` / `EVIDENCE_MISSING` | 视为 NONE | 视为 NONE，并入 blocking_reasons |
| `NOT_APPLICABLE` | 跳过 | 跳过 |
| 高风险项（`risk_ref`）非 PASS | 由 unverified_paths 阻断 COMPLETE | 同时令 `delivery_dimensions.risk_coverage_status` 为 UNVERIFIED/BLOCKED |

`status` 判定不变：COMPLETE 需要全部 mandatory Gate、证据、覆盖、L4、独立性满足且无 unverified_paths。因此 V1.3.4 的范围化部分完成仍为 `PARTIAL`，由 `delivery_dimensions.delivery_status` 标注 `PARTIAL_SCOPED`。

## 4. 强制兼容用例（已实现测试）

测试文件：`tests/unit/test_version_dispatch.py`

| 用例 | 断言 | 结果 |
|---|---|---|
| V1.3.3 输入（真实验收证据 `G:\AI\uiux-acceptance-v133\evidence\audit`） | `status=PARTIAL`、`derived_g6.state=UNVERIFIED`、`runtime_evidence_level=NONE`、`delivery_status=PARTIAL_VERIFIED` | PASS |
| V1.3.3 输出不含 V1.3.4 新字段 | `delivery_dimensions`/`scope_summary` 不存在 | PASS |
| V1.3.3 单条 UNVERIFIED | aggregate=NONE、reason_code=`UNVERIFIED_PATH` | PASS |
| 无版本输入 | 校验失败（`schema_version` required） | PASS |
| 未知版本 | `SCHEMA_VERSION_UNSUPPORTED` | PASS |
| 混合版本 finalize | `SCHEMA_VERSION_MISMATCH`、非 COMPLETE | PASS |
| V1.3.4 排除 disposition | aggregate 不被拉低、`unverified_paths` 保留原因码、`scope_coverage_status=PARTIAL` | PASS |
| V1.3.4 审计遗漏 | aggregate=NONE | PASS |
| V1.3.4 高风险缺口 | `risk_coverage_status != PASS`、非 COMPLETE | PASS |
| V1.3.4 全 PASS | COMPLETE、`scope_coverage_status=COMPLETE` | PASS |

全量回归：`460 + 13 = 473 tests passed`（2026-10-24，worktree `v1.3.4-hardening`）。

## 5. 安装/升级/回滚

- 安装 V1.3.4：`python scripts/setup_skill.py install --scope user --source <repo>`（默认 `--version 1.3.4`）；发行 manifest 与 suite-link 的 `schema_version` 随安装版本写入。
- 升级：V1.3.3 已安装 → `upgrade --version 1.3.4`；同版本重复升级返回 `UPGRADE_NOT_NEWER`（exit 10）。
- 回滚：`rollback --version 1.3.3`（若 1.3.3 版本目录仍存在）。
- 跨版本回归已并入 `tests/integration/test_install.py`。

## 6. 迁移操作建议

1. 旧任务证据（V1.3.3 TaskRequest/GateResults/Coverage）保持原样，可直接被 V1.3.4 引擎读取并复现旧语义。
2. 新任务使用 V1.3.4 契约生成证据；若需 `disposition`/`scope_ref`/`risk_ref`，只能写入 V1.3.4 契约文件。
3. 不要把 V1.3.4 新字段写进 V1.3.3 文件（schema 会拒绝），也不要手工混用两个版本（finalize 会 `SCHEMA_VERSION_MISMATCH`）。
4. 迁移完成后运行 `uiux-engine validate --schema <name> --instance <file>` 与 `uiux-engine finalize ...` 复核。
