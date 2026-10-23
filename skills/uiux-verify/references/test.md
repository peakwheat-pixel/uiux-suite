# 只读测试与覆盖复核（verify）

## 原则

- 冻结版本：记录 `reviewed_head` / `source_fingerprint`；审查期间源码不得变化。
- 只读执行：输出只进报告/沙箱目录；不改生产源码、不写真实用户数据。
- 证据优先：先看 `evidence-manifest` 与 tool-log，再重跑关键测试。

## 复核清单

1. 所有必选 Gate 是否 PASS；WARN 是否有有效处置记录。
2. 每条证据的 `status`、`probe_id`、`evidence_level`、哈希与过期时间。
3. `coverage_matrix` 是否覆盖请求层级；最弱路径是否达标。
4. L4 评审是否存在、10 维是否齐全、来源是否独立。
5. 源码指纹与审查声明是否一致。
6. 是否存在 Mock/Offscreen 冒充 Native、同会话自测冒充独立审查。

## 重跑

在隔离环境中重跑关键测试；记录命令、退出码、版本与日志哈希。无法重跑时明确 `UNVERIFIED`，不得沿用旧 PASS 冒充当前结论。

## 输出

验证报告 + `gate-results`/`task-result`（由 `finalize` 派生）+ 证据缺口清单。
