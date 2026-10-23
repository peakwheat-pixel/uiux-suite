# Universal UI/UX Engineering Skill Suite V1.3.2 — 完整实施方案

> **状态：设计基线候选 / IMPLEMENTATION PLAN（非已实现或已验收产品）**  
> 日期：2026-10-23  
> 目标用户：以 DSH 为主要 Agent、同时使用 Codex / Claude Code / ZCode / Antigravity / Qoder 的 Windows 软件开发者  
> 来源：V1.2 方案、Gemini V1.3 审查、V1.3.1 最终架构规范、V1.3.1 独立复审中的 V132-01～V132-12。  
> **实施红线：DSH First；Agent Agnostic；Standalone by Default；Orchestrator Caller-Only；Evidence Honesty；User Data Safety。**

## 0. 执行摘要与裁决

### 0.1 建设目标

建设一套可复用的 UI/UX 工程 Skill，使 Agent 能够：**理解现有软件 → 确定用户任务 → 审查操作流程（UX）→ 建立设计系统（UI）→ 生成可验证原型 → 控制代码改造 → 实际运行测试 → 独立复审与交付**。支持 Windows Tauri（React/TS）、PySide6/Qt；Web 作为基础，WPF/WinForms 为第二梯队扩展。

**不是**仅自动生成 CSS，不是单纯 Lint 工具，也不是依赖多 Agent 编排器运行的子系统。质量由四层组成：①确定性静态安全与规范门禁；②场景化启发式 UX/UI 审查；③Mock/Offscreen/Native/OS 分级真实运行；④具备证据的独立专业设计评审。自动化只负责可客观检验的下限，设计评价决定体验上限。

### 0.2 V1.3.2 核心决策

| 编号 | 决策 | 理由 |
|---|---|---|
| ADR-01 | 两个顶层 Skill：`uiux`（设计/改造/自测）和 `uiux-verify`（只读验证/独立评审） | DSH Skill 发现、上下文控制与职责边界更明确；不假定两个名称本身构成独立会话 |
| ADR-02 | 一个版本化发行运行时 + 两个薄 Skill 启动器 | 安装、移动、全局/项目级使用时均可解析共享脚本，避免路径断裂 |
| ADR-03 | 用 Schema + CLI Runner 控制可验证 Gate，模型不能自行赋值 `PASS` | 阻止文档式假验收；需说明同一信任域的防篡改边界 |
| ADR-04 | UX 能力由「源代码发现/运行发现/Agent 任务契约」交叉确认 | 避免模型漏报 `async_load`、`destructive`、`user_mutation` 绕过状态检查 |
| ADR-05 | 原始证据留本地私密 Vault，提交时仅允许经过脱敏的摘要 | 用户项目可能含私人路径、图片、商业数据 |
| ADR-06 | 运行证据等级与 Reviewer 独立性等级分开 | Mock 不等于原生；同会话验证不等于独立审查 |
| ADR-07 | Agent 仅接受外部编排调用，绝不主动依赖/启动 `multi-agent-project-orchestrator` | 兼容已有工作流，同时保持完整的单 Agent 独立能力 |
| ADR-08 | Stage 0/1 先做真实安装、正反样本与探针；再做 Token、原型和生产改造 | 先验证真实工程价值，再扩大能力边界 |

### 0.3 可交付结果范围

- 最终发行包：两个 Skill、阶段参考手册、离线知识库、契约 Schema、执行器、检查器、Tauri/Qt/Windows 测试适配器、安装与卸载脚本、许可证清单、示例/靶场与操作手册。
- 每个目标项目：模式化任务请求、功能/界面基线、问题台账、任务流契约、设计 Token、可选原型、改动 diff、分级测试和独立审查报告。
- **非承诺**：无额外宿主权限、无真实 Windows 会话、或缺少原生驱动时，不承诺全自动真机验证；不以经验数值宣称“改善 40%/60%”。

---

## 1. 范围、使用者与非目标

### 1.1 首期支持的任务模式

| mode | 作用 | 允许修改生产源码 | 交付物层级 |
|---|---|---:|---|
| `audit` | 只读审查已有软件，输出 UI/UX 缺陷与建议 | 否 | `report-only` |
| `design-only` | 设计用户流程、信息架构、Token 与方案 | 否 | `design-spec` |
| `prototype` | 在隔离目录生成可交互原型并测试 | 否（只写原型沙箱） | `interactive-prototype` |
| `new-build` | 新软件/新模块按先设计后开发实施 | 是（获授权范围） | `production-code` |
| `redesign` | 已有软件模块的完整 UI/UX 重构 | 是（获授权范围） | `production-code` |
| `targeted-fix` | 修改某个页面/交互/控件缺陷 | 是（仅限目标） | `production-code` |
| `verify` | 对冻结版本独立执行 QA/Review | 否 | `verification-report` |

### 1.2 非目标及其边界

- 不管理项目的整体产品路线图、非 UI/UX 的业务需求和外部 Agent 的开发排期。
- 不自行启动 `multi-agent-project-orchestrator`；该工具若存在，只能作为外部调用方。
- 不承诺单靠自动脚本评判“高级感”“用户心智模型”或创意审美；专业设计评审须保留证据、分歧与适用场景。
- 不在无许可、无真实测试权限的条件下进行原生 Windows UI 改造或 OS 键鼠控制。
- 不以缩短点击次数为唯一 UX 指标；正确性、可发现性与错误恢复同等重要。

### 1.3 设计标准

默认面向 Windows 长时工作台，强调：操作区域稳定、密度可调、左导航/中工作区/右属性区等布局按任务选型、键鼠并行、合理快捷键与撤销、导入/处理/导出阶段明确、中文/英文混排与 DPI、明确危险操作边界。不得照搬消费级移动端“一页一个 CTA”的规则。

---

## 2. 核心架构

```text
使用者 / 调用方
  ├─ DSH（优先） ─────────────────────────────────────────────────┐
  ├─ Codex / Claude / ZCode / Antigravity / Qoder（逐项验证） ─────┤
  └─ multi-agent-project-orchestrator（可选、仅外部调用） ────────┤
                                                                  ▼
                Agent Skills 入口（两个顶层 SKILL.md）
               ┌───────────────┐    ┌─────────────────────┐
               │ uiux          │    │ uiux-verify         │
               │ 设计/改造/自测│    │ 只读/验证/审查      │
               └──────┬────────┘    └─────────┬───────────┘
                      └──────────────┬──────────┘
                                     ▼
                versioned uiux-engine Runtime / CLI
          请求校验 | 阶段状态机 | Gate 计算 | 资产寻址 | 审计日志
                                     │
               ┌─────────────────────┼──────────────────────┐
               ▼                     ▼                      ▼
         UX/UI 设计层           确定性检测层             GUI 测试层
   功能图/用户路径/原型    Flow Validator / AST Lint     Playwright
   Token/设计原则/评审     Layout & Contrast Probe       WebdriverIO Tauri
                                                       pytest-qt/QTest/UIA
                                     │
                                     ▼
                 `.uiux/` 项目级隔离证据 + 标准 TaskResult
```

### 2.1 双 Skill 的职责

**`uiux`**：预检、发现、建立基线、提出问题、设计 IA/Flows/Token、原型、受控改造、自测；根据调用模式决定止步阶段；不能签发“独立 Reviewer 通过”。

