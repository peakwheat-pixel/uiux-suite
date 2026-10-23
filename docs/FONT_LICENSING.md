# 字体许可与 CJK 分发（m3）

- 本发行包**不捆绑任何字体文件**；Qt/PySide6 使用操作系统已安装字体。
- 证据中的 CJK 检测使用本机 `Microsoft YaHei`/`Microsoft YaHei UI`，仅记录存在性，不分发字体。
- Web/Tailwind 产物只输出 CSS 字体族名，不嵌入 webfont；使用者需自行确认字体许可。
- 若未来引入开源 CJK 字体（如 Noto Sans CJK，SIL OFL 1.1），必须记录来源、版本、许可证与校验和，并加入 `knowledge/index.v1.0.json`。
- 第三方组件许可清单见 `THIRD_PARTY_NOTICES.md`。