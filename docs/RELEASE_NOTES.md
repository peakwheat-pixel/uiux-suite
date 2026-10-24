# UIUX Suite V1.3.3 FINAL 发行说明

> 状态：**V1.3.3 FINAL**；61/61 DONE；G6 PASS（ISOLATED_REVIEW_VERIFIED）；外部独立审查 INDEPENDENCE_UNVERIFIED；UI 撤销按钮 E2E 未通过。

## 交付物

| 产物 | 路径 |
|---|---|
| Windows 安装包 | `dist/uiux-suite-1.3.3-win64.zip`（155 个载荷文件 + `RELEASE_MANIFEST.json`（ZIP 共 156 项），含 7 个运行时 wheel） |
| 校验和 | `dist/SHA256SUMS.txt` |
| 发行清单 | ZIP 内 `RELEASE_MANIFEST.json`（每文件 SHA256/size/role） |
| 安装验证 | `evidence/T5.5/release-verification.json` + `release-install.txt` |
| 完整规范 | `SPEC_V1.3.3.md` |
| 验收记录 | `docs/STAGE0_ACCEPTANCE.md` … `docs/STAGE5_ACCEPTANCE.md` |
| 审计 | `docs/audits/V1.3.3_CONTRACT_REVIEW.md` |

## 安装

```powershell
Expand-Archive dist\uiux-suite-1.3.3-win64.zip -DestinationPath C:\tools
cd C:\tools\uiux-suite-1.3.3
python scripts\setup_skill.py --host dsh install --scope user --source .
# 双入口：uiux / uiux-verify
python skills\uiux\scripts\launch.py enums
python skills\uiux\scripts\launch.py doctor --scope user
```

要求：Python ≥3.10，`jsonschema` 4.20–4.x；Node 仅 doctor 能力检查需要。

## 已验证

- 460 项 pytest 全绿；Stage 2 DONE；PySide6 QPA 实测（NATIVE_QPA，3 个缩放）。
- 安装/双入口/doctor/卸载/升级回滚/长路径/junction/UNC 拒绝。
- 规则目录冻结 20 条；T1.2–T1.7 检测器、负向攻击 11/11、混淆矩阵 TP38/FP0/TN8/FN0。
- Stage 2 discovery/design system/prototype/options。
- Stage 3 受控改动/回滚、Vault 字节校验、完整性链、安全分级、真实 Win11 Notepad（WinUI 3）UIA 只读证据。
- 发行包内安装、双入口、doctor 均 exit 0；干净卸载 85 files；rollback same-version exit 0；install 集成测试 11 passed（临时隔离目录，155 个载荷文件 + `RELEASE_MANIFEST.json`（ZIP 共 156 项））。

## 未验证（不得宣称 PASS）

- 原生对话框/WinUI/WPF/Qt UIA 的完整矩阵（T3.4 已过 WPF UIA/对话框/菜单与 WinUI 读写，仍有 WinUI 动作限制）。
- 独立来源审查：G6 PASS 基于隔离会话审查（ISOLATED_REVIEW_VERIFIED）；未取得 host_verified/external 独立来源，INDEPENDENCE_UNVERIFIED。
- 其他 Agent 宿主（Codex/Claude/ZCode/Antigravity/Qoder）。
- MCP 与断点恢复。
- 物理 DPI 变更、真实浏览器中的 Tailwind/CSS 产物执行。

## 构建可复现性

- ZIP 不可比特级复现（manifest 含 `generated_at`/Node 版本）；以 `dist/SHA256SUMS.txt` 记录的本包 SHA256 为验证锚点，`evidence/T5.5/release-verification.json` 记录构建 commit。

## 安全与限制

- 本地同权 Agent 可修改证据与工具日志；本包只提供哈希链/一致性校验，不提供硬件签名。
- 证据 `evidence/T0.3` 含本机路径，属本机私有；发行 ZIP 不含 `evidence/`。
- `dist/` 不入 Git；ZIP 的 SHA256 与文件清单在 `dist/SHA256SUMS.txt` 与 `evidence/T5.5`。
