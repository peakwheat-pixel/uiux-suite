# 受控改造与自测（G4/G5）

## 改造前

- 确认模式（new-build / redesign / targeted-fix）与授权 write scope。
- 保存源码指纹与回滚点（Git commit 或目录备份）。
- 确认测试数据副本、隔离 `APPDATA`/cache/DB。

## 改造

- 只在 `allowed_write_globs` 内修改；不写真实用户数据。
- UI 改动遵循既有设计系统；新增 Token 必须登记来源。
- 危险操作（删除/覆盖/导出）必须有确认或撤销，并补回归。

## 自测

1. 静态 Lint / 类型检查 / 构建。
2. 单元/组件测试。
3. 目标层级运行测试：Mock → Native（按 `runtime_targets`）。
4. 几何与视觉检查（裁切、对比度、DPI）。
5. 数据安全：前后哈希、无越权写入。

## 证据与 finalize

- 每条 Gate 附 `evidence_refs`、`probe_id`、tool-log。
- `coverage_matrix` 逐 task/scenario 记录层级与状态。
- 运行 `uiux-engine finalize`，由引擎派生状态；不得手改 PASS。

## 常见错误

- 用 Mock 结果宣称 Native。
- 只截成功态，不测 error/empty/loading。
- 修了目标控件但破坏邻接布局（需邻接回归）。