**`uiux-verify`**：对冻结的源码版本/设计交付物进行只读检查、重复运行测试、判断覆盖与 UX/UI 质量、报告证据缺口、签发有证据支持的验证结论；不修改生产业务源码，不替开发者修复缺陷。

两者的 `SKILL.md` 应保持短小，深层知识文件放在 `references/` 按阶段阅读。**Gate 的强制执行应由本地可信 CLI 而不是提示词承担**。DSH 的 Skill 可见性字段属于宿主特性，核心文件只使用 Agent Skills 的通用 frontmatter，宿主扩展另设适配选项。

### 2.2 四层质量体系

| 层 | 内容 | 可签发的证据 |
|---|---|---|
| L1 确定性 | Schema 校验、代码规范、测试锚点存在、风险守卫、许可证与目录边界 | 文件/行号、规则 ID、退出码、日志哈希 |
| L2 启发式 | 信息密度、导航一致性、主次操作、无意义装饰、复杂背景、可发现性 | 附上下文的 `WARNING`、截图、建议及置信度 |
| L3 运行态 | 任务路径、状态转换、文本裁切、窗口缩放、真实 IPC、原生对话框 | 分环境的测试命令、截图、trace、覆盖矩阵 |
| L4 设计/体验评审 | 工作流效率、学习成本、用户心智模型、视觉层级、专业审美 | 任务证据、前后对照、明确理由和独立复审结论 |

任何 L1～L3 全绿都**不能**自动替代 L4；L4 主观评审也不能覆盖 L1 硬失败。

---

## 3. 发行包与跨项目安装（V132-01）

### 3.1 唯一源码仓与发行结构

```text
universal-uiux-engineering/                # 开发仓库
  skills/
    uiux/SKILL.md
    uiux/references/{discover,flow,design,prototype,build}.md
    uiux-verify/SKILL.md
    uiux-verify/references/{test,expert-review}.md
  runtime/uiux_engine/
    cli.py                                 # doctor/prepare/run/gate/finalize/verify
    gates.py                               # Mode × Gate & policy
    assets.py                              # 安装根解析与版本校验
    contracts.py                           # jsonschema 检验
    evidence.py                            # 分级证据与脱敏
    git_policy.py                          # caller-managed / standalone
    safety.py                              # 沙箱与 write_scope
    discovery.py                           # 代码/行为能力交叉发现
    qa_reviewer.py                         # 验证角色与审查来源记录
  tools/
    style_token_linter.py
    ux_flow_validator.py
    layout_geometry_probe.py
    token_compiler.py
    license_audit.py
    probes/
      playwright_dom_probe.mjs
      tauri_wdio_runner.mjs
      pyside6_qt_probe.py
      win_uia_helper.py
  knowledge/                               # 版本锁定、许可证清楚的离线资源
  contracts/
    task-request.v1.3.2.schema.json
    task-result.v1.3.2.schema.json
    flows.v1.3.2.schema.json
    gate-results.v1.3.2.schema.json
    evidence-manifest.v1.3.2.schema.json
    tokens.dtcg.schema.json
    host-capability.v1.3.2.schema.json
  fixtures/{web,tauri,qt}/{positive,negative}/
  tests/{unit,integration,e2e,security,compat}/
  packaging/build_release.py
  scripts/setup_skill.py
  scripts/uninstall_skill.py
  THIRD_PARTY_NOTICES.md
  RELEASE_MANIFEST.json                     # 版本/文件哈希/兼容性声明
  docs/{INSTALL,QUICKSTART,CLI,UX_RUBRIC,SAFETY,RELEASE}.md
```

### 3.2 安装时的物理布局

用户级安装（推荐）及项目级安装都采用**同一版本化发行根 + 两个小型 Skill 启动器**：

```text
%USERPROFILE%\.agents\
  uiux-suite\versions\1.3.2\            # 发行根：runtime/tools/contracts/knowledge
  skills\
    uiux\SKILL.md
    uiux\scripts\launch.py               # 薄启动器（小文件，随 Skill 安装）
    uiux\suite-link.json                  # 版本、相对或绝对发行根定位
    uiux\references\*.md                # 轻量阶段文档，随入口同步安装
    uiux-verify\SKILL.md
    uiux-verify\scripts\launch.py
    uiux-verify\suite-link.json
    uiux-verify\references\*.md         # 验证规则，随入口同步安装
```

项目级则在 `<project>/.agents/uiux-suite/versions/1.3.2` 和 `<project>/.agents/skills/{uiux,uiux-verify}` 安装；也可以经用户确认选用 DSH 专属 `.dsh/skills`，但不能静默生成遮蔽同名 Skill。**每个 Skill 启动器只随包复制 `SKILL.md`、轻量 `references/`、`launch.py` 和 `suite-link.json`**；共用的工具、Schema、完整知识库和业务逻辑仍仅维护在版本化发行根。按需读取的 `references/` 必须在安装后保持相对于 `SKILL.md` 的有效路径。

`launch.py`：以自身 `__file__` 所在目录读取 `suite-link.json`；优先解析安装器生成的相对路径，用户级跨盘时采用绝对路径；对最终 `suite_root` 执行 `Path.resolve()`，校验 `RELEASE_MANIFEST.json` 的期望版本及关键哈希，再运行所选 Python 虚拟环境中的 `uiux_engine.cli`。**对路径中空格、中文、UNC、盘符、软链接都使用参数数组传递，不经 shell 拼接命令**。

**重要边界**：复制单个 `SKILL.md` 并不代表完整安装；只有 `setup_skill.py` 创建的有效 `suite-link.json` + 发行根才可用。`doctor` 检查孤儿链接并明确失败原因。若配置路径移动，须运行 `repair/relink` 重建定位，不假装跨机器复制后自动可用。

### 3.3 安装器与 Doctor 设计

以下命令属于**拟开发的套件接口，不是 DSH 现成命令**：

```powershell
python scripts/setup_skill.py install --scope user --host dsh
python scripts/setup_skill.py install --scope project --project "G:\CODEX\New Manga" --host generic
python scripts/setup_skill.py doctor --scope user
python scripts/setup_skill.py repair --scope user
python scripts/uninstall_skill.py --scope user --version 1.3.2
```

- `install`：锁版本、检测同名 Skill 及优先级遮蔽、建立发行根并复制两个入口及其 `references/`、检查文件哈希；不默认覆盖用户已有同名文件。
- `doctor`：验证两个入口、从 Skill 到 Runner 的真实寻址、Python/Node/Qt/Playwright/WDIO 能力、许可与现有版本、可用 GUI 环境；以 `READY/MISSING/INCOMPATIBLE/UNVERIFIED` 报告，不下载或修改宿主配置。
- `uninstall`：只删除自身 manifest 明确登记的安装文件，保留用户生成的项目 `.uiux/` 报告与 Vault；并存版本需不破坏其他版本的入口。
- **必测恢复测试**：安装后删除开发源码仓库，在含空格、中文的全新项目里运行 `doctor` 和三个本地检测器；切换旧/新发行版本，卸载旧版本不损坏新版本。

### 3.4 Agent 兼容性认定

