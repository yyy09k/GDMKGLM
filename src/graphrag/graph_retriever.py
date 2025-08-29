"""
图谱检索器 - 基于知识图谱的信息检索
整合graph_tool.py的查询功能
"""

import os
import sys
import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass

# 导入项目模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, project_root)

from src.knowledge_graph.graph_tool import GraphTool, GraphNode, GraphRelation

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GraphSearchResult:
    """图谱搜索结果 """
    entities: List[GraphNode]
    relations: List[GraphRelation]
    context_text: str
    relevance_score: float
    search_keywords: List[str]
    search_strategy: str = "default"  # 搜索策略标识
    retrieval_time: float = 0.0      # 检索耗时

class GraphRetriever:
    """图谱检索器类 """
    
    def __init__(self, 
                 neo4j_uri: str = "neo4j://127.0.0.1:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = r"42810916402\Ssnx"):
        """
        初始化图谱检索器
        
        Args:
            neo4j_uri: Neo4j连接地址
            neo4j_user: 用户名
            neo4j_password: 密码
        """
        self.graph_tool = GraphTool(neo4j_uri, neo4j_user, neo4j_password)
        
        # 医学关键词词典
        self.medical_keywords = {
            "疾病": ["糖尿病", "高血压", "心脏病", "妊娠期糖尿病", "GDM", "妊高症", "贫血", "感染"],
            "症状": ["多饮", "多尿", "多食", "体重下降", "疲劳", "头痛", "水肿", "蛋白尿", "血压升高"],
            "治疗": ["胰岛素", "运动", "饮食", "药物", "监测", "控制", "管理", "注射", "口服药"],
            "检查": ["血糖", "尿糖", "糖耐量", "检测", "筛查", "OGTT", "血压", "尿蛋白", "B超"],
            "风险": ["遗传", "肥胖", "年龄", "家族史", "孕期", "高龄", "既往史", "BMI"],
            "营养": ["饮食", "食物", "营养", "热量", "碳水化合物", "蛋白质", "脂肪", "维生素"],
            "并发症": ["早产", "巨大儿", "低血糖", "酮症", "感染", "羊水过多", "胎儿窘迫"]
        }
        
        # 问题类型识别模式
        self.question_patterns = {
            "症状": ["症状有哪些", "有什么症状", "什么症状", "症状是什么", "表现为", "有哪些表现"],
            "诊断": ["如何诊断", "诊断方法", "怎么诊断", "如何检查", "检查什么", "诊断标准"],
            "治疗": ["如何治疗", "治疗方法", "怎么治", "用什么药", "如何管理", "治疗"],
            "原因": ["什么原因", "为什么", "病因", "引起", "导致", "原因"],
            "预防": ["如何预防", "预防方法", "怎样避免", "防止", "预防措施"],
            "饮食": ["饮食管理", "吃什么", "饮食", "食物", "营养", "不能吃", "应该吃"],
            "风险": ["什么风险", "有什么风险", "危险因素", "风险", "高危", "容易得", "易患"]
        }
        
        logger.info("✅ 图谱检索器初始化完成")
    
    def extract_medical_entities(self, query: str) -> Tuple[List[str], str]:
        """
        从查询中提取医学实体关键词
        
        Args:
            query: 用户查询
            
        Returns:
            (提取的医学关键词列表, 问题类型)
        """
        entities = []
        query_lower = query.lower()
        
        # 1. 识别问题类型
        question_type = "general"
        for q_type, patterns in self.question_patterns.items():
            if any(pattern in query for pattern in patterns):  # 直接在原query中匹配
                question_type = q_type
                break
        
        # 2. 预定义关键词精确匹配
        for category, keywords in self.medical_keywords.items():
            for keyword in keywords:
                if keyword in query:  # 不转小写，保持精确匹配
                    entities.append(keyword)
        
        # 3. 医学术语模式匹配 - 修复正则表达式，避免匹配整句
        medical_patterns = [
            r'妊娠期糖尿病',
            r'(?<!妊娠期)糖尿病(?!的症状有哪些|如何诊断)',  # 避免匹配完整问句
            r'高血压', 
            r'血糖(?!高有什么风险)',  # 避免匹配问句
            r'胰岛素',
            r'糖耐量(?!检查怎么做)',  # 避免匹配问句
            r'OGTT'
        ]
        
        for pattern in medical_patterns:
            matches = re.findall(pattern, query)
            entities.extend(matches)
        
        # 4. 避免提取完整句子,只保留有意义的医学词汇
        if not entities:
            # 提取2-4字的中文医学术语
            words = re.findall(r'[\u4e00-\u9fff]{2,4}', query)
            stopwords = {"什么", "哪些", "如何", "怎么", "怎样", "为什么", "有什么", "是什么", "症状", "治疗"}
            entities = [w for w in words if w not in stopwords and len(w) >= 2]
        
        # 去重并限制数量，避免关键词过多
        unique_entities = list(dict.fromkeys(entities))[:5]  # 最多保留5个关键词
        
        return unique_entities, question_type
    
    def search_entities(self, keywords: List[str]) -> List[GraphNode]:
        """
        根据关键词搜索相关实体
        
        Args:
            keywords: 搜索关键词列表
            
        Returns:
            匹配的实体列表
        """
        all_entities = []
        
        for keyword in keywords:
            # 1. 精确匹配
            exact_entities = self.graph_tool.find_entity_by_name(keyword, fuzzy=False)
            all_entities.extend(exact_entities)
            
            # 2. 模糊匹配
            fuzzy_entities = self.graph_tool.find_entity_by_name(keyword, fuzzy=True)
            all_entities.extend(fuzzy_entities)
            
            # 3. 如果是核心医学术语，扩展搜索
            if any(keyword in keywords for keywords in self.medical_keywords.values()):
                expanded_entities = self._expand_medical_search(keyword)
                all_entities.extend(expanded_entities)
        
        # 去重（基于实体ID）
        unique_entities = {}
        for entity in all_entities:
            if entity.id not in unique_entities:
                unique_entities[entity.id] = entity
        
        # 按相关性排序
        sorted_entities = self._rank_entities_by_relevance(list(unique_entities.values()), keywords)
        
        return sorted_entities[:20]  # 限制返回数量
    
    def _expand_medical_search(self, keyword: str) -> List[GraphNode]:
        """
        扩展医学术语搜索
        
        Args:
            keyword: 医学关键词
            
        Returns:
            扩展搜索的实体列表
        """
        expanded_entities = []
        
        # 疾病扩展映射
        disease_expansions = {
            "糖尿病": ["妊娠期糖尿病", "2型糖尿病", "1型糖尿病"],
            "高血压": ["妊娠期高血压", "妊高症"],
            "感染": ["泌尿系感染", "呼吸道感染"]
        }
        
        # 症状扩展映射  
        symptom_expansions = {
            "多饮": ["烦渴", "口干"],
            "多尿": ["尿频", "夜尿增多"],
            "疲劳": ["乏力", "疲乏"]
        }
        
        # 检查扩展映射
        test_expansions = {
            "血糖": ["空腹血糖", "餐后血糖", "随机血糖"],
            "糖耐量": ["OGTT", "葡萄糖耐量试验"]
        }
        
        all_expansions = {**disease_expansions, **symptom_expansions, **test_expansions}
        
        if keyword in all_expansions:
            for expansion in all_expansions[keyword]:
                entities = self.graph_tool.find_entity_by_name(expansion, fuzzy=True)
                expanded_entities.extend(entities)
        
        return expanded_entities
    
    def _rank_entities_by_relevance(self, entities: List[GraphNode], keywords: List[str]) -> List[GraphNode]:
        """
        按相关性对实体排序
        
        Args:
            entities: 实体列表
            keywords: 查询关键词
            
        Returns:
            排序后的实体列表
        """
        def calculate_relevance(entity: GraphNode) -> float:
            score = 0.0
            entity_name_lower = entity.name.lower()
            
            # 1. 名称匹配得分
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower == entity_name_lower:
                    score += 10  # 完全匹配
                elif keyword_lower in entity_name_lower:
                    score += 5   # 包含匹配
                elif entity_name_lower in keyword_lower:
                    score += 3   # 被包含匹配
            
            # 2. 实体类型得分
            important_types = ["Disease", "Symptom", "Treatment", "DiagnosticMethod"]
            if entity.label in important_types:
                score += 2
            
            # 3. 属性匹配得分
            if entity.properties:
                for key, value in entity.properties.items():
                    if isinstance(value, str):
                        for keyword in keywords:
                            if keyword.lower() in value.lower():
                                score += 1
            
            return score
        
        # 计算相关性得分并排序
        entity_scores = [(entity, calculate_relevance(entity)) for entity in entities]
        entity_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [entity for entity, score in entity_scores]
    
    def get_entity_context(self, entities: List[GraphNode], question_type: str, max_depth: int = 2) -> Tuple[List[GraphRelation], str]:
        """
        获取实体的上下文信息
        
        Args:
            entities: 实体列表
            question_type: 问题类型
            max_depth: 最大搜索深度
            
        Returns:
            (关系列表, 上下文文本)
        """
        all_relations = []
        context_parts = []
        processed_entities = set()
        
        # 根据问题类型使用不同的上下文获取策略
        for entity in entities[:5]:  # 限制处理的实体数量
            if entity.id in processed_entities:
                continue
                
            processed_entities.add(entity.id)
            
            # 使用graph_tool的问题上下文方法
            if question_type != "general":
                question_context = self.graph_tool.get_question_context(f"{entity.name}的{question_type}")
                if question_context and "未找到" not in question_context:
                    context_parts.append(f"【{entity.label}】{entity.name}\n{question_context}")
                    continue
            
            # 获取实体邻居信息作为补充
            neighbors = self.graph_tool.get_entity_neighbors(entity.name)
            
            if neighbors["center"]:
                # 添加实体信息
                entity_info = f"【{entity.label}】{entity.name}"
                if entity.properties:
                    props = []
                    for key, value in entity.properties.items():
                        if key not in ['id', 'name'] and value:
                            props.append(f"{key}: {value}")
                    if props:
                        entity_info += f"\n属性: {', '.join(props[:3])}"
                
                context_parts.append(entity_info)
                
                # 添加相关关系信息
                if neighbors["all"]:
                    relation_texts = []
                    for neighbor in neighbors["all"][:5]:  # 限制每个实体的邻居数量
                        relation_text = f"{neighbor['relation']} {neighbor['name']}"
                        relation_texts.append(relation_text)
                        
                        # 创建关系对象
                        relation = GraphRelation(
                            source=entity.name,
                            target=neighbor['name'],
                            relation_type=neighbor['relation'],
                            properties={}
                        )
                        all_relations.append(relation)
                    
                    if relation_texts:
                        context_parts.append(f"相关: {', '.join(relation_texts)}")
        
        context_text = "\n\n".join(context_parts)
        return all_relations, context_text
    
    def calculate_relevance_score(self, query: str, entities: List[GraphNode], 
                                relations: List[GraphRelation], question_type: str) -> float:
        """
        计算检索结果的相关性得分
        
        Args:
            query: 原始查询
            entities: 匹配的实体
            relations: 相关关系
            question_type: 问题类型
            
        Returns:
            相关性得分 (0-1)
        """
        if not entities:
            return 0.0
        
        score = 0.0
        query_lower = query.lower()
        
        # 1. 实体名称匹配得分,提高基础分值
        entity_score = 0.0
        for entity in entities:
            entity_name_lower = entity.name.lower()
            
            # 完全匹配或包含匹配
            if entity_name_lower in query_lower or query_lower.replace("的", "").replace("？", "") in entity_name_lower:
                entity_score += 0.4  # 提高基础匹配分值
            
            # 核心医学术语匹配
            key_terms = ["妊娠期糖尿病", "糖尿病", "血糖", "胰岛素", "糖耐量"]
            for term in key_terms:
                if term in entity.name and term in query:
                    entity_score += 0.3  # 医学术语匹配加分
            
            # 部分词匹配
            entity_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', entity.name))
            query_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', query))
            common_words = entity_words & query_words
            if common_words:
                entity_score += len(common_words) * 0.1
        
        # 2. 问题类型匹配得分
        type_score = 0.0
        type_mapping = {
            "症状": ["Symptom", "MedicalConcept"],
            "治疗": ["Treatment", "Medication"],
            "诊断": ["DiagnosticMethod"], 
            "风险": ["RiskFactor", "Complication"],
            "饮食": ["Food", "NutritionalGuideline"],
            "general": ["Disease", "Symptom", "Treatment", "DiagnosticMethod"]
        }
        
        expected_types = type_mapping.get(question_type, type_mapping["general"])
        type_match_count = 0
        for entity in entities:
            if entity.label in expected_types:
                type_match_count += 1
                type_score += 0.2  # 每个类型匹配加0.2分
        
        # 3. 关系丰富度得分 - 调整权重
        relation_score = min(len(relations) * 0.03, 0.2)  # 每个关系0.03分，最多0.2分
        
        # 4. 上下文质量得分
        context_score = 0.0
        for entity in entities:
            if entity.properties:
                # 有description属性的实体加分更多
                if 'description' in entity.properties:
                    context_score += 0.15
                else:
                    context_score += 0.05
        context_score = min(context_score, 0.25)  # 最多0.25分
        
        # 5. 疾病专用查询加成
        disease_bonus = 0.0
        if any("妊娠期糖尿病" in entity.name for entity in entities):
            disease_bonus = 0.2  # 找到核心疾病时加成
        
        # 综合计算
        total_score = entity_score + type_score + relation_score + context_score + disease_bonus
        
        # 结果质量加成
        quality_multiplier = 1.0
        if len(entities) >= 3 and len(relations) >= 5:
            quality_multiplier = 1.1  # 结果丰富时轻微加成
        elif type_match_count >= 2:
            quality_multiplier = 1.05  # 类型匹配好时加成
        
        # 最终分数计算和归一化
        final_score = total_score * quality_multiplier
        
        # 确保分数在合理范围内 (0.1-1.0)
        if final_score > 0:
            final_score = max(final_score, 0.1)  # 有结果时最低0.1分
            final_score = min(final_score, 1.0)   # 最高1.0分
        
        return final_score
    
    def retrieve(self, query: str, top_k: int = 5) -> List[GraphSearchResult]:
        """
        执行图谱检索
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            
        Returns:
            图谱搜索结果列表
        """
        start_time = time.time()
        logger.info(f"🔍 图谱检索查询: {query}")
        
        try:
            # 1. 提取医学实体关键词和问题类型
            keywords, question_type = self.extract_medical_entities(query)
            logger.info(f"提取关键词: {keywords}, 问题类型: {question_type}")
            
            if not keywords:
                # 如果没有提取到关键词，使用查询中的所有有意义的词
                keywords = [word.strip() for word in query.split() if len(word.strip()) > 1]
            
            # 2. 搜索相关实体
            entities = self.search_entities(keywords)
            logger.info(f"找到 {len(entities)} 个相关实体")
            
            if not entities:
                retrieval_time = time.time() - start_time
                return [GraphSearchResult(
                    entities=[],
                    relations=[],
                    context_text="未找到相关的图谱信息",
                    relevance_score=0.0,
                    search_keywords=keywords,
                    search_strategy="empty_result",
                    retrieval_time=retrieval_time
                )]
            
            # 3. 获取实体上下文
            relations, context_text = self.get_entity_context(entities, question_type)
            
            # 4. 计算相关性得分
            relevance_score = self.calculate_relevance_score(query, entities, relations, question_type)
            
            # 5. 确定搜索策略
            if question_type != "general":
                search_strategy = f"specialized_{question_type}"
            else:
                search_strategy = "general_graph"
            
            retrieval_time = time.time() - start_time
            
            # 6. 构建搜索结果
            result = GraphSearchResult(
                entities=entities[:top_k],  # 限制实体数量
                relations=relations,
                context_text=context_text,
                relevance_score=relevance_score,
                search_keywords=keywords,
                search_strategy=search_strategy,
                retrieval_time=retrieval_time
            )
            
            logger.info(f"✅ 图谱检索完成，耗时: {retrieval_time:.3f}s，相关性: {relevance_score:.3f}")
            return [result]  # 返回单个增强结果
            
        except Exception as e:
            logger.error(f"❌ 图谱检索失败: {e}")
            retrieval_time = time.time() - start_time
            return [GraphSearchResult(
                entities=[],
                relations=[],
                context_text=f"图谱检索出现错误: {str(e)}",
                relevance_score=0.0,
                search_keywords=keywords if 'keywords' in locals() else [],
                search_strategy="error",
                retrieval_time=retrieval_time
            )]
    
    def get_disease_context(self, disease_name: str) -> Optional[GraphSearchResult]:
        """
        获取特定疾病的详细上下文
        
        Args:
            disease_name: 疾病名称
            
        Returns:
            疾病相关的图谱信息
        """
        start_time = time.time()
        
        try:
            # 使用graph_tool的专用疾病查询方法
            disease_info = self.graph_tool.get_disease_info(disease_name)
            
            if not disease_info:
                return None
            
            # 构建增强的上下文文本
            context_parts = [f"【疾病详情】{disease_info['name']}"]
            
            if disease_info.get('symptoms'):
                symptoms = disease_info['symptoms'][:8]  # 限制数量
                context_parts.append(f"主要症状: {', '.join(symptoms)}")
            
            if disease_info.get('treatments'):
                treatments = disease_info['treatments'][:5]
                context_parts.append(f"治疗方法: {', '.join(treatments)}")
            
            if disease_info.get('risk_factors'):
                risks = disease_info['risk_factors'][:5]
                context_parts.append(f"风险因素: {', '.join(risks)}")
            
            if disease_info.get('diagnosis_methods'):
                diagnosis = disease_info['diagnosis_methods'][:5]
                context_parts.append(f"诊断方法: {', '.join(diagnosis)}")
            
            if disease_info.get('complications'):
                complications = disease_info['complications'][:5]
                context_parts.append(f"可能并发症: {', '.join(complications)}")
            
            context_text = "\n".join(context_parts)
            
            # 构建实体对象
            entities = [GraphNode(
                id="disease_" + disease_name,
                name=disease_name,
                label="Disease",
                properties=disease_info.get('properties', {})
            )]
            
            retrieval_time = time.time() - start_time
            
            return GraphSearchResult(
                entities=entities,
                relations=[],  # 关系信息已经整合到context_text中
                context_text=context_text,
                relevance_score=1.0,  # 直接疾病查询，相关性最高
                search_keywords=[disease_name],
                search_strategy="disease_specific",
                retrieval_time=retrieval_time
            )
            
        except Exception as e:
            logger.error(f"❌ 获取疾病上下文失败: {e}")
            return None
    
    def close(self):
        """关闭图谱连接"""
        if hasattr(self.graph_tool, 'close'):
            self.graph_tool.close()
        logger.info("✅ 图谱检索器已关闭")

# 便捷函数
def create_graph_retriever(**kwargs) -> GraphRetriever:
    """创建图谱检索器实例"""
    return GraphRetriever(**kwargs)

# 测试代码
if __name__ == "__main__":
    print("🚀 测试图谱检索器...")
    
    try:
        retriever = GraphRetriever()
        
        # 1️⃣ 测试关键词提取
        print("\n1️⃣ 测试关键词提取...")
        test_queries_for_extraction = [
            "妊娠期糖尿病有什么症状？",
            "如何诊断糖尿病？",
            "孕妇血糖高有什么风险？",
            "糖耐量检查怎么做？",
            "妊娠期糖尿病的饮食管理"
        ]
        
        for query in test_queries_for_extraction:
            keywords, question_type = retriever.extract_medical_entities(query)
            print(f"查询: {query}")
            print(f"  ➤ 提取关键词: {keywords}")
            print(f"  ➤ 问题类型: {question_type}")
            print()
        
        # 2️⃣ 测试图谱检索
        print("\n2️⃣ 测试图谱检索...")
        test_queries = [
            "妊娠期糖尿病的症状有哪些？",
            "如何治疗糖尿病？", 
            "孕妇血糖高有什么风险？",
            "糖耐量检查怎么做？"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n--- 测试查询 {i}: {query} ---")
            results = retriever.retrieve(query, top_k=3)
            
            if results:
                for j, result in enumerate(results, 1):
                    print(f"\n📋 结果 {j}:")
                    print(f"  相关性得分: {result.relevance_score:.3f}")
                    print(f"  搜索策略: {result.search_strategy}")
                    print(f"  检索耗时: {result.retrieval_time:.3f}s")
                    print(f"  找到实体: {len(result.entities)} 个")
                    if result.entities:
                        entity_names = [entity.name for entity in result.entities[:3]]
                        print(f"    实体列表: {', '.join(entity_names)}")
                    print(f"  找到关系: {len(result.relations)} 个")
                    print(f"  搜索关键词: {result.search_keywords}")
                    
                    # 显示上下文预览
                    if result.context_text:
                        preview = result.context_text[:300] + "..." if len(result.context_text) > 300 else result.context_text
                        print(f"  上下文预览: {preview}")
                    else:
                        print("  上下文: 无")
            else:
                print("  ❌ 未找到相关结果")
        
        # 3️⃣ 测试疾病专用查询
        print("\n3️⃣ 测试疾病专用查询...")
        disease_names = [
            "妊娠期糖尿病",
            "糖尿病", 
            "高血压",
            "妊娠期高血压"
        ]
        
        for disease in disease_names:
            print(f"\n--- 测试疾病: {disease} ---")
            disease_result = retriever.get_disease_context(disease)
            
            if disease_result:
                print(f"✅ 找到疾病信息:")
                print(f"  相关性得分: {disease_result.relevance_score:.3f}")
                print(f"  搜索策略: {disease_result.search_strategy}")
                print(f"  检索耗时: {disease_result.retrieval_time:.3f}s")
                print(f"  实体数量: {len(disease_result.entities)}")
                
                # 显示疾病详细信息
                if disease_result.context_text:
                    print(f"  疾病详情:")
                    # 按行分割并添加缩进，便于阅读
                    lines = disease_result.context_text.split('\n')
                    for line in lines[:10]:  # 限制显示行数
                        if line.strip():
                            print(f"    {line}")
                    if len(lines) > 10:
                        print(f"    ... (还有 {len(lines) - 10} 行)")
                else:
                    print("  疾病详情: 无")
            else:
                print(f"  ❌ 未找到疾病 '{disease}' 的相关信息")
        
        # 4️⃣ 测试实体搜索功能
        print("\n4️⃣ 测试实体搜索...")
        test_entities = ["糖尿病", "血糖", "胰岛素", "孕期"]
        
        for entity_name in test_entities:
            print(f"\n--- 搜索实体: {entity_name} ---")
            entities = retriever.search_entities([entity_name])
            
            if entities:
                print(f"✅ 找到 {len(entities)} 个相关实体:")
                for i, entity in enumerate(entities[:5], 1):  # 只显示前5个
                    print(f"  {i}. 【{entity.label}】{entity.name}")
                    if entity.properties:
                        # 显示部分属性
                        props = []
                        for key, value in list(entity.properties.items())[:2]:
                            if key not in ['id', 'name'] and value:
                                props.append(f"{key}: {value}")
                        if props:
                            print(f"     属性: {', '.join(props)}")
            else:
                print(f"  ❌ 未找到实体 '{entity_name}'")
        
        # 5️⃣ 性能测试
        print("\n5️⃣ 性能测试...")
        performance_queries = [
            "妊娠期糖尿病",
            "血糖监测",
            "胰岛素注射",
            "孕期营养管理"
        ]
        
        total_time = 0
        total_queries = len(performance_queries)
        
        for query in performance_queries:
            start_time = time.time()
            results = retriever.retrieve(query, top_k=5)
            query_time = time.time() - start_time
            total_time += query_time
            
            print(f"  查询 '{query}': {query_time:.3f}s, 结果数: {len(results)}")
        
        avg_time = total_time / total_queries
        print(f"\n📊 性能统计:")
        print(f"  总查询数: {total_queries}")
        print(f"  总耗时: {total_time:.3f}s")
        print(f"  平均耗时: {avg_time:.3f}s/查询")
        print(f"  查询效率: {'优秀' if avg_time < 0.5 else '良好' if avg_time < 1.0 else '需优化'}")
        
        # 清理资源
        retriever.close()
        print("\n✅ 图谱检索器测试完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
