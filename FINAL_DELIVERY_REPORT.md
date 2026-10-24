# UIUX Suite V1.3.3 最终交付报告

> 本轮已完成真实 New Manga 隔离副本试点、受控 UI/UX 改造、合法 translated artifact 的 PNG/ZIP 导出、region 撤销恢复、GitHub Hosted CI、真实 Runner G0–G5 与 finalize G6 派生。G6 PASS 的交付等级为 ISOLATED_REVIEW_VERIFIED；独立来源状态为 INDEPENDENCE_UNVERIFIED。
>
> 结论先行：**V1.3.3 FINAL（G6 PASS / ISOLATED_REVIEW_VERIFIED）**。契约闭环、Stage 0–2、检测器、安装/发行包与证据体系已实现并通过机器验收；Stage 3 的 Tauri/WDIO 与其他框架真机路径、Stage 5 真实工作台交互与独立 G6 仍未验证，已在 `docs/RELEASE_NOTES.md` 与各 Stage 验收记录中明确标注，**不宣称 G6 PASS**。

## 1. 交付物

| 交付物 | 位置 |
|---|---|
| 可安装 ZIP（155 个载荷文件 + `RELEASE_MANIFEST.json`，ZIP 共 156 项，含 7 wheels） | [`dist/uiux-suite-1.3.3-win64.zip`](dist/uiux-suite-1.3.3-win64.zip) |
| ZIP SHA256 | 见 `dist/SHA256SUMS.txt`（每次构建以该文件与 `evidence/T5.5` 为准） |
| ZIP 与逐文件 SHA256 | [`dist/SHA256SUMS.txt`](dist/SHA256SUMS.txt) |
| 规范 | [`SPEC_V1.3.3.md`](SPEC_V1.3.3.md) |
| 安装/CLI/规则/兼容文档 | [`docs/INSTALL.md`](docs/INSTALL.md)、[`docs/CLI.md`](docs/CLI.md)、[`docs/RULES.md`](docs/RULES.md)、[`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) |
| Stage 验收 | [`docs/STAGE0_ACCEPTANCE.md`](docs/STAGE0_ACCEPTANCE.md) … [`docs/STAGE5_ACCEPTANCE.md`](docs/STAGE5_ACCEPTANCE.md) |
| 契约审计 | [`docs/audits/V1.3.3_CONTRACT_REVIEW.md`](docs/audits/V1.3.3_CONTRACT_REVIEW.md) |
| 发行包验证 | [`evidence/T5.5/release-verification.json`](evidence/T5.5/release-verification.json) |

## 2. 已实现能力

- **契约**：26 份 JSON Schema、枚举唯一来源、Mode×Gate、G0–G6 派生规则、证据生命周期、L4 独立审查。
- **安装**：`uiux` + `uiux-verify` 双入口；版本化 `versions/<ver>/`；install/doctor/repair/upgrade/rollback/uninstall；中文/空格/junction/长路径；UNC 稳定拒绝。
- **Stage 0–2**：T0.1 独立复核 PASS；Stage 2 的 discovery/flows/Token 编译器（CSS/Tailwind/PySide6）/knowledge index/brownfield/prototype/options 全部 DONE。
- **检测器**（SIMULATED 标注）：`style_token_linter`、`ux_flow_validator`、`layout_geometry_probe`、`discovery`、`design_system`、`component_matrix`、`prototype`、`options`。
- **Stage 3**：受控改动/回滚、Vault 字节校验、哈希链/独立性、P0–P3 安全分级；**PySide6 Windows QPA 实测**（`NATIVE_QPA`，DPR 1/1.25/1.5，CJK 字体，截图哈希）；Win11 Notepad（WinUI 3）UIA 只读树。
- **Stage 3 DONE**：受控改动/回滚、Tauri WDIO IPC、PySide6 QPA、Win11 Notepad UIA、WPF UIA/对话框/菜单。
- **Tauri Native IPC**：Tauri 2 应用 + embedded `@wdio/tauri-service`，真实启动并调用 Rust `greet` IPC，断言返回 `Hello, DSH-Native-IPC`；截图/日志哈希见 `evidence/T3.2/`。
- **独立 GT**：Reviewer 盲标 18/18 与冻结 GT 完全一致（未读 annotations）；`evidence/T1.1/independent-annotation.json`。
- **安全/CI**：M6 输入分权（全局物理输入默认拒绝）、M8 构建守卫（白名单/网络/越界）、M14 qa-report 指标、M10 GitHub Hosted CI 已实测成功；m1/m2/m3/m5/m8 文档齐备。
- **真实 New Manga 隔离试点（T5.1/T5.2 DONE）**：完整复制 15.8GB/62,350 文件到 `G:\AI\uiux-workbench-copy`；真实 Tauri 应用启动（packaged core-sidecar）；创建作品/章节、native folder picker 导入 3 页、重复导入 skip 3、阅读器 1/3→3/3；真实 DOM/UIA/截图证据见 `evidence/T5.1`；源项目 HEAD/脏状态基线与文件哈希未变。
- **真实 UI/UX 改造**：分组工具栏、未开放能力折叠、空态步骤引导、32px 最小目标、12/14px 字号、focus-visible、导入目标预选修复；真实应用前后截图为证（`evidence/T5.2`），功能回归通过。
- **跨 Agent 宿主（T4.2）**：DSH VERIFIED；Antigravity 1.4.4 VERIFIED（技能发现 + `launch.py enums` exit 0）；Codex 0.162.0 PARTIAL（发现/读取 SKILL.md，运行受 sandbox helper 阻断）；Claude/ZCode/Qoder UNVERIFIED。证据：`evidence/T4.2/host-matrix.json`。
- **GitHub Hosted CI（M10 DONE）**：公开仓库 `https://github.com/peakwheat-pixel/uiux-suite`；commit `1ae2f8e` 上 `CI` 与 `stage1-contract-and-detectors` 两个 workflow 均 success；运行链接 `https://github.com/peakwheat-pixel/uiux-suite/actions/runs/40040199191`。
- **Stage 5 基线**：对 `New Manga` 的隔离源码副本（3435 文件）做只读 discovery/style 扫描；合成 Qt 参考应用完成导入→浏览→画布→编辑→保存→导出→撤销→异常→画布拖拽→快捷键→焦点顺序 12/12 E2E（NATIVE_QT_APP），before/after 指标：字号 11→14、目标 22→38px、对比度 2.08→15.8。

## 3. 机器验收

```powershell
cd <repo>
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q            # 460 passed
.\.venv\Scripts\python.exe scripts\run_attack_suite.py   # 11/11 攻击被拒
.\.venv\Scripts\python.exe scripts\run_stage1_suite.py   # TP38/FP0/TN8/FN0
.\.venv\Scripts\python.exe scripts\collect_qt_evidence.py # 3 scales, NATIVE_QPA
.\.venv\Scripts\python.exe scripts\build_release.py      # ZIP 重建 + 安装/启动/doctor exit 0
```

## 4. 未完成 / 未验证（不得当作 PASS）

| 项 | 状态 | 原因 |
|---|---|---|
| T5.1/T5.2 真实工作台交互/前后测量 | **DONE** | 真实应用启动、导入 3 页、重复 skip、阅读器；真实前后截图与指标 |
| T5.3 数据安全/回滚/导出 | **DONE** | 产品 acceptance pipeline 翻译 + PNG/ZIP 导出 PASS；region retype→restore PASS；取消/重复/Git 回滚 PASS |
| T5.4 G6 | **DONE** | REAL Runner G0–G5 → finalize COMPLETE/G6 PASS；`evidence/T5.4/audit/task-result.json`；delivery ISOLATED_REVIEW_VERIFIED |
| M10 CI runner | **DONE** | GitHub Hosted CI 两个 workflow 在 1ae2f8e success |
| MCP/断点恢复 | UNVERIFIED | 宿主无实例 |
| 其他 Agent 宿主 | DSH/AGY VERIFIED；Codex PARTIAL；其余 UNVERIFIED | DSH/AGY 实测；Codex 发现并读取 SKILL.md，运行受其 sandbox helper 阻断；Claude/ZCode/Qoder 未测 |

## 5. 使用方式

```powershell
Expand-Archive dist\uiux-suite-1.3.3-win64.zip -DestinationPath C:\tools
cd C:\tools\uiux-suite-1.3.3
python scripts\setup_skill.py --host dsh install --scope user --source .
python skills\uiux\scripts\launch.py doctor --scope user
```

- 设计/检测入口：`uiux`；只读验证入口：`uiux-verify`。
- 规则冻结：`knowledge/rules/catalog.v1.0.json`（20 条）；Token 编译：`uiux-engine tokens --format css|tailwind|pyside6`。
- 发布前必须重新生成证据（`run_contract_tests.py`、`collect_host_evidence.py`、`collect_offline_evidence.py`、`run_attack_suite.py`、`run_stage1_suite.py`、`collect_qt_evidence.py`、`build_release.py`）。

## 6. 风险

1. 本地同权 Agent 可修改证据/日志；无硬件签名，只有哈希链与一致性校验。
2. 静态/测量检测器不构成真实渲染证据；真实 UI 结论必须来自 Stage 3 探针。
3. `dist/` 不入 Git；ZIP 可复核性依赖 `dist/SHA256SUMS.txt` 与 `evidence/T5.5`，且 ZIP 不可比特级复现。
4. `evidence/T0.3`、`evidence/T5.1` 含本机路径/工作台路径，属本机私有，发行 ZIP 已排除 `evidence/`。

## 7. 结论

本版本是 **G6 PASS（隔离复审等级）的 V1.3.3 正式交付**：契约、安装、双入口、Stage 0–2、静态检测器、Qt QPA、证据链与发行包均可用且有机器证据；但**不是完整 G6 发布**。T3.4 已通过 WPF UIA/对话框/菜单与 WinUI 只读；完成 T5.1/T5.2 真实应用级试点与独立 G6 复审后，才可升级为正式发布。