`.agents/skills` 的共享放置是**优先尝试路径**，不是对全部 Agent 的功能承诺。矩阵逐个记录：发现/加载、执行脚本权限、读取路径、GUI 访问、MCP、文件权限、断点恢复。未实测的 Agent 记 `UNVERIFIED`；提供复制启动指令的通用手工入口。DSH 须最先实测，其他宿主不能借 DSH 成功来推定通过。

---

## 4. 任务协议与阶段状态机

### 4.1 TaskRequest v1.3.2 样例

```json
{
  "schema_version": "1.3.2",
  "run_id": "UIUX-20261023-001",
  "mode": "redesign",
  "project_root": "G:/CODEX/New Manga",
  "target_scope": ["src/ui/workbench/**"],
  "caller": {
    "kind": "direct",
    "invoker": "dsh",
    "git_management": "standalone"
  },
  "execution_policy": {
    "read_only_source": false,
    "allow_production_data_write": false,
    "allow_os_input_simulation": false,
    "allowed_write_globs": ["src/ui/workbench/**", ".uiux/**"],
    "max_total_repair_cycles": 2,
    "require_native_for_production_complete": true
  },
  "evidence_policy": {"profile": "local_private", "retention_days": 30},
  "runtime_targets": ["SIMULATED", "NATIVE_APP"],
  "requested_outputs": ["DESIGN_SYSTEM.md", "flows.json", "qa-report.json"]
}
```

外部编排调用把 `caller.kind` 改为 `orchestrator`，`git_management` 改为 `caller_managed`，并在 `caller` 中增加由外部提供且**实测确认其含义**的 `task_id`、`role`、`base_head`、`worktree_path`、`artifact_dir`、`allowed_write_globs`。该分支下 Runner **不得建分支、改基准 HEAD、提交或清理外部 Worktree**。

权限说明：`allowed_write_globs` 是策略声明；仅当调用方通过隔离沙箱、文件 ACL 或进程级权限等方式强制执行时，才算强隔离。若 Agent 拥有不受限 Shell，Runner 不能单凭配置文件阻止 Agent 绕过；必须如实标注为流程级约束。

### 4.2 核心 UX `flows.json` 样例

```json
{
  "schema_version": "1.3.2",
  "view_id": "import-panel",
  "view_archetype": "desktop_workbench",
  "capabilities": {
    "async_load": true,
    "collection_display": true,
    "user_mutation": false,
    "long_running_task": true
  },
  "capability_evidence": [
    {"capability": "async_load", "source": "src/ui/import/ImportPanel.tsx", "discovery": "static"},
    {"capability": "long_running_task", "source": "import_progress", "discovery": "runtime"}
  ],
  "tasks": [{
    "task_id": "import-folder",
    "actor_goal": "选择本地漫画目录并导入图库",
    "entry_point": "toolbar.import",
    "steps": ["open-dialog", "select-folder", "confirm", "wait-progress", "review-result"],
    "states": ["empty", "loading", "ready", "error", "progress", "cancelled"],
    "runtime_assertions": ["import-dialog-opens", "progress-visible", "import-result-renders"],
    "destructive_operations": []
  }],
  "ui_anchors": [{"semantic_id": "import.progress", "testid": "import-progress"}]
}
```

**重要：** `capabilities` / `ui_anchors` 可作为设计和检查输入，不能被直接视为功能已实现证据。Runner 还需检查源码和运行测试能否证明其对应能力与状态确实存在。

### 4.3 TaskResult v1.3.2 必备字段

```json
{
  "schema_version": "1.3.2",
  "run_id": "UIUX-20261023-001",
  "mode": "redesign",
  "status": "PARTIAL",
  "delivery_status": "SELFTEST_VERIFIED",
  "source_revision": "<40-char-Git-commit-or-null>",
  "runtime_evidence_level": "SIMULATED",
  "review_isolation_level": "SELFTEST",
  "independent_review_status": "UNVERIFIED",
  "gates": {"G0": "PASS", "G1": "PASS", "G2": "PASS", "G3": "PASS", "G4": "PASS", "G5": "UNVERIFIED", "G6": "BLOCKED"},
  "unverified_paths": ["native-import-dialog"],
  "evidence_manifest": ".uiux/evidence/UIUX-20261023-001/manifest.json",
  "blocking_reasons": ["NATIVE_GUI_NOT_EXECUTED"]
}
```

Schema 应约束字段与枚举，并通过交叉字段验证不允许 `status=COMPLETE` 同时存在必选 `UNVERIFIED/BLOCKED/FAIL`。非 Git 项目可使用单独 `source_snapshot_digest`（目录内容哈希）代替 Git Commit，但不允许伪造 40 位 HEAD。

### 4.4 状态及证据枚举（禁止混用）

- Gate：`PASS | FAIL | WARN_REVIEW_REQUIRED | BLOCKED | UNVERIFIED | NOT_APPLICABLE`。
- Run：`COMPLETE | PARTIAL | FAILED | BLOCKED`；设计-only 完成是“范围内完成”，不能误称生产运行已验收。
- Runtime：`NONE | SIMULATED | NATIVE_APP | OS_INTEGRATION`，不同业务路径可具有不同层级。
- Review Isolation：`SELFTEST | ISOLATED_SESSION | INDEPENDENT_AGENT | UNVERIFIED`。
- Evidence：`AVAILABLE | REDACTED_ONLY | SOURCE_EVIDENCE_UNAVAILABLE | EXPIRED`。

`UNVERIFIED` 表示应测但没有可用的有效证据，`BLOCKED` 表示当前被明确的环境/权限/依赖问题阻断，`NOT_APPLICABLE` 仅适用于矩阵判为不适用的 Gate。`WARN_REVIEW_REQUIRED` 不得无审查记录直接转 `PASS`。

---

## 5. G0～G6 门禁、真实性与防绕过设计（V132-02）

### 5.1 Mode × Gate 应用矩阵

M = 必选；R = 读取/评估必选但不生成新版本；A = 条件必选；— = 不适用。

| mode | G0 环境权限 | G1 现状基线 | G2 UX/Flows | G3 Design System | G4 构建/Lint | G5 真实运行 | G6 汇总验收 |
|---|---|---|---|---|---|---|---|
| `audit` | M | M | R | R | — | M（无环境则 UNVERIFIED） | M |
| `design-only` | M | A | M | M | — | — | M（仅设计规格） |
| `prototype` | M | A | M | M | M（原型内） | M（原型层） | M |
| `new-build` | M | — | M | M | M | M（按目标运行层） | M |
| `redesign` | M | M | M | M | M | M（按目标运行层） | M |
| `targeted-fix` | M | M（目标） | A | M（复用） | M | M（目标与邻接） | M |
| `verify` | M | R | R | R | R（只读） | M（重跑） | M |

凡适用 Gate 无证据，则结果不得提升至 `PASS`。`new-build/redesign` 的 Native 是默认完整交付要求，缺环境可保留 PARTIAL，严禁强行切换为 NOT_APPLICABLE。

### 5.2 每个 Gate 的定义与准出

