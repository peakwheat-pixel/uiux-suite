# 独立评审与 L4 复核（expert-review）

## 独立性来源

| 等级 | 条件 | 可签发 |
|---|---|---|
| `SELFTEST` | 同会话/开发者自测 | 仅 `SELFTEST_VERIFIED` |
| `ISOLATED_SESSION` | 冻结源码 + 干净上下文 + 只读执行 + 来源证明 | `ISOLATED_REVIEW_VERIFIED` |
| `INDEPENDENT_AGENT` | 独立 Agent/环境 + 只读证明 + 冻结绑定 | `INDEPENDENT_REVIEW_PASS` |

自报 `session_id` 不构成证明；同模型家族的偏差需在报告中提示。

## 结论结构

- `review_origin`：host / launched_by / verified_identity / trust_source
- `reviewed_head` / `source_fingerprint`
- `read_only_proof`（方法 + 证据）
- `evidence_manifest_hash`
- `verdict`（PASS / FAIL / PARTIAL / UNVERIFIED）
- `dissent` 与待验证问题

## L4 复核

- 检查 10 维是否都有任务/场景与证据引用。
- 检查分歧是否记录、结论是否依赖未验证假设。
- L4 不能覆盖 L1–L3 硬失败。

## 禁止

- 用"新会话"口头声明代替隔离证据。
- 审查期间允许源码变化。
- 原始证据缺失仍签发 PASS。
