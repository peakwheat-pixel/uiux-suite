# Style Token Linter（Stage 1 / T1.2）

> 状态：T1.2 实现 + T1.1 双栈靶场（`web` / `qt`）。
> 入口：`runtime/uiux_engine/style_linter.py`；测试：`tests/unit/test_style_linter.py`。
> 依赖：仅 Python 标准库（`re` / `html.parser` / `pathlib` 等），未新增第三方包。

## 1. 定位与边界

`style_token_linter` 是**只读、确定性、静态筛查器**：对 CSS/QSS 文本以及可选的 HTML/TSX 片段做轻量解析，输出与冻结规则目录（`knowledge/rules/catalog.v1.0.json`）对齐的 findings。

- 只使用 catalog 中已冻结的 Rule ID；**severity 直接读 catalog，不在此模块内硬编码或自造**。
- 规则 ID 或路径不在冻结目录时直接抛错（`KeyError` / `ValueError`），不会静默编造。
- 静态无法判定的事项（如未知背景色、动态 class、无法解析的颜色/单位）**跳过而不猜测**；"没有输出"表示"静态不可证"，不表示"无风险"。
- 这是 regex / 轻量解析的**筛选**，不宣称 AST 证明（符合 SPEC V1.3.3 §7）。
- 不生成截图、不启动浏览器/Qt、不做真实渲染测量。像素级对比度、裁切、目标尺寸分别属于 `layout_geometry_probe` / `accessibility_checker` 的路线。

## 2. 输入

| 输入 | 说明 |
|---|---|
| CSS 文本 | `.css`，完整样式表；支持注释、`@media`/`@supports` 嵌套、CSS 自定义属性 `var()`（最多解析 5 层） |
| QSS 文本 | `.qss`，与 CSS 共用声明解析；QSS 不支持 `outline`/`line-height`/动画，因此这些规则在 QSS 上通常不会命中 |
| HTML | `.html` / `.htm`：解析 `<style>` 块与元素 `style` 属性，并执行无障碍/文案/标题检查 |
| TSX | `.tsx` / `.jsx`：只扫描 `style={{ ... }}` 对象字面量，不做 JSX AST 证明、不做无障碍检查 |
| 内联片段 | `lint_text(text, file=..., stack=...)`，`file` 后缀决定解析模式 |

公开 API：

```python
from uiux_engine import style_linter

style_linter.lint_text(text, file="widget.css", stack="web", exemptions=[...], now=...)
style_linter.lint_file(path, root=repo_root, exemptions=[...], now=...)
style_linter.lint_files([path_a, path_b], root=repo_root, exemptions=[...], now=...)
style_linter.dump_result(result)      # 稳定 JSON（sort_keys + UTF-8 + 末尾换行）
style_linter.supported_rules()        # 本 linter 可输出的 rule_id / catalog severity
style_linter.catalog_bindings()       # 绑定冻结 catalog 的问题列表（空 = 正常）
```

`lint_files` 在一轮内聚合多个文件，**豁免只应用一次**；`files_checked`、`summary`、`exemptions_applied` 为整轮结果。

## 3. 输出契约（稳定 JSON）

```json
{
  "ok": true,
  "findings": [
    {
      "rule_id": "UX-SPACE-001",
      "severity": "WARNING",
      "file": "tests/fixtures/ground_truth/web/positive/spacing.css",
      "line": 2,
      "message": "spacing value '13px' is outside the 4px token grid for selector '.card'"
    }
  ],
  "summary": {"fail": 0, "warning": 1, "info": 0},
  "exemptions_applied": [],
  "linter_version": "1.0",
  "detector": "style_token_linter",
  "catalog_version": "1.0",
  "files_checked": ["tests/fixtures/ground_truth/web/positive/spacing.css"]
}
```

- `ok`：`summary.fail == 0`（WARNING/INFO 不使 `ok=false`）。
- `findings`：按 `(file, line, rule_id, message, evidence_ref)` 稳定排序；每条必含 `rule_id/severity/file/line/message`，HTML 无障碍 finding 可带 `evidence_ref`（如 `<button>`）。
- `summary`：分别统计 `fail` / `warning` / `info`，key 固定。
- `severity`：只能取 catalog 的 `FAIL | WARNING | INFO`；跨层映射不是本模块职责。
- `exemptions_applied`：**审计记录**，见 §5；即使豁免未生效也会出现。
- 输出不做时间戳/随机数；同一输入两次运行结果逐字节一致。

