# 安装与运维（V1.3.3）

## 1. 环境要求

- Windows 10/11；PowerShell 7 优先。
- Python **3.10+**（本机验证：3.12.14 与 3.14.6）；运行时依赖见 `requirements.txt`。
- Node.js **>= 20**（GUI/后续探针需要；仅 CLI 契约可不需要）。
- 不需要管理员权限：默认用户级安装到 `%USERPROFILE%\.agents`。

## 2. 用户级安装（推荐）

```powershell
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh install --scope user --version 1.3.3
```

产物：

```text
%USERPROFILE%\.agents\
  uiux-suite\versions\1.3.3\            # runtime/contracts/skills? 实际为 runtime/contracts/setup_skill.py 等
  uiux-suite\state\install-1.3.3.json   # 安装登记（逐文件 SHA256）
  skills\uiux\{SKILL.md,references,scripts/launch.py,suite-link.json}
  skills\uiux-verify\...
```

安装器只写上述登记文件；不写项目目录；不覆盖未知同名 Skill。

## 3. 项目级安装

```powershell
.\.venv\Scripts\python.exe scripts\setup_skill.py --host generic install --scope project --project "G:\demo" --version 1.3.3
```

项目根 = 含 `.git` 的最近祖先；非 Git 项目需 `--project` 指向 cwd 根。

## 4. doctor

```powershell
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh doctor --scope user
# 或安装后（不依赖开发仓）：
$env:USERPROFILE\.agents\skills\uiux\scripts\launch.py doctor --scope user
```

退出码：`0` READY/UNVERIFIED；`11` MISSING/INCOMPATIBLE/链接问题。输出含 `host_capability`（root/rank/shadow/能力）与 `links`。

## 5. 升级 / 回滚 / 修复 / 卸载

```powershell
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh upgrade --scope user --source . --version 1.3.4
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh rollback --scope user --version 1.3.3
.\.venv\Scripts\python.exe scripts\setup_skill.py --host dsh repair --scope user
.\.venv\Scripts\python.exe scripts\uninstall_skill.py --scope user --version 1.3.3
```

- 旧版本目录保留；`suite-link.active_version` 只指向当前激活版本；卸载旧版不删共享文件。
- 卸载只删登记文件；保留 `.uiux/`、用户数据与其他版本。

## 6. Python 选择与仓库独立性

- 安装器优先选择 **不在开发仓内且能 `import jsonschema`** 的 Python（`--python-exe` 可显式指定），写入安装登记与 `suite-link.python_exe`。
- 启动器按 `suite-link.python_exe` → 当前解释器 → PATH `python` 依次回退；都不可用时退出码 5（`PYTHON_EXE_MISSING`）。
- 安装后的 `doctor` 随 suite 一同安装，可在移动/删除开发仓后继续使用。

## 7. 离线安装

`dist/wheels/` 已包含运行时依赖（win_amd64，cp312 与 cp314）：

```powershell
python -m venv .venv-offline
.\.venv-offline\Scripts\python.exe -m pip install --no-index --find-links dist\wheels -r requirements.txt
```

如目标机架构不同，用 `pip download` 重新取对应 wheel。

## 8. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动器退出 3 | `suite-link.json` 缺失/损坏 | 重新 `repair` |
| 退出 4 | suite 根缺失/版本不符 | 检查安装登记与 active_version |
| 退出 5 | 找不到可用的 Python（含 jsonschema） | 安装 Python 或 `--python-exe` 重装 |
| 退出 6 | manifest 哈希不符 | 重装/升级；勿手改 suite 文件 |
| doctor 11 | 链接/能力缺失 | 按 `problems` 逐项修复 |
