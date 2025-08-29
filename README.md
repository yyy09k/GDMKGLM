# GDMKGLM(妊娠期糖尿病管理本地大模型)

A GraphRAG-Enhanced Knowledge Management System for Gestational Diabetes Mellitus
基于GraphRAG架构的妊娠期糖尿病知识问答系统。

## 项目结构

- `data/`: 数据文件
  - `guidelines/`: 临床指南原始文件
  - `pubmed/`: PubMed文献原始文件
  - `textbooks/`: 教科书知识原始文件
  - `faq/`: 患者常见问题原始文件
  - `processed/`: 预处理后的数据
    - `faq/`:处理后的患者常见问题
    - `guidelines/`: 处理后的临床指南
    - `pubmed/`: 处理后的PubMed文献
    - `textbooks/`: 处理后的教科书知识
    - `all_documents_index.json`: 所有处理后数据文件索引
  - `data_summary.json`: 所有原始医学数据汇总
- `src/`: 源代码
  - `graphrag/`
    - `embeddings.py`: 嵌入处理模块,向量化引擎
    - `gdm_graphrag_engine.py`: GDM GraphRAG主引擎
    - `graph_retriever.py`: 图谱检索器,基于知识图谱的信息检索
    - `hybrid_retriever.py`: 混合检索器,整合语义检索和图谱检索
    - `prompt_templates.py`: GraphRAG提示词模板系统（GDM）
  - `knowledge_graph/`
    - `graph_schema.py`: 妊娠期糖尿病知识图谱模式定义代码
    - `graph_tool.py`: 图谱操作工具类，支持知识图谱的查询、分析和管理功能
    - `knowledge_extractor.py`: 知识提取器代码
    - `neo4j_init.py`: Neo4j数据库初始化脚本
    - `test_extraction.py`: 知识提取器测试文件
  - `utils/`: 工具函数
    - `text_extractor.py`: 文本预处理工具，提取文本
    - `deepseek_client.py`: 客户端，调用deepseek开发的知识提取模块
  - `download_guidelines.py`: 脚本
  - `pubmed_collector.py`: 脚本
  - `enrich_pubmed_data.py`: 脚本
  - `textbook_collector.py`: 脚本
  - `faq_collector.py`: 脚本
  - `validate_data.py`: 验证了所有收数据文件，生成数据摘要报告
- `models/`: 模型文件
  - `knowledge/`: 知识提取相关
    - `gdm_knowledge.json`: 提取到的实体关系等
  - `knowledge_graph_schema.md`: 妊娠期糖尿病知识图谱模型设计
  - `vectors/`: 向量存储数据库
- `static/`
  - `css/`
    - `style.css`
  - `js/`
    - `app.js`
- `templates/`
  - `index.html`
- `session_manager.py`: Neo4j会话管理器,GDM GraphRAG系统历史对话功能(未启用)
- `app.py/`: 应用程序
- `README.md`: 项目说明
- `requirements.txt`: 项目相关包

## 环境设置

```bash
# 创建虚拟环境
python -m venv gdm_env

# 激活环境
source gdm_env/bin/activate  # Linux/Mac
# 或
.\gdm_env\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 数据统计

* 临床指南: 5份
* PubMed文章: 45篇
* 教科书资源: 4份
* FAQ问答: 28条
* 总计处理文档段落: 1060个

## 使用方法

### 数据处理

```bash
# 处理原始数据
python src/utils/text_processor.py
```