## 4. 规则覆盖（10 条，全部来自冻结 catalog）

| Rule ID | catalog severity | 静态检测点 | 典型样本 |
|---|---|---|---|
| `UX-COLOR-001` | FAIL | 同一规则块内可解析的 `color` + `background(-color)`，按 WCAG 2.2 AA 计算对比度（常规 4.5:1，大字 3:1）；未知背景/渐变/透明跳过 | `web/positive/contrast.css`、`qt/positive/contrast.qss` |
| `UX-COLOR-002` | WARNING | 选择器含 error/danger/invalid/warning/success 等状态词，且该块只声明颜色类属性（无图标/文本/形状/边框等非颜色线索） | `web/positive/color_only.css`、`qt/positive/color_only.qss` |
| `UX-TYPE-001` | WARNING | `font-size` 折算后 < 12px（px/pt/rem/em，按 16px root 近似） | `web/positive/typography.css`、`qt/positive/type_spacing.qss` |
| `UX-TYPE-002` | WARNING | 行高比 < 1.3（unitless / em / %，或与同块 `font-size` 可折算的 px） | `web/positive/typography.css` |
| `UX-SPACE-001` | WARNING | `margin` / `padding` / `gap` 等间距值不在 4px token 栅格；`var()`/`calc()`/百分比/auto/负值跳过 | `web/positive/spacing.css`、`qt/positive/type_spacing.qss` |
| `UX-A11Y-001` | FAIL | 可交互元素（button/a/input/select/textarea/role）无可访问名称（可见文本、aria-label、aria-labelledby、label、title、value/alt 等） | `web/positive/a11y.html` |
| `UX-A11Y-003` | FAIL | `outline: none/0` 且无同块或全文件的可见 focus 替代（`box-shadow` / border / 其他 outline） | `web/positive/focus.css` |
| `UX-A11Y-004` | WARNING | 标题层级跳跃（如 h1→h3），仅比较出现顺序，不要求首个标题必须是 h1 | `web/positive/a11y.html` |
| `UX-COPY-001` | WARNING | error/role=alert 文案无"下一步"动作词（重试/检查/联系/修改/返回……） | `web/positive/a11y.html` |
| `UX-MOTION-001` | WARNING | 存在非零时长 `animation` / `transition`，且文件无 `prefers-reduced-motion: reduce` 守卫（守卫块内 `none` / `0s` / `0.01ms`） | `web/positive/motion.css` |

说明：catalog 中 `UX-COLOR-001/002`、`UX-A11Y-001/003/004` 的 `detector` 字段归属 `accessibility_checker`。本 linter 覆盖其**确定性静态子集**，仍使用 catalog 原 Rule ID 与原 severity，便于下游 Gate 只消费一个 ID 空间；其他动态/渲染态检测仍由 `accessibility_checker` 负责。

### 判定阈值与近似

- 对比度：sRGB 相对亮度公式；`#rgb/#rrggbb`、`rgb()/rgba()`（alpha < 1 跳过）、有限命名色；`!important` 忽略。
- 字号：`px` 精确；`pt × 4/3`；`rem/em × 16`（近似，文档化）；`%`/`calc()`/`clamp()` 跳过。
- 行高：unitless / `em` / `%` 直接取比值；`px` 需同块有可折算 `font-size`；其余跳过。
- 间距：4px 栅格（4/8/12…）；`0` 合法；负值视为光学微调而跳过。
- 动效：时长解析 `ms`/`s`；`transition-delay` 不视为动效本身。
- TSX 对象：camelCase → kebab-case；数值字面量对非 unitless 属性补 `px`；模板字符串/函数调用跳过。

## 5. 豁免（rule-exemption）与审计

豁免必须符合 `contracts/rule-exemption.v1.3.3.schema.json`，并满足 `runtime/uiux_engine/rules.py:check_exemption()` 的语义：

