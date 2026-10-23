# UIUX Suite V1.3.3 最终交付报告

> 结论先行：**Release Candidate（整体 PARTIAL）**。契约闭环、检测器、安装/发行包与证据体系已实现并通过机器验收；原生 Tauri/PySide6/WinUI/WPF、真实工作台试点、其他 Agent 宿主与 MCP/断点恢复仍未验证，已在 `docs/RELEASE_NOTES.md` 与各 Stage 验收记录中明确标注，**不宣称 G6 PASS**。

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| 可安装 ZIP（120 载荷 + manifest（ZIP 121 项），含 7 wheels） | [`dist/uiux-suite-1.3.3-win64.zip`](dist/uiux-suite-1.3.3-win64.zip) |
| ZIP 与逐文件 SHA256 | [`dist/SHA256SUMS.txt`](dist/SHA256SUMS.txt) |
| 规范 | [`SPEC_V1.3.3.md`](SPEC_V1.3.3.md) |
| 安装/CLI/规则/兼容文档 | [`docs/INSTALL.md`](docs/INSTALL.md)、[`docs/CLI.md`](docs/CLI.md)、[`docs/RULES.md`](docs/RULES.md)、[`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) |
| Stage 验收 | [`docs/STAGE0_ACCEPTANCE.md`](docs/STAGE0_ACCEPTANCE.md) … [`docs/STAGE5_ACCEPTANCE.md`](docs/STAGE5_ACCEPTANCE.md) |
| 契约审计 | [`docs/audits/V1.3.3_CONTRACT_REVIEW.md`](docs/audits/V1.3.3_CONTRACT_REVIEW.md) |
| 发行包验证 | [`evidence/T5.5/release-verification.json`](evidence/T5.5/release-verification.json) |

## 2. 已实现能力

- **契约**：19 份 JSON Schema、枚举唯一来源、Mode×Gate、G0–G6 派生规则、证据生命周期、L4 独立审查。
- **安装**：`uiux` + `uiux-verify` 双入口；版本化 `versions/<ver>/`；install/doctor/repair/upgrade/rollback/uninstall；中文/空格/junction/长路径；UNC 稳定拒绝。
- **检测器**（SIMULATED 标注）：
  - `style_token_linter`（10 规则，QSS/Web/TSX）；
  - `ux_flow_validator`（可达性/破坏性/空态/错误/加载）；
  - `layout_geometry_probe`（测量 JSON：裁切/重叠/目标/对比度/焦点）；
  - `discovery`（路由/Qt/组件/能力证据）；
  - `design_system`（token + 漂移检查）；
  - `component_matrix`/`prototype`/`options`。
- **证据与安全**：Vault 字节校验与隔离、哈希链、独立性绑定、P0–P3 安全分级、受控改动与回滚。
- **真实证据**：Win11 Notepad（WinUI 3） UIA 只读树（NATIVE_UIA，53 元素）——`evidence/T3.4/uia-probe.json`。

## 3. 机器验收

```powershell
cd <repo>
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q            # 418 passed
.\.venv\Scripts\python.exe scripts\run_attack_suite.py   # 11/11 攻击被拒
.\.venv\Scripts\python.exe scripts\run_stage1_suite.py   # TP38/FP0/TN8/FN0
.\.venv\Scripts\python.exe scripts\build_release.py      # ZIP 重建 + 安装/启动/doctor exit 0
```

## 4. 未完成 / 未验证（不得当作 PASS）

| 项 | 状态 | 原因 |
|---|---|---|
| T3.2 Tauri + WDIO Native IPC | UNVERIFIED | 本机无 Tauri 示例/驱动 |
| T3.3 PySide6 QPA/DPI | UNVERIFIED | 未安装 PySide6 |
| T3.4 原生对话框/WinUI/WPF/Qt | PARTIAL | 仅 Win11 Notepad（WinUI 3） 实测 |
| T5.1/T5.2 真实工作台试点/前后测量 | UNVERIFIED | 无授权隔离副本 |
| T5.3 真实项目数据安全 | PARTIAL | 仅代码/测试级回滚 |
| T5.4 独立 G6 | IN_PROGRESS | 需独立 Reviewer 签发 |
| M10 CI runner / M11 知识库 / M12 brownfield | IN_PROGRESS | 未执行或未实现 |
| MCP/断点恢复 | UNVERIFIED | 宿主无实例 |
| 其他 Agent 宿主 | UNVERIFIED | 未安装/未实测 |

## 5. 使用方式

```powershell
Expand-Archive dist\uiux-suite-1.3.3-win64.zip -DestinationPath C:\tools
cd C:\tools\uiux-suite-1.3.3
python scripts\setup_skill.py --host dsh install --scope user --source .
python skills\uiux\scripts\launch.py doctor --scope user
```

- 设计/检测入口：`uiux`；只读验证入口：`uiux-verify`。
- 规则冻结：`knowledge/rules/catalog.v1.0.json`（20 条）。
- 发布前必须重新生成证据（`scripts/run_contract_tests.py`、`collect_host_evidence.py`、`collect_offline_evidence.py`、`run_attack_suite.py`、`run_stage1_suite.py`、`build_release.py`）。

## 6. 风险

1. 本地同权 Agent 可修改证据/日志；无硬件签名，只有哈希链与一致性校验。
2. 所有检测器为静态/测量模式，不构成真实渲染证据；真实 UI 结论必须来自 Stage 3 探针。
3. `dist/` 不入 Git，ZIP 可复核性依赖 `dist/SHA256SUMS.txt` 与 `evidence/T5.5`。
4. `evidence/T0.3` 含本机路径，属本机私有，发行 ZIP 已排除 `evidence/`。

## 7. 结论

本版本可作为**受控试用的 Release Candidate**：契约、安装、双入口、冻结规则、静态检测器、证据链与发行包均可用且有机器证据；但**不是完整 G6 发布**。完成 T3.2/T3.3/T3.4 真实原生验证、T5.1/T5.2 隔离试点与独立 G6 复审后，才可升级为正式发布。
