# Universal UI/UX Engineering Skill Suite V1.3.3 — Contract Closure 实施规范

> **状态：T0.1 CONTRACT CLOSURE CANDIDATE（契约已实现并通过机器测试；独立复核待签发，尚未是 Stage 0 PASS）**
> 日期：2026-10-24
> 前版：`SPEC_V1.3.2.md`（不可变基线，commit `e7e921e`，tag `v1.3.2-baseline`，SHA256 `70f5f3399079ad138685295c9ec2915544c03e77b7cf49f08e5959bc9411ea04`）
> 本版分支：`v1.3.3-contract-closure`
> 实施证据：`evidence/T0.1/contract-test-evidence.json`（133 项契约+安装测试通过，exit_code=0）
> 适用对象：DSH（首选实测宿主）、Codex / Claude Code / ZCode / Antigravity / Qoder（逐项验证，未测即 `UNVERIFIED`）

---

## 0. 本版裁决与变更范围

### 0.1 V1.3.3 解决什么

V1.3.2 的 6 项 BLOCKER、18 项 MAJOR、8 项 MINOR 中，**B1–B6 的契约部分已在本版落地为机器可校验对象**：

| 编号 | 问题 | V1.3.3 关闭方式 | 证据 |
|---|---|---|---|
| B1 | 发行/启动契约未定义 | `suite-link`、`release-manifest`、`policy`、`tool-log`、`review-attestation` 五份 Schema + 路径规则 + 稳定 ReasonCode | `contracts/*.v1.3.3.schema.json`、`tests/unit/test_schemas.py` |
| B2 | 枚举不闭合、词表混用 | 唯一枚举字典 `contracts/enums.v1.3.3.json`；`RuleSeverity` 与 `GateState` 分离；ReasonCode 闭集 | `tests/unit/test_enums.py`（Schema 中每个 enum 值必须属于字典） |
| B3 | Gate 语义不可执行 | `mode-gate-policy.v1.3.3.json` 机器矩阵；`WARN` 解除规则；`COMPLETE` 组合约束；G6 改为 finalize 派生 | `tests/unit/test_policy.py`、`tests/integration/test_finalize.py` |
| B4 | 跨层/跨路径证据不成立 | `coverage-matrix` 逐 task/scenario/level 记录；`probe_id`、`evidence_level`、最弱层汇总、`LAYER_SPOOF_OR_MISSING` | `test_mock_only_coverage_cannot_claim_native_target`、`test_layer_spoof_mock_log_claiming_native_is_rejected` |
| B5 | L4 评审无落点 | `design-review.v1.3.3.schema.json`：10 维量表、证据引用、来源/独立性、分歧；`design_review_status` + G6 检查 | `test_required_l4_review_missing_blocks_complete` |
| B6 | 证据生命周期不可执行 | `evidence-manifest.v1.3.3.schema.json` 状态机、`AVAILABLE` 清单/引用哈希一致性（原件字节校验 T3.5）、过期即失效、脱敏不得冒充原件 | `test_expired_evidence_cannot_support_pass`、`test_invalid_fixtures_are_rejected` |

### 0.2 与 V1.3.2 的边界

- V1.3.2 原文保持只读，不被覆盖；本文件是**完整替代规范**，冲突时以本文件与 `contracts/` 为准。
- 本版是**契约闭环**，不是全功能完成：`uiux`/`uiux-verify` 两个 Skill 入口、安装器、doctor、检测器与探针按 Stage 0–5 继续交付。
- 不得把本版文档存在等同于 Stage 0 PASS；T0.1 需独立只读复核签发。

### 0.3 红线（不变）

1. **DSH 优先，Agent Agnostic**；两个顶层 Skill `uiux`（设计/改造/自测）与 `uiux-verify`（只读验证/独立评审）。
2. **不主动依赖、不主动启动任何外部编排器**；外部调用方若存在，只能以 `caller.kind=external` 被动传参，Runner 不得修改其分支、HEAD、Worktree 或证据治理。
3. **Mock/Offscreen 不得冒充 Native**；证据层级由工具日志与 probe 来源核验，不由模型声明。
4. **同会话自测不得冒充独立审查**；`INDEPENDENT_REVIEW_PASS` 必须绑定可核验的隔离来源、冻结版本与只读证明。
5. **不得修改真实用户数据或越过授权写入范围**；四类写根与授权证据进入契约。
6. **保留专业 UX/UI 设计能力**：L4 评审、信息架构、Token、原型与取舍记录是必选产物，不是 Lint 的附属物。

### 0.4 ADR（V1.3.3 修订）

| 编号 | 决策 | 说明 |
|---|---|---|
| ADR-01 | 两个顶层 Skill、共享版本化运行时 | 职责边界不变；不假定两个名称构成独立会话 |
| ADR-02 | 发行根 + 薄启动器 + `suite-link.json` | 启动器固定从 `<skill_root>/suite-link.json` 读取，禁止按 cwd 猜路径 |
| ADR-03 | Schema + 策略 + finalize 派生 Gate | 模型不得自填 PASS；但本地同权 Agent 仍可改文件，安全等级必须如实声明 |
| ADR-04 | 源码/运行/契约三路能力发现 | 差异必须落为 WARN/FAIL/UNVERIFIED，不得静默忽略 |
| ADR-05 | 原始证据本地 Vault、交付仅脱敏 Evidence | 脱敏摘要不能替代可复核原件 |
| ADR-06 | 运行证据等级与审查隔离等级正交 | 两个字段独立出现，禁止复合 L0–L4 等级 |
| ADR-07 | 外部编排器仅被动兼容 | 无外部系统时核心功能完整；不以其为 Release 前提 |
| ADR-08 | 先契约与靶场、后能力扩张 | T0.1 未过不得进入真实改造 |

