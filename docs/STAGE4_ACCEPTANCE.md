# Stage 4 验收记录（V1.3.3）

## 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T4.1 DSH 宿主兼容实测 | **DONE** | `evidence/T0.3/host-install-evidence.json`；双入口/doctor/外部 cwd |
| T4.2 其他 Agent 兼容矩阵 | **IN_PROGRESS** | `compat.py` 矩阵；其他宿主 `UNVERIFIED`（`HOST_UNVERIFIED`） |
| T4.3 被动外部调用契约 | **DONE** | `external.py`；caller/task_id/request 校验，`orchestrates=false` |
| T4.4 退化路径 | **DONE** | `compat.degradation_report()`：Python/Node/GUI/链接缺失 ReasonCode |

## 机器验收

```powershell
$env:PYTHONPATH='runtime'; .venv\Scripts\python.exe -m pytest tests -q   # 460 passed
```

## 未验证

- MCP 通道与断点恢复（DSH 宿主未提供可复现实例）。
- Codex/Claude/ZCode/Antigravity/Qoder 实际技能发现。
- 真实 GUI 点击链路（物理输入默认禁用）。

因此 **Stage 4 不宣称 PASS**；只声明 DSH 文件级/CLI 级兼容与明确降级行为。
