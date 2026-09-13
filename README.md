# 保险条款 RAG 智能问答

基于 **qwen_agent** 与 **Elasticsearch** 的保险条款检索增强问答系统。以雇主责任保险等保险条款 PDF 为知识库，回答保险理赔、伤残补助等业务问题。

## 项目简介

针对保险业务场景构建的 RAG 应用，包含多种实现形态：

- 基于 qwen_agent `Assistant` 的 PDF 检索智能助手（默认使用内置 PDF 检索工具）；
- 注册自定义 `es_retrieval` 工具的 Elasticsearch 检索机器人（ai_bot_es.py）；
- 带 WebUI 交互界面与自定义图像生成工具的演示（UI界面.py）；
- Elasticsearch 检索效果测试脚本。

## 技术栈

- qwen_agent（Assistant / WebUI / 自定义工具）
- Elasticsearch（文档检索）
- pypdf（PDF 解析）
- 通义千问大模型（qwen-max）

## 目录结构

```
insurance-rag/
├── 检索智能助手.py              # 主程序：基于 PDF 的检索智能助手
├── ai_bot_es.py                # Elasticsearch 检索机器人（注册 es_retrieval 工具）
├── UI界面.py                   # qwen_agent WebUI 演示（含自定义图像生成工具）
├── test_es_retrieval.py        # ES 检索测试
├── 融盛雇主责任保险条款（B款）.pdf
├── 融盛财产一次性伤残补助金保险.pdf
└── 阳光农业相互保险公司 雇主责任保险条款（2019）.pdf
```

## 运行方式

```bash
pip install qwen-agent dashscope elasticsearch pypdf
python "检索智能助手.py"     # 控制台问答
python ai_bot_es.py          # ES 检索版（需先启动 Elasticsearch）
python UI界面.py             # Web 界面
```

## 配置说明

- 通过环境变量 `DASHSCOPE_API_KEY` 配置密钥：复制 `.env.example` 为 `.env` 并填入你的 DashScope API Key（`.env` 已被 .gitignore 忽略，不会提交）。运行前在 PowerShell 执行：`$env:DASHSCOPE_API_KEY = (Get-Content .env | Where-Object {$_ -like 'DASHSCOPE*'} | ForEach-Object {($_ -split '=')[1]})`
- `ai_bot_es.py` 使用本地 ES 服务（默认 `https://localhost:9200`，账号 `elastic`），需提前创建索引并写入 PDF 解析内容。
