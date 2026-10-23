"""Build the machine-readable task registry and render the human plan.

Usage:
    python scripts/build_task_registry.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_DIR = REPO_ROOT / "plan"
DOCS_DIR = REPO_ROOT / "docs"


def task(
    task_id: str,
    title: str,
    stage: str,
    status: str,
    acceptance: str,
    *,
    depends_on: list[str] | None = None,
    due_before: str | None = None,
    evidence: str | None = None,
    files: list[str] | None = None,
    source: str | None = None,
    note: str | None = None,
) -> dict:
    return {
        "id": task_id,
        "title": title,
        "stage": stage,
        "status": status,
        "acceptance": acceptance,
        "depends_on": depends_on or [],
        "due_before": due_before,
        "evidence": evidence,
        "files": files or [],
        "source": source,
        "note": note,
    }


TASKS: list[dict] = [
    # ---------------- Stage 0 ----------------
    task(
        "T0.1",
        "Contract Closure：Schema、枚举、Gate 引擎、覆盖矩阵、L4、证据生命周期",
        "Stage 0",
        "DONE",
        "B1–B6 机器测试全绿；B5/B6 Schema 与时点锁定；独立契约复核无未解决阻断；evidence/T0.1/contract-test-evidence.json 存在且 exit_code=0",
        evidence="evidence/T0.1/contract-test-evidence.json",
        files=["contracts/", "runtime/uiux_engine/", "tests/", "SPEC_V1.3.3.md"],
        source="B1-B6",
        note="第 1 轮 FAIL → F-01..F-16 返修；第 2 轮独立复核 PASS；R-01..R-11 已关闭；160/160、exit 0。",
    ),
    task(
        "T0.2",
        "版本化发行根、双启动器、安装/卸载/升级/回滚",
        "Stage 0",
        "DONE",
        "删除开发仓后用户级安装可运行；版本并存；升级/回滚；卸载只删登记文件；manifest 哈希校验；M1/M3/M4/M5/M6(字段)关闭",
        depends_on=["T0.1"],
        due_before="Stage 0 Exit",
        evidence="tests/integration/test_install.py",
        files=["scripts/setup_skill.py", "scripts/uninstall_skill.py", "skills/", "packaging/"],
        source="M1/M3/M4/M5",
        note="11 项集成测试；版本并存/升级/回滚/未知 Skill 不覆盖/中文空格路径均实测。",
    ),
    task(
        "T0.3",
        "DSH 实机安装与双入口发现",
        "Stage 0",
        "DONE",
        "DSH 实际发现 uiux 与 uiux-verify；doctor 输出真实 root/rank；不依赖开发仓；中文/空格用例通过（UNC 由 M5 覆盖）",
        depends_on=["T0.2", "T0.4"],
        due_before="Stage 0 Exit",
        evidence="evidence/T0.3/host-install-evidence.json",
        source="V133-01",
        note="用户级安装后 DSH 会话技能目录出现双入口；doctor 输出 rank 500；UNC/junction/长路径见 M5。",
    ),
    task(
        "T0.4",
        "doctor：能力、根目录、遮蔽、退出码与 --json",
        "Stage 0",
        "DONE",
        "READY/MISSING/INCOMPATIBLE/UNVERIFIED 逐项输出；解析 DSH_AGENTS_HOME/DSH_HOME；遮蔽列表；host-capability.json 消费",
        depends_on=["T0.1"],
        due_before="Stage 0 Exit",
        evidence="evidence/T0.3/host-install-evidence.json",
        files=["runtime/uiux_engine/cli.py", "scripts/setup_skill.py"],
        source="M2/M9/m7",
        note="doctor 随 suite 安装，仓库删除后仍可用；MCP/恢复为 UNVERIFIED（Stage 4）。",
    ),
    task(
        "T0.5",
        "许可证清单、离线依赖与版本锁定",
        "Stage 0",
        "DONE",
        "THIRD_PARTY_NOTICES.md 逐文件来源/许可；requirements.lock；离线安装路径可复现",
        depends_on=["T0.1"],
        due_before="Stage 0 Exit",
        evidence="THIRD_PARTY_NOTICES.md; requirements.lock; dist/wheels/; evidence/T0.5/offline-install-evidence.json",
        source="M4/m3",
        note="离线 venv + --no-index 实测成功；wheel 清单/SHA256/日志入 evidence；无第三方字体随包分发。",
    ),
    task(
        "T0.6",
        "独立运行验证（删除开发仓回归）",
        "Stage 0",
        "DONE",
        "删除/移动开发仓后安装实例仍可 doctor + 最小 CLI；失败原因可诊断",
        depends_on=["T0.2", "T0.3"],
        due_before="Stage 0 Exit",
        evidence="evidence/T0.3/host-install-evidence.json; tests/integration/test_install.py",
        source="V133-01",
        note="安装后从 C:\\ 运行 doctor exit 0；suite-link/record 无开发仓绝对路径；测试覆盖删源码树。",
    ),
    # ---------------- Stage 1 ----------------
    task("T1.0", "规则目录与 Rule ID 冻结", "Stage 1", "DONE", "rule_id 注册表、严重度、豁免 schema 冻结；作为 T1.1/T1.2/T1.3 共同上游", depends_on=["T0.1"], due_before="Stage 1 Exit", evidence="knowledge/rules/catalog.v1.0.json; knowledge/rules/catalog.v1.0.freeze.json; tests/unit/test_rules.py", note="20 条规则、Rule ID 唯一、冻结摘要与豁免校验已测试。"),
    task("T1.1", "双栈正反 Fixtures 与冻结 GT", "Stage 1", "DONE", "≥8 正/反样本；GT 版本与哈希冻结；误报/漏报/权限越界/跨层样本", depends_on=["T0.2"], due_before="Stage 1 Exit", evidence="tests/fixtures/ground_truth/{web,qt,annotations}; tests/fixtures/_build_fixtures.py", note="18 样本 + 混淆矩阵冻结；GT 为单 Agent 标注（independent=false），独立标注留 Stage5/Reviewer。"),
    task("T1.2", "style_token_linter（AST/CSS/QSS 分级规则）", "Stage 1", "DONE", "规则表+枚举；正反 fixtures；误报/漏报/越界/跨层拒绝", depends_on=["T1.1"], due_before="Stage 1 Exit", evidence="runtime/uiux_engine/style_linter.py; tests/unit/test_style_linter.py; knowledge/rules/catalog.v1.0.json", note="10 规则、39 用例；静态/SIMULATED，不能外推未知项目 100%。"),
    task("T1.3", "ux_flow_validator（Schema + 能力交叉发现）", "Stage 1", "DONE", "可达性/破坏性/空态/错误/加载；Schema 合法", depends_on=["T1.1"], due_before="Stage 1 Exit", evidence="runtime/uiux_engine/flow_validator.py; tests/unit/test_flow_validator.py; contracts/flows.v1.3.3.schema.json", note="14 用例、6 规则；静态推导，不替代真实运行。"),
    task("T1.4", "layout_geometry_probe（Web DOM / Qt Offscreen 真实测量）", "Stage 1", "IN_PROGRESS", "裁切/对比度/间距测量；合法负样本零硬 FAIL；Offscreen 结果标注 SIMULATED", depends_on=["T1.1"], due_before="Stage 1 Exit", evidence="runtime/uiux_engine/geometry.py; tests/unit/test_geometry.py; qa/confusion-matrix.json", note="测量 JSON 模式 DONE（55 用例、SIMULATED）；真实 Web DOM/Qt Offscreen 探针依赖 Stage 3 能力，转 T3.3。"),
    task("T1.5", "Runner/Gate 引擎完整化（G0–G5 工具日志与证据闭环）", "Stage 1", "DONE", "finalize 从真实工具日志重算；拒绝伪造 PASS；CLI 退出码稳定", depends_on=["T0.1"], due_before="Stage 1 Exit", evidence="tests/unit/test_finalize.py; tests/integration/test_attacks.py", note="Gate 重算/证据可用/覆盖/独立性/伪造拒绝均由测试覆盖。"),
    task("T1.6", "负向攻击测试（假 PASS/删证据/跨层/Mock 冒充）", "Stage 1", "DONE", "全部攻击用例被拒绝并附退出码与日志", depends_on=["T1.5"], due_before="Stage 1 Exit", evidence="tests/integration/test_attacks.py; evidence/T1.6/attack-evidence.json", source="V132-02/V132-07", note="11 项攻击全部拒绝（exit 10/11），机器证据已生成。"),
    task("T1.7", "混淆矩阵、CI 与误报/漏报报告", "Stage 1", "DONE", "TP/FP/TN/FN 输出；CI 显示每条样本预期与实际；Windows runner", depends_on=["T1.1", "T1.2", "T1.3", "T1.4"], due_before="Stage 1 Exit", evidence="qa/confusion-matrix.json; qa/stage1-report.json; .github/workflows/stage1.yml", source="M10", note="25 样本 TP38/FP0/TN8/FN0；CI workflow 已提供，实际 runner 执行归 M10。"),
    # ---------------- Stage 2 ----------------
    task("T2.1", "页面/窗口/路由识别与三源能力比对", "Stage 2", "DONE", "功能地图；源码/运行/契约差异报告", depends_on=["T1.3"], due_before="Stage 2 Exit", evidence="runtime/uiux_engine/discovery.py; tests/unit/test_discovery.py; docs/DISCOVERY.md", note="13 用例；路由/Qt/组件识别、能力证据、三源 OBSERVED/UNVERIFIED/MISSING。"),
    task("T2.2", "flows.json 设计工具与状态推导", "Stage 2", "DONE", "按能力派生状态；可测试路径生成；review required 记录", depends_on=["T1.3"], due_before="Stage 2 Exit", evidence="runtime/uiux_engine/discovery.py#flows_from_discovery; tests/unit/test_discovery.py", note="按能力派生 loading/error/retry/empty/draft/progress/saved；生成草案需人工补 guard。"),
    task("T2.3", "DTCG Token 与 CSS/Tailwind/PySide6 编译器", "Stage 2", "DONE", "明暗主题与 CJK 字体测试；Token 可编译", depends_on=["T1.2"], due_before="Stage 2 Exit", evidence="runtime/uiux_engine/token_compiler.py; tests/unit/test_token_compiler.py; runtime/uiux_engine/qt_probe.py", note="CSS/Tailwind/PySide6 三种导出已实现并接 CLI；7 用例。"),
    task("T2.4", "离线知识库消费接口与合规来源", "Stage 2", "DONE", "knowledge index schema；来源/许可/checksum 可核查；无许可则自建量表", depends_on=["T0.5"], due_before="Stage 2 Exit", source="M11", evidence="contracts/knowledge-index.v1.3.3.schema.json; knowledge/index.v1.0.json; tests/unit/test_knowledge.py", note="自建量表 + 索引/校验和/引用-only 第三方；CLI knowledge 可验证。"),
    task("T2.5", "design-only 与 prototype（≥2 方案比较）", "Stage 2", "DONE", "两套可比较原型与取舍证据；不先写生产代码", depends_on=["T2.2", "T2.3"], due_before="Stage 2 Exit", evidence="runtime/uiux_engine/options.py; runtime/uiux_engine/prototype.py; tests/unit/test_options.py; tests/unit/test_prototype.py", note="options 加权对比 + prototype 契约/HTML 检查；未验证项标 UNVERIFIED。"),
    task("T2.6", "设计系统权威与存量组件采纳/漂移检测", "Stage 2", "DONE", "brownfield 采纳流程；token drift 检查；冲突优先级", depends_on=["T2.3"], due_before="Stage 2 Exit", source="M12", evidence="runtime/uiux_engine/design_system.py; runtime/uiux_engine/brownfield.py; tests/unit/test_brownfield.py", note="drift 检查 + brownfield 采纳报告 + 可访问性冲突优先级；8 用例。"),
    # ---------------- Stage 3 ----------------
    task("T3.1", "受控改造与 G4 范围校验", "Stage 3", "DONE", "改动在 write scope 内；可回退；G4 证据完整", depends_on=["T2.5"], due_before="Stage 3 Exit", evidence="runtime/uiux_engine/modify.py; tests/unit/test_modify.py; contracts/change-plan.v1.3.3.schema.json", note="10 用例：scope/traversal/hash/回退/试运行。"),
    task("T3.2", "Tauri .exe + WDIO Native IPC 验证", "Stage 3", "IN_PROGRESS", "至少一个非 Mock Rust IPC 场景；驱动握手与权限记录", depends_on=["T3.1"], due_before="Stage 3 Exit", note="本机无 Tauri 示例/驱动，未伪造 Native IPC 证据。"),
    task("T3.3", "PySide6 Windows Native QPA 与 DPI 验证", "Stage 3", "DONE", "100/125/150% DPI、中文字体、分栏与焦点", depends_on=["T3.1"], due_before="Stage 3 Exit", evidence="runtime/uiux_engine/qt_probe.py; scripts/collect_qt_evidence.py; evidence/T3.3/qt-qpa-evidence.json", note="Windows QPA 实测（NATIVE_QPA）；100% 为当前显示器，125/150 用 QT_SCALE_FACTOR 模拟 DPR；CJK 字体/焦点策略已记录，无物理点击。"),
    task("T3.4", "OS 集成测试（原生对话框/菜单）", "Stage 3", "IN_PROGRESS", "隔离测试环境；UIA 优先；物理输入默认禁用；TOCTOU 说明", depends_on=["T3.2", "T3.3"], due_before="Stage 3 Exit", source="M6/M8", evidence="evidence/T3.4/uia-probe.json; runtime/uiux_engine/uia.py; tests/unit/test_uia.py", note="真实 Win11 Notepad（WinUI 3）UIA 控制视图只读快照已采（NATIVE_UIA，53 元素）；点击/焦点顺序、WPF/Qt/原生对话框未验证。"),
    task("T3.5", "证据生命周期、脱敏与 Vault 退化验证", "Stage 3", "DONE", "删除 Vault 后不得重新签发 PASS；脱敏后扫描；保留期策略", depends_on=["T3.1"], due_before="Stage 3 Exit", source="B6", evidence="runtime/uiux_engine/vault.py; tests/unit/test_integrity_safety.py", note="字节级哈希校验/隔离/缺失检测；删除 Vault 后不重签 PASS。"),
    task("T3.6", "独立审查隔离验证", "Stage 3", "DONE", "自报 session 不能签发独立 PASS；隔离证明与 reviewed_head 绑定", depends_on=["T3.4"], due_before="Stage 3 Exit", source="V132-04", evidence="runtime/uiux_engine/integrity.py; tests/unit/test_integrity_safety.py", note="user_attested 独立性被拒；reviewed_head 绑定与 host_verified 证据校验。"),
    # ---------------- Stage 4 ----------------
    task("T4.1", "DSH 宿主兼容实测", "Stage 4", "DONE", "两入口发现/脚本执行/GUI/MCP/断点恢复逐项记录", depends_on=["T0.3"], due_before="Stage 4 Exit", source="M2", evidence="evidence/T0.3/host-install-evidence.json; docs/COMPATIBILITY.md", note="双入口发现/启动/doctor/退出码已实测；MCP/resume 记 UNVERIFIED。"),
    task("T4.2", "其他 Agent 兼容矩阵与降级入口", "Stage 4", "IN_PROGRESS", "Codex/Claude/ZCode/Antigravity/Qoder 未测标 UNVERIFIED", depends_on=["T4.1"], due_before="Stage 4 Exit", evidence="runtime/uiux_engine/compat.py; docs/COMPATIBILITY.md", note="矩阵与 UNVERIFIED 原因已实现；其他宿主未实测。"),
    task("T4.3", "被动外部调用契约（不依赖外部编排器）", "Stage 4", "DONE", "外部 caller 传 task_id/role/artifact_dir 时不改其分支/证据治理；无外部系统时核心正常", depends_on=["T0.1"], due_before="Stage 4 Exit", source="ADR-07 修订", evidence="runtime/uiux_engine/external.py; tests/unit/test_compat.py", note="caller 校验 role/request；引擎 orchestrates=false。"),
    task("T4.4", "退化路径（缺 Node/GUI/旧宿主/离线/软链）", "Stage 4", "DONE", "每项返回稳定 ReasonCode 与可恢复建议", depends_on=["T4.1"], due_before="Stage 4 Exit", source="M9", evidence="runtime/uiux_engine/compat.py; tests/unit/test_compat.py", note="缺失项返回 PYTHON_EXE_MISSING/HOST_UNVERIFIED/LINK_MISSING。"),
    # ---------------- Stage 5 ----------------
    task("T5.1", "真实复杂工作台试点（隔离副本）", "Stage 5", "IN_PROGRESS", "冻结导入→浏览→编辑→异常→保存/导出任务；只在副本/独立 worktree 操作", depends_on=["T3.6", "T4.4"], due_before="Stage 5 Exit", evidence="evidence/T5.1/workbench-e2e-evidence.json; evidence/T5.1/workbench-static-baseline.json", note="合成参考应用（sandbox/workbench_app）E2E 9/9：导入/浏览/画布/编辑/保存/导出/撤销/异常；New Manga 仅隔离源码静态基线，应用未启动。"),
    task("T5.2", "改版前后对照测量", "Stage 5", "IN_PROGRESS", "同机同窗口同素材；成功任务/步骤/恢复/快捷键/布局缺陷记录", depends_on=["T5.1"], due_before="Stage 5 Exit", evidence="evidence/T5.1/workbench-e2e-evidence.json", note="合成参考应用 before/after 已测：字号 11→14、目标 22→38px、对比度 2.08→15.8；真实工作台前后对照未做。"),
    task("T5.3", "真实项目数据安全与回滚演练", "Stage 5", "IN_PROGRESS", "备份→失败注入→恢复验证；真实项目只读", depends_on=["T5.1"], due_before="Stage 5 Exit", evidence="tests/unit/test_modify.py; runtime/uiux_engine/modify.py", note="受控改动/回滚与合成数据演练 DONE；真实项目未执行写入。"),
    task("T5.4", "独立复审与 G6 签发", "Stage 5", "IN_PROGRESS", "冻结版本独立复验；未覆盖项 PARTIAL/UNVERIFIED 明示", depends_on=["T5.3"], due_before="Stage 5 Exit", source="B5", note="待独立 Reviewer 只读复核后签发。"),
    task("T5.5", "发行包、文档、许可证与交付报告", "Stage 5", "DONE", "dist/ 可安装 ZIP、手册、兼容矩阵、证据索引、FINAL_DELIVERY_REPORT.md", depends_on=["T5.4"], due_before="Stage 5 Exit", evidence="dist/uiux-suite-1.3.3-win64.zip; evidence/T5.5/release-verification.json; docs/RELEASE_NOTES.md", note="143 载荷 + RELEASE_MANIFEST（ZIP 共 144 项），安装/启动/doctor 实测 exit 0；交付报告随最终复核更新。"),
    # ---------------- Remediation tasks: MAJOR ----------------
    task("M1", "安装登记/升级/回滚状态契约", "Stage 0", "DONE", "install-<version>.json 登记全部安装文件；upgrade/rollback 可复现；版本并存", depends_on=["T0.1"], due_before="T0.2", evidence="tests/integration/test_install.py", source="MAJOR", note="install/upgrade/rollback/uninstall 与版本并存已实测"),
    task("M2", "DSH_HOME/AGENTS_HOME 与项目根/遮蔽检测", "Stage 0", "DONE", "解析环境变量；5 级 rank；shadowed_by；非 Git/monorepo 说明", depends_on=["T0.1"], due_before="T0.4", evidence="evidence/T0.3/host-install-evidence.json; tests/integration/test_paths.py", source="MAJOR", note="5 级 rank（含 custom 300）与遮蔽已测；monorepo 说明见 docs/INSTALL.md"),
    task("M3", "install 根分离与写根登记", "Stage 0", "DONE", "install_write_root 入 policy/schema；快照与写范围排除；只读模式不写项目", depends_on=["T0.1"], due_before="T0.2", evidence="contracts/policy.v1.3.3.schema.json; scripts/setup_skill.py", source="MAJOR", note="安装只写 <agents_home>；测试确认不触碰项目 .uiux"),
    task("M4", "Python/Node 版本锁定与依赖清单", "Stage 0", "DONE", "版本区间写入 doctor；requirements.lock/package-lock；离线包", depends_on=["T0.1"], due_before="T0.4", evidence="requirements.lock; dist/wheels/; evidence/T0.5/offline-install-evidence.json", source="MAJOR", note="Python>=3.10、Node>=20、jsonschema 4.20–4.x 由 doctor 校验；离线 wheels 实测。"),
    task("M5", "相对/绝对/UNC/junction/MAX_PATH 路径鲁棒性", "Stage 0", "DONE", "suite-link 基准固定；UNC/漫游/失效链接用例；长路径检查", depends_on=["T0.1"], due_before="T0.2", evidence="tests/integration/test_paths.py; tests/integration/test_install.py", source="MAJOR", note="中文空格、junction、>260 长路径通过；UNC 缺失路径稳定 RELEASE_ROOT_MISSING。"),
    task("M6", "OS 输入分权与桌面隔离证明", "Stage 3", "DONE", "全局物理输入默认禁止；测试通道需显式；UIA 只读/动作分权", depends_on=["T0.1"], due_before="Stage 3 Exit", evidence="runtime/uiux_engine/input_policy.py; tests/unit/test_input_build_guard.py; CLI input-policy", note="默认 DENY；隔离+显式才允许全局物理输入；UIA 动作需隔离。"),
    task("M7", "四类根权限优先级与 finalize 校验", "Stage 0", "DONE", "read/report/sandbox/install 四根入 schema 与语义校验；allowed_write_globs 单一来源；越权拒绝", depends_on=["T0.1"], due_before="T0.1", evidence="tests/unit/test_semantics.py", source="MAJOR"),
    task("M8", "不可信项目构建执行模型", "Stage 3", "DONE", "白名单执行、网络/破坏性/越界拦截", depends_on=["T0.1"], due_before="Stage 3 Exit", evidence="runtime/uiux_engine/build_guard.py; tests/unit/test_input_build_guard.py; CLI build-guard", note="白名单可执行；网络/破坏性/越界默认拒绝；10 用例。"),
    task("M9", "CLI 退出码、--json 与阶段验收命令", "Stage 0", "DONE", "退出码表写入 docs/CLI.md；doctor/finalize --json schema；每个 Stage Exit 三列化", depends_on=["T0.1"], due_before="T0.4", evidence="docs/STAGE_GATES.md; docs/CLI.md", source="MAJOR", note="validate/finalize/doctor/launch 退出码与 Stage Exit 表已落库。"),
        task("M10", "CI 骨架与 Windows runner", "Stage 1", "IN_PROGRESS", "fixtures 预期/实际、失败即红、artifact 归档；Windows runner", depends_on=["T1.1"], due_before="Stage 1 Exit", evidence="evidence/T1.0/ci-local.json; .github/workflows", note="GitHub workflow + 本地 scripts/run_ci.py 已实现并留证；真实 GitHub/gitea runner 未执行。"),
    task("M11", "第三方知识来源、许可与消费接口", "Stage 2", "DONE", "来源锁 commit/许可；knowledge index；无法锁许可则自建", depends_on=["T0.5"], due_before="Stage 2 Exit", source="MAJOR", evidence="knowledge/index.v1.0.json; contracts/knowledge-index.v1.3.3.schema.json; tests/unit/test_knowledge.py", note="自建量表 + 索引校验和；WCAG 仅引用不打包，license=unknown。"),
    task("M12", "存量设计系统采纳与 token drift", "Stage 2", "DONE", "brownfield 流程；drift 检查器；冲突优先级", depends_on=["T2.3"], due_before="Stage 2 Exit", source="MAJOR", evidence="runtime/uiux_engine/design_system.py; runtime/uiux_engine/brownfield.py; tests/unit/test_brownfield.py", note="drift + 采纳 + 冲突优先级 DONE；8 用例。"),
    task("M13", "靶场 GT 独立标注与阻断种子", "Stage 1", "IN_PROGRESS", "标注流程与分歧仲裁；阻断种子清单；零误判硬 FAIL", depends_on=["T1.0"], due_before="Stage 1 Exit", source="MAJOR", evidence="tests/fixtures/ground_truth/annotations; qa/confusion-matrix.json", note="GT 已冻结但为单 Agent 标注（independent=false）；独立标注/仲裁待 Reviewer/Stage 5。"),
    task("M14", "P0–P3 分级与可观测安全指标", "Stage 3", "DONE", "P0–P3 + qa-report schema + 指标", depends_on=["T0.1"], due_before="Stage 3 Exit", evidence="runtime/uiux_engine/safety.py; contracts/qa-report.v1.3.3.schema.json; tests/unit/test_integrity_safety.py", note="分级/指标 + qa-report Schema 已落；真实项目写入为 0 的结论仅限测试范围。"),
    task("M15", "DAG 循环与遗漏修复", "Stage 0", "DONE", "T1.0 作为共同上游；DAG 补齐 T0.4/T0.6/T1.7/T2.4/T2.6；编号修正", depends_on=[], due_before="T0.1", evidence="SPEC_V1.3.3.md §13", source="MAJOR"),
    task("M16", "附录命令一致性", "Stage 5", "TODO", "统一 python 解释器与引号；附录拆分 Stage 0/1 与 2/3", depends_on=["T5.5"], due_before="Stage 5 Exit", source="MAJOR"),
    task("M17", "非 Git 快照与回退", "Stage 0", "DONE", "dir_digest + 备份副本 + 差异哈希；回滚路径", depends_on=["T0.1"], due_before="T0.2", evidence="runtime/uiux_engine/snapshot.py; tests/unit/test_snapshot.py", source="MAJOR", note="snapshot/diff/backup 已实现；CLI 支持 --out/--backup/--diff；回滚=备份副本拷回（显式运维命令）。"),
    task("M18", "无障碍维度与 Rule ID", "Stage 1", "IN_PROGRESS", "accessible name/键盘/target size/ARIA-UIA 语义规则", depends_on=["T1.0"], due_before="Stage 1 Exit", evidence="knowledge/rules/catalog.v1.0.json; evidence/T3.4/uia-probe.json; runtime/uiux_engine/uia.py", source="MAJOR", note="A11Y-001..004 规则与静态子集 DONE；真实 Win32 UIA 只读树已采；WinUI/WPF/Qt 与动态键盘待后续。"),
    # ---------------- Remediation tasks: MINOR ----------------
    task("m1", "Prompt Injection 威胁模型", "Stage 3", "DONE", "威胁模型与缓解", depends_on=[], due_before="Stage 3 Exit", source="MINOR", evidence="docs/THREAT_MODEL.md", note="资产/威胁/缓解/残余风险；外部内容只作数据。"),
    task("m2", "同模型系统性偏差提示", "Stage 4", "DONE", "偏差与能力限制说明", depends_on=[], due_before="Stage 4 Exit", source="MINOR", evidence="docs/BIAS_AND_LIMITS.md", note="明确同模型盲区与静态检测限制。"),
    task("m3", "字体许可与 CJK 字体分发", "Stage 2", "DONE", "不捆绑字体；许可/来源说明", depends_on=[], due_before="Stage 2 Exit", source="MINOR", evidence="docs/FONT_LICENSING.md; THIRD_PARTY_NOTICES.md", note="包内无字体文件；CJK 仅使用系统字体。"),
    task("m4", "混淆矩阵契约与产物登记", "Stage 1", "DONE", "confusion-matrix schema；纳入 §3.1 目录与 CLI 输出", depends_on=["T1.7"], due_before="Stage 1 Exit", evidence="contracts/confusion-matrix.v1.3.3.schema.json; qa/confusion-matrix.json", source="MINOR", note="schema 已注册；run_stage1_suite.py 产出并校验。"),
    task("m5", "安全、兼容与迁移文档", "Stage 5", "DONE", "SECURITY/THREAT_MODEL/AGENT_COMPAT/MIGRATION", depends_on=[], due_before="Stage 5 Exit", source="MINOR", evidence="docs/SECURITY.md; docs/THREAT_MODEL.md; docs/MIGRATION.md; docs/AGENT_COMPATIBILITY.md", note="四份文档已补；其他宿主仍 UNVERIFIED。"),
    task("m6", "统一 CLI 名称与 doctor 归属", "Stage 0", "DONE", "cli.py 单入口；setup doctor 与 engine doctor 分工写清", depends_on=["T0.1"], due_before="T0.4", evidence="docs/CLI.md", source="MINOR", note="统一为 uiux_engine.cli 与 setup_skill.py doctor"),
    task("m7", "Host Capability 消费者", "Stage 0", "DONE", "doctor --json 输出 host-capability.json；T4.1 复用", depends_on=["T0.4"], due_before="T0.4", evidence="tests/integration/test_install.py", source="MINOR", note="setup doctor 输出并通过 host-capability Schema"),
    task("m8", "延迟/性能预算测量", "Stage 3", "DONE", "预算 + 测量证据", depends_on=[], due_before="Stage 3 Exit", source="MINOR", evidence="docs/PERFORMANCE_BUDGET.md; scripts/measure_performance.py; evidence/T1.0/performance-budget.json", note="小样本实测：10 文件扫描 4.2ms、discovery 749ms；非大项目基准。"),
]

STATUSES = {"DONE", "IN_PROGRESS", "TODO", "BLOCKED"}
STAGES = {"Stage 0", "Stage 1", "Stage 2", "Stage 3", "Stage 4", "Stage 5"}


def validate(tasks: list[dict]) -> list[str]:
    problems: list[str] = []
    ids = [item["id"] for item in tasks]
    if len(ids) != len(set(ids)):
        problems.append("duplicate task ids")
    known = set(ids)
    for item in tasks:
        for field in ("id", "title", "stage", "status", "acceptance"):
            if not item.get(field):
                problems.append(f"{item['id']}: missing {field}")
        if item["status"] not in STATUSES:
            problems.append(f"{item['id']}: invalid status {item['status']}")
        if item["stage"] not in STAGES:
            problems.append(f"{item['id']}: invalid stage {item['stage']}")
        for dependency in item["depends_on"]:
            if dependency not in known:
                problems.append(f"{item['id']}: unknown dependency {dependency}")
    expected_major = {f"M{i}" for i in range(1, 19)}
    expected_minor = {f"m{i}" for i in range(1, 9)}
    missing = (expected_major | expected_minor) - known
    if missing:
        problems.append(f"missing remediation tasks: {sorted(missing)}")
    # dependency cycle check
    graph = {item["id"]: item["depends_on"] for item in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            problems.append(f"dependency cycle: {' -> '.join(stack + [node])}")
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            visit(dependency, stack + [node])
        visiting.discard(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return problems


def render_markdown(tasks: list[dict]) -> str:
    lines = [
        "# V1.3.3 任务计划（机器可读源的渲染）",
        "",
        "> 本文件由 `scripts/build_task_registry.py` 从 `plan/tasks.v1.3.3.json` 生成，禁止手工编辑。",
        "",
        f"- 任务总数：{len(tasks)}",
        "",
        "| ID | 阶段 | 状态 | 最晚时点 | 依赖 | 标题 | 验收摘要 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in tasks:
        dependencies = ", ".join(item["depends_on"]) or "—"
        due = item["due_before"] or "—"
        acceptance = item["acceptance"].replace("|", "\\|")
        if len(acceptance) > 90:
            acceptance = acceptance[:87] + "..."
        lines.append(
            f"| {item['id']} | {item['stage']} | {item['status']} | {due} | {dependencies} | {item['title']} | {acceptance} |"
        )
    lines.extend(
        [
            "",
            "## 状态计数",
            "",
            "| 状态 | 数量 |",
            "|---|---|",
        ]
    )
    for status in sorted(STATUSES):
        count = sum(1 for item in tasks if item["status"] == status)
        lines.append(f"| {status} | {count} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    problems = validate(TASKS)
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, ensure_ascii=False, indent=2))
        return 1
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    registry = {
        "schema_version": "1.3.3",
        "generated_by": "scripts/build_task_registry.py",
        "status_enum": sorted(STATUSES),
        "stage_enum": sorted(STAGES),
        "tasks": TASKS,
    }
    (PLAN_DIR / "tasks.v1.3.3.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DOCS_DIR / "TASK_PLAN.md").write_text(render_markdown(TASKS), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "tasks": len(TASKS),
                "done": sum(1 for item in TASKS if item["status"] == "DONE"),
                "in_progress": sum(1 for item in TASKS if item["status"] == "IN_PROGRESS"),
                "registry": "plan/tasks.v1.3.3.json",
                "rendered": "docs/TASK_PLAN.md",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
