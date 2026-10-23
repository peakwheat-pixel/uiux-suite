# CLI 契约（V1.3.3）

入口：`python -m uiux_engine.cli`（`cwd=runtime` 或 `PYTHONPATH=runtime`）。

## 命令

| 命令 | 作用 |
|---|---|
| `enums` | 输出唯一枚举字典（JSON） |
| `validate --schema <name> --instance <path>` | 校验单个实例；`task-request` 额外执行交叉字段语义 |
| `policy --mode <mode> [--request <path>]` | 解析 Mode×Gate 矩阵、派生 Gate、最低运行层级 |
| `finalize --request ... --gate-results ... --coverage ... --evidence-manifest ... [--tool-logs ...] [--design-review ...] [--review-attestation ...] [--warn-reviews ...] [--now ...] [--out ...]` | 从证据派生 G6 与 TaskResult |

## 退出码（稳定契约）

| 码 | 含义 |
|---:|---|
| 0 | 校验通过 / `status=COMPLETE` |
| 2 | 用法错误（未知 schema、缺参数） |
| 10 | Schema 或交叉字段校验失败；生成结果不合法 |
| 11 | `status=PARTIAL` |
| 12 | `status=FAILED` |
| 13 | `status=BLOCKED` |

## 输出

- `stdout` 为 UTF-8 JSON；`validate` 成功输出 `{"ok": true, ...}`，失败输出 `{"ok": false, "errors": [...]}`。
- `finalize` 输出状态摘要（`status`、`delivery_status`、`independent_review_status`、`design_review_status`、`runtime_evidence_level`、`g6`、`resolved_gates`、`blocking_reasons`、`unverified_paths`）。
- `--out` 写入完整 TaskResult（供 Schema 再校验与归档）。

## 组合示例

```powershell
$env:PYTHONPATH = "runtime"
.\.venv\Scripts\python.exe -m uiux_engine.cli validate --schema task-request --instance tests\fixtures\contracts\valid\task-request-redesign.json
.\.venv\Scripts\python.exe -m uiux_engine.cli finalize --request ... --gate-results ... --coverage ... --evidence-manifest ... --tool-logs ... --design-review ... --review-attestation ... --now 2026-10-23T12:00:00+00:00 --out result.json
```

## 尚未实现

- `doctor`（T0.4）：`--json` 输出 `host-capability.json`，含 root/rank/shadowed_by。
- `prepare` / `run` / `verify` 子命令（Stage 0–1）。
- 安装器与启动器 CLI（T0.2）。