---

## 1. 范围、模式与交付层级

### 1.1 七种模式

| mode | 作用 | 可改生产源码 | 交付层级 | L4 必选 |
|---|---|---:|---|---:|
| `audit` | 只读审查现状 | 否 | `report-only` | 否 |
| `design-only` | 流程/IA/Token/方案 | 否 | `design-spec` | 是 |
| `prototype` | 隔离沙箱原型 | 否 | `interactive-prototype` | 是 |
| `new-build` | 新模块先设计后实现 | 是（授权范围） | `production-code` | 是 |
| `redesign` | 完整 UI/UX 重构 | 是（授权范围） | `production-code` | 是 |
| `targeted-fix` | 单点缺陷修复 | 是（仅目标） | `production-code` | 否 |
| `verify` | 冻结版本独立 QA/Review | 否 | `verification-report` | 否 |

### 1.2 非目标

- 不管理产品路线图、非 UI/UX 业务需求或外部 Agent 排期。
- 不以缩短点击数作为唯一 UX 指标；正确性、可发现性、错误恢复同等重要。
- 不承诺在没有原生运行环境时完成 Native 验收；缺环境必须 `PARTIAL/UNVERIFIED`。
- 不承诺本地同权恶意 Agent 无法篡改证据；高可信签发依赖独立校验器/CI（见 §5.6）。

---

## 2. 架构

```text
使用者 / 调用方（DSH 或其它 Agent，可为 CI/外部调用方）
        │
        ▼
  Skill 入口：uiux（设计/改造/自测）  uiux-verify（只读验证/独立评审）
        │            └── scripts/launch.py ──> suite-link.json
        ▼
  versioned runtime：contracts 校验 | mode-gate 策略 | finalize 派生 | 证据治理
        │
        ├── UX/UI 设计层：功能图、flows、Token、原型、L4 评审
        ├── 确定性检测层：token lint、flow validator、geometry probe
        └── GUI 测试层：Playwright / WDIO-Tauri / pytest-qt / UIA
        │
        ▼
  `.uiux/`：state（可变） | vault（本地原件） | evidence（脱敏交付）
```

### 2.1 双 Skill 职责

- **`uiux`**：预检、发现、基线、flows、设计系统、原型、受控改造、自测；不能签发"独立 Reviewer 通过"。
- **`uiux-verify`**：对冻结版本只读执行、重跑关键测试、评审覆盖与 UX/UI、报告证据缺口、签发有证据支持的结论；不修复、不改生产源码。
- 两个 `SKILL.md` 保持短小；深层知识放 `references/`，按阶段读取。

### 2.2 四层质量

| 层 | 内容 | 可签发证据 |
|---|---|---|
| L1 确定性 | Schema、规范、测试锚点、范围与许可 | 文件/行号、Rule ID、退出码、日志哈希 |
| L2 启发式 | 密度、导航、主次操作、可发现性 | 上下文 WARNING、截图、置信度 |
| L3 运行态 | 任务路径、状态、裁切、DPI、真实 IPC/对话框 | 命令、截图、trace、覆盖矩阵 |
| L4 设计/体验 | 工作流效率、学习成本、心智模型、视觉层级、专业适配 | design-review 产物 + 证据引用 + 独立结论 |

L1–L3 全绿不能替代 L4；L4 也不能覆盖 L1/L3 硬失败。

### 2.3 运行时模块（本版已实现）

| 模块 | 职责 |
|---|---|
| `runtime/uiux_engine/enums.py` | 载入唯一枚举字典并自检 |
| `runtime/uiux_engine/contracts.py` | 14 份 Schema 的注册、校验、规范化哈希 |
| `runtime/uiux_engine/policy.py` | Mode×Gate 解析、条件事实求值、运行层级下限 |
| `runtime/uiux_engine/evidence.py` | 证据状态机、过期/脱敏/哈希核验 |
| `runtime/uiux_engine/gates.py` | G0–G5 校验、WARN 解除、覆盖汇总、L4/审查、G6 派生 |
| `runtime/uiux_engine/validation.py` | 交叉字段语义校验（写根、授权、runtime_targets） |
| `runtime/uiux_engine/cli.py` | `enums` / `validate` / `policy` / `finalize`，稳定退出码 |

---

## 3. 契约（Single Source of Truth）

### 3.1 契约文件

