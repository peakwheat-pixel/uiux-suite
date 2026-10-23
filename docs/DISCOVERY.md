# 页面/能力发现与 flows 生成（T2.1/T2.2）

## 输入

示例项目目录（`.tsx/.ts/.jsx/.js/.html/.ui/.qml`）。扫描忽略 `.git/__pycache__/node_modules/.venv/dist/build`。

## 识别

| 对象 | 规则 | 置信度 |
|---|---|---|
| 路由 | `router.tsx` 中 `path: "...", element: <Component` | 0.9 |
| 页面/对话框 | `export function Name`；`role="dialog"` 或 `*Dialog` → dialog | 0.5–0.8 |
| Qt 窗口/面板 | `.ui` 中 `<class>` / `<widget class="Q..." name="...">` | 0.8 |
| archetype | table/QTableView → data_table；dialog → modal_form；canvas/QGraphicsView → canvas_editor；QMainWindow → desktop_workbench；否则 consumer_view | — |
| 能力 | fetch/axios/useQuery、table/map、form/useState、QProgressBar/QThread、delete/remove/purge/confirm、canvas/WebGL | 0.7 |

每个识别到的能力都带 `capability_evidence{file,line,pattern}`；没有证据的能力保持 `false`。

## 三源

- `source`：静态扫描 → `OBSERVED`。
- `runtime`：Stage 2 无探针 → `UNVERIFIED`（不伪造）。
- `contract`：项目内存在 `flows.json` → `OBSERVED`，否则 `MISSING`。
- 每个 page 进入 `unverified_paths`（runtime 未验证）。

## flows 生成

`flows_from_discovery(report)` 生成并通过 `flows.v1.3.3` schema：

- 每个 page 一个 task；entry_point=`list`；states 由能力推导（loading/error/retry/empty/draft/progress/saved）。
- capability_evidence 直接复用；ui_anchors 由 pages 生成。
- 生成的 flows 是**草案**，需人工/Stage 3 补关键状态与破坏性操作 guard。

## 输出

`contracts/discovery.v1.3.3.schema.json` 合法 JSON；`sources` 与 `unverified_paths` 诚实标注。

## 测试

`tests/unit/test_discovery.py`（13 用例）。
