# 实施状态（Recovery Entry）

> 更新：2026-10-24。以 Git、`pytest`、`evidence/` 与 `dist/SHA256SUMS.txt` 为准；本文件不重复未验证结论。

## 1. 当前结论

- **V1.3.3 FINAL（61/61 DONE）**：`dist/uiux-suite-1.3.3-win64.zip` 可安装并验证（install/enums/doctor exit 0；clean uninstall 85 files；rollback same-version exit 0）。
- **G6 PASS（ISOLATED_REVIEW_VERIFIED）**：G0–G5 真实 Runner 通过，finalize 输出 COMPLETE/G6 PASS；外部独立来源 `INDEPENDENCE_UNVERIFIED`，UI 撤销按钮 E2E 未通过，见 `FINAL_DELIVERY_REPORT.md` §3.1/§4。
- 分支：`v1.3.3-contract-closure`；基线 `main` `e7e921e`（tag `v1.3.2-baseline`，SHA256 `70f5f339…9411ea04` 未变）。
- 当前测试：**460 passed**（`$env:PYTHONPATH='runtime'; .venv\Scripts\python.exe -m pytest tests -q`）。

## 2. 已实现（有证据）

| 领域 | 产物 | 证据 |
|---|---|---|
| 契约 | `contracts/`：26 份 Schema + 枚举字典 + Mode×Gate | `tests/unit/test_schemas.py`、`test_enums.py`、`test_policy.py` |
| 安装 | 双入口、版本化 suite、install/doctor/repair/upgrade/rollback/uninstall | `tests/integration/test_install.py`、`test_paths.py` |
| Gate/finalize | G0–G6 派生、WARN 处置、L4、证据生命周期 | `tests/unit/test_finalize.py`、`tests/integration/test_attacks.py` |
| 规则与检测器 | 冻结 20 条；style/flow/geometry/discovery/design-system/component/prototype/options | `knowledge/rules/`、`tests/unit/test_*.py`、`qa/confusion-matrix.json` |
| Stage 3 安全 | modify/vault/integrity/safety/uia | `runtime/uiux_engine/*.py`、`tests/unit/test_*` |
| 宿主兼容 | DSH 实测；其他宿主 UNVERIFIED；退化 ReasonCode | `docs/COMPATIBILITY.md`、`compat.py` |
| 发行 | 155 载荷 + manifest ZIP、SHA256SUMS、安装验证 | `dist/`、`evidence/T5.5/` |

## 3. Stage 状态

| Stage | 状态 | 说明 |
|---|---|---|
| 0 | **DONE / FROZEN** | T0.1 独立复核 PASS；T0.2–T0.6、M5 有机器证据 |
| 1 | **DONE** | T1.0–T1.8 DONE；M13 独立 GT DONE；M18 DONE（无全局物理键盘） |
| 2 | **DONE** | T2.1–T2.6、M11、M12 均有测试/证据 |
| 3 | **DONE** | T3.1–T3.6 全部有证据；WinUI 动作/全局物理输入限制见 STAGE3 |
| 4 | **DONE** | T4.2 DSH/AGY VERIFIED、Codex PARTIAL；其余 UNVERIFIED |
| 5 | **DONE** | T5.1–T5.4 完成；真实 G0–G5 Runner → G6 PASS（ISOLATED_REVIEW_VERIFIED） |

## 4. 机器验收命令

```powershell
cd <repo>
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\run_attack_suite.py
.\.venv\Scripts\python.exe scripts\run_stage1_suite.py
.\.venv\Scripts\python.exe scripts\build_release.py
```

## 5. 外部阻断

T5.1–T5.4、T4.2、M10 需要真实应用/数据授权、其他宿主隔离配置或 CI runner；详见 `docs/BLOCKERS.md`。

## 6. 恢复点

- 最新提交与标签以 `git log --oneline -1` / `git tag` 为准；不得在 `SPEC_V1.3.2.md` 上修改（基线哈希冻结）。
- 所有证据脚本重跑后必须重新提交 evidence；发行包重建后必须更新 `dist/SHA256SUMS.txt` 与 `evidence/T5.5/`。