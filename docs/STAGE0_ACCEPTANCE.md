# Stage 0 验收记录（V1.3.3）

> 更新时间：2026-10-24。结论以 Git、测试与 evidence 文件为准；本文只做索引。

## 1. 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T0.1 Contract Closure | **DONE（独立复核 PASS）** | `docs/audits/V1.3.3_CONTRACT_REVIEW.md`、`evidence/T0.1/contract-test-evidence.json` |
| T0.2 版本化发行根/双启动器/安装卸载升级回滚 | DONE | `tests/integration/test_install.py`（11 项） |
| T0.3 DSH 实机安装与双入口发现 | DONE | `evidence/T0.3/host-install-evidence.json`；DSH 会话技能目录出现 `uiux` / `uiux-verify` |
| T0.4 doctor | DONE | doctor 输出 `host_capability`；真实 root/rank/shadow；退出码 0/11 |
| T0.5 许可/离线/版本锁定 | DONE | `LICENSE`、`THIRD_PARTY_NOTICES.md`、`requirements.lock`、`dist/wheels/`；`evidence/T0.5/offline-install-evidence.json` |
| T0.6 仓库独立运行 | DONE | 安装后从 `C:\` 运行 `launch.py doctor` exit 0；`host-install-evidence.json.repo_independence` |
| M5 UNC/junction/MAX_PATH | DONE | `tests/integration/test_paths.py`（junction、>260 长路径、UNC 稳定拒绝） |

## 2. 机器验收命令

```powershell
cd G:\AI\universal-uiux-engineering
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe scripts\run_contract_tests.py
.\.venv\Scripts\python.exe scripts\collect_host_evidence.py
.\.venv\Scripts\python.exe scripts\collect_offline_evidence.py
```

预期：`pytest` 全绿；T0.1 evidence `exit_code=0` 且 `failures=0`；host evidence `independent_of_source_checkout=true`；offline evidence 三个 exit code 均为 0。

## 3. 已知限制（不阻断 Stage 0）

1. doctor 的 MCP/断点恢复为 `UNVERIFIED`（Stage 4 验证）。
2. 其他 Agent 宿主未实测（T4.2 兼容矩阵）。
3. 本地同权 Agent 可改证据/工具日志；本包只声明"一致派生 + 防意外损坏"，高可信签发在 T3.6/CI。
4. 原件字节级证据校验在 T3.5 生效；T0.1 仅清单/引用哈希。
5. T0.6 的"删除开发仓"采用**代理验证**：删除临时源码副本 + 外部 cwd 运行 + 安装树无开发仓绝对引用；未真实删除本开发仓。
6. `evidence/T0.3/` 含本机绝对路径，是**本机私有证据**，随仓库保留但不随发行包分发；发行包只带脱敏摘要与哈希。
7. `dist/wheels/` 不入 Git；离线可复核性由 `evidence/T0.5` 的 wheel 清单 + SHA256 + 安装日志保证。

## 4. Stage 0 判定

- T0.1–T0.6 与 M5 均有可复核证据，M5 无残留。
- 第 3 轮增量确认发现的 3 项 MAJOR（S-01/S-02/S-03）与 11 项 MINOR 已修复；最终结论以第 4 轮只读确认与最终证据为准。
