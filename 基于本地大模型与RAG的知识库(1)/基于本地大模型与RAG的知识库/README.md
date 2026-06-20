\# 运维数字员工 — RAG 智能问答模块（成员 A）



\## 功能简介

基于本地部署的 \*\*DeepSeek-R1 1.5B\*\* 大模型与 \*\*LangChain RAG\*\* 框架，构建垂直领域运维知识库问答系统。  

支持：

\- 运维常见问题自动回答（账号冻结、VPN 故障、磁盘清理等）

\- 无关问题/闲聊自动拒答并转人工

\- 通过 HTTP API 供其他模块（前端、后端）调用



\## 环境要求

\- Python 3.10 \~ 3.12（推荐 3.11）

\- Ollama 已安装并拉取模型：`ollama pull deepseek-r1:1.5b`

\- 操作系统：Windows / macOS / Linux

\- 内存：至少 8 GB（用于加载 1.5B 模型和 BGE 嵌入）



\## 快速开始



\### 1. 安装 Python 依赖

```bash

pip install -r requirements.txt