| 文件 | 用途 |
|---|---|
| `contracts/enums.v1.3.3.json` | 唯一状态字典、ReasonCode 闭集、枚举映射 |
| `contracts/common.v1.3.3.schema.json` | 公共定义：hash、路径、指纹、证据引用、WARN 记录、授权 |
| `contracts/task-request.v1.3.3.schema.json` | 任务请求与交叉约束 |
| `contracts/task-result.v1.3.3.schema.json` | 运行结果、G6、覆盖矩阵、阻塞原因 |
| `contracts/gate-results.v1.3.3.schema.json` | G0–G5 结果与 G6 派生结构 |
| `contracts/coverage-matrix.v1.3.3.schema.json` | 逐 task/scenario/level 覆盖 |
| `contracts/evidence-manifest.v1.3.3.schema.json` | 证据状态、保留期、脱敏、来源 |
| `contracts/tool-log.v1.3.3.schema.json` | 工具命令、退出码、层级、日志哈希 |
| `contracts/review-attestation.v1.3.3.schema.json` | 审查来源、隔离等级、只读证明、冻结版本 |
| `contracts/design-review.v1.3.3.schema.json` | L4 十维量表与结论 |
| `contracts/suite-link.v1.3.3.schema.json` | 入口到发行根的定位 |
| `contracts/release-manifest.v1.3.3.schema.json` | 发行文件哈希与规范化规则 |
| `contracts/policy.v1.3.3.schema.json` | 四类根、权限、授权、Git、证据策略 |
| `contracts/host-capability.v1.3.3.schema.json` | doctor 输出与宿主能力 |
| `contracts/flows.v1.3.3.schema.json` | 任务流与能力证据 |
| `contracts/mode-gate-policy.v1.3.3.json` | 机器可读 Mode×Gate 矩阵、运行层级、L4/COMPLETE 策略 |

### 3.2 枚举命名空间（禁止混用）

- `RuleSeverity = FAIL | WARNING | INFO`：检测规则观察。
- `GateState = PASS | FAIL | WARN_REVIEW_REQUIRED | BLOCKED | UNVERIFIED | NOT_APPLICABLE`：阶段门禁。
- `RunStatus = COMPLETE | PARTIAL | FAILED | BLOCKED`。
- `RuntimeEvidenceLevel = NONE | SIMULATED | NATIVE_APP | OS_INTEGRATION`（有序）。
- `ReviewIsolationLevel = UNVERIFIED | SELFTEST | ISOLATED_SESSION | INDEPENDENT_AGENT`（有序）。
- `DeliveryStatus = NOT_VERIFIED | SELFTEST_VERIFIED | ISOLATED_REVIEW_VERIFIED | INDEPENDENT_VERIFIED | PARTIAL_VERIFIED`。
- `IndependentReviewStatus = NOT_APPLICABLE | UNVERIFIED | INDEPENDENCE_UNVERIFIED | INDEPENDENT_REVIEW_PASS | INDEPENDENT_REVIEW_FAIL`。
- `DesignReviewStatus = NOT_REQUIRED | MISSING | INCOMPLETE | PASS | FAIL | UNVERIFIED`。
- `EvidenceStatus = AVAILABLE | REDACTED_ONLY | SOURCE_EVIDENCE_UNAVAILABLE | EXPIRED | INVALID_HASH | QUARANTINED`。
- 映射：`RuleSeverity.FAIL → GateState.FAIL`，`RuleSeverity.WARNING → GateState.WARN_REVIEW_REQUIRED`，`RuleSeverity.INFO → GateState.PASS`。
- 所有示例 JSON 必须能通过对应 Schema；Schema 中每个 enum 值必须属于字典（自动测试）。

### 3.3 TaskRequest 关键字段

- `policy`：内嵌 `policy` 实例（四类根 + 权限 + 授权 + Git + 证据策略）。
- `execution_policy`：`read_only_source`、`allow_production_data_write`、`allow_uia_input`、`allow_physical_os_input`、`os_input_target_allowlist`、`allowed_write_globs`、`max_total_repair_cycles ≤ 2`、`require_native_for_production_complete`。
- `evidence_policy`：profile、`retention_days`、`release_retention_days`、脱敏配置（图像/路径/字段/recheck）。
- `runtime_targets`：期望覆盖层级，只允许 `SIMULATED | NATIVE_APP | OS_INTEGRATION`；不得事后调低。
- `review`：`independent_required` 与 `reviewer_context_ref`。
- 交叉约束：只读模式不得声明源码写 glob；生产写必须有 `production_write` 授权；物理 OS 输入必须有 `os_input_physical` 授权与非空目标白名单；`source_write_scope ⊆ allowed_write_globs`；四类写根互不重叠。

### 3.4 TaskResult 关键字段

`status`、`delivery_status`、`independent_review_status`、`design_review_status`、`source_fingerprint{kind, value}`、`runtime_evidence_level`、`review_isolation_level`、`gates{G0..G5}`、`derived_g6`、`coverage_matrix[]`、`unverified_paths[]`、`blocking_reasons[{gate, code, detail}]`、`warn_reviews[]`、`evidence_manifest`、`design_review_ref`、`review_attestation_ref`、`repair_cycles`。

### 3.5 覆盖矩阵（B4）

每条记录至少包含：`task_id`、`scenario_id`、`required_runtime_level`、`observed_runtime_level`、`test_state`、`review_isolation_level`、`probe_id`、`evidence_refs[]`、`execution_environment`、`source_fingerprint`。

汇总规则：**最弱必选路径**。任一必选路径未 PASS，整体 `runtime_evidence_level` 降为 `NONE`；单条 Native PASS 不能代表整体 Native PASS。

交叉校验（V1.3.3 返修）：`observed_runtime_level` 不是自报值——每条记录必须至少一条同 `probe_id` 的 evidence provenance 达到该层级，且 `NATIVE_APP/OS_INTEGRATION` 记录必须有对应 tool-log 且 `execution_level ≥ observed`、退出码为 0；否则 `LAYER_SPOOF_OR_MISSING / TOOL_LOG_MISSING`。Gate 结果中的 `observed_runtime_level` 同样不得超过其证据引用的最大层级。

