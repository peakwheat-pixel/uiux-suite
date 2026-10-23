# 延迟/性能预算（m8）

| 项目 | 预算 | 说明 |
|---|---:|---|
| 单文件 style/design 扫描 | < 150 ms | 典型 TSX/CSS |
| 100 文件扫描 | < 3 s | 本地 SSD |
| 全套 pytest | < 60 s | 当前约 29 s |
| 发行包构建+验证 | < 120 s | 含安装/doctor |
| Qt QPA 3 缩放采集 | < 60 s | 含截图 |

测量脚本：`scripts/measure_performance.py`，证据写入 `evidence/T1.0/performance-budget.json`。超预算只记录为 WARNING，不改变 Gate；真实大规模项目需单独基准。

当前小样本实测：10 文件扫描约 4 ms、token CSS 编译 <1 ms、合成应用 discovery <1 ms。对隔离的 New Manga 源码副本可设置 `UIUX_DISCOVERY_ROOT` 复测（约 0.75 s）。