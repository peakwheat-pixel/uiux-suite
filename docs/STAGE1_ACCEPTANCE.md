# Stage 1 验收记录（V1.3.3）

> 更新时间：2026-10-24。结论以 Git、pytest、`qa/confusion-matrix.json` 与 evidence 为准。

## 1. 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T1.0 规则目录与 Rule ID 冻结 | **DONE** | `knowledge/rules/catalog.v1.0.json`（20 条）+ freeze；`tests/unit/test_rules.py` |
| T1.1 双栈正反 Fixtures 与冻结 GT | **DONE** | `tests/fixtures/ground_truth/{web,qt,annotations}`；18 样本 |
| T1.2 style_token_linter | **DONE** | `runtime/uiux_engine/style_linter.py`；39 用例；10 条规则 |
| T1.3 ux_flow_validator | **DONE** | `runtime/uiux_engine/flow_validator.py`；14 用例；6 条规则 |
| T1.4 layout_geometry_probe | **PARTIAL / IN_PROGRESS** | 测量 JSON 模式 DONE（55 用例、SIMULATED）；真实 Web DOM/Qt Offscreen 探针转 T3.3 |
| T1.5 Runner/Gate 引擎完整化 | **DONE** | `tests/unit/test_finalize.py`（27）+ `tests/integration/test_attacks.py`（11） |
| T1.6 负向攻击测试 | **DONE** | 11 项攻击全部被拒（exit 10/11）；`evidence/T1.6/attack-evidence.json` |
| T1.7 混淆矩阵/CI | **DONE（SIMULATED）** | `qa/confusion-matrix.json`：25 样本 TP38/FP0/TN8/FN0；`.github/workflows/stage1.yml` |
| M10 CI Windows runner | IN_PROGRESS | workflow 已提交，真实 runner 执行未验证 |
| M18 无障碍 Rule ID | IN_PROGRESS | A11Y-001..004 规则/静态子集 DONE；ARIA-UIA 矩阵与动态键盘验证转 T3.3/T3.4 |
| m4 混淆矩阵契约 | DONE | `contracts/confusion-matrix.v1.3.3.schema.json` |

## 2. 机器验收

```powershell
cd <repo>
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q            # 当时 292 passed
.\.venv\Scripts\python.exe scripts\run_attack_suite.py   # 11/11, exit 0
.\.venv\Scripts\python.exe scripts\run_stage1_suite.py   # TP38/FP0/TN8/FN0, exit 0
```

## 3. 已知限制

1. 所有检测器当前为静态/测量 JSON 模式，标注 `SIMULATED`；不构成 NATIVE 或真实截图证据。
2. T1.4 的真实 DOM/Qt Offscreen 测量依赖 Stage 3 的 UI 探针（T3.3）。
3. 混淆矩阵样本 25 个，覆盖 10 个规则；其余规则（如目标重叠/裁切的真实场景）在 Stage 3 扩展。
4. CI workflow 尚未在真实 runner 上执行（M10）。
5. T1.1 GT 为单 Agent 标注（`independent=false`），独立复核归 Stage 5/Reviewer。

## 4. Stage 1 判定

- T1.0–T1.3、T1.5–T1.7 有可复核证据；T1.4 为 PARTIAL，因此 **Stage 1 暂不宣称 PASS**。
- 阻塞点不阻断 Stage 2：真实测量属于 Stage 3 能力，T3.3 接手；Stage 2–5 可继续。