### 3.6 证据生命周期（B6）

- `AVAILABLE` 必须给出 `source_sha256` 且与证据引用一致；**原件字节级校验在 T3.5 生效**（T0.1 只做清单/引用哈希一致性校验），`REDACTED_ONLY` 仅作上下文，不能支撑 PASS。
- `expiry_at` 到期自动视为 `EXPIRED`；原件删除且无替代 → `SOURCE_EVIDENCE_UNAVAILABLE`；哈希不符 → `INVALID_HASH`；敏感风险 → `QUARANTINED`。
- 历史已验收结果保留为带时点记录；重新签发必须提供满足**当前策略**的有效证据。
- 三区：`state`（可变）、`vault`（本地原件，默认不入 Git）、`evidence`（脱敏可移交）。截图打码、DOM/UIA 字段过滤、CSV/JSON 列级脱敏、脱敏后扫描缺一不可。
- 运行级保留期与发布/审计保留期分开配置；清理不得静默删除需复核的原件。

### 3.7 L4 设计评审（B5）

`design-review` 必含：`scenario_id`、`rubric_version`、10 个维度（目标可发现性、任务完整、心智模型/IA、异常恢复、连续性、键盘效率、视觉层级、信息密度、学习成本、专业适配）、每维证据引用与判定、评审者来源与独立性证明、总体结论、分歧、待验证问题。

- L4 结论不得机械求和替代 L1/L3；硬 Gate 失败不因 L4 PASS 而消除。
- `deliverable_tier=production-code` 或 profile 要求独立时，L4 评审者必须独立并附证明；否则 `INCOMPLETE`。该判定由 `policy.l4_independent_required()` 按 `deliverable_tier` 派生，不读取 `request.review.independent_required`（后者只约束运行级独立验收）。

### 3.8 ReasonCode

`ReasonCode` 是稳定闭集（见 `enums.v1.3.3.json` 的 `reason_codes`），覆盖：契约、安装、证据、Gate、审查、源码/写入、运行时七组。文字详情只放 `detail`，不得用自然语言编码。

---

## 4. 安装、寻址与发行契约（B1/M1–M5）

### 4.1 物理布局（不变）

```text
%USERPROFILE%\.agents\
  uiux-suite\versions\1.3.3\            # 发行根：runtime/tools/contracts/knowledge
  uiux-suite\state\install-1.3.3.json   # 安装登记（新增）
  skills\uiux\SKILL.md
  skills\uiux\scripts\launch.py
  skills\uiux\suite-link.json
  skills\uiux\references\*.md
  skills\uiux-verify\...
```

- `suite_root` 基准固定为 `suite-link.json` 所在目录（即 `<skill_root>`）。
- `launch.py` 从 `Path(__file__).resolve().parent.parent / "suite-link.json"` 读取；禁止按 cwd 或任意拼接寻找。
- `suite_root` 使用 `relative_locator`（允许 `..`，禁止盘符/反斜杠）；跨盘/UNC/漫游时必须用 `path_kind=absolute`。
- 版本错误/链接损坏 → `LINK_MISSING / LINK_INVALID / VERSION_MISMATCH / MANIFEST_MISMATCH`，doctor 必须给出可操作原因。

### 4.2 ReleaseManifest

- SHA-256 对**原始字节**计算，不转换换行、不合并大小写不同文件。
- 路径统一小写正斜杠；排除 `__pycache__`、`*.pyc`、`.venv`；文件必须声明 role（runtime/schema/launcher/skill/knowledge/docs/license/other）。
- `bundle_sha256` 记录清单自身摘要；启动期只校验清单列出的文件，并明示"只防意外损坏，不防同权 Agent"。

### 4.3 安装登记与版本生命周期

- `install-<version>.json` 记录 `files[{path, sha256}]`、scope、host、installed_at。
- 入口只存 `active_version`；版本目录可并存；卸载仅删除非 active 且无引用的登记文件；保留用户 `.uiux/`。
- 提供 `upgrade --to` 与 `rollback --to`；升级前校验目标版本 manifest。

### 4.4 宿主发现

- 依据 DSH 默认根与 rank：project-dsh 100、project-agents 200、custom 300、user-dsh 400、user-agents 500；`DSH_HOME`/`DSH_AGENTS_HOME` 优先于 `%USERPROFILE%`。
- doctor 输出 `entries[{name, root, rank, shadowed_by}]` 与 `host-capability.json`；项目级安装需考虑"最近 `.git` 祖先"，非 Git 项目仅在 cwd 为项目根时可见。
- 未实测宿主记 `UNVERIFIED`，不得以 DSH 成功推定其它 Agent 通过。

---

## 5. Gate 机器语义（B3/B4）

### 5.1 Mode×Gate 矩阵（机器可读于 `mode-gate-policy.v1.3.3.json`）

`M`=MANDATORY，`R`=REVIEW_ONLY，`A`=CONDITIONAL（附 when），`—`=NOT_APPLICABLE。G6 为派生，不在输入矩阵中。

| mode | G0 | G1 | G2 | G3 | G4 | G5 |
|---|---|---|---|---|---|---|
| `audit` | M | M | R | R | R（只读 Lint） | M |
| `design-only` | M | A（已有 UI） | M | M | — | — |
| `prototype` | M | A（已有 UI） | M | M | M | M |
| `new-build` | M | — | M | M | M | M |
| `redesign` | M | M | M | M | M | M |
| `targeted-fix` | M | M | M | M | M | M |
| `verify` | M | R | R | R | R | M |

