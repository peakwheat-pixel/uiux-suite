# 设计系统与 Token 一致性检查（Stage 2 / T2.3 + T2.4）

> 状态：T2.3 token 规范 + T2.4 离线知识库（自建量表）实现。
> 入口：`runtime/uiux_engine/design_system.py`；权威 token：`knowledge/design-system/tokens.v1.0.json`；冻结摘要：`knowledge/design-system/tokens.v1.0.freeze.json`。
> 契约：`contracts/design-tokens.v1.3.3.schema.json`（只读消费，不修改）。
> 依赖：仅标准库 + 本仓 T1.2 静态解析原语（`style_linter`），未新增第三方包。

## 1. 定位与边界

`design_system` 是**只读、确定性、静态筛查器**，回答两个问题：

1. 当前 token 文件是否仍符合 `design-tokens` 契约，且与冻结摘要一致；
2. 源码（CSS/QSS/TSX）中是否存在脱离 token 的硬编码颜色、间距、字号、行高与动效。

边界：

- 只使用 catalog 已冻结的 Rule ID（`UX-SPACE-001`、`UX-TYPE-001/002`、`UX-MOTION-001`）；severity 直接读 `knowledge/rules/catalog.v1.0.json`，本模块不硬编码、不自造。
- 无法映射到上述规则的偏差使用 `dimension`（`color_token` / `font_size_token` / `line_height_token`）并固定 `WARNING`；**不新造 Rule ID**。
- 静态无法判定的事项（未知单位、未解析 `var()`、`calc()`/`clamp()`、渐变、半透明颜色、相对字号）**跳过而不猜测**；"没有输出"表示"静态不可证"，不表示"无风险"。
- 这是 regex / 轻量解析的**筛选**，不是 AST 证明，也不做真实渲染测量（SPEC V1.3.3 §7）。
- 不生成截图、不启动浏览器/Qt、不做 token drift 的 brownfield 差异报告（T2.6）与多方案原型（T2.5）。

## 2. Token 权威与冻结

| 产物 | 路径 | 校验 |
|---|---|---|
| Token 集 | `knowledge/design-system/tokens.v1.0.json` | `contracts/design-tokens.v1.3.3.schema.json` |
| 冻结摘要 | `knowledge/design-system/tokens.v1.0.freeze.json` | 规范化 SHA256 + 计数 + 版本/主题 |
| 运行时 | `runtime/uiux_engine/design_system.py` | `semantic_problems()` / `verify_frozen()` / `lint_*` |

- 冻结摘要 = `contracts.sha256_json(tokens)`（`sort_keys=True` + 紧凑分隔符的规范 JSON），并记录 `colors/spacing/typography/radii/motion` 五组计数、`token_set_version`、`theme`。
- 冻结摘要还记录来源与许可：`source="self-authored"`、`license="internal"`、`font_policy="system fonts only; no bundled font binaries"`。这是 T2.4/M11 的"无法锁定第三方许可则自建量表"路径：**不引入第三方 token 包，不分发字体二进制**。
- token 别名：`colors` 中的语义 token 用 `var(--palette-token)` 引用基础色板（如 `color-text-primary: var(--color-neutral-900)`）。`semantic_problems()` 会解析别名链，未解析引用或循环引用直接报错。
- `theme: "both"`：明暗主题共用一套色板，深色语义 token 以 `-dark` 后缀显式命名（如 `color-bg-canvas-dark`），避免用同名覆盖隐藏主题分支。
- `spacing` 数字按 **px** 解释；字符串支持 `px/rem/em`（token 侧统一按 16px root 折算，文档化近似）。

## 3. Token 表（v1.0）

### 3.1 颜色（34 项）

基础色板（14 项，字面值）：

| Token | 值 | 用途 |
|---|---|---|
| `color-neutral-0` | `#ffffff` | 画布/反白文字 |
| `color-neutral-50` | `#f6f8fa` | 次级背景 |
| `color-neutral-100` | `#eaeef2` | 深色主题正文 |
| `color-neutral-300` | `#d0d7de` | 边框/次级文字（深色） |
| `color-neutral-500` | `#6e7781` | 弱化文字 |
| `color-neutral-700` | `#57606a` | 次级文字 |
| `color-neutral-900` | `#1f2328` | 正文（浅色） |
| `color-neutral-950` | `#0d1117` | 画布（深色） |
| `color-blue-300` | `#54aeff` | 深色主题强调 |
| `color-blue-500` | `#0969da` | 强调/链接 |
| `color-blue-700` | `#0550ae` | 强调 hover |
| `color-green-600` | `#1a7f37` | 成功 |
| `color-red-600` | `#cf222e` | 危险/错误 |
| `color-amber-600` | `#9a6700` | 警告 |