1. 只对 **WARNING** severity 生效；`FAIL` 规则即使豁免格式合法也会被拒绝（硬失败不可静默消除）。
2. 未知 `rule_id`、过期/未生效、`created_at > expires_at`、Schema 非法 → **不生效**。
3. `scope` 是相对 locator glob，对 finding 的相对 `file` 匹配；支持 `**`、`*`、`?`。
4. 每次运行都会把每条豁免写入 `exemptions_applied`，状态为 `applied` / `unused` / `rejected`，并附 `problems`、`suppressed_count`、`suppressed[{file,line,rule_id}]`、审批信息；**审计不会因为豁免无效而消失**。
5. 豁免只减少重复告警，不改变 Gate 状态（与 `docs/RULES.md` 一致）。

示例：

```json
{
  "rule_id": "UX-SPACE-001",
  "scope": "tests/fixtures/ground_truth/web/positive/spacing.css",
  "reason": "legacy layout frozen until Q2 migration",
  "owner": "design-system",
  "approved_by": "lead",
  "created_at": "2026-10-01T00:00:00+00:00",
  "expires_at": "2027-01-01T00:00:00+00:00",
  "ticket": "UX-123"
}
```

```python
result = style_linter.lint_file(
    path,
    exemptions=[exemption],
    now=parse_time("2026-10-24T00:00:00+00:00"),  # 可复现的时点
)
```

## 6. T1.1 双栈靶场与冻结 GT

```text
tests/fixtures/ground_truth/
├── web/positive/   # contrast / typography / spacing / focus / motion / color_only / a11y / inline_style / tsx_inline
├── web/negative/   # tokens / focus_replacement / a11y / inline_style
├── qt/positive/    # contrast.qss / type_spacing.qss / color_only.qss
├── qt/negative/    # tokens.qss / state_cue.qss
└── annotations/    # 每个 fixture 一个 GT JSON（含 env、标注方法、expected[rule_id,line,severity]）
```

- 正样本（`case_kind=positive`）必须**精确命中** `expected`（既不能漏，也不能多）；负样本（`negative`）必须 `findings=[]`。
- `annotations/*.json` 是冻结标注记录，字段：
  `schema_version`、`fixture`、`stack`、`case_kind`、`environment`（host/python/renderer/`runtime_evidence_level`）、`annotation`（标注者/方法/是否独立/冻结时间）、`expected`、`notes`。
- 当前为**同会话人工标注**（`annotation.independent=false`），不冒充独立标注；独立复核记录留给 T1.7 / Reviewer。
- 当前样本为静态源码样本，未附真实截图；截图/渲染测量属于 T1.4 geometry probe 的证据路径，不在此重复伪造。

## 7. 测试

```powershell
$env:PYTHONPATH='runtime'
.venv\Scripts\python.exe -m pytest tests/unit/test_style_linter.py -q
```

覆盖：全部 fixture GT（正/反）、输出结构与稳定排序、severity 只来自 catalog、WARNING 豁免生效 + 审计、过期豁免、未知规则豁免、FAIL 不可豁免、scope 不匹配、`**` glob、QSS、HTML 内联、TSX style、聚合 `lint_files`、未知 stack 拒绝。

## 8. 已知限制与后续（未决风险）

1. **静态筛查 ≠ 渲染证据**：不检测真实像素、字体、DPI、层叠/继承后的最终颜色；需要动态检测时仍走 accessibility/geometry 路线。
2. **QSS 限制**：Qt 的 focus 指示通常通过 `border` 而非 `outline`，QSS 也不支持 `line-height`/CSS 动画；因此 `UX-A11Y-003`、`UX-TYPE-002`、`UX-MOTION-001` 在 QSS 上静态不可判，需 Qt 原生测量（T1.4 / Stage 3）。
3. **近似**：`em` 字号按 16px、行高归属同块、TSX 每个 `style={{}}` 统一取其起始行；动态 class/条件样式无法静态确认。
4. **颜色解析**：渐变、透明、叠加 alpha、无法解析的命名色、跨选择器继承的背景都按"未知"跳过（保守，避免硬 FAIL 误报）。
5. **无截图/无独立标注**：T1.1 验收中的"截图 + 独立标注"尚未闭环，需 T1.4/T1.7 或 Reviewer 补齐；本文件与 annotations 中如实标记 `SIMULATED` / `independent=false`。
6. **HTML 解析**：基于 `html.parser` 的容错解析，不覆盖自定义模板语法/JSX 无障碍语义；仅保证测试靶场与简单片段。
7. 正则/轻量解析无法证明"没有违规"；对未知项目不承诺 100% 检出（与 SPEC Stage 1 验收一致）。
