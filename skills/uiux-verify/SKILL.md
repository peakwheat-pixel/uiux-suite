---
name: uiux-verify
description: 只读 UI/UX 验证与独立评审入口：对冻结版本重跑关键测试、复核 flows/设计与证据缺口，并据可信隔离来源签发验证结论。不修改生产源码，不替开发者修复。
---

# uiux-verify

本 Skill 负责 **只读验证与独立评审**。它复用同一版本化运行时，但只读取冻结版本与既有证据，不产生代码改动。

## 何时使用

- 对冻结的源码版本执行 QA / Review（`verify`）。
- 复核 `uiux` 交付的 Gate 证据、覆盖矩阵与 L4 评审。
- 判断能否签发 `INDEPENDENT_REVIEW_PASS`。

## 工作流

1. **冻结与来源**：记录 `reviewed_head` / `source_fingerprint`，确认源码在审查期间不变。
2. **只读执行**：重跑关键测试与检查；所有输出进入报告/沙箱目录。
3. **证据复核**：逐 Gate 检查 evidence 状态、probe、层级与哈希；缺证据记 `UNVERIFIED`。
4. **独立结论**：提供可信来源、只读证明与证据清单哈希后，才可签发独立通过；否则标 `SELFTEST` 或 `INDEPENDENCE_UNVERIFIED`。

## 参考

- `references/test.md`：只读测试与覆盖复核
- `references/expert-review.md`：L4 与独立审查

## 边界

- 不修改生产源码，不替开发者修复缺陷。
- 不以自报的 `session_id` 作为独立性证明。
- 不把 Mock/Offscreen 结果当作 Native 证据。
