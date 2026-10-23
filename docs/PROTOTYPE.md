# 原型契约检查（T2.6）

## 契约

`contracts/prototype.v1.3.3.schema.json`：

- `prototype_id`、`kind`（html/figma/spec/code）、`flows_ref`
- `states`：原型声明的状态
- `anchors`：semantic_id + testid/selector
- `accessibility`：keyboard/labels/contrast 各自 VERIFIED/UNVERIFIED/FAIL
- `checks`：自定义检查（PASS/FAIL/UNVERIFIED）

可选 `source_file`：HTML 原型文件。

## 判定

| 检查 | 失败条件 |
|---|---|
| `states-subset` | 原型 state 不在 flows 中 |
| `anchors-known` | anchor semantic_id 不在 flows.ui_anchors |
| `flows-ref` | flows 文件不存在 |
| `html-testids` | HTML 缺少声明的 data-testid |
| `html-states` | HTML 缺少声明的 data-state |
| `a11y-*` | accessibility=FAIL；UNVERIFIED 不假 PASS |

整体状态：任一 FAIL → FAIL；否则任一 UNVERIFIED → UNVERIFIED；全部 PASS → PASS。

## 限制

- HTML 仅做结构扫描，不执行 JS、不点击验证交互。
- Figma/spec 只校验契约字段，视觉一致性需人工/Stage 3 证据。
- 未验证项必须如实标 UNVERIFIED，不得升格为 PASS。

## 测试

`tests/unit/test_prototype.py`（9 用例）。
