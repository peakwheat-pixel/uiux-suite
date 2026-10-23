# 宿主兼容矩阵（Stage 4）

> 事实优先：只有 DSH 本机有实测证据；其他宿主一律 `UNVERIFIED`，不根据"看起来支持"宣称兼容。

| 宿主 | 状态 | 证据 / 原因 |
|---|---|---|
| DSH | **OBSERVED** | `evidence/T0.3/host-install-evidence.json`：双入口发现、rank 500、doctor、外部 cwd、`pytest` 460 |
| Codex | UNVERIFIED | `HOST_UNVERIFIED`（未安装/未实测） |
| Claude Code | UNVERIFIED | 同上 |
| ZCode | UNVERIFIED | 同上 |
| Antigravity | UNVERIFIED | 同上 |
| Qoder | UNVERIFIED | 同上 |
| generic | UNVERIFIED | 只保证文件契约与 Python 启动器，未实测 |

## 已实测能力（DSH）

- 双 Skill 入口：`uiux`、`uiux-verify` 被发现并启动。
- `launch.py enums` / `doctor` 退出码 0；安装树不依赖开发仓。
- 中文/空格/junction/长路径/UNC 缺失路径用例通过。
- MCP 与断点恢复：**UNVERIFIED**（Stage 4 未拿到宿主真实 MCP 通道）。

## 降级行为

`compat.degradation_report()` 返回：

| 缺失项 | ReasonCode |
|---|---|
| Python <3.10 或不可用 | `PYTHON_EXE_MISSING` |
| Node 缺失 | `HOST_UNVERIFIED` |
| 无 GUI | `HOST_UNVERIFIED` |
| suite-link 缺失 | `LINK_MISSING` |

外部 caller 通过 `external.accept_call()` 传入 `caller/task_id/request_path/role`；引擎只接受被动调用，`orchestrates=false`，不会反向编排调用方。
