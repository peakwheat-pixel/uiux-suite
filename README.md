# Universal UI/UX Engineering Suite — V1.3.4

面向 DSH（DeepSeek Harness）的 UI/UX 工程能力包：双 Skill 入口、7 模式契约、G0–G6 门禁、原生/模拟证据分层、L4 设计评审与可复核的安装/验收链路。

> **版本：1.3.4（开发中 — Phase A，rc1 构建前）**
> **兼容：V1.3.3 契约与历史证据保持只读可读**
> **本轮新增：双契约版本分派、Coverage disposition、交付六维度、跨版本升级/回滚回归**

## V1.3.4 增量

| 项 | 说明 |
|---|---|
| 双契约 | 26 份 v1.3.4 Schema 与 v1.3.3 并存；版本按 `schema_version` 分派，缺版本/未知版本/混合版本 fail-closed |
| Coverage | `coverage-matrix.record` 新增可选 `disposition` / `scope_ref` / `risk_ref`；`test_state` 五枚举不变 |
| 交付维度 | `task-result` 新增可选 `delivery_dimensions`（执行/范围/证据/风险/独立性/交付）与 `scope_summary` |
| 聚合规则 | 环境类不可达可从 runtime aggregate 排除但保留原因码；审计遗漏/产品失败仍强制 NONE |
| 迁移 | 见 `docs/MIGRATION_V1.3.3_TO_V1.3.4.md`；发行 Gate 见 `docs/V1.3.4_GATE_MAP.md` |

## 快速开始

```powershell
# 1. 解压发行包
Expand-Archive dist\uiux-suite-1.3.4-win64.zip -DestinationPath C:\tools
cd C:\tools\uiux-suite-1.3.4

# 2. 项目级安装（推荐先试项目级；也可 --scope user）
python scripts\setup_skill.py --host dsh install --scope project --project C:\my-project --version 1.3.4

# 3. doctor
python scripts\setup_skill.py --host dsh doctor --scope project --project C:\my-project

# 4. 双入口
python C:\my-project\.agents\skills\uiux\scripts\launch.py enums
python C:\my-project\.agents\skills\uiux-verify\scripts\launch.py enums
```

详细安装、CLI、规则与兼容性见 `docs/INSTALL.md`、`docs/CLI.md`、`docs/RULES.md`、`docs/COMPATIBILITY.md`。

## 双 Skill 调用提示词

```text
# UI/UX 主入口
使用 uiux 技能理解这个项目/界面，生成 flows 与设计系统，
完成指定的 UI/UX 改造，并运行真实测试与证据记录。
不要签发独立验收。

# 独立验证入口
使用 uiux-verify 技能对冻结版本做只读复核：
重跑关键测试、检查 flows/设计/证据缺口、
按实际独立等级签发验证结论。不要修改生产源码。
```

## 目录

| 路径 | 内容 |
|---|---|
| `contracts/` | v1.3.3/v1.3.4 双套 JSON Schema、枚举字典、Mode×Gate 机器策略 |
| `runtime/uiux_engine/` | 契约、策略、Gate/finalize、证据、CLI（版本分派） |
| `skills/uiux`、`skills/uiux-verify` | 双 Skill 入口与启动器 |
| `scripts/` | 安装/doctor/卸载/证据/任务登记、契约生成器 |
| `tests/` | 473 项契约、版本分派、Gate、安装与宿主测试 |
| `docs/` | 规范、任务计划、迁移矩阵、验收与限制 |
| `dist/` | 本地发行包与校验和（不入 Git） |

## 验证

```powershell
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q        # 473 passed (Phase A)
.\.venv\Scripts\python.exe scripts\run_attack_suite.py
.\.venv\Scripts\python.exe scripts\run_stage1_suite.py
```

## 继承自 V1.3.3 的真实限制（不得写成 PASS）

- 没有 host_verified/external 外部独立审查；最高隔离等级为 `ISOLATED_SESSION`。
- UI 撤销按钮端到端测试未通过；撤销仅通过真实 IPC/domain revision restore + 单测验证。
- 导出使用产品 acceptance bridge 的 mock/local providers 与 2 页合成 fixture；ZIP 非 Tauri 对话框点击。
- T4.2：DSH、Antigravity 已实测；Codex 发现/读取通过但 runtime 被其 sandbox helper 阻断；Claude/ZCode/Qoder 未验证。
- 已知 P2/P3：CJK 标题 mojibake、导入后计数需刷新、无 AT 运行时验证。

## 发行信息

- 包：`dist/uiux-suite-1.3.4-win64.zip`（Phase B 正式发行时生成）
- SHA256：见 `dist/SHA256SUMS.txt`
- 本版本验收结论：见 V1.3.4 最终验收报告（Phase B/C 完成后）