- 单元格只能取枚举值；条件必须携带 `when` 与 `else`，不得混入括号散文。
- `REVIEW_ONLY` 只读取/评估既有产物，不产生新版本，且不能单独支撑 COMPLETE。
- audit 的 G4 不再与 "audit/verify 仅只读检查" 冲突：统一为 REVIEW_ONLY。

### 5.2 WARN 解除

`WARN_REVIEW_REQUIRED` 必须绑定处置记录：`finding_id`、`gate`、`disposition(FIXED|ACCEPTED_RISK|NOT_APPLICABLE|REJECTED)`、评审来源与身份、`reviewed_head`、证据引用、`expires_at`、理由。

- `ACCEPTED_RISK / NOT_APPLICABLE` 不得由 `selftest` 来源裁决。
- `FIXED` 必须有回归证据；`REJECTED` 必须给出反证（`evidence_refs` 非空）。
- 处置记录必须通过 `common#/$defs/warn_review` Schema 校验，`reviewed_head` 必须等于冻结源码指纹；缺失字段或旧 HEAD → `WARN_REVIEW_INVALID / REVIEWED_HEAD_MISMATCH`。
- 无有效记录 → `WARN_REVIEW_MISSING`，阻断 COMPLETE；过期记录 → `WARN_REVIEW_INVALID`。

### 5.3 COMPLETE 组合约束

`status=COMPLETE` 当且仅当：

1. 所有 `MANDATORY` Gate 为 PASS（或 WARN 且处置有效）；
2. 每个必选 Gate 至少一条 `AVAILABLE` 有效证据且哈希/过期/探针一致；
3. 覆盖矩阵满足 `runtime_targets` 与 G5 最低层级，且逐路径 provenance 校验通过；
4. L4 要求的模式 `design_review_status=PASS`（production-code 要求独立 L4）；
5. 独立验收要求时 `independent_review_status=INDEPENDENT_REVIEW_PASS`；
6. 源码指纹一致、审查期间未变更、`gate-results.request_digest` 与当前请求一致；
7. 无阻塞原因、无必选未验证路径。

`COMPLETE ≠ INDEPENDENT_REVIEW_PASS`：只有模式/交付层级或 profile 要求独立时才强制后者。有效 `ISOLATED_SESSION` 审查可产生 `ISOLATED_REVIEW_VERIFIED`；否则为 `SELFTEST_VERIFIED` 的范围内完成。

存在明确失败（MANDATORY/REVIEW_ONLY Gate FAIL 或 L4 FAIL）时输出 `FAILED`，不得降级为 `PARTIAL`。

### 5.4 运行层级与跨层冒充

- G5 最低层级：audit/prototype 默认 `SIMULATED`；new-build/redesign/targeted-fix/verify 默认 `NATIVE_APP`；请求 `OS_INTEGRATION` 或 `require_native_for_production_complete` 时提升。
- 证据声明的 `evidence_level` 必须与 `tool-log.execution_level`、`probe_id` 来源一致；低于要求 → `LAYER_SPOOF_OR_MISSING`。
- Gate 的 `observed_runtime_level` 不得超过其证据引用的最大层级。
- 覆盖记录的 `observed_runtime_level` 必须有同 probe 的 provenance/tool-log 支撑；仅改 coverage 字段抬高层级 → `LAYER_SPOOF_OR_MISSING`。
- 工具日志缺失 → `TOOL_LOG_MISSING`；退出码非零 → `TOOL_EXIT_NONZERO`。

### 5.5 G6 派生

G6 不再作为输入 Gate。`finalize` 读取 G0–G5、覆盖矩阵、证据清单、L4 与审查声明，计算：

```
g6.checks = [gate:G0..G5, coverage:targets, evidence:available,
             design:l4, review:isolation, source:fingerprint]
g6.state  = PASS 仅当 run.status == COMPLETE
```

`gate-results` 中出现 `gates.G6` 或顶层 `g6` 字段 → Schema 拒绝（`additionalProperties` 与 enum 双重约束）。

### 5.6 finalize 判定（摘要）

```python
validate(request, gate_results, coverage, manifest, tool_logs, design_review, attestation)
verify request_digest == sha256(request)          # 禁止事后调低 runtime_targets
resolved = mode_gate_policy.resolve(mode, facts)
check_applicability_and_states()
discharge_warn_reviews_or_block()                 # schema + reviewed_head + expiry
verify_evidence(available, expiry, hash, probe, layer)
aggregate_coverage(weakest_required_path)         # provenance-bound observed levels
design_status = l4_policy(...)                    # production-code ⇒ independent reviewer
review_status, isolation = review_policy(attestation, manifest_digest, fingerprint)
status = COMPLETE | PARTIAL | FAILED | BLOCKED
g6 = derive(...)
```

- 本地同权 Agent 可改文件：本工具只声明"防意外损坏 + 一致派生"，不宣称不可绕过的安全门禁。
- 高可信签发必须由独立校验器/CI 读取冻结提交与完整证据后执行。

### 5.7 修复预算

每次 Run 默认最多 2 轮批量修复；不可逆副作用、越权写入、数据损坏立即 `BLOCKED`；两轮不收敛输出 `PARTIAL/FAILED` 并保留可恢复证据。

