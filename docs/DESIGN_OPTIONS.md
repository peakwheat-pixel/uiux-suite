# 多方案对比与选择记录（T2.7）

## 契约

`contracts/design-options.v1.3.3.schema.json`：

- 至少 2 个 `options`，每项含 pros/cons/risks 与 5 维评分（1–5）。
- `selected_option_id` 必须存在；`rationale` ≥ 10 字符。
- 维度：usability / visual / feasibility / risk / accessibility。

## 评分

加权：usability 0.25、visual 0.15、feasibility 0.20、risk 0.15、accessibility 0.25。

- 输出排序与 selected 的加权分。
- selected 不是最高分 → WARNING（允许，但需在 rationale 说明）。
- accessibility ≤2 或 risk ≤2 → WARNING。
- 重复 option_id、selected 不存在、schema 不合法 → 拒绝（ok=false）。

## 用途

- 让 Agent 在动手前给出至少两个可比较方案，记录取舍，而不是直接实现单一路径。
- 该记录可作为 `design-review` 的输入证据；不替代独立评审。

## 测试

`tests/unit/test_options.py`（8 用例）。