- **G0 Preflight**：确认项目技术栈、指定范围、外部调用方、数据副本、Git/源码快照、执行权限、运行条件、依赖清单；不得对用户真实数据执行副作用性试验。
- **G1 Baseline**：建立页面/窗口列表、任务流基线、现有截图与环境、源代码状态、合法显示尺寸及已知缺陷；截图等原始证据只能进 Vault。
- **G2 Flow Contract**：`flows.json` 通过 Schema、能力交叉发现、风险状态检查及状态转换可验证性预检；无法确认任务语义的项目列 `REVIEW_REQUIRED`。
- **G3 Design System**：Token 及排版/图标/组件规范成型；目标平台产物能编译/载入；至少记录被选中方案及被放弃方案的取舍理由。
- **G4 Controlled Build**：批准的代码范围变更、静态 Lint、构建、单元测试、危险变更回归、源代码范围核验通过；`audit/verify` 仅做只读检查。
- **G5 Runtime**：按目标技术栈执行核心真实任务和几何检查，按测试层级逐条登记；模拟层不自动升级为原生层。
- **G6 Finalize**：检查所有适用 Gate、失败/豁免、源码指纹、审查隔离状态、日志哈希与证据来源；输出状态由 CLI 计算。

### 5.3 机器签发流程

```text
Agent 提交设计/代码/测试意图
        ↓
Runner 执行工具并记录命令、exit code、输入版本、实际输出
        ↓
根据 Schema 与 Mode×Gate 计算 gate-results（生成而非人工填）
        ↓
记录 tool_version / source_fingerprint / environment / result_hash
        ↓
Runner finalize 重新读取证据、比对摘要和必选 Gate
        ↓
有效证据齐全 → 对可覆盖范围签发 COMPLETE 或 PARTIAL
无证据/已篡改/跨层冒充 → 非零退出码 + 对应原因
```

**关于“签发”与防篡改的真实边界**：普通本地 JSON + SHA256 可发现意外篡改，不等同于防御拥有同等磁盘权限的恶意 Agent。高可信度 Release Gate 必须由**Agent 无法修改的独立校验器**（CI/独立只读服务/隔离 Runner）读取冻结 Commit 和完整证据后签发；如 Agent 可修改 Runner、证据、哈希与源码，则只能声明流程性自测，不能宣称具备不可绕过的安全门禁。

### 5.4 `finalize` 核心判定伪代码

```python
def finalize(request, files, trusted_policy, workspace):
    schema_validate(request)
    required = required_gates_for(request.mode, request.runtime_targets)
    assert_protected_runner_version(trusted_policy.runner_digest)
    assert_write_scope_compliance(workspace, request.execution_policy)
    assert_source_fingerprint_matches(workspace, files.source_snapshot)
    results = recompute_from_tool_logs(files, required)   # 不读取模型自填 PASS
    for gate in required:
        if gate not in results or results[gate].state in {'NOT_APPLICABLE','UNVERIFIED','BLOCKED','FAIL'}:
            return partial_or_blocked(reason=gate, results=results)
        assert_valid_evidence_hashes(results[gate].evidence)
    review = establish_review_isolation(files.review_attestation)
    return issue_scope_bounded_result(results, review)
```

`finalize` 不能保证所有设计判断自动正确；专家评审属于证据化评审，不使用脚本杜撰审美 `PASS`。

### 5.5 修复预算与停止条件

默认每次 Run 最多 2 轮批量修复（I1/I2），每轮修完应整体运行最小回归集合；不可逆副作用、越权写入、数据损坏、无法验证时立即 BLOCKED。两轮未收敛输出 `PARTIAL/FAILED` 和可恢复证据，不自动修改既有结论；支持从最后有效 Gate 恢复，不重复修改已通过的无关模块。

---

## 6. UX 真实性：从声明契约到实际行为（V132-03）

### 6.1 三路能力发现

1. **代码静态发现**：扫描路由/窗口、网络或 IPC 调用、异步状态、删除/重命名/覆盖/保存、长任务/取消、选择器、快捷键、后端文件写入。分析结果附源码位置与置信度。
2. **运行发现**：基于实际 GUI 观察任务操作路径、进度/错误/撤销/完成反馈；包括窗口截图、事件日志、实际文件系统沙箱结果。
3. **任务设计契约**：Agent 根据用户目标写 `flows.json`、`view_archetype`、`capabilities`、预期状态与测试锚点。

三路交叉：发现 `destructive` 行为却未声明，G2 进入 `WARN_REVIEW_REQUIRED` 或风险较高时 `FAIL`；声明了运行锚点但测试缺少真实状态转换，G5 FAIL。静态扫描无法确定全部语义时必须 `UNVERIFIED` 或请求证据，不可擅自宣称没有异步/风险行为。

### 6.2 按能力派生状态，而非强制固定五态

| 能力 | 常见适用状态 | 例外/补充 |
|---|---|---|
| 异步加载 | loading / ready / error / retry | 极短同步操作不用强制 skeleton |
| 集合展示 | empty / ready | 空状态应有说明或可行入口 |
| 可编辑内容 | dirty / saving / saved / conflict | 有可靠自动保存时改为保存指示及失败恢复 |
| 长时任务 | queued / running / progress / complete / failure / cancelled | 不支持取消的不可中断任务需说明限制及安全退出策略，不强行添加假取消 |
| 危险不可逆操作 | guard / confirmation 或 undo / result | 依据风险、可恢复性及现有平台模式判定 |

场景原型：`modal_form / consumer_view / data_table / desktop_workbench / canvas_editor`。多个高频工具栏按钮不是硬失败；优先根据频率、分组、位置稳定性、快捷键、工具提示来评价。

### 6.3 UX 评审量表（需证据）

至少覆盖：①目标可发现性，②任务完整度，③用户心智模型与 IA，④关键路径与重复步骤，⑤反馈/错误恢复，⑥连续任务中断恢复，⑦键盘效率，⑧视觉层级和信息密度，⑨学习成本，⑩专业场景适配。每项提供：任务/场景 ID、证据、判定与建议；主观量表为分维度说明，不将分数机械求和决定是否通过。与原始任务基线使用同素材、同机器、同窗口设置比较。

---

## 7. UI 设计系统与静态检查（V132-10）

### 7.1 Design System 产出

`DESIGN_SYSTEM.md` + DTCG `tokens.json` 为可持久化单一设计规范，定义语义颜色、排版字号/行高、中英文字体栈、空间尺度、边框/圆角、阴影、状态色、图标源、布局分栏、密度档、明暗主题；按技术栈编译为 CSS Variables/Tailwind 或 PySide6 `theme_tokens.py`/QSS。保留当前成熟项目原组件体系，禁止为了套用新库无谓重写。

### 7.2 Lint 规则分级

| 规则 | FAIL 的充分条件 | WARNING 的情况 |
|---|---|---|
| 未授权硬编码颜色 | 新增业务 UI 代码绕开 Token 且无已审核例外 | SVG 插画/图表色等需要核查具体作用 |
| Emoji 冒充功能图标 | 按钮图标槽把 Emoji 当系统功能图标 | 正文/用户内容合法使用 Emoji |
| 失去焦点可见性 | 自定义可交互控件取消原焦点样式且无替代 | hover/active 等状态弱但无法确定 |
| 动态文字裁切 | 运行实际文本计算及截图显示确定裁切 | 仅 `sizeHint` 偏大、合法 ellipsis、特殊字体 |
| 间距不规则 | **一般不设全局硬 FAIL** | 不合理魔术值且无 Token，按组件/场景评估 |
| 对比度 | WCAG 适用条件、真实背景确定且低于阈值 | 透明叠层/Canvas/背景图无法可靠计算时 UNVERIFIED |

