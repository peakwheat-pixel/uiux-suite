# 决策记录（ADR log）

> 本文件记录 V1.3.3 及后续阶段影响契约、安全和验收口径的决策。新决策追加编号，不覆盖旧记录；被替代时标注 Superseded。

| ID | 日期 | 决策 | 理由 | 状态 |
|---|---|---|---|---|
| D-001 | 2026-10-23 | V1.3.2 以独立 commit + tag 冻结为只读基线 | 审核行号与 SHA256 可长期复核；禁止覆盖原文 | Accepted |
| D-002 | 2026-10-24 | 状态词表拆为 RuleSeverity / GateState / RunStatus / DeliveryStatus / IndependentReviewStatus 等独立枚举 | V1.3.2 多套词表混用，Schema 无法稳定生成 | Accepted |
| D-003 | 2026-10-24 | G6 改为 finalize 派生，不作为输入 Gate | 消除"G6 依赖自身计算"的循环；输入含 G6 由 Schema 拒绝 | Accepted |
| D-004 | 2026-10-24 | WARN_REVIEW_REQUIRED 必须绑定处置记录才能解除 | 防止 WARN 与 PASS 同权；记录 finding/来源/冻结版本/有效期/证据 | Accepted |
| D-005 | 2026-10-24 | COMPLETE 不普遍等于 INDEPENDENT_REVIEW_PASS | 防止把范围内自测误报为独立验收；独立签发只在模式/profile 要求时强制 | Accepted |
| D-006 | 2026-10-24 | 运行层级按"最弱必选路径"汇总 | 单点 Native PASS 不能代表整体 Native；Mock 不得冒充 | Accepted |
| D-007 | 2026-10-24 | audit 的 G4 定为 REVIEW_ONLY（只读 Lint/检查） | 消除矩阵"—"与"audit/verify 仅只读检查"的冲突 | Accepted |
| D-008 | 2026-10-24 | targeted-fix 的 G2 定为 MANDATORY | 条件必选在 V1.3.2 无触发条件，无法确定性计算 | Accepted |
| D-009 | 2026-10-24 | L4 用独立 `design-review` 产物表达，10 维量表 + 证据引用 + 来源/分歧 | 让"专业设计评审"有机器可验证载体，同时不把主观量表求和冒充硬门禁 | Accepted |
| D-010 | 2026-10-24 | 证据状态机：AVAILABLE 必须可校验原件；REDACTED_ONLY 不能支撑 PASS；过期即失效 | Evidence Honesty 与 Vault 红线 | Accepted |
| D-011 | 2026-10-24 | suite-link 相对定位允许 `..`（relative_locator）；跨盘/UNC 用 absolute | 用户级布局需要从 skill 根指向 `uiux-suite`，普通 rel_path 禁止 `..` 会误伤 | Accepted |
| D-012 | 2026-10-24 | 不主动依赖/启动任何外部编排器；仅保留 `caller.kind=external` 被动传参 | 保证无外部系统时核心独立运行；尊重调用方 Git/证据边界 | Accepted |
| D-013 | 2026-10-24 | CLI 退出码写入契约：0/2/10/11/12/13 | 阶段验收可自动化；避免"明确报错"不可判定 | Accepted |
| D-014 | 2026-10-24 | 项目依赖安装进 `.venv`，jsonschema/pytest 版本固定并在证据中记录 | 可复现；后续补 requirements.lock（M4） | Accepted |
| D-015 | 2026-10-24 | 本地 finalize 只声明"一致派生 + 防意外损坏"，不宣称不可绕过 | 同权 Agent 可改 Runner/证据；高可信签发交独立校验器/CI（ADR-03 边界） | Accepted |
| D-016 | 2026-10-24 | 对外部编排器只保留被动兼容，删除主动集成任务（原 T4.3 改为被动调用契约测试） | 用户架构约束；避免把外部系统作为 Release 前提 | Accepted |
| D-017 | 2026-10-24 | production-code 的 L4 独立性由 `deliverable_tier` 派生；运行级独立验收由 `review_policy` 单独判定 | 修复 F-01：两者语义不同，混用会漏掉 production-code 自审；拆分为 `design_review_policy` 与 `review_policy` | Accepted |
| D-018 | 2026-10-24 | coverage 的 `observed_runtime_level` 必须由同 probe 的 evidence provenance + tool-log 支撑；gate observed 不得超过证据层级 | 修复 F-02：跨层证据不能由 coverage 自报，红线 3 要求工具日志核验 | Accepted |
| D-019 | 2026-10-24 | WARN 处置文件与内嵌记录统一走 `common#/$defs/warn_review` Schema，且 `reviewed_head` 必须等于冻结指纹；REJECTED 需反证 | 修复 F-03：缺字段/旧 HEAD 不得解除 WARN；REJECTED 是有效处置而非死枚举 | Accepted |
| D-020 | 2026-10-24 | `gate-results.request_digest` 绑定 TaskRequest；不一致即 `REQUEST_DIGEST_MISMATCH` | 修复 F-14：阻止事后重生成 request 调低 runtime_targets | Accepted |
| D-021 | 2026-10-24 | B6 的原件字节校验明确为 T3.5 实现；T0.1 只校验清单/引用哈希一致性 | 修复 F-06：避免把分期能力写成已实现；SPEC §3.6 与 §15 已同步 | Accepted |
| D-022 | 2026-10-24 | 明确失败（MANDATORY/REVIEW_ONLY FAIL、L4 FAIL）统一输出 FAILED | 修复 F-09：机器策略与引擎状态升级规则一致 | Accepted |
| D-023 | 2026-10-24 | 接受 `ISOLATED_REVIEW_VERIFIED` 与 `INDEPENDENCE_UNVERIFIED` 并存；独立验收未要求时，隔离会话审查可交付 | 修复 R-11：delivery 描述评审过程，independent status 描述信任锚；release_audit/verify 仍强制独立 PASS，不构成安全降级 | Accepted |

## 待决事项

- D-017（Stage 1）：规则目录与 Rule ID 命名空间冻结。
- D-018（Stage 2）：第三方知识库无法锁定许可时的自建量表范围。
- D-019（Stage 3）：Windows Sandbox/VM 与共享桌面的验收分级与证明格式。
