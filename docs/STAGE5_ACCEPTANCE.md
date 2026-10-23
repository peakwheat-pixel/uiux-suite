# Stage 5 验收记录（V1.3.3）

## 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T5.1 真实复杂工作台试点 | **DONE** | 真实 New Manga 完整隔离副本启动；导入 3 页、重复 skip、阅读器 1/3→3/3；`evidence/T5.1/real-app-pilot.json` |
| T5.2 改版前后对照测量 | **DONE** | 真实应用改造前后截图/指标：小目标 1-2→0、min font 10→11/12、分组工具栏/高级折叠/空态步骤；`evidence/T5.2/before-after.json` |
| T5.3 数据安全/回滚/导出 | **IN_PROGRESS** | 取消/重复跳过/DB/源未变/Git 回滚 PASS；导出需 translated artifact，撤销/重做产品未提供 |
| T5.4 独立复审与 G6 | **IN_PROGRESS（INCOMPLETE）** | reviewer-v133 只读复审：G6 不可签发，阻断见 `evidence/T5.4/g6-review.json` |
| M16 附录命令一致性 | **DONE** | `scripts/check_command_consistency.py` 0 issue；文档统一 `.venv` 解释器 |
| T5.5 发行包/文档/交付报告 | **DONE** | 151 载荷 + manifest（ZIP 152 项）；安装/双入口/doctor 实测 exit 0 |

## 合成工作台 E2E（NATIVE_QT_APP）

`sandbox/workbench_app` + `scripts/run_workbench_e2e.py` 在真实 Qt（Windows QPA）中执行：

1. 导入 JSON → 列表浏览 → 画布新增 → 画布拖拽 → 编辑属性 → 保存 → 导出 → 撤销/重做 → 快捷键 → 非法导入拒绝 → 焦点顺序。
2. 全部 12 步通过（含画布拖拽、快捷键元数据+触发、焦点顺序）；before/after 指标与截图哈希写入证据。
3. 数据全部合成、临时目录；不触碰真实项目。

限制：QTest 是 Qt 级事件（非 OS 物理键鼠/UIA 点击）；非法导入对话框由测试替身自动确认；截图是 `QWidget.grab()`。

## 发行包验证

```powershell
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe scripts\build_release.py
# ok=true files=151 install_exit=0 enums_exit=0 doctor_exit=0
```

证据：`evidence/T5.5/release-verification.json`、`release-install.txt`；ZIP SHA256 见 `dist/SHA256SUMS.txt`。

## 结论

- 发行包、合成应用 E2E、静态基线、before/after 指标已具备；
- 真实试点与前后对比已完成；T5.3 导出/撤销、独立 G6 未完成，**整体仍为 PARTIAL / RC，不是 G6 PASS**；
- 禁止把 UNVERIFIED 项写成 PASS；`docs/RELEASE_NOTES.md` 已列全部未验证能力。