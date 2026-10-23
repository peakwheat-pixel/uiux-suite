# CLI 契约（V1.3.3）

入口：`.\.venv\Scripts\python.exe -m uiux_engine.cli`（`cwd=runtime` 或 `PYTHONPATH=runtime`）。

## 命令

| 命令 | 作用 |
|---|---|
| `enums` | 输出唯一枚举字典（JSON） |
| `validate --schema <name> --instance <path>` | 校验单个实例；`task-request` 额外执行交叉字段语义 |
| `policy --mode <mode> [--request <path>]` | 解析 Mode×Gate 矩阵、派生 Gate、最低运行层级 |
| `finalize --request ... --gate-results ... --coverage ... --evidence-manifest ... [--tool-logs ...] [--design-review ...] [--review-attestation ...] [--warn-reviews ...] [--now ...] [--out ...]` | 从证据派生 G6 与 TaskResult |
| `rules` | 校验冻结规则目录与冻结摘要 |
| `snapshot --root ... [--out ...] [--backup ...] [--diff A B]` | 非 Git 目录摘要/备份/差异 |
| `modify --root ... --plan ... [--apply] [--backup DIR] [--revert DIR]` | 受控改动：写作用域/哈希/回滚（T3.1） |
| `vault --root ... --manifest ... [--quarantine DIR]` | 证据字节校验/隔离（T3.5） |
| `integrity --chain ... [--attestation ...] [--commit ...]` | 持久化哈希链与审查绑定校验（T3.6） |
| `safety --plan ...` | 变更计划 P0–P3 分级（T3.7） |
| `compat [--agents-home ...]` | 宿主退化检查（T4.4） |

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
.\.venv\Scripts\python.exe -m uiux_engine.cli finalize --request ... --gate-results ... --coverage ... --evidence-manifest ... --tool-logs ... --design-review ... --review-attestation ... --warn-reviews ... --repair-cycles 0 --now 2026-10-23T12:00:00+00:00 --out result.json
```

`gate-results.request_digest` 必须等于 `sha256(canonical TaskRequest)`；不匹配时退出码 10（`REQUEST_DIGEST_MISMATCH`），阻止事后调低 `runtime_targets`。`--repair-cycles` 只接受 0..2。

## 非 Git 快照（M17）

```powershell
.\.venv\Scripts\python.exe -m uiux_engine.cli snapshot --root "G:\project" --out "G:\project\.uiux\state\snapshot.json" --backup "G:\backup\project"
.\.venv\Scripts\python.exe -m uiux_engine.cli snapshot --diff before.json after.json
```

- `snapshot` 输出 `file_count` 与 `digest`；忽略 `.git/.venv/__pycache__/node_modules` 与符号链接。
- `--backup` 复制一份可回滚副本（目标必须不存在）；回滚即把备份副本拷回目标目录（显式运维操作）。
- `--diff` 输出 added/removed/changed；一致退出 0，有差异退出 11。

## 安装 / doctor / 启动器（T0.2 起）

```powershell
# 用户级安装（DSH_AGENTS_HOME 可覆盖默认 ~/.agents）
.\.venv\Scripts\python.exe scripts\setup_skill.py install --scope user --host dsh --version 1.3.3

# 项目级安装
.\.venv\Scripts\python.exe scripts\setup_skill.py install --scope project --project "G:\demo" --host generic

# doctor：输出 host-capability JSON（root/rank/shadowed_by/能力）
.\.venv\Scripts\python.exe scripts\setup_skill.py doctor --scope user [--project G:\demo] [--out host-capability.json]

# 升级/回滚/修复/卸载
.\.venv\Scripts\python.exe scripts\setup_skill.py upgrade  --scope user --source . --version 1.3.4
.\.venv\Scripts\python.exe scripts\setup_skill.py rollback --scope user --version 1.3.3
.\.venv\Scripts\python.exe scripts\setup_skill.py repair   --scope user
python scripts\uninstall_skill.py --scope user --version 1.3.3
```

启动器（Skill 入口实际调用）：

```powershell
python %USERPROFILE%\.agents\skills\uiux\scripts\launch.py enums
```

### 启动器退出码

| 码 | 含义 |
|---:|---|
| 0 | 正常执行运行时命令 |
| 3 | `LINK_MISSING` / `LINK_INVALID` |
| 4 | `RELEASE_ROOT_MISSING` / `VERSION_MISMATCH` |
| 5 | `PYTHON_EXE_MISSING` |
| 6 | `MANIFEST_MISMATCH` / `MANIFEST_CORRUPT` |
| 7 | `INSTALLED_DOCTOR_MISSING`（suite 内 doctor 缺失，需重装/修复） |

### setup/doctor 退出码

| 码 | 含义 |
|---:|---|
| 0 | 安装成功 / doctor 为 READY 或 UNVERIFIED |
| 10 | 安装或校验失败（`SKILL_EXISTS`、`SUITE_EXISTS`、Schema 错误等） |
| 11 | doctor 发现 MISSING/INCOMPATIBLE 或 link 问题 |

## 尚未实现

- `prepare` / `run` / `verify` 子命令（Stage 0–1）。
- engine-side `doctor` 子命令（当前 doctor 归属 `scripts/setup_skill.py`，输出 `host-capability.v1.3.3`）。
- `--json` 之外的人类可读摘要。