---

## 6. UX 真实性与设计能力

### 6.1 三路能力发现

1. 源码静态发现（路由/窗口、IPC/网络、异步状态、破坏性操作、长任务、选择器、快捷键）。
2. 运行发现（真实任务路径、状态反馈、截图、沙箱文件结果）。
3. 任务契约（`flows.json` 的能力声明、状态与断言）。

交叉规则：源码发现 `destructive/async/long_running` 而契约未声明 → G2 至少 `WARN_REVIEW_REQUIRED`；声明了运行锚点但测试无状态转换 → G5 FAIL；静态无法确认语义 → `UNVERIFIED`，不得声称"没有风险行为"。

### 6.2 状态按能力派生

异步加载、集合展示、可编辑内容、长时任务、危险不可逆操作各自派生状态集合；不为不可取消的长任务伪造取消。

### 6.3 L4 评审量表

十个维度见 `design-review` Schema；每维必须给出任务/场景 ID、证据引用、判定与建议；保留分歧与待验证问题；不以加权总分机械决定通过。与基线使用同素材、同机器、同窗口/DPI 比较。

### 6.4 设计系统与存量项目

- `DESIGN_SYSTEM.md` + DTCG `tokens.json` 为项目唯一权威；外部设计资源仅作候选。
- 保留成熟项目原组件体系，禁止为套用新库无谓重写；brownfield 需先盘点→映射→差异清单→逐步收敛，并提供 token drift 检查（M12，Stage 2）。

---

## 7. UI 检测、布局与无障碍

- Lint 分级：硬 FAIL 仅用于可确定违规（未授权硬编码色、Emoji 冒充功能图标、失去焦点可见性、真实文本裁切、WCAG 适用条件下的低对比度）；间距不设全局硬 FAIL；未知背景 → `UNVERIFIED`。
- Web 用 AST/PostCSS，Qt 用 `ast`/QSS 解析；正则只能筛选，不得宣称 AST 证明。
- 几何测量用真实渲染（`getBoundingClientRect`、`scrollWidth`、`geometry()`、字体度量、截图）；浮层/Badge/Canvas/合法 ellipsis 排除。
- 无障碍（M18，Stage 1）：accessible name、键盘可达、WCAG 2.2 target size、UIA/ARIA 语义；不得只做对比度。
- Offscreen 150% 只证明相对布局，不冒充真实 Windows DPI 证据。

---

## 8. GUI 测试与 OS 安全

- 技术栈策略：Web（Playwright Test）、Tauri v2（`@wdio/tauri-service` + 真实 `.exe`）、PySide6（pytest-qt/QTest + Offscreen 快测 + Native QPA）、黑盒（pywinauto/UIA）。
- 覆盖矩阵逐 task 记录 `renderer_mock / native_app / os_integration` 的 PASS/FAIL/UNVERIFIED/NOT_APPLICABLE，并附命令、输入、输出、权限、时间、版本、日志哈希。
- OS 输入默认仅允许协议级与 UIA 模式方法；物理键鼠必须显式授权、目标白名单、隔离桌面/VM；共享桌面存在 TOCTOU，不承诺零误触，必须提供紧急中止与焦点失配中止。
- 仅启动二进制不等于证明导入/保存 Native 路径。

---

## 9. 数据安全、写入边界与 Git

- 四类根：`read_roots`、`report_write_root`、`sandbox_write_root`、`install_write_root` + `source_write_scope`；写根互不重叠，source scope ⊆ allowed_write_globs。
- 只读模式（audit/verify/design-only/prototype）不得声明源码写 glob；测试数据复制到沙箱，使用隔离 `APPDATA`/cache/DB 路径。
- 非 Git 项目：`dir_digest` + 备份副本 + 差异哈希；禁止伪造 40 位 HEAD。
- `caller_managed`：不得建分支、改 HEAD、提交或清理外部 Worktree。
- 路径白名单是流程约束，不是 OS 强制安全；发布时必须标注安全等级。

---

## 10. Reviewer 独立性

- `SELFTEST`：同会话自测，只能 `SELFTEST_VERIFIED`。
- `ISOLATED_SESSION`：冻结源码 + 干净上下文 + 只读执行；需宿主/外部来源证明，否则 `INDEPENDENCE_UNVERIFIED`。
- `INDEPENDENT_AGENT`：独立 Agent/执行环境 + 冻结版本 + 只读证明 + `reviewed_head`/`reviewed_source` 绑定 + 证据清单哈希一致。
- 自报 `session_id` 不能构成独立性证明；同模型家族的偏差需在报告中提示（m2，Stage 4）。

---

## 11. 靶场、指标与验收

- 每栈正/负样本标注预期结果与 Rule ID；GT 独立标注、分歧仲裁（M13）。
- 输出 TP/FP/TN/FN、Precision/Recall/FPR/FNR，区分硬门禁与启发式告警；`confusion-matrix.json` 纳入契约（m4）。
- Stage 1 最小验收：冻结靶场内预期 FAIL 的阻断种子全部命中；合法负样本零硬 FAIL；不对未知项目承诺 100% 检出。
- 性能/延迟按任务型态设基线，不套用全局 100ms。

---

## 12. Stage 0–5 实施计划

> 阶段以 Exit Criteria 发放准入；不得以文档"已修订"代替"已实现"。任务清单与依赖见 `plan/tasks.v1.3.3.json` 与 `docs/TASK_PLAN.md`。

