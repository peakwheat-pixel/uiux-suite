# Universal UI/UX Engineering Suite — V1.3.3 FINAL

面向 DSH（DeepSeek Harness）的 UI/UX 工程能力包：双 Skill 入口、7 模式契约、G0–G6 门禁、原生/模拟证据分层、L4 设计评审与可复核的安装/验收链路。

> **版本：1.3.3 FINAL**
> **任务：61 / 61 DONE**
> **G6：PASS（ISOLATED_REVIEW_VERIFIED）**
> **外部独立审查：INDEPENDENCE_UNVERIFIED**
> **UI 撤销按钮端到端测试：未通过（IPC/domain 撤销 PASS；Workbench overlay 本次测量 0×0，按钮点击不可达）**

## 快速开始

```powershell
# 1. 解压发行包
Expand-Archive dist\uiux-suite-1.3.3-win64.zip -DestinationPath C:\tools
cd C:\tools\uiux-suite-1.3.3

# 2. 项目级安装（推荐先试项目级；也可 --scope user）
python scripts\setup_skill.py --host dsh install --scope project --project C:\my-project --version 1.3.3

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
| `contracts/` | 26 份 JSON Schema、枚举字典、Mode×Gate 机器策略 |
| `runtime/uiux_engine/` | 契约、策略、Gate/finalize、证据、CLI |
| `skills/uiux`、`skills/uiux-verify` | 双 Skill 入口与启动器 |
| `scripts/` | 安装/doctor/卸载/证据/任务登记 |
| `tests/` | 460 项契约、Gate、安装与宿主测试 |
| `docs/` | 规范、任务计划、验收与限制 |
| `dist/` | 本地发行包与校验和（不入 Git） |

## 验证

```powershell
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q        # 460 passed
.\.venv\Scripts\python.exe scripts\run_attack_suite.py
.\.venv\Scripts\python.exe scripts\run_stage1_suite.py
```

## 真实限制（不得写成 PASS）

- G6 为隔离审查等级 PASS；没有 host_verified/external 外部独立审查。
- UI 撤销按钮端到端测试未通过；撤销仅通过真实 IPC/domain revision restore + 单测验证。
- 导出使用产品 acceptance bridge 的 mock/local providers 与 2 页合成 fixture；ZIP 非 Tauri 对话框点击。
- T4.2：DSH、Antigravity 已实测；Codex 发现/读取通过但 runtime 被其 sandbox helper 阻断；Claude/ZCode/Qoder 未验证。
- 已知 P2/P3：CJK 标题 mojibake、导入后计数需刷新、无 AT 运行时验证。

## 发行信息

- 包：`dist/uiux-suite-1.3.3-win64.zip`
- SHA256：见 `dist/SHA256SUMS.txt`
- 校验/安装验证：`evidence/T5.5/release-verification.json`
- G6：`evidence/T5.4/audit/task-result.json`
