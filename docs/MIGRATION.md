# 迁移与回退（m5）

## 从 V1.3.2 升级
1. 备份 `SPEC_V1.3.2.md`（不可变基线）与现有安装目录。
2. 解压 V1.3.3 ZIP，执行 `python scripts/setup_skill.py --host dsh install --scope user --source .`。
3. 运行 `launch.py doctor --scope user`，确认双入口与依赖。
4. 旧版本保留在 `versions/<ver>/`；回退使用 `rollback` 或重新激活旧版本。

## 卸载
`python scripts/uninstall_skill.py --host dsh --scope user`；不删除用户项目与未知同名 Skill。

## 数据兼容
契约版本 `1.3.3`；旧证据需重新采集，禁止把旧 PASS 直接迁移到新 Gate。