语义别名（20 项，`var()` 引用色板）：`color-text-primary/secondary/muted/on-accent`、`color-bg-canvas/subtle`、`color-border-default/strong`、`color-accent/accent-hover`、`color-success/danger/warning`，以及深色主题的 `color-text-primary-dark/secondary-dark/muted-dark`、`color-bg-canvas-dark/subtle-dark`、`color-border-default-dark`、`color-accent-dark`。

> token-equal 字面值（如源码里写 `#0969da`）与 `var(--color-accent)` 同视为合规；其他字面颜色判为 `color_token` 偏差。

### 3.2 间距（8 项，4px 栅格）

`space-0=0`、`space-1=4`、`space-2=8`、`space-3=12`、`space-4=16`、`space-6=24`、`space-8=32`、`space-12=48`（单位 px）。

### 3.3 字体（8 组）

| Style | fontSize | lineHeight | fontWeight | 用途 |
|---|---|---|---|---|
| `caption` | 12 | 1.4 | 400 | 辅助说明 |
| `label` | 13 | 1.45 | 500 | 控件标签 |
| `body` | 14 | 1.5 | 400 | 正文 |
| `body-lg` | 16 | 1.6 | 400 | 大正文 |
| `heading-3` | 20 | 1.3 | 600 | 三级标题 |
| `heading-2` | 24 | 1.25 | 600 | 二级标题 |
| `heading-1` | 32 | 1.2 | 700 | 一级标题 |
| `mono` | 13 | 1.45 | 400 | 等宽代码 |

字体族使用系统栈并显式包含 CJK：`"Segoe UI", "Microsoft YaHei", "PingFang SC", system-ui, sans-serif`（等宽栈含 `Cascadia Mono`, `Consolas`, `Microsoft YaHei`）。**不随包分发任何字体文件**（m3）。

### 3.4 圆角（5 项）与动效（5 项）

- 圆角：`none=0`、`sm=4`、`md=8`、`lg=12`、`full=999`（px）。当前一致性检查不扫描 `border-radius`（无对应 catalog 规则），仅作为编译/后续 drift 的权威来源。
- 动效：`instant=0ms/linear`、`fast=120ms/ease-out`、`base=200ms/cubic-bezier(0.2, 0, 0, 1)`、`slow=320ms/ease-in-out`、`reduced=0ms/linear`。

## 4. 一致性检查（design_system.py）

### 4.1 公开 API

```python
from uiux_engine import design_system

design_system.load_tokens()                 # 载入 token 集
design_system.token_schema_errors(tokens)   # JSON Schema 错误列表（空 = 合法）
design_system.semantic_problems(tokens)     # schema + 别名语义（空 = 合法）
design_system.freeze_record(tokens)         # 派生冻结摘要
design_system.canonical_digest(tokens)      # 规范化 SHA256
design_system.verify_frozen()               # 与已提交冻结摘要比对（空 = 一致）
design_system.token_index(tokens)           # 扁平 token 记录（token/group/css_var/raw/value/alias/resolved）
design_system.token_scale(tokens)           # 可比较值集合（colors/spacing_px/font_size_px/line_height/motion_ms）
design_system.lint_text(text, file="x.css", stack=None, tokens=None)
design_system.lint_file(path, root=..., stack=None, tokens=None)
design_system.lint_files([...], root=..., stack=None, tokens=None)
design_system.dump_result(result)           # 稳定 JSON（sort_keys + UTF-8 + 末尾换行）
design_system.supported_rules()             # 本模块可输出的 rule_id + catalog severity
design_system.catalog_bindings()            # 绑定冻结 catalog 的问题（空 = 正常）
design_system.dimensions()                  # 可用 dimension 列表
```

