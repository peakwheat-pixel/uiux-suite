# V1.3.3 任务计划（机器可读源的渲染）

> 本文件由 `scripts/build_task_registry.py` 从 `plan/tasks.v1.3.3.json` 生成，禁止手工编辑。

- 任务总数：61

| ID | 阶段 | 状态 | 最晚时点 | 依赖 | 标题 | 验收摘要 |
|---|---|---|---|---|---|---|
| T0.1 | Stage 0 | DONE | — | — | Contract Closure：Schema、枚举、Gate 引擎、覆盖矩阵、L4、证据生命周期 | B1–B6 机器测试全绿；B5/B6 Schema 与时点锁定；独立契约复核无未解决阻断；evidence/T0.1/contract-test-evidence.json ... |
| T0.2 | Stage 0 | DONE | Stage 0 Exit | T0.1 | 版本化发行根、双启动器、安装/卸载/升级/回滚 | 删除开发仓后用户级安装可运行；版本并存；升级/回滚；卸载只删登记文件；manifest 哈希校验；M1/M3/M4/M5/M6(字段)关闭 |
| T0.3 | Stage 0 | DONE | Stage 0 Exit | T0.2, T0.4 | DSH 实机安装与双入口发现 | DSH 实际发现 uiux 与 uiux-verify；doctor 输出真实 root/rank；不依赖开发仓；中文/空格用例通过（UNC 由 M5 覆盖） |
| T0.4 | Stage 0 | DONE | Stage 0 Exit | T0.1 | doctor：能力、根目录、遮蔽、退出码与 --json | READY/MISSING/INCOMPATIBLE/UNVERIFIED 逐项输出；解析 DSH_AGENTS_HOME/DSH_HOME；遮蔽列表；host-capabi... |
| T0.5 | Stage 0 | DONE | Stage 0 Exit | T0.1 | 许可证清单、离线依赖与版本锁定 | THIRD_PARTY_NOTICES.md 逐文件来源/许可；requirements.lock；离线安装路径可复现 |
| T0.6 | Stage 0 | DONE | Stage 0 Exit | T0.2, T0.3 | 独立运行验证（删除开发仓回归） | 删除/移动开发仓后安装实例仍可 doctor + 最小 CLI；失败原因可诊断 |
| T1.0 | Stage 1 | DONE | Stage 1 Exit | T0.1 | 规则目录与 Rule ID 冻结 | rule_id 注册表、严重度、豁免 schema 冻结；作为 T1.1/T1.2/T1.3 共同上游 |
| T1.1 | Stage 1 | DONE | Stage 1 Exit | T0.2 | 双栈正反 Fixtures 与冻结 GT | ≥8 正/反样本；GT 版本与哈希冻结；误报/漏报/权限越界/跨层样本 |
| T1.2 | Stage 1 | DONE | Stage 1 Exit | T1.1 | style_token_linter（AST/CSS/QSS 分级规则） | 规则表+枚举；正反 fixtures；误报/漏报/越界/跨层拒绝 |
| T1.3 | Stage 1 | DONE | Stage 1 Exit | T1.1 | ux_flow_validator（Schema + 能力交叉发现） | 可达性/破坏性/空态/错误/加载；Schema 合法 |
| T1.4 | Stage 1 | DONE | Stage 1 Exit | T1.1 | layout_geometry_probe（Web DOM / Qt Offscreen 真实测量） | 裁切/重叠/目标/对比度/焦点；Web DOM 与 Qt 真实尺寸 |
| T1.5 | Stage 1 | DONE | Stage 1 Exit | T0.1 | Runner/Gate 引擎完整化（G0–G5 工具日志与证据闭环） | finalize 从真实工具日志重算；拒绝伪造 PASS；CLI 退出码稳定 |
| T1.6 | Stage 1 | DONE | Stage 1 Exit | T1.5 | 负向攻击测试（假 PASS/删证据/跨层/Mock 冒充） | 全部攻击用例被拒绝并附退出码与日志 |
| T1.7 | Stage 1 | DONE | Stage 1 Exit | T1.1, T1.2, T1.3, T1.4 | 混淆矩阵、CI 与误报/漏报报告 | TP/FP/TN/FN 输出；CI 显示每条样本预期与实际；Windows runner |
| T2.1 | Stage 2 | DONE | Stage 2 Exit | T1.3 | 页面/窗口/路由识别与三源能力比对 | 功能地图；源码/运行/契约差异报告 |
| T2.2 | Stage 2 | DONE | Stage 2 Exit | T1.3 | flows.json 设计工具与状态推导 | 按能力派生状态；可测试路径生成；review required 记录 |
| T2.3 | Stage 2 | DONE | Stage 2 Exit | T1.2 | DTCG Token 与 CSS/Tailwind/PySide6 编译器 | 明暗主题与 CJK 字体测试；Token 可编译 |
| T2.4 | Stage 2 | DONE | Stage 2 Exit | T0.5 | 离线知识库消费接口与合规来源 | knowledge index schema；来源/许可/checksum 可核查；无许可则自建量表 |
| T2.5 | Stage 2 | DONE | Stage 2 Exit | T2.2, T2.3 | design-only 与 prototype（≥2 方案比较） | 两套可比较原型与取舍证据；不先写生产代码 |
| T2.6 | Stage 2 | DONE | Stage 2 Exit | T2.3 | 设计系统权威与存量组件采纳/漂移检测 | brownfield 采纳流程；token drift 检查；冲突优先级 |
| T3.1 | Stage 3 | DONE | Stage 3 Exit | T2.5 | 受控改造与 G4 范围校验 | 改动在 write scope 内；可回退；G4 证据完整 |
| T3.2 | Stage 3 | DONE | Stage 3 Exit | T3.1 | Tauri .exe + WDIO Native IPC 验证 | Tauri 2 应用真实启动；WDIO 调用 Rust IPC 命令并验证返回 |
| T3.3 | Stage 3 | DONE | Stage 3 Exit | T3.1 | PySide6 Windows Native QPA 与 DPI 验证 | 100/125/150% DPI、中文字体、分栏与焦点 |
| T3.4 | Stage 3 | DONE | Stage 3 Exit | T3.3 | OS 集成测试（原生对话框/菜单/UIA） | WPF/WinUI/Qt UIA 读写、原生对话框、菜单、快捷键 |
| T3.5 | Stage 3 | DONE | Stage 3 Exit | T3.1 | 证据生命周期、脱敏与 Vault 退化验证 | 删除 Vault 后不得重新签发 PASS；脱敏后扫描；保留期策略 |
| T3.6 | Stage 3 | DONE | Stage 3 Exit | T3.4 | 独立审查隔离验证 | 自报 session 不能签发独立 PASS；隔离证明与 reviewed_head 绑定 |
| T4.1 | Stage 4 | DONE | Stage 4 Exit | T0.3 | DSH 宿主兼容实测 | 两入口发现/脚本执行/GUI/MCP/断点恢复逐项记录 |
| T4.2 | Stage 4 | DONE | Stage 4 Exit | T4.1 | 其他 Agent 兼容矩阵与降级入口 | 宿主发现/安装/启动/工具寻址/异常降级 |
| T4.3 | Stage 4 | DONE | Stage 4 Exit | T0.1 | 被动外部调用契约（不依赖外部编排器） | 外部 caller 传 task_id/role/artifact_dir 时不改其分支/证据治理；无外部系统时核心正常 |
| T4.4 | Stage 4 | DONE | Stage 4 Exit | T4.1 | 退化路径（缺 Node/GUI/旧宿主/离线/软链） | 每项返回稳定 ReasonCode 与可恢复建议 |
| T5.1 | Stage 5 | DONE | Stage 5 Exit | T3.3 | 真实复杂工作台试点（隔离副本） | 启动真实 New Manga；导入/浏览/阅读/编辑与真实界面基线 |
| T5.2 | Stage 5 | DONE | Stage 5 Exit | T5.1 | 改版前后对照测量 | 真实应用受控改造与前后对照；功能回归 |
| T5.3 | Stage 5 | DONE | Stage 5 Exit | T5.1 | 真实项目数据安全与回滚演练 | 隔离数据读写、取消/撤销、导出、Git 回滚、源未变更 |
| T5.4 | Stage 5 | DONE | Stage 5 Exit | T5.1, T5.2, T5.3 | 独立复审与 G6 签发 | 冻结版本、独立 Reviewer、G6 裁决 |
| T5.5 | Stage 5 | DONE | Stage 5 Exit | T5.4 | 发行包、文档、许可证与交付报告 | dist/ 可安装 ZIP、手册、兼容矩阵、证据索引、FINAL_DELIVERY_REPORT.md |
| M1 | Stage 0 | DONE | T0.2 | T0.1 | 安装登记/升级/回滚状态契约 | install-<version>.json 登记全部安装文件；upgrade/rollback 可复现；版本并存 |
| M2 | Stage 0 | DONE | T0.4 | T0.1 | DSH_HOME/AGENTS_HOME 与项目根/遮蔽检测 | 解析环境变量；5 级 rank；shadowed_by；非 Git/monorepo 说明 |
| M3 | Stage 0 | DONE | T0.2 | T0.1 | install 根分离与写根登记 | install_write_root 入 policy/schema；快照与写范围排除；只读模式不写项目 |
| M4 | Stage 0 | DONE | T0.4 | T0.1 | Python/Node 版本锁定与依赖清单 | 版本区间写入 doctor；requirements.lock/package-lock；离线包 |
| M5 | Stage 0 | DONE | T0.2 | T0.1 | 相对/绝对/UNC/junction/MAX_PATH 路径鲁棒性 | suite-link 基准固定；UNC/漫游/失效链接用例；长路径检查 |
| M6 | Stage 3 | DONE | Stage 3 Exit | T0.1 | OS 输入分权与桌面隔离证明 | 全局物理输入默认禁止；测试通道需显式；UIA 只读/动作分权 |
| M7 | Stage 0 | DONE | T0.1 | T0.1 | 四类根权限优先级与 finalize 校验 | read/report/sandbox/install 四根入 schema 与语义校验；allowed_write_globs 单一来源；越权拒绝 |
| M8 | Stage 3 | DONE | Stage 3 Exit | T0.1 | 不可信项目构建执行模型 | 白名单执行、网络/破坏性/越界拦截 |
| M9 | Stage 0 | DONE | T0.4 | T0.1 | CLI 退出码、--json 与阶段验收命令 | 退出码表写入 docs/CLI.md；doctor/finalize --json schema；每个 Stage Exit 三列化 |
| M10 | Stage 5 | DONE | Release | T1.6 | CI 骨架与 Windows runner | GitHub Actions Push/PR/dispatch；真实运行与日志 |
| M11 | Stage 2 | DONE | Stage 2 Exit | T0.5 | 第三方知识来源、许可与消费接口 | 来源锁 commit/许可；knowledge index；无法锁许可则自建 |
| M12 | Stage 2 | DONE | Stage 2 Exit | T2.3 | 存量设计系统采纳与 token drift | brownfield 流程；drift 检查器；冲突优先级 |
| M13 | Stage 1 | DONE | Stage 1 Exit | T1.1 | 靶场 GT 独立标注与阻断种子 | 独立标注/仲裁；与冻结 GT 对照 |
| M14 | Stage 3 | DONE | Stage 3 Exit | T0.1 | P0–P3 分级与可观测安全指标 | P0–P3 + qa-report schema + 指标 |
| M15 | Stage 0 | DONE | T0.1 | — | DAG 循环与遗漏修复 | T1.0 作为共同上游；DAG 补齐 T0.4/T0.6/T1.7/T2.4/T2.6；编号修正 |
| M16 | Stage 5 | DONE | Stage 5 Exit | T5.5 | 附录命令一致性 | 统一 python 解释器与引号；附录命令与 CLI 一致 |
| M17 | Stage 0 | DONE | T0.2 | T0.1 | 非 Git 快照与回退 | dir_digest + 备份副本 + 差异哈希；回滚路径 |
| M18 | Stage 1 | DONE | Stage 1 Exit | T1.0 | 无障碍维度与 Rule ID | A11Y 维度/规则；UIA 读/写与焦点证据 |
| m1 | Stage 3 | DONE | Stage 3 Exit | — | Prompt Injection 威胁模型 | 威胁模型与缓解 |
| m2 | Stage 4 | DONE | Stage 4 Exit | — | 同模型系统性偏差提示 | 偏差与能力限制说明 |
| m3 | Stage 2 | DONE | Stage 2 Exit | — | 字体许可与 CJK 字体分发 | 不捆绑字体；许可/来源说明 |
| m4 | Stage 1 | DONE | Stage 1 Exit | T1.7 | 混淆矩阵契约与产物登记 | confusion-matrix schema；纳入 §3.1 目录与 CLI 输出 |
| m5 | Stage 5 | DONE | Stage 5 Exit | — | 安全、兼容与迁移文档 | SECURITY/THREAT_MODEL/AGENT_COMPAT/MIGRATION |
| m6 | Stage 0 | DONE | T0.4 | T0.1 | 统一 CLI 名称与 doctor 归属 | cli.py 单入口；setup doctor 与 engine doctor 分工写清 |
| m7 | Stage 0 | DONE | T0.4 | T0.4 | Host Capability 消费者 | doctor --json 输出 host-capability.json；T4.1 复用 |
| m8 | Stage 3 | DONE | Stage 3 Exit | — | 延迟/性能预算测量 | 预算 + 测量证据 |

## 状态计数

| 状态 | 数量 |
|---|---|
| BLOCKED | 0 |
| DONE | 61 |
| IN_PROGRESS | 0 |
| TODO | 0 |
