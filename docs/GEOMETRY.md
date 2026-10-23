# layout_geometry_probe（Stage 1 / T1.4，测量 JSON 模式）

> 状态：Stage 1 交付（离屏/测量模式）。
> 运行时等级：**SIMULATED**（测量 JSON 输入）。
> 真实 GUI 探针（Web DOM 实机 / Qt Offscreen / UIA）属 Stage 3（T3.3），本模块不实现、不冒充。

## 1. 目标与边界

本模块实现冻结规则目录（`knowledge/rules/catalog.v1.0.json`）中 `layout_geometry_probe` 负责的确定性几何检测：

| Rule ID | 严重度 | 检测内容 | catalog detector |
|---|---|---|---|
| `UX-SPACE-002` | FAIL | 交互目标小于 24x24 CSS px | `layout_geometry_probe` |
| `UX-GEOM-001` | FAIL | 文本/关键控件被裁切、溢出或不可见 | `layout_geometry_probe` |
| `UX-GEOM-002` | FAIL | 两个交互目标重叠 | `layout_geometry_probe` |
| `UX-COLOR-001` | FAIL | 正文对比度低于 WCAG 2.2 AA（测量模式实现） | `accessibility_checker` |
| `UX-A11Y-003` | FAIL | 键盘焦点不可见或焦点环对比度 < 3:1（测量模式实现） | `accessibility_checker` |

约束：

- Rule ID 只能来自冻结 catalog，`severity` 从 catalog 读取，不硬编码、不新造 ID。
- 输入必须是**测量 JSON**，不是真实 GUI 会话。无法用测量 JSON 证明的部分（真实渲染、字体度量、绘制顺序、遮挡、透明度叠加）不在本模块承诺范围内。
- 合法负样本零硬 FAIL 是 Stage 1 退出条件；误报控制见 §4。

## 2. SIMULATED 声明（不可升级）

- 输出恒为 `"runtime_level": "SIMULATED"`、`"mode": "measurement_json"`、`"probe_id": "layout_geometry_probe"`。
- 即使输入文档自带 `"runtime_level": "NATIVE_APP"` 或原生测量来源字段，本模块也**忽略**该声明，绝不把测量 JSON 抬升为 `NATIVE_APP` 证据（`contracts/enums.v1.3.3.json` 的 `RuntimeEvidenceLevel` 序关系：SIMULATED 不得支撑 Native 结论）。
- 需要 NATIVE 证据时必须由 Stage 3 的真实探针产出 tool-log/截图，本模块输出不得作为其替代。

## 3. 输入契约

```json
{
  "name": "optional sample name",
  "runtime_level": "optional, ignored",
  "viewport": {"w": 1280, "h": 800},
  "background": "#ffffff",
  "elements": [
    {
      "id": "save-button",
      "role": "button",
      "rect": {"x": 40, "y": 132, "w": 88, "h": 32},
      "text": "保存",
      "interactive": true,
      "parentId": "toolbar",
      "styles": {
        "fontSize": 14,
        "lineHeight": 20,
        "fontWeight": 700,
        "color": "#ffffff",
        "bgColor": "#1d4ed8",
        "focusVisible": true,
        "focusColor": "#1d4ed8"
      },
      "overflow": {
        "scrollWidth": 180,
        "clientWidth": 88,
        "scrollHeight": 32,
        "clientHeight": 32,
        "hidden": false,
        "clipped": false,
        "scrollable": false,
        "ellipsis": false
      }
    }
  ]
}
```

字段语义：

- `viewport`：必填，`w/h` > 0；仅校验与回显（Stage 3 截图交叉核对使用）。
- `background`：可选，画布背景色，默认 `#ffffff`；作为背景继承链的兜底。
- `elements[]`：
  - `id`：必填，非空且唯一。
  - `role`：必填字符串；`interactive` 只认显式布尔值（默认 `false`），不从 role 推断。
  - `rect`：必填，`x/y` 任意有限数，`w/h` >= 0，单位 CSS px，原点为视口左上角。
  - `text`：可选，元素可见文本；用于对比度与文本裁切判定。
  - `parentId`：可选，父元素引用；用于背景继承与裁剪容器判定；必须存在、不得自引用、不得成环。
  - `styles`（严格白名单，未知键报错）：
    - `fontSize` / `lineHeight`：> 0，单位 CSS px（注意 `lineHeight` 不是无单位倍数）。
    - `fontWeight`：1..1000，默认 400；>= 700 视为粗体。
    - `color` / `bgColor` / `focusColor`：`#rgb`、`#rrggbb` 或 `rgb(r, g, b)`；alpha 通道不支持（`rgba()` 报错）。
    - `focusVisible`：布尔，仅对 `interactive: true` 生效。
  - `overflow`（严格白名单，未知键报错）：
    - `scrollWidth/clientWidth/scrollHeight/clientHeight`：测量值；成对出现才做对应轴向溢出判定。
    - `hidden: true`：该元素是裁剪容器，对其直接子元素做包含性检查。
    - `clipped: true`：测量工具已直接判定裁切。
    - `scrollable: true`：合法滚动区域，抑制自身溢出判定。
    - `ellipsis: true`：合法省略号截断（SPEC §7 允许的 ellipsis 例外），仅抑制水平溢出判定。

非法输入（缺字段、类型错误、重复 id、悬空/环形 `parentId`、未知 `styles`/`overflow` 键、不支持的颜色）统一抛 `MeasurementError`（`ValueError` 子类），不静默放过。

## 4. 判定规则与误报控制

