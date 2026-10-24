# Fixture 与环境预检（TASK-01）

> V1.3.4 起，任何真实项目试点必须先声明 fixture 并完成环境预检；**环境错误不得计入产品缺陷**。

## 1. 文件与命令

| 项 | 位置 |
|---|---|
| Fixture Schema | `fixtures/schema/fixture.v1.schema.json` |
| 内置 fixture | `fixtures/new-manga/minimal.json`、`fixtures/generic/web-minimal.json` |
| 引擎模块 | `runtime/uiux_engine/fixture.py` |
| CLI | `uiux-engine fixture validate|preflight|apply --fixture <path> [--sandbox <dir>]` |

## 2. Fixture 结构

```json
{
  "schema_version": "1.0",
  "fixture_id": "FIX-<PROJECT>-<SCOPE>",
  "project": {"name": "...", "stack": "tauri2-react-webview2|electron|web-spa|qt|winui|wpf", "app_executable": "<sandbox>/app/app.exe"},
  "read_only": true,
  "roots": {"data_root": "<sandbox>/data", "derived_root": "<sandbox>/derived", "catalog_db": "<sandbox>/data/catalog.json", "managed_root": "<sandbox>/data/managed"},
  "environment": {"required_executables": [], "required_env": [], "ports": [{"port": 9222, "purpose": "cdp"}], "min_free_gb": 1, "os": "windows"},
  "data": {"entities": {"regions": 2, "pipeline_runs": 2}, "files": [], "catalog_snapshot": {"kind": "json_snapshot", "tables": {}}}
}
```

`<sandbox>` 占位符在 `apply` 时被替换为沙箱根；任何解析后逃逸沙箱的 root 或文件路径都会触发 `READONLY_VIOLATION`。

## 3. 七类失败与检测方式

| class | 检测点 | code |
|---|---|---|
| `fixture_invalid` | `load_fixture`（Schema/语义） | `FIXTURE_INVALID` |
| `missing_executable` | `preflight_problems` | `EXECUTABLE_MISSING` |
| `missing_env` | `preflight_problems` | `ENV_VAR_MISSING` |
| `port_occupied` | `preflight_problems` | `CDP_PORT_NOT_LISTENING` / `PORT_OCCUPIED` |
| `data_root_missing` | `preflight_problems` | `SANDBOX_ROOT_UNRESOLVED` / `DISK_SPACE_LOW` |
| `readonly_violation` | `resolve_roots` / `apply_fixture` | `READONLY_VIOLATION` |
| `unsupported_stack` | `semantic_problems` | `STACK_UNSUPPORTED` |

`uiux-engine fixture validate` 输出 `failure_class_matrix` 供 R2 Gate 机械核对。

## 4. A/B 对照归因

`fixture.classify_ab_attribution(bad_problems, good_problems, product_signal)`：

- bad run 仅出现环境/fixture 类问题、good 对照干净 → `environment_authored=true`，**不得**记为产品 P0/P1；
- 两类共享问题或存在产品信号 → `product_defect_eligible=true`；
- 归因结果必须写入 issue 的 `attribution` 字段（TASK-04）。

## 5. 使用流程（New Manga 试点）

1. `fixture validate` → 确认声明合法。
2. `fixture apply --sandbox <new-sandbox>` → 生成合成 Region/Run/媒体/任务/导入导出数据（JSON 快照，**不是**真实 SQLite）。
3. `fixture preflight --sandbox <new-sandbox>` → 环境预检；任何问题先按环境处理。
4. 启动应用后再次 preflight（CDP 端口 9222 应监听）。
5. 审计/验证完成后保留 fixture 与 preflight 证据；真实数据目录不得被写入。

## 6. 约束

- 不写真实用户数据、不写生产目录、不复制真实数据库；
- `catalog_snapshot` 为 JSON 快照，不得声称是原生 SQLite；
- 无法构造的场景保留 `UNVERIFIED` + `disposition` 原因码，不得伪造 PASS；
- fixture 的实体数量是合成规模，不参与产品正确性判断。
