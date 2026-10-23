# 组件/状态覆盖矩阵（T2.5）

## 输入

- `flows.json`（声明 `view_id`、tasks/states）
- 源码目录（`.tsx/.ts/.jsx/.js/.py/.ui`）

## 规则

- 组件识别：`function Name(`、`class Name(`、`const Name = (`、Qt `class Name(...QWidget)`。
- 状态识别：源码中出现 `data-state="<state>"`、`'<state>'` 或 `"<state>"`。
- 覆盖：flows 中每个 state 是否至少被一个组件覆盖；未覆盖计入 `summary.gaps`。
- 输出通过 `contracts/component-matrix.v1.3.3.schema.json`；有 gap 时 `validate_matrix().ok=false` 并给出警告。

## 限制

- 纯静态扫描，不验证真实渲染；动态状态/条件分支可能漏检。
- 状态名必须与 flows 一致；不要临时造状态名（违反契约）。
- 该矩阵用于提示缺口，不能替代 Stage 3 的真实 UI 探针。

## 测试

`tests/unit/test_component_matrix.py`（8 用例）。