Web 使用 AST/CSS parser（如 TS parser + PostCSS）；Qt Python 使用 `ast`，QSS 可用解析器并须验证其对 Qt 语法的覆盖。正则只能作为筛选器，不得把正则匹配宣传为 AST 证明。异常豁免需 `rule_id + target_id + reason + owner + expiry + evidence`，不能让 Agent 随便加注释绕过。

### 7.3 真实布局测量

Web：通过 DOM 实际渲染的 `getBoundingClientRect()`、`scrollWidth/clientWidth`、Computed Style 与截图；Qt：使用 `QWidget.geometry()`、字体度量、边距、换行/elide 规则、抓图。对浮层、Badge、Canvas、滚动容器、允许的 ellipsis 等排除机械误报。

检查 CJK 回退、长文本、短文本、深浅主题、100%/125%/150% DPI（Native 阶段），必要时增加 175%。**Offscreen 150% 只能作为布局相对比例测试，不能冒充真实 Windows DPI 证据**。

---

## 8. 真实 GUI 测试与 OS 安全（V132-07）

### 8.1 两个独立维度的验证等级

| 字段 | 枚举 | 含义 |
|---|---|---|
| `runtime_evidence_level` | `SIMULATED` | Mock 或 Qt Offscreen 的逻辑/布局模拟 |
| 同上 | `NATIVE_APP` | 实际应用进程、真实 WebView2/Windows Qt 窗口、被测试路径的业务交互 |
| 同上 | `OS_INTEGRATION` | 实际 Windows 文件对话框/系统菜单/跨窗口交互等 |
| `review_isolation_level` | `SELFTEST` | 同会话或开发者自测；不得称独立验收 |
| 同上 | `ISOLATED_SESSION` | 可以核验的干净会话 + 冻结代码 + 只读执行 |
| 同上 | `INDEPENDENT_AGENT` | 独立 Agent/执行环境、源码受保护、可复核的外部证据 |

这两个字段必须在每条测试用例与总体结果中独立出现，不使用含糊的 `L0~L4` 复合等级。

### 8.2 技术栈测试策略

**Web**：Playwright Test 作为确定性主引擎；Playwright MCP 可用于发现和交互探索，但不能替代可重复的测试文件。Chrome/Vite 测试只证明浏览器目标环境。

**Tauri v2（Windows）**：
- Renderer 快测：Vite/React + Mock IPC，验证 DOM、状态、组件、前端错误反馈。
- Native 应用：`@wdio/tauri-service` 驱动已编译 `.exe`，根据项目是否可修改选择嵌入式/外部驱动；审查只读时不得未经授权修改 `Cargo.toml`。具体被测 Rust IPC 命令、权限和真实测试数据操作必须记录在覆盖矩阵。
- OS 层：UIA/pywinauto 处理原生文件/目录对话框及真实系统菜单。**仅成功启动二进制，不等于已证明文件导入/保存的 Native 路径。**

**PySide6/Qt**：
- 源码可访问时优先 `pytest-qt` + `QTest` + 自研 QWidget/QGraphicsScene 探针；Offscreen 负责组件逻辑/布局快测。
- Native Windows QPA 测试真实 CJK 渲染、窗口边框/DPI、菜单/文件对话框；部分 Qt 原生对话框需专门 OS 测试。
- 黑盒 `pywinauto`/UIA 用于系统集成、无源码目标与外部交互，不取代内部断言。

**Canvas/自绘区**：提供**仅测试模式启用**的只读 scene-state bridge（逻辑 ID/视口/缩放/选中），配固定测试素材的可重复截图对照；不可把 pHash 接近视为业务操作必然正确，必须同时检查状态和输出文件。

### 8.3 核心路径覆盖矩阵

每个 `task_id` 逐条记录 `renderer_mock`、`native_app`、`os_integration` 的 `PASS/FAIL/UNVERIFIED/NOT_APPLICABLE`，并附测试命令、输入、输出、系统权限、时间、版本、日志哈希。若 `import-folder` 仅通过 Mock，Native 功能仍为 `UNVERIFIED`；如果本次路径只需要模拟验证，须通过交付模式事先定义，不能测试后降低要求。

### 8.4 OS 级输入安全

默认 `allow_os_input_simulation=false`；优先协议级 Playwright/WebDriver、Qt 内部事件、UIA 的模式方法。物理鼠标/键盘控制优先放入专用 VM/Windows Sandbox 或可证明隔离的交互桌面，且需明确授权。宿主共享桌面即使每次核对 PID/HWND 仍有 TOCTOU 竞态，不能承诺绝对零误触；必须提供紧急中断、焦点失配中止、目标进程白名单和危险组合键禁用。

---

## 9. 只读、写入边界与用户数据安全（V132-05/06）

### 9.1 写入范围策略

**只读源项目**不等于不允许生成任何文件。模式 `audit/verify` 允许在**独立指定的输出根**写报告、状态、临时测试沙箱；禁止写生产源码、真实用户数据库/素材、正式配置。优先复制测试数据到临时根并使用测试配置启动程序（测试环境变量、隔离的 `APPDATA`、cache 和数据库路径）。

- `project_read_roots`：只读的源目录/二进制/数据；尽量以只读挂载、ACL、Git Worktree 与差异哈希实现保护。
- `report_write_root`：`.uiux/` 的报告范围或用户指定的外置受控目录。
- `sandbox_write_root`：临时副本/Fixture 数据；运行结束按策略清理。
- `source_write_scope`：仅 `new-build/redesign/targeted-fix` 且经明确授权的文件模式；可包括明确登记的构建输出与临时文件，不能偷渡业务数据目录。

**强制性说明**：在不限制 AI Shell 权限的普通会话中，路径白名单属于流程约束而非操作系统强制安全机制。发布时必须清楚标注安全等级；不能以运行自检代替 OS 隔离。

### 9.2 三分区证据结构

```text
<project>/.uiux/
  config.yaml                              # 范围与隐私策略
  DESIGN_SYSTEM.md / tokens.json          # 可纳入代码评审的设计产物
  state/<run_id>/                          # 可变临时状态，gitignore
  vault/<run_id>/                          # 原始截图/日志/界面树，gitignore，默认本地私密
  evidence/<run_id>/                       # 脱敏可移交：
     request.redacted.json
     findings.json / flows.json
     gate-results.json / qa-report.json
     manifest.json / result.json
```

Vault 需设置保留期限（建议可配置默认 30 天）、敏感路径排除规则、文件权限与清理策略；不得仅凭 `.gitignore` 声称数据不会云同步/泄漏。Evidence 仅使用脱敏摘要，日志中的路径替换需避免误替换合法测试证据，脱敏后重跑敏感信息扫描。Vault 删除后 manifest 标记 `SOURCE_EVIDENCE_UNAVAILABLE` 或 `EXPIRED`，保留历史哈希但不得声称原件可复核。

### 9.3 Git 与外部编排适配

- `direct`：默认不在用户工作分支偷偷切换；在干净 Worktree 或受控分支中运行，Git 政策由用户/项目配置选择；存在未提交修改时先保存快照并对冲突提示。
- `orchestrator/caller_managed`：禁止主动操作外部的分支与提交；只读获得 `base_head`、`delivery_head`、角色和允许范围，严格遵守调用方 `write_scope`，证据按调用方要求出具。
- **证据入 Git 为可选 `orchestrator_git_strict` Profile**；必须先用已安装 Orchestrator 的真实 CLI 校验参数和隐私边界，不能只依据文件名称推断其支持。未安装 Orchestrator 时独立功能应完全正常。

