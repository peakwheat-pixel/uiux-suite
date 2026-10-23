# 规则冻结与豁免（Stage 1 / T1.0）

## 1. 冻结产物

| 产物 | 路径 | 校验 |
|---|---|---|
| 规则清单 | `knowledge/rules/catalog.v1.0.json` | `rule-catalog.v1.3.3.schema.json` |
| 冻结记录 | `knowledge/rules/catalog.v1.0.freeze.json` | 与清单规范化 SHA256 比对 |
| 豁免契约 | `contracts/rule-exemption.v1.3.3.schema.json` | Schema + 语义（规则存在、未过期、日期顺序） |
| 运行时 | `runtime/uiux_engine/rules.py` | `semantic_problems()` / `verify_frozen()` / `check_exemption()` |

## 2. 当前规则集（20 条）

| 类别 | 规则 |
|---|---|
| COLOR | UX-COLOR-001 对比度不足（FAIL）；UX-COLOR-002 仅颜色编码（WARNING） |
| TYPE | UX-TYPE-001 字号过小；UX-TYPE-002 行高过紧 |
| SPACE | UX-SPACE-001 脱离 token 栅格；UX-SPACE-002 点击目标 <24px（FAIL） |
| FLOW | UX-FLOW-001 不可达节点（FAIL）；UX-FLOW-002 破坏性操作无保护（FAIL）；UX-FLOW-003 空状态缺失；UX-FLOW-004 错误无恢复（FAIL） |
| A11Y | UX-A11Y-001 无可访问名称（FAIL）；UX-A11Y-002 焦点陷阱（FAIL）；UX-A11Y-003 焦点不可见（FAIL）；UX-A11Y-004 标题跳级 |
| GEOM | UX-GEOM-001 裁切（FAIL）；UX-GEOM-002 目标重叠（FAIL） |
| COPY | UX-COPY-001 错误文案无下一步 |
| STATE | UX-STATE-001 加载态缺失；UX-STATE-002 脏状态无提示 |
| MOTION | UX-MOTION-001 未尊重 reduced-motion |

## 3. 使用

```powershell
python -m uiux_engine.cli rules
# {"ok": true, "catalog_version": "1.0", "rules_count": 20,
#  "sha256": "...", "frozen": true, "errors": []}
```

- 退出码：0 有效且冻结一致；10 Schema/语义/冻结不一致。
- 检测器（T1.2–T1.4）必须按 `rule_id` 输出，不得临时造 ID。
- WARNING 规则触发时通过 `WARN_REVIEW_REQUIRED` 处置；豁免不改变 Gate 状态，只避免重复告警。

## 4. 豁免

```json
{
  "rule_id": "UX-SPACE-001",
  "scope": "src/legacy/**",
  "reason": "legacy layout frozen until Q2 migration",
  "owner": "design-system",
  "approved_by": "lead",
  "created_at": "2026-10-01T00:00:00+00:00",
  "expires_at": "2027-01-01T00:00:00+00:00",
  "ticket": "UX-123"
}
```

- `reason` >= 10 字符；必须有审批人与到期时间。
- 过期、未知 rule_id、created_at 晚于 expires_at → 无效（不得静默忽略）。
- 豁免必须进入审计输出（T1.2 linter 的 exemption audit）。

## 5. 变更流程

1. 修改 catalog → 2. 运行 `rules` 校验 → 3. 重算 freeze → 4. 更新 `docs/TASK_PLAN.md` 证据 → 5. 提交同一 commit（catalog + freeze + 测试）。
