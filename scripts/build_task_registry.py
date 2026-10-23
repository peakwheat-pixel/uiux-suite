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
    task("T1.1", "双栈正反 Fixtures 与冻结 GT", "Stage 1", "IN_PROGRESS", "Web/Tauri 与 Qt 正负样本含预期结果、Rule ID、环境与截图；独立标注记录", depends_on=["T0.1", "T1.0"], due_before="Stage 1 Exit", source="M13/m4"),
    task("T1.2", "style_token_linter（AST/CSS/QSS 分级规则）", "Stage 1", "IN_PROGRESS", "硬失败/告警分级；豁免审计；正反样本零误判硬 FAIL", depends_on=["T1.0", "T1.1"], due_before="Stage 1 Exit"),
    task("T1.3", "ux_flow_validator（Schema + 能力交叉发现）", "Stage 1", "TODO", "flows.json 校验；静态与契约能力差异告警；destructive 漏报触发 WARN/FAIL", depends_on=["T1.0", "T1.1"], due_before="Stage 1 Exit"),
    task("T1.4", "layout_geometry_probe（Web DOM / Qt Offscreen 真实测量）", "Stage 1", "TODO", "裁切/对比度/间距测量；合法负样本零硬 FAIL；Offscreen 结果标注 SIMULATED", depends_on=["T1.1"], due_before="Stage 1 Exit"),
    task("T1.5", "Runner/Gate 引擎完整化（G0–G5 工具日志与证据闭环）", "Stage 1", "IN_PROGRESS", "finalize 从真实工具日志重算；拒绝伪造 PASS；CLI 退出码稳定", depends_on=["T0.1"], due_before="Stage 1 Exit"),
    task("T1.6", "负向攻击测试（假 PASS/删证据/跨层/Mock 冒充）", "Stage 1", "TODO", "全部攻击用例被拒绝并附退出码与日志", depends_on=["T1.5"], due_before="Stage 1 Exit", source="V132-02/V132-07"),
    task("T1.7", "混淆矩阵、CI 与误报/漏报报告", "Stage 1", "TODO", "TP/FP/TN/FN 输出；CI 显示每条样本预期与实际；Windows runner", depends_on=["T1.1", "T1.2", "T1.3", "T1.4"], due_before="Stage 1 Exit", source="M10"),
    # ---------------- Stage 2 ----------------
    task("T2.1", "页面/窗口/路由识别与三源能力比对", "Stage 2", "TODO", "功能地图；源码/运行/契约差异报告", depends_on=["T1.3"], due_before="Stage 2 Exit"),
    task("T2.2", "flows.json 设计工具与状态推导", "Stage 2", "TODO", "按能力派生状态；可测试路径生成；review required 记录", depends_on=["T1.3"], due_before="Stage 2 Exit"),
    task("T2.3", "DTCG Token 与 CSS/Tailwind/PySide6 编译器", "Stage 2", "TODO", "明暗主题与 CJK 字体测试；Token 可编译", depends_on=["T1.2"], due_before="Stage 2 Exit"),
    task("T2.4", "离线知识库消费接口与合规来源", "Stage 2", "TODO", "knowledge index schema；来源/许可/checksum 可核查；无许可则自建量表", depends_on=["T0.5"], due_before="Stage 2 Exit", source="M11"),
    task("T2.5", "design-only 与 prototype（≥2 方案比较）", "Stage 2", "TODO", "两套可比较原型与取舍证据；不先写生产代码", depends_on=["T2.2", "T2.3"], due_before="Stage 2 Exit"),
    task("T2.6", "设计系统权威与存量组件采纳/漂移检测", "Stage 2", "TODO", "brownfield 采纳流程；token drift 检查；冲突优先级", depends_on=["T2.3"], due_before="Stage 2 Exit", source="M12"),
    # ---------------- Stage 3 ----------------
    task("T3.1", "受控改造与 G4 范围校验", "Stage 3", "TODO", "改动在 write scope 内；可回退；G4 证据完整", depends_on=["T2.5"], due_before="Stage 3 Exit"),
    task("T3.2", "Tauri .exe + WDIO Native IPC 验证", "Stage 3", "TODO", "至少一个非 Mock Rust IPC 场景；驱动握手与权限记录", depends_on=["T3.1"], due_before="Stage 3 Exit"),
    task("T3.3", "PySide6 Windows Native QPA 与 DPI 验证", "Stage 3", "TODO", "100/125/150% DPI、中文字体、分栏与焦点", depends_on=["T3.1"], due_before="Stage 3 Exit"),
    task("T3.4", "OS 集成测试（原生对话框/菜单）", "Stage 3", "TODO", "隔离测试环境；UIA 优先；物理输入默认禁用；TOCTOU 说明", depends_on=["T3.2", "T3.3"], due_before="Stage 3 Exit", source="M6/M8"),
    task("T3.5", "证据生命周期、脱敏与 Vault 退化验证", "Stage 3", "TODO", "删除 Vault 后不得重新签发 PASS；脱敏后扫描；保留期策略", depends_on=["T3.1"], due_before="Stage 3 Exit", source="B6"),
    task("T3.6", "独立审查隔离验证", "Stage 3", "TODO", "自报 session 不能签发独立 PASS；隔离证明与 reviewed_head 绑定", depends_on=["T3.4"], due_before="Stage 3 Exit", source="V132-04"),
    # ---------------- Stage 4 ----------------
    task("T4.1", "DSH 宿主兼容实测", "Stage 4", "TODO", "两入口发现/脚本执行/GUI/MCP/断点恢复逐项记录", depends_on=["T0.3"], due_before="Stage 4 Exit", source="M2"),
    task("T4.2", "其他 Agent 兼容矩阵与降级入口", "Stage 4", "TODO", "Codex/Claude/ZCode/Antigravity/Qoder 未测标 UNVERIFIED", depends_on=["T4.1"], due_before="Stage 4 Exit"),
    task("T4.3", "被动外部调用契约（不依赖外部编排器）", "Stage 4", "TODO", "外部 caller 传 task_id/role/artifact_dir 时不改其分支/证据治理；无外部系统时核心正常", depends_on=["T0.1"], due_before="Stage 4 Exit", source="ADR-07 修订"),
    task("T4.4", "退化路径（缺 Node/GUI/旧宿主/离线/软链）", "Stage 4", "TODO", "每项返回稳定 ReasonCode 与可恢复建议", depends_on=["T4.1"], due_before="Stage 4 Exit", source="M9"),
    # ---------------- Stage 5 ----------------
    task("T5.1", "真实复杂工作台试点（隔离副本）", "Stage 5", "TODO", "冻结导入→浏览→编辑→异常→保存/导出任务；只在副本/独立 worktree 操作", depends_on=["T3.6", "T4.4"], due_before="Stage 5 Exit"),
    task("T5.2", "改版前后对照测量", "Stage 5", "TODO", "同机同窗口同素材；成功任务/步骤/恢复/快捷键/布局缺陷记录", depends_on=["T5.1"], due_before="Stage 5 Exit"),
    task("T5.3", "数据安全、回滚与导出正确性", "Stage 5", "TODO", "真实数据写入 0 次；源码前后 hash 一致；回滚演练通过", depends_on=["T5.1"], due_before="Stage 5 Exit", source="M14"),
    task("T5.4", "独立复审与 G6 签发", "Stage 5", "TODO", "冻结版本独立复验；未覆盖项 PARTIAL/UNVERIFIED 明示", depends_on=["T5.3"], due_before="Stage 5 Exit", source="B5"),
    task("T5.5", "发行包、文档、许可证与交付报告", "Stage 5", "TODO", "dist/ 可安装 ZIP、手册、兼容矩阵、证据索引、FINAL_DELIVERY_REPORT.md", depends_on=["T5.4"], due_before="Stage 5 Exit"),
    # ---------------- Remediation tasks: MAJOR ----------------
    task("M1", "安装登记/升级/回滚状态契约", "Stage 0", "DONE", "install-<version>.json 登记全部安装文件；upgrade/rollback 可复现；版本并存", depends_on=["T0.1"], due_before="T0.2", evidence="tests/integration/test_install.py", source="MAJOR", note="install/upgrade/rollback/uninstall 与版本并存已实测"),
    task("M2", "DSH_HOME/AGENTS_HOME 与项目根/遮蔽检测", "Stage 0", "DONE", "解析环境变量；5 级 rank；shadowed_by；非 Git/monorepo 说明", depends_on=["T0.1"], due_before="T0.4", evidence="evidence/T0.3/host-install-evidence.json; tests/integration/test_paths.py", source="MAJOR", note="5 级 rank（含 custom 300）与遮蔽已测；monorepo 说明见 docs/INSTALL.md"),
    task("M3", "install 根分离与写根登记", "Stage 0", "DONE", "install_write_root 入 policy/schema；快照与写范围排除；只读模式不写项目", depends_on=["T0.1"], due_before="T0.2", evidence="contracts/policy.v1.3.3.schema.json; scripts/setup_skill.py", source="MAJOR", note="安装只写 <agents_home>；测试确认不触碰项目 .uiux"),
    task("M4", "Python/Node 版本锁定与依赖清单", "Stage 0", "DONE", "版本区间写入 doctor；requirements.lock/package-lock；离线包", depends_on=["T0.1"], due_before="T0.4", evidence="requirements.lock; dist/wheels/; evidence/T0.5/offline-install-evidence.json", source="MAJOR", note="Python>=3.10、Node>=20、jsonschema 4.20–4.x 由 doctor 校验；离线 wheels 实测。"),
    task("M5", "相对/绝对/UNC/junction/MAX_PATH 路径鲁棒性", "Stage 0", "DONE", "suite-link 基准固定；UNC/漫游/失效链接用例；长路径检查", depends_on=["T0.1"], due_before="T0.2", evidence="tests/integration/test_paths.py; tests/integration/test_install.py", source="MAJOR", note="中文空格、junction、>260 长路径通过；UNC 缺失路径稳定 RELEASE_ROOT_MISSING。"),
    task("M6", "OS 输入分权与桌面隔离证明", "Stage 3", "TODO", "UIA 与物理输入分离；desktop_isolation_proof；授权记录；T3.4 验收", depends_on=["T0.1"], due_before="Stage 3 Exit", source="MAJOR", note="policy/schema 字段已在 T0.1 落地"),
    task("M7", "四类根权限优先级与 finalize 校验", "Stage 0", "DONE", "read/report/sandbox/install 四根入 schema 与语义校验；allowed_write_globs 单一来源；越权拒绝", depends_on=["T0.1"], due_before="T0.1", evidence="tests/unit/test_semantics.py", source="MAJOR"),
    task("M8", "不可信项目构建执行模型", "Stage 3", "TODO", "只读模式构建沙箱/副本；执行清单；网络与清理策略；SECURITY.md", depends_on=["T0.1"], due_before="Stage 3 Exit", source="MAJOR"),
    task("M9", "CLI 退出码、--json 与阶段验收命令", "Stage 0", "DONE", "退出码表写入 docs/CLI.md；doctor/finalize --json schema；每个 Stage Exit 三列化", depends_on=["T0.1"], due_before="T0.4", evidence="docs/STAGE_GATES.md; docs/CLI.md", source="MAJOR", note="validate/finalize/doctor/launch 退出码与 Stage Exit 表已落库。"),
    task("M10", "CI 骨架与 Windows runner", "Stage 1", "TODO", "CI 显示每条 fixture 预期/实际；Artifacts 归档", depends_on=["T1.1"], due_before="Stage 1 Exit", source="MAJOR"),
    task("M11", "第三方知识来源、许可与消费接口", "Stage 2", "TODO", "来源锁 commit/许可；knowledge index；无法锁许可则自建", depends_on=["T0.5"], due_before="Stage 2 Exit", source="MAJOR"),
    task("M12", "存量设计系统采纳与 token drift", "Stage 2", "TODO", "brownfield 流程；drift 检查器；冲突优先级", depends_on=["T2.3"], due_before="Stage 2 Exit", source="MAJOR"),
    task("M13", "靶场 GT 独立标注与阻断种子", "Stage 1", "TODO", "标注流程与分歧仲裁；阻断种子清单；零误判硬 FAIL", depends_on=["T1.0"], due_before="Stage 1 Exit", source="MAJOR"),
    task("M14", "P0–P3 分级与可观测安全指标", "Stage 3", "TODO", "qa-report schema；数据写入 0 次可证；Release 判定", depends_on=["T0.1"], due_before="Stage 3 Exit", source="MAJOR"),
    task("M15", "DAG 循环与遗漏修复", "Stage 0", "DONE", "T1.0 作为共同上游；DAG 补齐 T0.4/T0.6/T1.7/T2.4/T2.6；编号修正", depends_on=[], due_before="T0.1", evidence="SPEC_V1.3.3.md §13", source="MAJOR"),
    task("M16", "附录命令一致性", "Stage 5", "TODO", "统一 python 解释器与引号；附录拆分 Stage 0/1 与 2/3", depends_on=["T5.5"], due_before="Stage 5 Exit", source="MAJOR"),
    task("M17", "非 Git 快照与回退", "Stage 0", "DONE", "dir_digest + 备份副本 + 差异哈希；回滚路径", depends_on=["T0.1"], due_before="T0.2", evidence="runtime/uiux_engine/snapshot.py; tests/unit/test_snapshot.py", source="MAJOR", note="snapshot/diff/backup 已实现；CLI 支持 --out/--backup/--diff；回滚=备份副本拷回（显式运维命令）。"),
    task("M18", "无障碍维度与 Rule ID", "Stage 1", "TODO", "accessible name/键盘/target size/ARIA-UIA 语义规则", depends_on=["T1.0"], due_before="Stage 1 Exit", source="MAJOR"),
    # ---------------- Remediation tasks: MINOR ----------------
    task("m1", "Prompt Injection 威胁模型", "Stage 3", "TODO", "项目内容视为不可信输入；提示隔离与拒绝规则", depends_on=["M8"], due_before="Stage 3 Exit", source="MINOR"),
    task("m2", "同模型系统性偏差提示", "Stage 4", "TODO", "独立审查要求不同模型家族或明示风险", depends_on=["T3.6"], due_before="Stage 4 Exit", source="MINOR"),
    task("m3", "字体许可与 CJK 字体分发", "Stage 2", "TODO", "字体栈许可核查；不随包分发未授权字体", depends_on=["T2.3"], due_before="Stage 2 Exit", source="MINOR"),
    task("m4", "混淆矩阵契约与产物登记", "Stage 1", "TODO", "confusion-matrix schema；纳入 §3.1 目录与 CLI 输出", depends_on=["T1.7"], due_before="Stage 1 Exit", source="MINOR"),
    task("m5", "安全、兼容与迁移文档", "Stage 5", "TODO", "SECURITY/THREAT_MODEL/AGENT_COMPAT/MIGRATION", depends_on=["T5.5"], due_before="Stage 5 Exit", source="MINOR"),
    task("m6", "统一 CLI 名称与 doctor 归属", "Stage 0", "DONE", "cli.py 单入口；setup doctor 与 engine doctor 分工写清", depends_on=["T0.1"], due_before="T0.4", evidence="docs/CLI.md", source="MINOR", note="统一为 uiux_engine.cli 与 setup_skill.py doctor"),
    task("m7", "Host Capability 消费者", "Stage 0", "DONE", "doctor --json 输出 host-capability.json；T4.1 复用", depends_on=["T0.4"], due_before="T0.4", evidence="tests/integration/test_install.py", source="MINOR", note="setup doctor 输出并通过 host-capability Schema"),
    task("m8", "延迟/性能预算测量", "Stage 3", "TODO", "按任务型态设基线；不得套用全局 100ms", depends_on=["T3.3"], due_before="Stage 3 Exit", source="MINOR"),
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
