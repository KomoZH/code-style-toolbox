# Code Style Toolbox · 代码风格迁移工具

本地运行的代码风格迁移工具，支持 **C++ / Python / Java** 三种语言。全本地离线处理，不依赖云端服务，不依赖 JVM。

## 核心功能

### 1. 代码风格提取
上传自己的代码示例，自动归纳可复用的风格规则：命名约定、缩进与括号风格、空行排版、注释风格、类型声明与错误处理、常用惯用法等。提取结果以结构化 YAML 规则集保存，支持查看、编辑、导入导出、多套规则切换，并带置信度标注。

### 2. 代码风格转换
粘贴或上传代码，按选定规则集自动重写。**严格保持原有逻辑、语义、函数签名与 API 调用不变**，只调整表现形式：

- Python：AST 等价校验（ast 校验 + tokenize 重写）
- C++/Java：令牌流等价校验（自研令牌化扫描器）
- 安全回退：语法校验前置 + C++ 宏/模板/预处理黑名单 + 失败自动保留原代码
- 转换前后 diff 对照视图

支持单文件与批量处理、语言自动识别（识别失败可手动指定）、转换历史与撤销、内置示例一键演示。

## 快速开始

```bat
:: Windows：双击或命令行运行
scripts\run.bat
```

自动创建虚拟环境、安装依赖并启动独立桌面窗口（基于 pywebview + 系统内置 WebView2）。

要求：Python 3.13+、Windows 10/11（自带 WebView2 运行时）。

### 其他脚本

| 脚本 | 用途 |
|---|---|
| `scripts\run.bat` / `run.ps1` | 一键启动（源码模式） |
| `scripts\build_frontend.bat` | 构建前端（需要 Node 22+） |
| `scripts\package.bat` | PyInstaller 打包绿色免安装版 |
| `scripts\demo_e2e.py` | 端到端演示（服务运行时执行） |

## 技术栈

- **后端**：Python 3.13 + FastAPI + uvicorn
- **前端**：Vite + React + MUI + Tailwind CSS（构建产物由后端托管）
- **桌面窗口**：pywebview 5.4（WebView2，零额外运行时）
- **打包**：PyInstaller --onedir

## 目录结构

```
backend/    FastAPI 后端 + 风格提取/转换引擎
frontend/   React 前端源码
examples/   三语言演示示例
data/presets/  内置预设规则（PEP8 / Google C++ / Google Java）
tests/      198 项 pytest 测试
scripts/    启动 / 构建 / 打包 / 演示脚本
docs/       PRD、架构设计、测试报告
```

## 文档

- [产品需求 PRD](docs/PRD.md)
- [架构设计](docs/ARCHITECTURE.md)
- [测试报告](docs/TEST_REPORT.md)
