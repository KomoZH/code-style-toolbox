# Code Style Toolbox — 产品需求文档（PRD）

## 1. 项目信息

- **Language**: 中文
- **Programming Language**: Python 3.13（核心引擎，风格提取与转换）+ Node 22 / Vite + React + MUI + Tailwind CSS（入口界面）；前后端本地进程通信（HTTP/IPC），最终以 PyInstaller/Electron 打包为 Windows 可执行程序，**不依赖 JVM**
- **Project Name**: `code_style_toolbox`
- **原始需求复述**:  
  开发一个本地运行的代码风格迁移工具，支持 C++、Python、Java 三种语言。两大核心功能：
  1. **风格提取**：用户上传代码示例后，自动归纳可复用、可描述的风格规则（命名约定、缩进与括号、空行排版、注释、类型声明与错误处理、惯用法等），以结构化规则清单/配置文件保存，可查看、编辑、复用。
  2. **风格转换**：用户粘贴或上传代码，依据已提取规则自动重写；严格保持原有逻辑、语义、函数签名与 API 调用不变，仅改变表现形式，并提供前后差异对照。  
     其他要求：单文件与批量处理；自动识别语言；转换前语法校验，无法安全转换时明确提示并保留原始代码；全本地处理不依赖云端；简洁入口界面并附示例文件演示完整流程；不依赖 JVM；最终在 Windows 本机可安装运行。

## 2. 产品定义

### Product Goals

1. **规则可沉淀**：从用户代码样例中提取结构化、可读、可编辑、可复用的风格规则配置，使个人/团队风格资产化。
2. **转换零风险**：风格迁移只改形式不改语义——语法校验前置、转换失败自动保留原代码，保证转换结果 100% 可回退。
3. **开箱即用**：本地单机运行、无需云端与 JVM，安装后即可通过示例文件完成"提取 → 转换"全流程演示。

### User Stories

1. 作为开发者，我想上传一份我的项目代码样例，让工具自动总结出我的命名、缩进、括号等风格规则，以便沉淀为团队规范。
2. 作为团队负责人，我想查看并微调提取出的规则配置文件，以便修正机器归纳的偏差后再复用。
3. 作为开发者，我想粘贴一段别人写的代码，套用我自己的风格规则自动重写，以便快速融入我的代码库。
4. 作为开发者，我想看到转换前后的 diff 对照，以便确认只有风格变化、逻辑未被改动。
5. 作为批量处理者，我想一次选择多个文件/整个目录进行转换，且无法安全转换的文件会被跳过并明确提示，以便放心批量操作。

## 3. 技术规范

### Requirements Pool

#### P0（必须实现）

| 编号   | 需求                                                  | 验收标准                           |
| ---- | --------------------------------------------------- | ------------------------------ |
| P0-1 | 风格提取：支持 C++/Python/Java 代码样例上传，输出结构化规则配置（YAML/JSON） | 对示例文件提取出命名/缩进/括号/注释等核心规则并落盘    |
| P0-2 | 规则查看与编辑：界面可浏览规则清单并修改保存                              | 修改后的规则对后续转换生效                  |
| P0-3 | 风格转换：粘贴或上传单文件，按选定规则重写代码                             | 转换不改变语义、函数签名、API 调用（AST/令牌级等价） |
| P0-4 | 差异对照：展示转换前后 diff 视图                                 | 界面可并排/行内查看差异                   |
| P0-5 | 语言自动识别                                              | 三种语言的文件/粘贴代码均正确识别              |
| P0-6 | 语法校验与安全回退：转换前校验语法，失败或无法安全转换时明确提示并保留原代码              | 非法输入不产生破坏性的输出                  |
| P0-7 | 全本地处理：不调用任何云端服务                                     | 断网环境下功能完整可用                    |
| P0-8 | Windows 可运行交付：安装程序或免安装可执行包（不依赖 JVM）                 | 目标 Windows 机器上双击即可启动           |

#### P1（重要）

| 编号   | 需求                                 | 验收标准            |
| ---- | ---------------------------------- | --------------- |
| P1-1 | 批量处理：多文件/目录批量转换，生成处理报告（成功/跳过/失败清单） | 目录级批量执行并输出汇总报告  |
| P1-2 | 规则配置管理：多套规则的保存、命名、切换、导入导出          | 可复用至少两套规则并互相切换  |
| P1-3 | 示例文件与演示引导：内置三种语言示例，一键演示"提取→转换"全流程  | 新用户 5 分钟内完成首次演示 |
| P1-4 | 提取置信度提示：对样本不足或规则冲突的条目给出标注          | 低置信度规则在界面上有醒目标识 |

