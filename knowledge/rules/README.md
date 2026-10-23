# 规则目录（Rule Catalog v1.0）

本目录是 Stage 1 的**冻结规则源**：

| 文件 | 作用 |
|---|---|
| `catalog.v1.0.json` | 规则清单（20 条，Rule ID 唯一） |
| `catalog.v1.0.freeze.json` | 冻结记录：catalog 规范化 SHA256、规则数、版本 |
| `README.md` | 命名与变更规则 |

## Rule ID 约定

`UX-<CATEGORY>-<NNN>`，例如 `UX-A11Y-001`：

- CATEGORY ∈ `COLOR / TYPE / SPACE / FLOW / GEOM / A11Y / COPY / STATE / MOTION`
- NNN 为三位序号，只增不改；废弃规则保留 ID 并标 `enabled=false`。

## 严重度

- `FAIL`：确定性硬失败，可阻断 COMPLETE。
- `WARNING`：需复核/处置（WARN_REVIEW_REQUIRED）。
- `INFO`：只提示，不进入 Gate。

## 变更规则

1. 任何规则增删改必须先改 `catalog.v1.0.json`，再重算 `catalog.v1.0.freeze.json`。
2. `catalog_version` 按语义化递增（本版 1.0）；Stage 1 内冻结后不得静默修改。
3. 豁免必须使用 `rule-exemption` Schema，带 owner、审批人、到期时间与理由；过期豁免不得生效。
4. `uiux-engine rules` 会校验 Schema、ID 唯一性、枚举命名空间与冻结摘要。