---

## 10. Reviewer 独立性与正式发布门槛（V132-04）

### 10.1 分级审查

- **Selftest**：`uiux` 或相同会话执行测试；可输出 `SELFTEST_VERIFIED`，`independent_review_status=UNVERIFIED`。
- **Isolated-session review**：冻结源码内容、重新开启上下文且能得到宿主或外部流程可信审查来源证明；审查者只读执行，结果绑定 `reviewed_head`/`source_snapshot_digest`。如果只能靠模型自填 `session_id`，必须 `INDEPENDENCE_UNVERIFIED`。
- **Independent-agent review**：通过外部可信系统将 Owner 和 Reviewer 分配给不同上下文/Agent，冻结源码与审查权限；外部系统是否是 `multi-agent-project-orchestrator` 不影响通用协议的运行。

### 10.2 审查环境可核实字段

`review_origin`（host / launched_by / verified identity）、`reviewed_head`、`builder_context_ref`、`reviewer_context_ref`、`source_unchanged`、`isolation_proof_type`、`tool_digest`、`evidence_manifest_hash`。`reviewed_head` 本身只能证明审查了哪个版本，不能证明 Reviewer 独立。审核期间只允许报告/沙箱目录变化；不以整个仓库非空的 `git status` 判断源码被修改，应按源码白名单/快照对比。

### 10.3 独立验收不能作弊

任何自称独立审查却无可信审查来源、来源与 Owner 相同、审查期间源码变更、不能重跑关键测试、原始证据缺失且无替代的情况，最多输出部分验证；`INDEPENDENT_REVIEW_PASS` 只允许在符合审查隔离与适用 Gate 的前提下签发。

---

## 11. 正反靶场、量化测试与质量门槛（V132-12）

### 11.1 Fixtures 设计

每个栈至少包含以下**标注了预期结果的正/负样本**：

| 栈 | 缺陷正样本（预期被发现） | 合法负样本（预期不得硬失败） |
|---|---|---|
| React / Web / Tauri | 未授权颜色、Emoji 功能图标、异步无反馈、缺错误恢复、危险覆盖无守卫、隐藏主路径、真实文字裁切、低对比度 | 合法多工具栏、SVG 插画色、1px 边框、Badge 合法重叠、合法 Ellipsis+Tooltip、Canvas 图层、禁用按钮低对比度 |
| PySide6 / Qt | 窄按钮中文裁切、长任务无进度、错误对话框死胡同、窗口缩放截断、危险删除无确认/撤销、缺控件名称 | 自适应换行 QLabel、QSizePolicy.Expanding、固定布局内合法覆盖、QGraphicsView 画布、原生对话框调用 |

追加对抗样本：缺声明但有源码删除、声明空 testid 却没有状态行为、篡改 `gate-results.json`、伪造 Review session、自行加白名单例外、将 Mock 成绩冒充 Native、嵌入敏感路径/图片的截图。

### 11.2 指标与接受标准

- Fixture 需冻结版本、标签、截图/源码环境、Rule ID、预期 `FAIL/WARNING/UNVERIFIED`。
- 汇报 TP / FP / TN / FN、Precision / Recall / False Positive Rate / False Negative Rate，并区分高置信度硬门禁与启发式 Warning。
- Stage 1 最小验收：**冻结靶场内所有预期 `FAIL` 的阻断型种子必须被命中；冻结合法负样本零误判为硬 `FAIL`**。仅对这批 Fixture 给出结论，不对未知真实软件承诺 100% 检出。
- 后续每修复一个规则需补充新的正/负回归例；CI 必须显示每条样本的预期与实际。
- 性能预算、DPI 与响应延迟按具体任务型态设定基线，不采用所有点击 100ms 必反馈的全局绝对值；禁止把浏览器 CLS 指标硬套到 Qt 窗口。

---

## 12. 详细阶段实施计划（Stage 0～Stage 5）

> **每阶段必须产出可复核实物与验收结论，禁止以文档“已修订”代替代码“已实现”。阶段内可自动安排任务与返修，但不允许跳过安全边界。**

### Stage 0｜规范冻结、安装闭环和真实宿主预检

**目标**：解决部署阻断，不依赖外部 Orchestrator 即可在 DSH 中运行最小 Runner。

- T0.1：冻结 V1.3.2 Contract、状态枚举、任务模式与目录规范，补齐 V132-01～V132-05 的测试定义。
- T0.2：制作版本化发行根、双薄启动器、`suite-link.json`、manifest 哈希校验、安装/卸载/repair。
- T0.3：DSH 实机安装，读取 `uiux` 与 `uiux-verify`，校验正常解析同一 Runner。
- T0.4：开发 `doctor`：Python/Node、Playwright、PySide6/pytest-qt、WDIO、Windows GUI 能力，逐项 READY/MISSING。
- T0.5：离线依赖和许可证清单，锁 commit、仓库许可及逐文件来源；避免直接打包未经核实的第三方数据。
- T0.6：独立运行验证；外部 Orchestrator 若本机存在才做可选 `--help` 与契约探针，**绝不作为 Stage 0 必备依赖**。

**Stage 0 Exit**：移除原开发仓仍可在 DSH 的全新测试项目运行两个入口的 doctor/最小 CLI；中文/空格路径通过；shadow/错误版本明确报错；无外部 Orchestrator 也能通过。

### Stage 1｜确定性检查器 + 正反靶场 + 基础证据签发

- T1.1：准备双栈 positive/negative Fixtures 和冻结 GT。
- T1.2：实现 `style_token_linter.py`（AST/CSS/QSS 分级规则与豁免审计）。
- T1.3：实现 `ux_flow_validator.py`（Schema + 规则 + 源代码能力差异预检）。
- T1.4：实现 `layout_geometry_probe.py` + Web DOM/Qt Offscreen 的最小真实测量。
- T1.5：实现 `uiux_runner.py`/CLI 的 G0/G1/G2/G4/G5 最小门禁、`gate-results`、manifest、`finalize` 重新计算逻辑。
- T1.6：负向攻击测试：假 PASS、删除证据、篡改源代码指纹、Mock 冒充 Native、生产数据写入拒绝。
- T1.7：CI 产生 TP/FP/TN/FN、各 Rule 的覆盖及白名单报告。

**Stage 1 Exit**：靶场缺陷可被可复现地识别；合法负样本零硬 FAIL 误报；`finalize` 对人工伪造 PASS、证据缺失及跨层冒充拒绝；输出局限声明。

### Stage 2｜UX 专业设计、Flow 真实性与 Token 编译

- T2.1：实现页面/窗口/路由/命令识别和功能地图；静态-运行-契约三源能力比对。
- T2.2：实现 `flows.json` 设计工具、场景分类、必选状态推导与可测试路径生成。
- T2.3：实现 DTCG Token Schema、CSS/Tailwind、PySide6 token/QSS 编译器；明暗主题与 CJK 文字字体测试。
- T2.4：集成可合规使用的 UI UX Pro Max / XIAS 知识数据；视觉设计参考与专业工作台 UX 量表。
- T2.5：实现 `design-only` 和 `prototype`（至少 2 种可比较方案），提供前后评审证据，不先写生产代码。
- T2.6：引入规则冲突处理：同一项目以 DESIGN_SYSTEM/Token 为唯一权威，外部设计插件仅作辅助候选。