| 规则 | 触发条件 | 合法负样本（不得误报） |
|---|---|---|
| `UX-SPACE-002` | `interactive` 且 `w < 24` 或 `h < 24` | `24x24` 恰好达标；非交互元素（图标/装饰）不检查 |
| `UX-GEOM-001` | 内容元素（有文本或可交互）满足任一：`overflow.clipped`；`scrollWidth - clientWidth > 0.5`（未声明 ellipsis/scrollable）；`scrollHeight - clientHeight > 0.5`（未声明 scrollable）；`overflow.hidden` 祖先未完全包含该元素；文本盒面积接近 0 或高度 < `lineHeight - 0.5` | 子元素完全位于裁剪祖先内；`overflow` 指标相等；`ellipsis`/`scrollable` 例外；纯装饰元素不判定 |
| `UX-GEOM-002` | 两个 `interactive` 元素矩形相交且交集宽、高均 > 0.5 px | 边缘相邻（交集为 0）；亚像素舍入（<= 0.5 px）；完全嵌套的交互目标（视为有意组合） |
| `UX-COLOR-001` | 有文本、有 `color`；有效背景取自身 → 祖先 → 画布；对比度（四舍五入 2 位）< 4.5:1（普通文本）或 < 3:1（大字） | 大字：`fontSize >= 24px`，或 `fontSize >= 18.66px` 且 `fontWeight >= 700`；无文本/无颜色信息不判定 |
| `UX-A11Y-003` | `interactive` 且 `focusVisible: false`；或 `focusVisible: true` 且给出 `focusColor`、焦点环与**祖先背景**对比度（四舍五入）< 3:1 | 非交互元素；未提供任何焦点信息；焦点环对比度达标 |

补充约定：

- 几何容差统一 0.5 CSS px（子像素/布局舍入），对比度按四舍五入到 2 位小数后与阈值比较。
- 焦点环画在元素盒外，因此与**祖先背景**比较（元素自身 `bgColor` 不参与），属文档化的近似。
- 重叠对只报一次，`element_id` / `related_element_id` 按字典序稳定输出。
- `UX-COLOR-001` / `UX-A11Y-003` 在 catalog 中归属 `accessibility_checker`；本模块只在其可被静态测量覆盖的子集上报告，不改变规则归属。

## 5. 输出契约

```json
{
  "ok": false,
  "probe_id": "layout_geometry_probe",
  "mode": "measurement_json",
  "runtime_level": "SIMULATED",
  "viewport": {"w": 1280, "h": 800},
  "findings": [
    {
      "rule_id": "UX-GEOM-001",
      "severity": "FAIL",
      "element_id": "clipped-label",
      "message": "content width 260 exceeds box width 180",
      "evidence": {"role": "text", "rect": {"x": 16, "y": 80, "w": 180, "h": 20}, "reasons": ["..."]}
    }
  ],
  "summary": {
    "fail": 1,
    "warning": 0,
    "info": 0,
    "elements": 16,
    "interactive_elements": 5,
    "rules_evaluated": [
      "UX-SPACE-002",
      "UX-GEOM-001",
      "UX-GEOM-002",
      "UX-COLOR-001",
      "UX-A11Y-003"
    ]
  }
}
```

- `ok`：无 FAIL finding 时为 `true`。
- findings 按 `(rule_id, element_id, related_element_id, message)` 稳定排序；`severity` 一律来自 catalog。
- 重叠 finding 额外带 `related_element_id`。

## 6. Fixtures 与测试

| 样本 | 用途 | 预期 FAIL |
|---|---|---|
| `tests/fixtures/geometry/clean-measurement.json` | 合法负样本：包含子元素、相邻目标、24x24 边界、合法 ellipsis/scrollable、大字对比度 | 0 |
| `tests/fixtures/geometry/clipped-overlap-measurement.json` | 溢出/祖先裁切/显式裁切 + 目标重叠 + 过小目标 + 焦点不可见 | 6 |
| `tests/fixtures/geometry/low-contrast-measurement.json` | 普通文本对比度不足、背景继承、`rgb()`/`#rgb` 解析；大字/粗体合法负样本 | 6 |
| `tests/fixtures/geometry/focus-measurement.json` | 焦点不可见/焦点环对比度不足/目标过小；24x24 边界、深色祖先焦点环 | 3 |

每个 `*-measurement.json` 都有同名 `.gt.json` 冻结 GT（期望 findings、FAIL 计数、`must_not_match`）。

测试命令（Windows）：

```powershell
$env:PYTHONPATH='runtime'; .venv\Scripts\python.exe -m pytest tests/unit/test_geometry.py -q
```

覆盖：颜色解析、WCAG 相对亮度/对比度、大字阈值、四条样本 GT、合法负样本零 FAIL、包含/相邻/嵌套/亚像素边界、目标尺寸边界、焦点信息门槛、背景继承、确定性排序、非法输入、catalog 冻结一致性。

## 7. 已知限制（诚实声明）

- 测量 JSON 无法自证真实渲染：不得据此声称 NATIVE 或"已检 100%"。浮层、Canvas、badge、合法 ellipsis 等场景需测量方按 §3 的 `overflow` 语义标注，否则可能漏报或需人工复核。
- 不支持 alpha 合成、渐变背景、半透明前景；此类颜色应按有效不透明色由测量方折算，或视为未覆盖。
- 重叠判定不建模 z-index/绘制顺序与遮挡（静态矩形无关顺序）。
- 焦点环仅比较颜色对比，不判断环厚度/样式是否足够可见。
- 这些缺口不在 Stage 1 承诺内；Stage 3 由真实 DOM/UIA 探针 + 截图证据补齐，并进入 T1.7 混淆矩阵统计。
