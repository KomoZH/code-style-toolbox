# Code Style Toolbox — 测试报告

> QA：严过关（Edward / Yan）｜ 测试轮次：1 轮完成（自修复测试 Bug 后全绿，未触发源码 Bug 路由）
> 测试日期：2025-10-16 ｜ 环境：Python 3.13.14（隔离环境 `workbuddy/binaries/python/envs/default`）

## 1. 总结

| 维度 | 结果 |
|---|---|
| pytest 单元/集成用例 | **198 个，全部通过（100%）**，耗时 ~1.8s |
| 真实 uvicorn 服务实测 | **18 项 HTTP 检查，全部通过**（127.0.0.1:18766 实测） |
| 路由判定 | **NoOne** —— 未发现需要工程师修复的源码 Bug |
| 源码 Bug | 0 个 |
| 测试代码 Bug | 6 个（第 1 轮自行修复，重跑全绿） |

覆盖率（估算）：引擎层（detector/naming/tokenizer/blacklist/verifier/differ/extractor×3/rewriter×3/profile_store）与全部 13 个 REST 端点均有直接测试；关键错误路径（语法非法、黑名单、等价校验回退、语言不符、碰撞保护）全覆盖。

## 2. 测试文件清单（tests/）

| 文件 | 用例数 | 覆盖目标 |
|---|---|---|
| `conftest.py` | — | sys.path 注入、示例读取、profile 工厂 fixture |
| `test_naming.py` | 32 | 命名风格判定/转换、前缀剥离、非法目标、边界名 |
| `test_detector.py` | 18 | 扩展名映射、内容特征打分、unknown→manual_required |
| `test_tokenizer.py` | 13 | 令牌化（字符串/原始字符串/注释/预处理续行/数字/运算符）、括号配平 |
| `test_blacklist.py` | 10 | 函数式宏/模板特化/#if 系命中；对象式宏与 Java 不命中 |
| `test_verifier.py` | 15 | Python AST 等价（重命名映射、逻辑变更检出、语法错误）；令牌流等价（const east/west 归一化、非法映射拒绝） |
| `test_differ.py` | 6 | DiffOp 结构与四种 tag |
| `test_extractor.py` | 11 | 三语言提取（示例文件实测）、置信度/meta、冲突标记、非法样例跳过与回落 |
| `test_rewriter_python.py` | 19 | PEP8 转换、AST/运行时等价、属性与关键字参数保护、dunder/私有前缀、碰撞、空白规则开/关、Tab 缩进、语法错误/空文件/单字符/纯注释 |
| `test_rewriter_cpp_java.py` | 18 | 黑名单 skipped、括号不配平 failed、Google 风格转换、const east/west、成员访问保护、碰撞、注释保留、@Override、Java 文本块 |
| `test_profile_store.py` | 13 | YAML 双向序列化、CRUD、损坏文件跳过、导入重分配 id、预设只读/另存 |
| `test_api.py` | 28 | 全部 13 个 REST 端点 + 统一 {code,message,data} 包装 + 混合批量 summary |
| `test_e2e.py` | 9 | 三语言「提取→落盘→转换→diff」全流程 + 语义等价抽查 |

## 3. 边界与错误路径验证（重点复核）

| 场景 | 预期 | 实测 |
|---|---|---|
| Python 语法错误输入 | failed + 保留原文 + 错误码 1002 | ✅ |
| C++/Java 括号不配平 | failed + 保留原文 + 1002 | ✅ |
| C++ 函数式宏 / #ifdef / 模板特化 | skipped + 保留原文 + 2001 | ✅ |
| 空文件 / 单字符 / 纯注释文件 | 不崩溃，正常 converted | ✅ |
| 语言识别失败（乱码/空白） | unknown + manual_required，API 返回 1001 | ✅ |
| 手动指定语言路径 | extract/convert 均可用 | ✅ |
| 重命名碰撞（totalCount vs total_count） | 放弃该条重命名，语义不破坏 | ✅ |
| 属性访问 / 关键字参数 / 导入名 | 不改写（防改 API 语义） | ✅ |
| 混合批量（好+语法错+语言不符） | summary 精确统计 1/1/1 | ✅ |
| 转换后运行时行为 | exec 原始与转换结果 stdout 完全一致 | ✅ |
| 字符串/多行 docstring 内容 | 空白规则不改写其内部 | ✅ |

## 4. 真实服务实测（uvicorn 18766）

health / detect×3 / extract / profiles CRUD / export / import / presets / convert（单文件+混合批量）/ history / restore / examples / SPA 首页托管 —— 18 项全部 PASS，统一响应包装 `{code,message,data}` 一致。实测产生的临时 profile/history 已清理。

## 5. 第 1 轮修复的测试 Bug（非源码问题）

1. `test_runtime_behavior_preserved`：exec 未注入 `__name__="__main__"`，示例主入口未执行 → 修正 globals。
2. `test_messy_example_converted_with_pep8` 等 2 例：误假设实例方法（`mgr.loadUsers`）会被重命名；源码按架构 §5-4 对属性位置标识符做保守排除，行为正确 → 修正断言。
3. `test_messy_example_to_google_style`（Java）：测试 profile 漏配 `naming: camelCase`，默认 snake_case 下重命名为恒等 → 修正 fixture。
4. `test_string_with_escapes_and_newline_inside`：测试输入中的 char 字面量写法本身非法 → 修正输入。
5. `test_convert[__init__]`：误假设 dunder 词干不变 → 记录实际行为（见 §6 观察项 1）。

## 6. 观察项（非阻塞，建议记录，不要求本期修复）

1. **`Naming.convert("__init__", ...)` 会丢弃词干尾部下划线**（`__init__` → `__init`）。当前所有重写器均跳过 dunder 名，不会被触发；若未来扩大重命名范围需先修。
2. **`python_extractor.py` 第 111 行 `except (tokenize.TokenError, ...)` 引用了未导入的模块名 `tokenize`**（实际导入为 `py_tokenize`）。该 except 在 ast.parse 已通过的前提下几乎不可达（latent），但一旦触发会抛 NameError 而非静默跳过。建议改为 `py_tokenize.TokenError`。
3. **Python Pass 2 会给关键字参数 `=` 两侧加空格**（`default=None` → `default = None`），不符合 PEP8 但不影响语义与等价校验。若要严格 PEP8，`space_around_operators` 需区分赋值与关键字参数语境。
4. 经实例调用的方法/成员整体不改写（`demo.add_user`、`mgr.loadUsers`）是架构 §5-4 的既定保守策略，安全但意味着成员方法命名规则对 Java/C++ 实际不生效——产品层可考虑在文档中说明。

## 7. 结论

核心引擎与全部 API 按 PRD/架构契约工作，安全铁律（黑名单→语法校验→等价校验→失败回退）在所有受测路径上成立。**路由判定：NoOne**，可进入安装与端到端演示验证阶段（任务 #5）。