**Stage 2 Exit**：能生成与真实功能相符的状态契约，源码漏报危险/异步能力会被发现；Web 与 Qt Token 输出可运行；两个合理原型有明确取舍；合规来源可核查。

### Stage 3｜受控实现与 Windows 真机验证

- T3.1：`redesign/targeted-fix/new-build` 在受控工作树完成小范围改造，Gate G4 保证改动和业务范围。
- T3.2：Tauri 真实 `.exe` + `@wdio/tauri-service` 验证至少一个非 Mock Rust IPC 场景；记录驱动握手和权限。
- T3.3：PySide6 Windows Native QPA 验证 100%/125%/150% DPI 中文按钮、长文本、分栏与焦点行为。
- T3.4：原生系统对话框路径选择、取消、错误处理的 OS 集成测试；优先隔离 VM/测试桌面。
- T3.5：私密 Vault、脱敏 evidence、删除 Vault 后状态退化、输出白名单和源码不变验证。
- T3.6：冻结源码并由新隔离上下文运行 `uiux-verify`，验证审查来源不足时不会错误签发独立 PASS。

**Stage 3 Exit**：在两个不同技术栈上完成最小生产改造的真机回归；明确各条路径 Native 与 OS 层覆盖；运行阶段不触碰真实用户数据；独立审查证据不靠模型自报。

### Stage 4｜跨 Agent 适配与外部被动编排联调

- T4.1：实际测试 DSH、Codex、Claude Code 的 Skill 发现、命令权限、共享工具解析与运行证据；未测宿主不宣称完整支持。
- T4.2：对 ZCode、Antigravity、Qoder 建立测试计划与通用 CLI 降级入口；按真实版本/环境验证。
- T4.3：如有真实 Orchestrator 安装，阅读其确切 CLI/manifest 契约，完成 `caller_managed`、Owner/Reviewer 分离、禁止反向调用的集成测试。
- T4.4：测试 Agent 兼容失败、缺 Node/GUI、旧版本 DSH、不正确 Skill 优先级、离线运行、软链接受限等退化路径。

**Stage 4 Exit**：各 Agent/能力状态表附实际日志；Orchestrator 在不存在时核心功能正常，在存在时可被外部调用且不破坏分支/证据治理。

### Stage 5｜复杂工作台真实任务验收与正式发行

- T5.1：以真实复杂桌面项目做可回退试点（可选漫画翻译工作台），冻结“目录导入 → 浏览 → 编辑 → 错误/取消/撤销 → 保存/导出”任务。
- T5.2：同硬件、同窗口/DPI、同输入素材，比较改版前后成功完成任务、关键步骤、错误恢复、快捷键效率、可发现性及布局缺陷。
- T5.3：进行生产路径回归、保存导出文件正确性、历史数据不损坏与回滚演练；不把减少点击数当唯一胜利标准。
- T5.4：独立上下文/Agent 对冻结版本执行复验，完成 G6；未覆盖项目以 PARTIAL/UNVERIFIED 明示。
- T5.5：生成发行包、许可证告知、安装/卸载/升级手册、示例、FAQ、兼容矩阵、验收证据及版本号。

**Stage 5 Exit（Release Gate）**：存在可从头复现的 Windows 原生核心任务测试；无未解决 P0/P1；所有发布必选 Gate 有真实有效证据；危险副作用和数据丢失为零；安装/卸载/回滚可复现；兼容范围只声明实测范围。

---

## 13. 工作分解、优先级与依赖 DAG

```text
T0.1 Schema/Policy Freeze
       ├──> T0.2 Package & Launcher ──> T0.3 DSH Doctor ───┐
       ├──> T0.5 License Lock ───────────────────────────────┤
       └──> T1.1 Fixtures ──> T1.2 Lint ─────────────────────┤
                         ├──> T1.3 Flow Validator ──────────┤
                         └──> T1.4 Geometry Probe ──────────┤
                                                              ▼
                         T1.5 Gate/Evidence Engine ──> T1.6 Adversarial
                                                              │
                                                              ▼
                         T2.1 Discovery / T2.2 UX Flows / T2.3 Token
                                                              │
                                                              ▼
                         T2.5 Prototypes ──> T3.1 Controlled Build
                                                              │
                                                 ┌────────────┴──────────┐
                                                 ▼                       ▼
                                           T3.2 Tauri Native       T3.3 Qt Native
                                                 └────────────┬──────────┘
                                                              ▼
                           T3.4 OS / T3.5 Privacy / T3.6 Independent Review
                                                              │
                                                              ▼
                                 T4 Host Compatibility / Optional Orchestrator
                                                              │
                                                              ▼
                                        T5 Real Workbench / Release Gate
```

建议开发纪律：各阶段不按时间保证完成，而按 Exit Criteria 发放下一阶段准入；发现重大缺陷可回滚至最近稳定 Gate；依赖不全可执行其他独立 Ready 任务，但不以跳过阻断项宣称 Release。

---

## 14. 已发现风险与处理

| 风险 ID | 风险 | 优先处理 |
|---|---|---|
| RISK-01 | Agent 可使用无限制 Shell 绕过 Runner | 建立独立信任边界，CI/只读容器或外部校验；不作无条件安全承诺 |
| RISK-02 | 安装目录与共享资产错位 | 版本化发行根、两入口启动器、doctor、删除源码仓回归 |
| RISK-03 | Qt/Tauri GUI 自动化运行不稳定 | 分级引擎、固定测试数据和 DPI、Native 真实复验，保留 UNVERIFIED |
| RISK-04 | 几何探针误报、规则过于机械 | 正反 Fixture、场景化 Warning、控件 ID/证据化豁免 |
| RISK-05 | UX 评审变成纯主观文本 | 真实任务流、原型对比与前后实验，独立审查记录 |
| RISK-06 | 真实业务数据被导入、删除或覆盖 | 测试沙箱 + 数据副本 + 禁止生产写入 + 退出后检查 |
| RISK-07 | 许可证、远程知识库漂移 | 锁 SHA/许可证、离线资源、独立法务校验 |
| RISK-08 | Orchestrator 深度绑定导致独立失效 | 单向被调用接口，未安装时 direct 模式持续回归 |
| RISK-09 | 跨 Agent 宣称超过实际测试范围 | 发布级兼容矩阵，严格 UNVERIFIED |
| RISK-10 | 证据泄密/体积膨胀/过期 | Vault、脱敏摘要、保留期限、清理后降级标记 |
| RISK-11 | “新会话”无法证明 Reviewer 独立 | 宿主可信来源 + 冻结提交 + 只读执行；缺证明则标 UNVERIFIED |
| RISK-12 | Stage 0～5 过度工程化 | Stage 1 先验证有意义的检测价值，达到 Gate 再增加工具 |

---

## 15. V132-01～V132-12 修改闭合矩阵

