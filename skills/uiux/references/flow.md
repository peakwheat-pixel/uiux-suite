# 任务流契约（G2）

## 目标

把"用户要完成什么"写成可检查的 `flows.json`，并让源码/运行/契约三路能力交叉可验证。

## 必填内容

- `view_id`、`view_archetype`（modal_form / consumer_view / data_table / desktop_workbench / canvas_editor）。
- `capabilities`：async_load、collection_display、user_mutation、long_running_task、destructive_operations（可选 canvas_rendering）。
- `capability_evidence[]`：capability、source{kind, ref}、discovery(static/runtime/contract)、confidence。
- `tasks[]`：task_id、actor_goal、entry_point、steps、states、runtime_assertions、destructive_operations。
- `ui_anchors[]`：semantic_id 与 testid/selector。

## 三路交叉规则

- 源码发现 destructive/async/long_running 而契约未声明 → 至少 `WARN_REVIEW_REQUIRED`。
- 声明运行断言但测试无真实状态转换 → G5 `FAIL`（缺证据则 `UNVERIFIED`）。
- 静态无法确认 → `UNVERIFIED`，禁止断言"没有风险行为"。

## 状态派生

按能力派生，不强制固定五态：

| 能力 | 常见状态 |
|---|---|
| 异步加载 | loading / ready / error / retry |
| 集合展示 | empty / ready |
| 可编辑 | dirty / saving / saved / conflict |
| 长时任务 | queued / running / progress / complete / failure / cancelled |
| 危险不可逆 | guard / confirmation 或 undo / result |

不可取消的长任务需说明限制与安全退出，不伪造取消。

## 产出

`flows.json` 通过 `uiux-engine validate --schema flows`。