输入支持 `.css`/`.qss`（样式表）与 `.tsx`/`.jsx`（仅 `style={{ ... }}` 对象，camelCase → kebab-case）。不支持的后缀/栈直接 `ValueError`，不静默降级。

### 4.2 输出契约（稳定 JSON）

```json
{
  "ok": false,
  "findings": [
    {
      "file": "src/card.css",
      "line": 7,
      "prop": "padding",
      "token": "spacing",
      "expected": "spacing token (0px, 4px, 8px, 12px, 16px, 24px, 32px, 48px)",
      "actual": "13px",
      "severity": "WARNING",
      "rule_id": "UX-SPACE-001",
      "message": "spacing value '13px' is outside the design-token spacing scale for 'padding'"
    }
  ],
  "summary": {"fail": 0, "warning": 1, "info": 0},
  "detector": "design_system_linter",
  "linter_version": "1.0",
  "token_set_version": "1.0",
  "token_sha256": "<64 hex>",
  "dimensions": ["color_token", "font_size_token", "line_height_token"],
  "catalog_version": "1.0",
  "files_checked": ["src/card.css"]
}
```

- 每条 finding **恰好**包含 `rule_id` 或 `dimension` 之一；`token` 取 `colors`/`spacing`/`typography.fontSize`/`typography.lineHeight`/`motion`。
- `actual` 是**解析后**的偏差值（别名已展开），如 `var(--brand-accent)` 会显示 `#ff0000`。
- `ok = findings 为空`；`summary` 按 severity 统计（当前规则均为 WARNING，`fail` 恒为 0）。
- findings 按 `(file, line, id, prop, actual, message)` 稳定排序；同一输入两次运行逐字节一致，无时间戳/随机数。

### 4.3 偏差分级映射

| 偏差 | 输出 ID | severity | 说明 |
|---|---|---|---|
| 硬编码颜色不在 `colors.*` | `dimension="color_token"` | WARNING | catalog 无 color token 规则；用维度，不新造 ID |
| `margin/padding/gap` 不在 `spacing.*` | `rule_id="UX-SPACE-001"` | catalog | 规则语义即"间距脱离 token 栅格" |
| `font-size` 非 token 且 < 12px | `rule_id="UX-TYPE-001"` | catalog | 规则语义为正文过小 |
| `font-size` 非 token 且 >= 12px | `dimension="font_size_token"` | WARNING | 只是 token 漂移，规则不可映射 |
| `line-height` 非 token 且 < 1.3 | `rule_id="UX-TYPE-002"` | catalog | 规则语义为行高过紧 |
| `line-height` 非 token 且 >= 1.3 | `dimension="line_height_token"` | WARNING | 只是 token 漂移，规则不可映射 |
| 动效时长不在 `motion.*` | `rule_id="UX-MOTION-001"` | catalog | catalog 唯一动效规则；message 同时注明 reduced-motion 未验证 |

> 边界：`line-height` 若命中 token（如标题 1.2）则**不**报 `UX-TYPE-002`，因为该值已由设计系统批准；`font-size` 若命中 token（最小 12px）同理。

## 5. 静态近似与保守跳过

- 单位：扫描侧只解析 `px` 与 `rem`（16px root）；`em`/`pt`/`%`/`vw`/`ch` 视为未知跳过（`em` 依赖上下文）。
- `var()`：支持 token 别名、CSS 自定义属性（文件内全局，后者覆盖同名 token 变量）以及 `var(--x, fallback)`；解析后仍含 `var(` 即跳过。
- 颜色：仅解析 `#rgb/#rrggbb`、`rgb()/rgba()`（alpha < 1 跳过）与有限命名色；渐变、`url()`、`color-mix()`、`currentColor` 等跳过；每个属性只取第一个可解析颜色（多色 shorthand 的其余颜色不单独判定）。
- 间距：`calc()/clamp()/min()/max()` 与百分比整体跳过；`0` 与负值（光学微调）不告警。
- 行高：支持 unitless/`em`/`%`；`px` 需同规则块有可解析 `font-size`；其余跳过。
- 动效：取第一个时长（`ms`/`s`）；`0`/`none` 视为无动效；shorthand 中第二个时长（可能是 delay）不单独判定；easing 不判定。
- TSX：每个 `style={{ ... }}` 统一取对象起始行号为 finding 行号，不做 JSX AST 证明。
- 自定义属性定义（`--x: ...`）本身不扫描，只在被 `var()` 使用时参与解析。