#### P2（可选）

| 编号   | 需求                            | 验收标准          |
| ---- | ----------------------------- | ------------- |
| P2-1 | 转换历史记录与撤销                     | 可回看最近转换并可还原文件 |
| P2-2 | 规则模板库（内置 Google/PEP8 等常见风格预设） | 可直接选用预设规则     |
| P2-3 | CLI 命令行入口（与 GUI 并存）           | 支持脚本化批量调用     |
| P2-4 | 导出转换报告（HTML/Markdown）         | 可分享 diff 报告   |

### 风格规则结构化字段清单建议（供架构设计参考）

```yaml
style_profile:
  name: "my_team_style"
  language: "python"          # python | cpp | java
  version: "1.0"

  naming:                     # 命名约定
    variables: "snake_case"   # snake_case | camelCase | PascalCase | UPPER_SNAKE
    functions: "snake_case"
    classes: "PascalCase"
    constants: "UPPER_SNAKE"
    private_prefix: "_"       # 私有成员前缀（python/java）
    member_suffix: ""         # C++ 成员后缀如 "m_"/"_"

  indent:                     # 缩进
    style: "space"            # space | tab
    size: 4
    continuation_size: 8      # 续行缩进

  brace_style:                # 括号风格（C++/Java）
    style: "allman"           # k_and_r | allman | linux
    namespace_brace: "same_line"
    space_before_paren: true  # if ( / if(

  spacing:
    space_around_operators: true
    space_after_comma: true
    max_line_length: 100
    trim_trailing_whitespace: true

  blank_lines:                # 空行与排版
    max_consecutive: 2
    between_functions: 2
    between_classes: 2
    after_imports: 2

  comments:
    style: "doxygen"          # doxygen | javadoc | plain | none
    docstring_format: "google"  # python: google | numpy | sphinx
    inline_min_spaces: 2
    header_block: true        # 文件头注释块

  declarations:               # 类型声明与错误处理
    cpp_use_auto: false
    cpp_const_style: "east"   # east | west
    java_use_var: false
    python_type_hints: true
    prefer_early_return: true
    exception_style: "specific"  # 捕获具体异常 vs 宽泛捕获

  idioms:                     # 常用写法与惯用法
    python_prefer_comprehension: true
    python_prefer_fstring: true
    cpp_prefer_range_for: true
    java_prefer_stringbuilder: true
    import_order: "stdlib,third_party,local"
```

> 说明：以上为初始字段建议，架构师可按解析器能力裁剪；每条规则需附带 `confidence`（提取置信度）与 `examples`（样例片段）两个元字段，支撑 P1-4。

### UI Design Draft

采用单窗口、顶部步骤式导航（提取 → 规则 → 转换 → 对照）的简洁布局：

1. **首页 / 步骤向导**：两个大功能卡片「提取风格」「转换代码」+「使用示例演示」按钮（P1-3）。
2. **提取页**：拖拽/上传样例文件区（支持多文件），语言自动识别徽标，「开始提取」按钮；完成后跳转规则页。
3. **规则页**：左侧规则分类树（命名/缩进/括号/空行/注释/声明/惯用法），右侧表单化编辑器 + 低置信度高亮（P1-4）；顶部规则集切换下拉与「导入/导出/另存为」（P1-2）。
4. **转换页**：左侧代码输入（粘贴文本域或文件/目录选择，单文件与批量 Tab 切换），中间「转换」按钮与语法校验状态提示，底部批量处理进度与结果清单（P1-1）。
5. **对照页**：左右并排 diff（语法高亮 + 行内增删标记），「采纳导出」按钮；无法安全转换的条目以警示色列出并说明原因（P0-6）。
6. 全局：右上角显示当前规则集与目标语言；所有操作离线完成，无网络请求。

### Open Questions

1. **转换保真验证粒度**：语义等价以"AST 等价 + 测试用例回归"中的哪一级作为验收基线？是否需要对 C++ 宏/模板等不可安全重写的构造明确列入黑名单（仅跳过）？
2. **粘贴代码的语言识别**：粘贴无文件名上下文的短代码片段时，识别失败是否允许用户手动指定语言（建议允许）？
3. **样例规模要求**：风格提取对样例代码量的最低要求（如 <200 行时仅产出低置信度规则）是否需要硬门槛提示？
4. **打包形态**：最终交付偏好"安装程序（NSIS/Inno Setup）"还是"绿色免安装压缩包"？或两者都提供？
5. **界面技术路线**：前端选 Electron（体积大、体验完整）还是 本地 Python 后端 + 系统浏览器打开 React 页面（体积小）？需架构师权衡后确认。
