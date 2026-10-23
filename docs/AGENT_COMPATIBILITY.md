# 其他 Agent 安装与使用

当前矩阵与实测状态见 `docs/COMPATIBILITY.md`：

- DSH：双入口实测通过（rank 100/200/300/400/500）。
- Codex / Claude Code / Antigravity / Qoder / ZCode：**UNVERIFIED**——本环境有部分 CLI，但未做隔离安装与技能发现实测；不得宣称兼容。
- 通用安装：`python scripts/setup_skill.py --host generic install --scope user --source .`；外部调用方需遵守本套件的 Gate/证据/写作用域契约。