## 6. Fixtures 与冻结预期

```text
tests/fixtures/design_system/
├── cases.v1.0.json                 # 冻结预期：file/stack/case_kind/expected[{line, rule_id|dimension}]
├── positive/web-tokens.css         # 合规：var() 别名 + token 字面值 + 0.5rem
├── positive/qt-theme.qss           # 合规：QSS token 等值字面值
├── positive/tsx-theme.tsx          # 合规：TSX inline style token 引用
├── positive/unknown-values.css     # 合规：未知值保守跳过（hsl/rgba/calc/em/normal/未定义 var）
├── negative/web-deviations.css     # 反样本：颜色/间距/字号/行高/动效 7 条偏差
├── negative/qt-hardcoded.qss       # 反样本：QSS 颜色 ×2 + 间距 ×1
├── negative/tsx-inline.tsx         # 反样本：TSX 同一行 5 条偏差
└── negative/local-alias.css        # 反样本：本地 var 别名绕过 token（颜色 + 间距）
```

- `case_kind="compliant"`（4 个）：必须 **0 findings**；`case_kind="violation"`（4 个）：必须与 `expected` 的 `(id, line)` **精确一致**，既不能漏也不能多。
- 反样本覆盖全部 4 个 Rule ID 与全部 3 个 dimension；正样本覆盖 CSS/QSS/TSX 三种输入与别名、字面值、未知跳过。

## 7. 测试

```powershell
$env:PYTHONPATH='runtime'
.venv\Scripts\python.exe -m pytest tests/unit/test_design_system.py -q
```

覆盖：schema 合法、五组 token 与 CJK 字体栈、冻结摘要与篡改检测、别名解析/循环/悬空引用、catalog 绑定与 severity 来源、正样本零偏差、反样本精确匹配、finding 字段与行号、token-equal 字面值、local `var()` 解析、未知值跳过、间距/字号/行高/动效边界、TSX 行号、QSS 栈、非法 token/后缀/栈拒绝、确定性、聚合排序与元数据。

## 8. 已知限制与风险

1. **静态筛查 ≠ 渲染证据**：不检测真实像素、字体、DPI、层叠/继承后的最终颜色；动态 class、条件样式、跨文件继承无法静态确认（与 T1.2 一致）。
2. **动效映射是"最接近的 catalog 规则"**：catalog 没有"动效脱离 token"规则，按任务约定将非 token 时长映射到 `UX-MOTION-001`，message 明确注明 reduced-motion 未验证；独立 Reviewer 若要求严格语义，需要 catalog 增补规则或改用 dimension。
3. **颜色只取每个声明中的第一个可解析颜色**：多色 `box-shadow`/渐变中的后续颜色不会被单独判定，可能漏报（保守方向）。
4. **单位近似**：`rem` 按 16px root 折算；`em/pt/%` 一律跳过，因此相对单位项目可能少报。
5. **TSX 行号是对象起始行**，不是属性行；仅做 `style={{}}` 字面量筛查，不做 JSX/模板 AST。
6. **未实现 token 编译器**（CSS/Tailwind/PySide6 导出）：本任务只交付 token 规范与一致性检查；Stage 2 Exit 要求的 "Web/Qt Token 可运行" 仍需 T2.5/后续编译导出与真机验证。
7. **未实现 brownfield drift 报告**（T2.6/M12）：`design_system` 提供值级偏差原语，但存量组件盘点→映射→差异清单流程不在本任务。
8. **规则集不含 `border-radius` 检查**：圆角 token 只有权威来源，暂无偏差分级（catalog 无对应规则，用 dimension 需任务另行约定）。

## 9. 变更流程

1. 修改 `tokens.v1.0.json` → 2. `semantic_problems()` 必须为空 → 3. 重算并更新 `tokens.v1.0.freeze.json`（`verify_frozen()` 为空）→ 4. 更新 fixtures 预期与 `docs/DESIGN_SYSTEM.md` → 5. 跑 `tests/unit/test_design_system.py` 与全量测试 → 6. 同一提交内包含 token、freeze、fixtures 与测试。
