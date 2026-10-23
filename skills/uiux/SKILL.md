---
name: uiux
description: UI/UX 工程入口：理解现有界面与任务流、建立 flows/设计系统、生成原型、执行受控改造并自测。用于 UI/UX 审查、设计、重构、定点修复与新模块建设；不签发独立验收。
---

# uiux

本 Skill 负责 **设计、改造与自测**。它以本地版本化运行时 `uiux-engine` 为唯一执行器，所有 Gate 结果由运行时从证据派生，模型不得自填 `PASS`。

## 何时使用

- 只读审查现有软件界面与任务流（`audit`）。
- 设计 IA / 流程 / Token / 方案（`design-only`）。
- 在隔离沙箱生成可交互原型（`prototype`）。
- 新模块先设计后开发（`new-build`）、整体重构（`redesign`）、单点修复（`targeted-fix`）。

## 工作流

1. **预检（G0）**：确认技术栈、范围、四类根、授权、运行环境；不碰真实用户数据。
2. **发现（G1/G2）**：源码静态发现 × 运行发现 × 任务契约三路交叉，产出 `flows.json`。
3. **设计（G3/L4）**：`DESIGN_SYSTEM.md` + DTCG Token；L4 评审用 `design-review` 十维量表。
4. **受控改造（G4）**：只在授权 write scope 内修改；保存 diff 与回滚点。
5. **运行验证（G5）**：按目标层级执行；Mock/Offscreen 不得冒充 Native。
6. **finalize**：`uiux-engine finalize` 从证据派生 G6 与 TaskResult。

## 命令

```bat
python <suite_root>\runtime\uiux_engine\cli.py finalize ...
```

正常使用应通过本 Skill 的 `scripts/launch.py` 调用；它会解析 `suite-link.json` 并校验发行清单。

## 参考

- `references/discover.md`：发现与基线
- `references/flow.md`：任务流契约
- `references/design.md`：设计系统与 L4
- `references/prototype.md`：原型
- `references/build.md`：受控改造与自测

## 边界

- 不能签发独立验收；需要独立结论时使用 `uiux-verify`。
- 不主动依赖任何外部编排器。
- 证据分级、WARN 处置与 COMPLETE 约束见 `SPEC_V1.3.3.md`。
