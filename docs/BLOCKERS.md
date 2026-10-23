# 阻断项（Blockers）

> 规则：只有涉及真实用户数据、授权范围外文件、不可恢复的破坏性操作、系统级高风险组件、未授权凭据/敏感数据、真实外部付费/不可逆服务，或必须由用户独占资源才能决定的事项，才登记为 `BLOCKED_WAITING_EXTERNAL`。普通实现失败、环境缺失、UNVERIFIED 记入任务状态与限制清单，不在此列。

## 当前阻断

| ID | 任务 | 类型 | 已尝试 | 所需外部条件 | 状态 |
|---|---|---|---|---|---|
| — | — | — | — | — | 无 |

## 技术缺口（非阻断，按 Stage 推进）

| 任务 | 缺口 | 计划 |
|---|---|---|
| T1.4 | 真实 Web DOM/Qt Offscreen 测量 | Stage 3 T3.3 真实 UI 探针；当前测量 JSON 模式标 SIMULATED |
| T2.3 | CSS/Tailwind/PySide6 token 编译器 | Stage 3 或 T2.3 续项；当前只提供 tokens/freeze/校验 |
| T2.4/M11 | knowledge index schema 与第三方来源锁 | Stage 4/5；当前走自建量表 |
| T2.6/M12 | brownfield 采纳流程与冲突优先级 | Stage 3/5 |
| M10 | CI 在真实 runner 执行 | 发布前；workflow 已提交 |
| M18 | ARIA-UIA 语义矩阵与动态键盘验证 | Stage 3 T3.3/T3.4 |


## 边界说明

- **T0.3（DSH 实机安装）**：当前机器存在 DSH 运行环境，可在用户级 `.agents` 下执行安装验证；不构成阻断。若发现写入系统级目录或需要管理员权限，则降级为用户级安装并记录。
- **Stage 3 原生 GUI**：若当前会话无法提供交互式 Windows 桌面，相关用例记 `UNVERIFIED` 并保留命令，不伪造 PASS；这是能力限制，不是阻断。
- **Stage 5 真实项目（`<workbench>`）**：只允许在独立副本或独立 worktree 操作；不修改真实工作目录。若副本不可创建，降级为合成 fixture 项目并声明限制。
- **外部编排器**：不存在时不阻断任何主路径。

## 记录格式（新增阻断时复制）

```text
ID | 任务 | 类型（数据/权限/不可逆/凭据/外部服务） | 已尝试的安全替代 | 所需外部条件 | 当前状态 | 证据路径
```

## V1.3.3 RC2 剩余外部阻断（2026-10-24）

| 任务 | 状态 | 所需外部条件 |
|---|---|---|
| T5.1/T5.2 真实工作台试点与前后对照 | BLOCKED_WAITING_EXTERNAL | 对 `New Manga` 真实应用、数据与权重目录的隔离运行授权；不得直接启动/修改原工作目录。合成应用 12/12 E2E 已完成。 |
| T5.3 真实项目数据安全/回滚演练 | BLOCKED_WAITING_EXTERNAL | 同上；需要允许在隔离副本写入并恢复真实项目数据。 |
| T5.4 独立 G6 签发 | BLOCKED_BY_DEPENDENCY | 依赖 T5.1–T5.3 与真实证据；当前只能签发 RC2 审阅，不能签发 G6 PASS。 |
| T4.2 其他 Agent 兼容矩阵 | BLOCKED_WAITING_EXTERNAL | Codex/Claude/ZCode/Antigravity/Qoder 的隔离配置目录与离线技能发现方式；需避免调用收费模型。 |
| M10 真实 CI runner | BLOCKED_WAITING_EXTERNAL | GitHub/gitea runner、仓库凭据或本地 Docker/act 执行环境。 |