| 复审问题 | V1.3.2 处理条款 | 最小验收与阶段 |
|---|---|---|
| V132-01 路径/安装 | §3 | 删除开发仓后双 Skill 可运行，Stage 0 |
| V132-02 Gate 可伪造 | §5 | 假 PASS、篡改证据不能 finalize，Stage 1 |
| V132-03 UX 漏报能力 | §6 | 源码异步/删除与契约不符报警，Stage 2 |
| V132-04 Reviewer 不独立 | §10 | 自报 ID 无法签发独立 PASS，Stage 3 |
| V132-05 只读与数据安全 | §9 | 源码/真实数据前后哈希不变，Stage 3 |
| V132-06 Vault 保全 | §9.2 | 脱敏、保留期限及证据失效语义，Stage 3 |
| V132-07 Native IPC 覆盖 | §8.3 | 启动成功≠文件导入 PASS，Stage 3 |
| V132-08 UX 专业性 | §6.3、§12 Stage 5 | 全链路真实任务对比与专家评审，Stage 5 |
| V132-09 Agent 兼容 | §3.4、§12 Stage 4 | 宿主逐项实测，Stage 4 |
| V132-10 静态规则误报 | §7、§11 | 合法负样本无硬 FAIL，Stage 1 |
| V132-11 枚举混用 | §4.4、§8.1 | Schema 拒绝旧/混合枚举，Stage 0～1 |
| V132-12 探针覆盖指标 | §11 | 冻结 GT + 混淆矩阵，Stage 1 |

---

## 16. 发布标准、交付包与使用指令

### 16.1 正式 Release 必交付

1. 可安装、可卸载、可修复的 DSH 优先双 Skill 包和版本化核心运行时。
2. `README`、快速上手、跨 Agent 兼容矩阵和故障处理说明。
3. 7 模式任务契约与完整 G0～G6 验收引擎。
4. 三大检测器和 Web/Tauri/Qt 运行探针。
5. Token 与设计系统生成及受控改造流程。
6. Stage 1 冻结 Fixture 数据集、测试结果与误报/漏报统计。
7. Windows Native 及独立 Reviewer 验收记录。
8. 许可证/NOTICE、隐私保护、Vault 管理、证据 manifest 和回滚说明。

### 16.2 DSH 使用示例（安装后预期，不代表当前已存在命令）

```text
/uiux 对当前项目进行只读 UI/UX 审查。先梳理界面与真实任务流，
以运行截图与实际操作为依据，输出问题分级、证据与优化方案，不修改源码。

/uiux 针对导入流程进行完整 UX 优化：先冻结基线，设计任务状态和界面方案，
再受控改造并执行 Mock + Windows Native 交互验证；不触碰真实用户数据。

/uiux-verify 对当前冻结源码版本进行独立复核：只读源码、运行隔离测试，
检查真实工作流、视觉一致性、业务回归与 Gate 证据；如果没有独立会话证明，
明确将结果标为 SELFTEST 或 INDEPENDENCE_UNVERIFIED，不虚报独立通过。
```

### 16.3 给 DSH 的首轮实施启动指令

```text
项目目标：实现 Universal UI/UX Engineering Skill Suite V1.3.2。
请先完整阅读《V1.3.2 完整实施方案》，从 Stage 0 开始实施；
DSH 为首个实测宿主，后续支持其他 Agent；不得主动调用
multi-agent-project-orchestrator，但允许它作为外部调用方。

本轮优先完成版本化发行包、两个可加载 Skill、共享工具寻址、doctor、
任务/门禁 Schema 和 Stage 1 正反靶场的最小可执行原型。
不得将仅有文档的模块记为已实现，不得将 Mock/Offscreen 称为 Windows Native，
不得以模型填写的 PASS 代替真实脚本验收；只读模式不得改生产源码和用户数据。
所有剩余功能按 Stage 0～5 的 Exit Criteria 自动规划推进；
不可逆/未经授权的操作与环境缺失时如实 BLOCKED。
```

---

## 17. 事实来源与尚待实测项目

### 17.1 本方案采用的外部规范与工具（已查阅公开文档；**非本地实现证明**）

- Agent Skills 官方规范：https://agentskills.io/specification — `SKILL.md`、`references/`、`scripts/` 结构和 frontmatter。
- DSH Skill 文件系统：https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.zh.md — 默认路径优先级和发现/模型调用区分。
- DSH Tool Skill：https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/tool-skill/README.md — 可见性、按需加载与模型目录。
- Tauri v2 WebDriver：https://v2.tauri.app/develop/tests/webdriver/ — `@wdio/tauri-service`、embedded/external、前端 browser 模式。
- pytest-qt：https://pytest-qt.readthedocs.io/en/latest/ — Qt 自动化测试工具。
- WCAG 2.2 文本对比度：https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- WCAG 2.2 点击目标：https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Anthropic frontend-design 许可证：https://github.com/anthropics/skills/blob/main/skills/frontend-design/LICENSE.txt （具体打包前必须锁定许可证所在 Git commit）。

### 17.2 未获证据不得记为完成

- DSH Windows 本机实际加载和两入口运行、真实工具权限及不同 DSH 版本兼容。
- 用户已安装的 `multi-agent-project-orchestrator` 各 CLI 参数、Git Blob 验证与角色文件真实细节；不得以 Gemini 口述代替实测。
- 本地 WebView2/WDIO handshake、真实 Tauri 文件导入 Native/OS 闭环。
- Windows 100/125/150% DPI 的原生真实渲染；Qt Offscreen 不能替代。
- 真实项目改造的用户体验收益、误报漏报和回归通过率。
- Codex/Claude/ZCode/Antigravity/Qoder 在用户机器上的实际兼容性。

### 17.3 当前版本裁决

**V1.3.2 设计基线：允许进入 Stage 0 与 Stage 1 开发；不意味着 Skill 已实现，更不意味着 Release Gate PASS。**

---

## 附录 A：Stage 0/1 最小验收指令清单（拟实现）

```text
1. setup_skill.py install --scope user --host dsh
2. setup_skill.py doctor --scope user
3. 进入全新带中文/空格的 Windows 测试项目，执行 uiux/verify 两入口预检
4. 删除开发源码目录，重复第 2～3 步（不得仍依赖开发目录）
5. 运行正/负 Fixtures，生成 confusion-matrix.json
6. 人为伪造 gate-results PASS、删除证据、替换源代码，finalize 应返回非零
7. 审查模式运行，校验源码与真实用户数据 hash 不变
8. 人为在 flows.json 漏声明 destructive/async，Runner 发现差异
9. 模拟层通过但原生层未跑，result.status 不得声称 Native COMPLETE
10. 在无 Orchestrator 环境执行上述全部核心能力
```

## 附录 B：实施状态台账模板

| task | 状态 | 验收依据 | 当前阻断 | 下一步 |
|---|---|---|---|---|
| T0.1 | NOT_STARTED | Schema 在真实 Runner 中可验证 | — | 构建 Schema/Policy |
| T0.2 | NOT_STARTED | 独立包安装/卸载/删除源码回归 | — | Packaging Prototype |
| T1.2 | NOT_STARTED | 靶场正负数据与实测报告 | — | 选择解析器 |
| T3.2 | NOT_STARTED | Tauri Native IPC 执行日志 | Windows 运行条件待确认 | Stage 3 环境准备 |
| T5.4 | NOT_STARTED | 冻结版本的独立复审报告 | Reviewer 环境待确认 | Stage 5 |

> 表内 `NOT_STARTED` 为方案制作时的真实状态；任务执行后应由运行器/实际证据更新，不得仅因文档完成将其修改为 `PASS`。
