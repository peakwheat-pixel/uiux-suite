# 第三方依赖与许可证（V1.3.3）

本包不随发行分发第三方源码或字体；运行时通过 Python 依赖使用以下组件。
版本固定见 `requirements.txt`、`requirements-dev.txt` 与 `requirements.lock`。

| 组件 | 版本（本机实测） | 许可证 | 来源 | 用途 |
|---|---|---|---|---|
| jsonschema | 4.23.0 / 4.26.0（兼容） | MIT | <https://github.com/python-jsonschema/jsonschema> | JSON Schema 2020-12 校验 |
| jsonschema-specifications | 2025.9.1 | MIT | <https://github.com/python-jsonschema/jsonschema-specifications> | 元 schema |
| referencing | 0.37.0 | MIT | <https://github.com/python-jsonschema/referencing> | `$ref` 注册表 |
| rpds-py | 2026.9.1 | MIT | <https://github.com/crate-py/rpds> | 不可变集合（jsonschema 依赖） |
| attrs | 26.1.0 | MIT | <https://github.com/python-attrs/attrs> | jsonschema 依赖 |
| typing_extensions | 4.16.0 | PSF-2.0 | <https://github.com/python/typing_extensions> | 类型兼容 |
| pytest（仅开发/测试） | 8.3.4 / 9.1.1（兼容） | MIT | <https://github.com/pytest-dev/pytest> | 测试运行 |
| pluggy（仅开发/测试） | 1.7.0 | MIT | <https://github.com/pytest-dev/pluggy> | pytest 插件 |
| iniconfig（仅开发/测试） | 2.3.1 | MIT | <https://github.com/pytest-dev/iniconfig> | pytest 配置 |
| packaging（仅开发/测试） | 26.3 | Apache-2.0 / BSD | <https://github.com/pypa/packaging> | 版本/I 依赖 |
| colorama（仅开发/测试） | 0.4.6 | BSD-3-Clause | <https://github.com/tartley/colorama> | Windows 终端颜色 |

## 字体

- 不随包分发任何字体文件。
- 设计/原型如使用 CJK 字体，默认引用系统字体（如 Microsoft YaHei、Noto Sans CJK），需在项目内自行核查许可。
- 若后续引入第三方字体，必须在本文件登记来源、许可与分发范围，未授权字体不得打包。

## 离线安装

- `requirements.txt` / `requirements-dev.txt` 固定版本；`requirements.lock` 为当前验证环境的完整锁定。
- 离线环境需预置对应 wheel（Stage 5 打包时纳入 `dist/wheels/`）；本轮尚未附带 wheel 缓存，登记为 T0.5 剩余项。