### Stage 0｜契约闭环、安装闭环与 DSH 预检

- **T0.1（本版完成，待独立复核）**：Schema、枚举、Gate 引擎、覆盖矩阵、L4、证据生命周期；契约+安装测试 133/133。
- T0.2 发行根/双启动器/安装卸载/升级回滚；M1/M3/M4/M5。
- T0.3 DSH 实机安装与双入口发现；M2/m6/m7 部分。
- T0.4 doctor：能力、根目录、遮蔽、退出码/JSON；M9。
- T0.5 许可证与离线依赖锁定。
- T0.6 删除开发仓后的独立运行验证。
- **Stage 0 Exit**：删除开发仓后仍可 doctor + 最小 CLI；中文/空格/UNC 通过；无外部编排器也通过。

### Stage 1｜确定性检测器与靶场

- T1.0 规则目录冻结；T1.1 正反 Fixtures；T1.2 token linter；T1.3 flow validator；T1.4 geometry probe；T1.5 Gate 引擎完整化；T1.6 对抗测试；T1.7 混淆矩阵/CI。
- M10 CI、M13 GT 标注、M18 无障碍、m4 混淆矩阵。
- **Exit**：可复现识别缺陷；合法负样本零硬 FAIL；伪造 PASS/跨层冒充被拒。

### Stage 2｜UX 设计与 Token

- T2.1 发现；T2.2 flows 工具；T2.3 DTCG/编译器；T2.4 知识库；T2.5 design-only/prototype；T2.6 brownfield/drift。
- M11/M12/m3。
- **Exit**：状态契约与真实功能相符；Web/Qt Token 可运行；两方案取舍有据。

### Stage 3｜受控改造与 Windows 真机

- T3.1 受控改造；T3.2 Tauri Native IPC；T3.3 Qt Native/DPI；T3.4 OS 集成；T3.5 证据生命周期；T3.6 独立审查隔离。
- M6/M8/M14/m1/m8。
- **Exit**：两栈最小生产改造真机回归；数据零写入；独立审查不靠自报。

### Stage 4｜跨 Agent 与被动外部调用

- T4.1 DSH 实测；T4.2 其它 Agent 矩阵；T4.3 被动外部调用；T4.4 退化路径。m2。
- **Exit**：各宿主附实测日志；未测标 UNVERIFIED；无外部系统核心正常。

### Stage 5｜真实工作台与发行

- T5.1 隔离副本试点；T5.2 前后对照；T5.3 数据安全与回滚；T5.4 独立复审；T5.5 发行包与报告。M16/m5。
- **Exit**：可复现 Native 核心任务；无未解决 P0/P1；安装/卸载/回滚可复现；兼容范围仅声明实测。

---

## 13. 依赖 DAG（修订）

```text
T0.1 Contract Closure
  ├──> T0.2 Installer/Launcher ──> T0.3 DSH install ──> T0.6 delete-repo check
  ├──> T0.4 Doctor ─────────────┘
  ├──> T0.5 Licenses ──> T2.4 Knowledge
  └──> T1.0 Rule registry ──> T1.1 Fixtures ──> T1.2/T1.3/T1.4
                                      └──> T1.7 Metrics/CI
  T1.5 Gate engine ──> T1.6 Adversarial
  T1.2/T1.3 ──> T2.1/T2.2 ──> T2.3 ──> T2.5 ──> T3.1
  T3.1 ──> T3.2/T3.3 ──> T3.4 ──> T3.6 ──> T4.1 ──> T4.2/T4.4
  T4.1 ──> T5.1 ──> T5.2/T5.3 ──> T5.4 ──> T5.5
```

- T1.0 是 T1.1 与 T1.2/T1.3 的共同上游，消除"Fixtures 需要 Rule ID 但规则尚未定义"的循环。
- T0.1 节点已落地；其余节点状态见 `docs/TASK_PLAN.md`。

---

## 14. 风险与处置

| 风险 | 处置 |
|---|---|
| 本地同权 Agent 可改 Runner/证据 | 明示仅流程性自测；高可信签发交独立校验器/CI |
| 安装路径/版本并存断裂 | 版本化发行根、安装登记、doctor、删仓回归 |
| GUI 自动化不稳定 | 分级引擎、固定数据、Native 复验、保留 UNVERIFIED |
| 规则误报 | 正反 Fixture、场景化 WARNING、证据化豁免 |
| UX 评审主观化 | 十维量表 + 证据引用 + 独立来源 + 分歧记录 |
| 真实数据被写 | 沙箱副本、四类根、授权证据、前后哈希 |
| 第三方知识/字体许可 | 锁 commit/许可、离线包、无法锁定则自建 |
| 跨层证据造假 | probe_id + tool-log 层级 + 最弱层汇总 |
| 独立审查伪造 | 可信来源 + 冻结版本 + 只读证明 + 不支持自报 session |
| 契约漂移 | 单一枚举字典 + Schema enum 一致性测试 + CI |

---

## 15. 发现项闭合矩阵

