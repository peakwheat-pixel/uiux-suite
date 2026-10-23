# Stage 2 验收记录（V1.3.3）

> 更新时间：2026-10-24。结论以 Git、pytest 与代码为准；本文件只做索引。

## 1. 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T2.1 页面/窗口/路由识别与三源能力比对 | **DONE** | `runtime/uiux_engine/discovery.py`；13 用例；`docs/DISCOVERY.md` |
| T2.2 flows 设计与状态推导 | **DONE** | `flows_from_discovery()`；schema 合法；草案需人工补 guard |
| T2.3 DTCG Token 与编译器 | **PARTIAL** | tokens v1.0 + freeze + 校验/别名/漂移（31 用例）；CSS/Tailwind/PySide6 编译器未实现 |
| T2.4 离线知识库与合规来源 | **PARTIAL** | 自建 token 量表 + 冻结摘要；knowledge index schema/第三方来源锁未建 |
| T2.5 design-only 与 prototype（≥2 方案） | **DONE** | `options.py` + `prototype.py`；25 用例；`docs/PROTOTYPE.md`、`docs/DESIGN_OPTIONS.md` |
| T2.6 存量设计系统采纳/漂移 | **PARTIAL** | token drift 静态检查 DONE；brownfield 采纳/冲突优先级未实现 |
| 组件/状态覆盖矩阵（辅助） | DONE | `component_matrix.py`；8 用例；`docs/COMPONENT_MATRIX.md` |

## 2. 机器验收

```powershell
cd <repo>
$env:PYTHONPATH='runtime'
.\.venv\Scripts\python.exe -m pytest tests -q     # 371 passed
```

## 3. 已知限制

1. 静态发现/漂移检查不是渲染证据；runtime 源恒为 `UNVERIFIED`。
2. token 编译导出（CSS/Tailwind/PySide6）未实现，Stage 2 Exit 前需补或明确延后。
3. 组件矩阵基于源码文本匹配，动态条件状态可能漏检。
4. options/prototype 不执行真实点击；交互验证归 Stage 3。
5. M11/M12/M13 仍 IN_PROGRESS（第三方来源锁、brownfield、独立标注）。

## 4. Stage 2 判定

- T2.1/T2.2/T2.5 与辅助矩阵有可复核证据；T2.3/T2.4/T2.6 为 PARTIAL。
- 因此 **Stage 2 暂不宣称 PASS**；不阻断 Stage 3（真实 UI 探针），缺口登记在 `docs/BLOCKERS.md`。
