# 阶段验收门（Stage Exit Gates）

> 每个 Stage 的退出必须同时满足三列：**机器命令**、**退出码/状态**、**证据产物**。
> 任一列为 UNVERIFIED 时，Stage 不得标记 PASS；只能记 PARTIAL/UNVERIFIED 并写明缺口。

## Stage 0 — 契约与安装

| 项 | 门 | 证据 |
|---|---|---|
| T0.1 契约闭环 | `scripts/run_contract_tests.py` → exit 0 且 `summary.failures=0`；独立复核 PASS | `evidence/T0.1/contract-test-evidence.json`、`docs/audits/V1.3.3_CONTRACT_REVIEW.md` |
| T0.2 安装闭环 | `pytest tests/integration/test_install.py` 全绿；`launch.py enums` exit 0 | `tests/integration/test_install.py` |
| T0.3 DSH 实机 | `collect_host_evidence.py` → `independent_of_source_checkout=true`；doctor 列出双入口 | `evidence/T0.3/host-install-evidence.json` |
| T0.4 doctor | `doctor` 退出 0/11 且输出 `host_capability`；双入口 READY | doctor JSON |
| T0.5 许可/离线 | `pip install --no-index --find-links dist/wheels -r requirements.txt` 成功；`THIRD_PARTY_NOTICES.md` 完整 | 离线 venv 日志（本机验证） |
| T0.6 仓库独立 | 安装后从任意 cwd 运行 `launch.py doctor` exit 0；suite-link/record 无开发仓绝对路径 | `host-install-evidence.json.repo_independence` |

Stage 0 Exit 规则：T0.1–T0.6 全部 DONE；未决 MINOR 必须登记，不得隐藏。

## Stage 1 — 规则、靶场与检测器

| 项 | 门 | 证据 |
|---|---|---|
| T1.0 规则冻结 | `rule_id` 注册表 Schema 校验通过；Rule ID 无重复 | `knowledge/rules/*` + 测试 |
| T1.1 GT 靶场 | 每条样本含预期状态、Rule ID、环境、截图；独立标注记录 | `tests/fixtures/ground-truth/` |
| T1.2 token linter | 正反样本零误判硬 FAIL；分级与豁免审计 | `pytest tests/detectors` |
| T1.3 flow validator | flows Schema 校验；能力差异输出 WARN/FAIL | `qa-report.json` |
| T1.4 geometry probe | 合法负样本零硬 FAIL；Offscreen 标 SIMULATED | probe 日志 |
| T1.5 runner 完整化 | finalize 从真实 tool-log 重算；伪造 PASS 被拒 | `finalize` 负向测试 |
| T1.6 攻击测试 | 假 PASS/删证据/跨层/Mock 全部拒绝 | 攻击用例日志 |
| T1.7 混淆矩阵/CI | TP/FP/TN/FN 输出；Windows runner 绿 | `confusion-matrix.json`、CI artifacts |

## Stage 2 — 设计系统与原型

| 项 | 门 | 证据 |
|---|---|---|
| T2.1 发现 | 页面/路由/能力三源比对报告 | discovery 报告 |
| T2.2 flows | 状态派生 + 可测路径 | `flows.json` |
| T2.3 tokens | DTCG→CSS/Tailwind/PySide6 编译；暗色/CJK | `tokens.json`、编译产物 |
| T2.4 知识库 | 来源/许可/checksum 可核查 | `knowledge/index.json` |
| T2.5 design-only/prototype | ≥2 方案 + 取舍证据 | 原型对比报告 |
| T2.6 存量系统 | 采纳/漂移检查/冲突优先级 | drift 报告 |

## Stage 3 — 受控实现与原生验证

| 项 | 门 | 证据 |
|---|---|---|
| T3.1 受控改造 | 写范围 ⊆ 授权；可回退 | `diff.patch` + G4 |
| T3.2 Tauri | 非 Mock Rust IPC 场景通过 | WDIO 日志 |
| T3.3 PySide6 | 100/125/150% DPI、CJK、焦点 | 截图/几何探针 |
| T3.4 OS 集成 | 隔离环境；UIA 优先；物理输入默认禁用 | `desktop_isolation_proof` |
| T3.5 证据生命周期 | 删 Vault 后不得重签 PASS；脱敏扫描 | 证据生命周期测试 |
| T3.6 独立隔离 | 自报 session 不能签发独立 PASS | `review-attestation` |

## Stage 4 — 宿主与兼容

| 项 | 门 | 证据 |
|---|---|---|
| T4.1 DSH 兼容 | 双入口/脚本/GUI/MCP/恢复逐项记录 | `host-capability.json` |
| T4.2 其他 Agent | 未测标 UNVERIFIED，不推定通过 | 兼容矩阵 |
| T4.3 被动外部调用 | 不改调用方分支/证据；无外部系统时核心正常 | 契约测试 |
| T4.4 退化路径 | 缺 Node/GUI/旧宿主/离线/软链均返回稳定 ReasonCode | 退化测试 |

## Stage 5 — 试点与交付

| 项 | 门 | 证据 |
|---|---|---|
| T5.1 真实工作台（副本） | 冻结导入→浏览→编辑→异常→保存/导出 | 任务记录 |
| T5.2 前后对照 | 成功任务/步骤/恢复/快捷键/布局缺陷 | 对照报告 |
| T5.3 数据安全 | 真实数据写入 0 次；源 hash 一致；回滚演练 | hash/回滚记录 |
| T5.4 独立复审 | 冻结版本复验；未覆盖项明示 | `review-attestation` |
| T5.5 交付 | `dist/` ZIP + 手册 + 兼容矩阵 + 证据索引 + `FINAL_DELIVERY_REPORT.md` | 交付包 |

## 统一退出码

| 码 | 含义 |
|---:|---|
| 0 | PASS/COMPLETE |
| 2 | 用法错误 |
| 10 | Schema/语义无效 |
| 11 | PARTIAL/INCOMPLETE |
| 12 | FAILED |
| 13 | BLOCKED |
| 3–7 | 安装/启动器专用（见 `docs/CLI.md`） |
