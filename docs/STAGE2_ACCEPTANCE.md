# Stage 2 验收记录（V1.3.3）

## 任务状态

| 任务 | 状态 | 证据 |
|---|---|---|
| T2.1 页面/窗口/路由识别与三源能力比对 | **DONE** | `discovery.py`；13 用例；`docs/DISCOVERY.md` |
| T2.2 flows 设计与状态推导 | **DONE** | `flows_from_discovery()`；schema 合法 |
| T2.3 DTCG Token 与 CSS/Tailwind/PySide6 编译器 | **DONE** | `token_compiler.py`；7 用例；CLI `tokens` |
| T2.4 离线知识库与合规来源 | **DONE** | `knowledge/index.v1.0.json` + `knowledge-index` schema；7 用例；CLI `knowledge` |
| T2.5 design-only 与 prototype（≥2 方案） | **DONE** | `options.py` + `prototype.py`；25 用例 |
| T2.6 存量设计系统采纳/漂移 | **DONE** | `design_system.py` + `brownfield.py`；8 用例 |
| 组件/状态覆盖矩阵（辅助） | DONE | `component_matrix.py`；8 用例 |

## 机器验收

```powershell
$env:PYTHONPATH='runtime'; .venv\Scripts\python.exe -m pytest tests -q   # 448 passed
```

## 限制

- 静态发现/漂移检查不是渲染证据；runtime 源恒为 `UNVERIFIED`。
- 设计系统 token 编译产物需真实 UI 验证（T3.3 已做 Qt QPA，Web/Tailwind 产物未在真实浏览器执行）。
- 组件矩阵基于源码文本匹配，动态条件状态可能漏检。
- WCAG 仅作为引用条目（license=unknown），未打包内容。

## Stage 2 判定

**DONE**：T2.1–T2.6、M11、M12 均有可复核测试或证据；限制已声明。