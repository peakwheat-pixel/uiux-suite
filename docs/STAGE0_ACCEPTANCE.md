# Stage 0 验收记录（V1.3.3）

> 更新时间：2026-10-24。结论以 Git、测试与 evidence 文件为准；本文只做索引。

## 1. 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T0.1 Contract Closure | **DONE（独立复核 PASS）** | `docs/audits/V1.3.3_CONTRACT_REVIEW.md`、`evidence/T0.1/contract-test-evidence.json` |
| T0.2 版本化发行根/双启动器/安装卸载升级回滚 | DONE | `tests/integration/test_install.py`（11 项） |
| T0.3 DSH 实机安装与双入口发现 | DONE | `evidence/T0.3/host-install-evidence.json`；DSH 会话技能目录出现 `uiux` / `uiux-verify` |
| T0.4 doctor | DONE | doctor 输出 `host_capability`；真实 root/rank/shadow；退出码 0/11 |
| T0.5 许可/离线/版本锁定 | DONE | `LICENSE`、`THIRD_PARTY_NOTICES.md`、`requirements.lock`、`dist/wheels/`；离线 venv 实测 |
| T0.6 仓库独立运行 | DONE | 安装后从 `C:\` 运行 `launch.py doctor` exit 0；suite-link/record 无开发仓绝对路径 |

## 2. 机器验收命令

```powershell
cd G:\AI\universal-uiux-engineering
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\run_contract_tests.py
.\.venv\Scripts\python.exe scripts\collect_host_evidence.py
```

预期：`pytest` 全绿；evidence `exit_code=0` 且 `failures=0`；host evidence `independent_of_source_checkout=true`。

## 3. 已知限制（不阻断 Stage 0）

1. doctor 的 MCP/断点恢复为 `UNVERIFIED`（Stage 4 验证）。
2. UNC/长路径、junction 仅部分覆盖（M5，Stage 0 后补）。
3. 其他 Agent 宿主未实测（T4.2 兼容矩阵）。
4. 本地同权 Agent 可改证据/工具日志；本包只声明"一致派生 + 防意外损坏"，高可信签发在 T3.6/CI。
5. 原件字节级证据校验在 T3.5 生效；T0.1 仅清单/引用哈希。

## 4. Stage 0 判定

- 代码/契约/安装/doctor/仓库独立均具备可复核证据。
- 待第 3 轮 Reviewer 对 R-01..R-11 增量确认后，T0.1 状态与证据引用方可最终冻结。
