# Stage 3 验收记录（V1.3.3）

> 更新时间：2026-10-24。真实原生能力受本机环境限制，未执行项一律标 UNVERIFIED，不伪造 PASS。

## 1. 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T3.1 受控改造与 G4 范围校验 | **DONE** | `modify.py` + change-plan schema；10 用例（scope/traversal/hash/回退/dry-run） |
| T3.2 Tauri + WDIO Native IPC | **IN_PROGRESS（UNVERIFIED）** | 本机无 Tauri 示例/驱动，未伪造 |
| T3.3 PySide6 Native QPA/DPI | **DONE** | `qt_probe.py` + `collect_qt_evidence.py`；`evidence/T3.3/qt-qpa-evidence.json`：NATIVE_QPA、DPR 1/1.25/1.5、CJK 字体；125/150 为 QT_SCALE_FACTOR 模拟 |
| T3.4 OS 集成/UIA | **PARTIAL** | 真实 Win11 Notepad（WinUI 3） UIA 只读树（`evidence/T3.4/uia-probe.json`，NATIVE_UIA，53 元素）；WinUI/WPF/Qt 未验证 |
| T3.5 证据 Vault 退化 | **DONE** | `vault.py`；字节级哈希、隔离、缺失检测（14 用例含 integrity/safety） |
| T3.6 独立审查隔离 | **DONE** | `integrity.py`；user_attested 拒绝、reviewed_head 绑定、host_verified 证据要求 |
| M14 P0–P3 安全指标 | PARTIAL | `safety.py` 分级/指标；qa-report schema 未建 |
| M18 无障碍 Rule ID/UIA | PARTIAL→改善 | A11Y 规则 + 静态子集 + 真实 Win11 Notepad（WinUI 3）UIA 模型；WinUI/WPF/Qt/动态键盘未验证 |

## 2. 机器验收

```powershell
cd <repo>
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q     # 当时 405 passed（当前 447）
pwsh -NoProfile -File scripts\collect_uia_evidence.ps1 -ProcessId <notepad-pid>
```

CLI 集成：`modify` / `vault` / `integrity` / `safety` / `compat` 已加入 `uiux_engine.cli`（见 `docs/CLI.md`），不再只是库级函数。

UIA 证据要点：

- `runtime_level=NATIVE_UIA`，read-only，window=Notepad；
- 53 个元素、24 个可交互、0 个缺失名称；
- 真实发现 24 个 target<24px（标题栏/菜单 OS 绘制），已记录为边界而非直接产品缺陷；
- 脚本 SHA256 写入证据，证明生成器可复核。

## 3. 已知限制

1. Tauri/PySide6 未安装，Native IPC/QPA/DPI 未验证；相关证据缺口必须在 Stage 5 发布说明中声明。
2. UIA 仅控制视图快照，不做点击/焦点顺序；不能用它宣称交互验证通过。
3. Win11 Notepad 实为 WinUI 3（UIA 树含 Microsoft.UI.Xaml.Controls.*）；本次仅控制视图只读快照，其他框架未验证。
4. 证据 Vault 校验的是引用文件哈希，不等于真实签名；本地同权可改证据的限制仍在。

## 4. Stage 3 判定

- T3.1/T3.5/T3.6 有可复核证据；T3.2 UNVERIFIED；T3.4 PARTIAL（T3.3 已 DONE）。
- **Stage 3 不宣称 PASS**；发布前必须保留 UNVERIFIED 声明。
