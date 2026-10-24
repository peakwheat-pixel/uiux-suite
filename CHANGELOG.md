# CHANGELOG

## V1.3.5 (2026-10-24) — Reliability Closure

- **R6 修复**：新增 `risk_gate` 引擎，移除恒真检查；机制完整性 vs 高风险执行覆盖分离；24 项负面/故障注入测试 + 2 项 V1.3.4 历史兼容回归。
- **V1.3.5 契约层**：26 份 schema + enums + mode-gate-policy；coverage 增加 capability/execution/backup/restore 可选字段；版本分派支持 1.3.3/1.3.4/1.3.5。
- **G1 全量发现**：隔离副本 12 页面、6 对话框、581 入口、7 GAP、24 状态线索；Inventory v1.3.5 baseline（18 项，高风险 10 项）；独立范围复核。
- **真实覆盖补采**：搜索/排序/筛选、阅读器、工作台、Region 空态、任务面板、设置、删除入口（18 次采集，两轮运行）。
- **高风险隔离执行**：备份/恢复框架 + 302 文件一致性验证；设置写/合成作品创建成功；危险写操作因产品能力（GAP/禁用/原生交互）保持 UNVERIFIED；高风险覆盖率如实为 3/10。
- **环境归因回归**：7 个历史环境陷阱 7/7 判为 ENVIRONMENT。
- **Release Facts/Linter**：机制/业务分离、只读/执行分离、A 级资格派生、10 项负面测试。
- **独立 Reviewer**：11/11 CONFIRMED，0 DISPUTED；`ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED`。

## V1.3.4 (2026-10-24)

- 双契约版本层、fixture 环境预检、inventory/declared scope、coverage disposition/六维交付、跨版本升级/回滚、真实试点与对账。

## V1.3.3

- 基础契约、G0–G6 门禁、uiux/uiux-verify 双 Skill、真实 New Manga 审计基线。