| 发现 | 状态 | 落点 |
|---|---|---|
| B1 发行/启动契约 | 契约 DONE（T0.1），实现 T0.2 | §3/§4、`suite-link`/`release-manifest`/`policy`/`tool-log`/`review-attestation` |
| B2 枚举闭合 | DONE | §3.2、`enums.v1.3.3.json`、enum 一致性测试 |
| B3 Gate 语义 | DONE | §5、`mode-gate-policy`、WARN/COMPLETE/G6 测试 |
| B4 跨层证据 | DONE | §3.5/§5.4、coverage/evidence 测试 |
| B5 L4 评审 | Schema DONE，实现 Stage 1–3 | §3.7、`design-review` |
| B6 证据生命周期 | Schema DONE；T0.1 做清单/引用哈希一致性，原件字节校验 T3.5 | §3.6、`evidence-manifest` |
| M1–M18 / m1–m8 | 已登记任务 | `plan/tasks.v1.3.3.json`、§12 |

---

## 16. 发布标准与交付物

Release 必交付：可安装/卸载/修复的发行包、双 Skill、快速上手与兼容矩阵、7 模式契约与 G0–G6 引擎、三大检测器与四类探针、Token/设计系统流程、Stage 1 冻结靶场与指标、Windows Native 与独立 Reviewer 记录、许可证/NOTICE/隐私/Vault 说明、回滚说明、`dist/` 交付包与 `FINAL_DELIVERY_REPORT.md`。

---

## 17. 事实来源与未验证项

### 17.1 已核对来源

- Agent Skills 规范：<https://agentskills.io/specification>
- DSH skill-filesystem 根与 rank：<https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.zh.md>（本版 2026-10-23 核对 rank 100/200/300/400/500、`DSH_AGENTS_HOME`/`DSH_HOME` 覆盖、最近 `.git` 祖先规则）
- Tauri v2 WebDriver、pytest-qt、WCAG 2.2 对比度/点击目标。

### 17.2 仍未实测

- 本机 DSH 版本、实际安装路径和插件加载状态（T0.3 由 doctor 实测）。
- WebView2/WDIO 握手、真实文件对话框闭环（Stage 3）。
- Windows 100/125/150% DPI 原生渲染（Stage 3）。
- 用户机器上其它 Agent 的兼容性（Stage 4）。
- 真实项目改造收益与误报率（Stage 5）。

---

## 附录 A：T0.1 验收清单与当前证据

| ID | 用例 | 本版结果 | 证据 |
|---|---|---|---|
| C-01 | 双 Skill 发现 | 未执行（T0.3） | — |
| C-02 | launch.py 与 suite-link 路径关系 | PASS（安装实例启动） | `test_install_doctor_launch_and_uninstall`、`test_launch_works_after_source_tree_is_deleted` |
| C-03 | 发行文件哈希错配 | PASS（launch/doctor 拒绝） | `test_launch_rejects_manifest_hash_mismatch` |
| C-04 | 全部样例校验 | PASS | 14 valid / 15 invalid fixtures |
| C-05 | 混用 WARNING 与 WARN_REVIEW_REQUIRED | PASS（拒绝） | `test_mixed_warning_and_gate_state_is_rejected` |
| C-06 | WARN 未解除直接 COMPLETE | PASS（拒绝） | `test_warn_without_disposition_blocks_complete`、`test_warn_review_missing_fields_is_rejected` |
| C-07 | G6 自循环 | PASS（拒绝 gates.G6 与顶层 g6） | `test_g6_cannot_be_supplied_as_input_gate`、`test_top_level_g6_is_rejected` |
| C-08 | audit/redesign 必选 Gate 不完整 | PASS | `test_audit_without_runtime_environment_is_partial_not_complete` |
| C-09 | 单点 Native 冒充整体 Native | PASS（最弱层汇总 + provenance 校验） | `test_mock_only_coverage_cannot_claim_native_target`、`test_coverage_claiming_native_without_native_provenance_is_rejected` |
| C-10 | 证据缺失/哈希不符/过期 | PASS | `test_expired_evidence_cannot_support_pass` |
| C-11 | L4 required 但缺失 / production-code 自审 | PASS | `test_required_l4_review_missing_blocks_complete`、`test_production_code_l4_selftest_reviewer_is_rejected` |
| C-12 | 非 Git/外部 caller 策略 | PASS（策略层） | `test_caller_managed_must_match_policy` |
| C-13 | DSH_AGENTS_HOME 与遮蔽 | 部分：doctor 遮蔽判定 PASS；真实 DSH 待 T0.3/T0.4 | `test_shadow_detection_reports_project_skill` |
| C-14 | 四类写根缺失/越权 | PASS | `test_semantic_violations_are_rejected` |
| C-15 | 中文/空格/UNC 路径 | 部分：中文/空格 PASS；UNC/长路径待 T0.2/T0.3 | `test_project_scope_with_chinese_and_space_path` |

**结论**：B1–B6 的契约与引擎具有机器测试证据；C-01/C-13/C-15 的真实宿主/UNC 部分尚未执行，**不得据此宣称 Stage 0 PASS**。T0.1 需在返修后通过独立只读复核才能标记 DONE。

## 附录 B：状态恢复与证据索引

- 当前阶段与 READY 任务：`docs/IMPLEMENTATION_STATUS.md`
- 任务清单：`docs/TASK_PLAN.md` / `plan/tasks.v1.3.3.json`
- 决策记录：`docs/DECISIONS.md`
- 阻断项：`docs/BLOCKERS.md`
- 契约测试证据：`evidence/T0.1/contract-test-evidence.json`
- 基线：commit `e7e921e`，tag `v1.3.2-baseline`，SHA256 `70f5f33…11ea04`
