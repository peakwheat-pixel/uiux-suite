# ux_flow_validator（T1.3）

## 1. 输入

`flows.json` 必须通过 `contracts/flows.v1.3.3.schema.json`。核心结构：

- `view_archetype`：modal_form / consumer_view / data_table / desktop_workbench / canvas_editor
- `capabilities`：async_load、collection_display、user_mutation、long_running_task、destructive_operations、canvas_rendering
- `capability_evidence`：每个声明的能力应有来源（file/anchor/task/runtime）
- `tasks[]`：entry_point、steps、states、runtime_assertions、destructive_operations

## 2. 判定（只使用冻结 Rule ID）

| Rule | 级别 | 条件 |
|---|---|---|
| UX-FLOW-001 | FAIL | `entry_point` 不在 `states`；断言引用未声明 state；重复 `task_id`；Schema 无效 |
| UX-FLOW-002 | FAIL | 声明 destructive_operations 但未建模任何操作；不可逆操作 `guard=none`；声明 guard 但无 evidence_refs |
| UX-FLOW-003 | WARNING | 声明 collection_display 但无空状态（empty/no-data/无数据/空状态） |
| UX-FLOW-004 | FAIL | async_load/long_running_task 但无 error/retry/恢复状态 |
| UX-STATE-001 | WARNING | async_load 但无 loading/进度状态 |
| UX-STATE-002 | WARNING | desktop_workbench + user_mutation 但无 dirty/unsaved/draft 状态 |

能力声明为 true 但缺少 `capability_evidence` 时，不冒充规则失败，进入 `unverified_paths`（ReasonCode `UNVERIFIED_PATH`）。

## 3. 输出

```json
{
  "ok": true,
  "schema_valid": true,
  "findings": [{"rule_id": "UX-FLOW-001", "severity": "FAIL", "message": "...", "task_id": "..."}],
  "summary": {"fail": 0, "warning": 0, "info": 0},
  "unverified_paths": [{"capability": "async_load", "reason_code": "UNVERIFIED_PATH"}]
}
```

## 4. 用法

```python
from uiux_engine import flow_validator
report = flow_validator.validate(flows_dict)
```

- 这是**静态契约校验**，不替代 Stage 3 的真实流程运行；运行期断言由 probe 负责。
- 规则集固定在 `knowledge/rules/catalog.v1.0.json`，新增规则需先升 catalog 版本。

## 5. 测试

`tests/unit/test_flow_validator.py`（14 用例）覆盖 GT、不可达、重复 task、Schema 无效、能力证据缺失、guard 证据缺失、空态/错误/加载/脏状态、Rule ID 存在性。
