"""
图谱操作工具类
支持知识图谱的查询、分析和管理功能
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from neo4j import GraphDatabase
from dataclasses import dataclass
import json
import time

# 添加项目根目录到Python路径，以便导入其他模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, project_root)

# 导入图谱模式定义
try:
    from src.knowledge_graph.graph_schema import NodeType, RelationType
except ImportError:
    # 如果在当前目录运行，尝试相对导入
    try:
        from .graph_schema import NodeType, RelationType
    except ImportError:
        from graph_schema import NodeType, RelationType

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class GraphNode:
    """图谱节点数据类"""
    id: str
    name: str
    label: str
    properties: Dict[str, Any]
    
@dataclass 
class GraphRelation:
    """图谱关系数据类"""
    source: str
    target: str
    relation_type: str
    properties: Dict[str, Any]

@dataclass
class SearchResult:
    """搜索结果数据类"""
    nodes: List[GraphNode]
    relations: List[GraphRelation]
    paths: List[List[str]]
    total_count: int

class GraphTool:
    """知识图谱操作工具类"""
    
    def __init__(self, 
                 uri: str = "neo4j://127.0.0.1:7687",
                 user: str = "neo4j", 
                 password: str = r"42810916402\Ssnx"):  # ✅ 修改
        """
        初始化图谱工具
        
        Args:
            uri: Neo4j连接地址
            user: 用户名
            password: 密码
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self._connect()
        
    def _connect(self):
        """连接到Neo4j数据库"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.user, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            # 测试连接
            self.driver.execute_query("RETURN 1")
            logger.info(f"成功连接到Neo4j: {self.uri}")
        except Exception as e:
            logger.error(f"连接Neo4j失败: {str(e)}")
            raise
    
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")
    
    def run_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """
        执行Cypher查询 - 使用优化的execute_query方法
        
        Args:
            query: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            查询结果列表
        """
        try:
            # ✅ 修改：使用 execute_query 方法提高性能
            result = self.driver.execute_query(query, parameters or {})
            return [record.data() for record in result.records]
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}")
            logger.error(f"查询: {query[:200]}...")  # 显示前200个字符
            return []
    
    # ===== 实体查询方法 =====
    
    def find_entity_by_name(self, name: str, fuzzy: bool = True) -> List[GraphNode]:
        """
        根据名称查找实体 - 支持Question节点的text属性
        
        Args:
            name: 实体名称
            fuzzy: 是否模糊匹配
            
        Returns:
            匹配的实体列表
        """
        if fuzzy:
            # 修改：改进模糊匹配逻辑，支持中文分词和部分匹配
            query = """
            MATCH (n)
            WHERE n.name CONTAINS $name OR n.text CONTAINS $name
                  OR toLower(n.name) CONTAINS toLower($name) 
                  OR toLower(coalesce(n.text, '')) CONTAINS toLower($name)
                  OR n.name =~ ('.*' + $name + '.*')
                  OR n.text =~ ('.*' + $name + '.*')
            RETURN COALESCE(n.name, n.text) as name, labels(n)[0] as label, 
                   id(n) as id, properties(n) as properties
            LIMIT 20
            """
        else:
            query = """
            MATCH (n)
            WHERE n.name = $name OR n.text = $name
            RETURN COALESCE(n.name, n.text) as name, labels(n)[0] as label,
                   id(n) as id, properties(n) as properties
            """
        
        results = self.run_query(query, {"name": name})
        return [
            GraphNode(
                id=str(r["id"]),
                name=r["name"] or "未命名",
                label=r["label"],
                properties=r["properties"] or {}
            )
            for r in results if r["name"]
        ]
    
    def find_entities_by_type(self, entity_type: str, limit: int = 50) -> List[GraphNode]:
        """
        根据类型查找实体
        
        Args:
            entity_type: 实体类型
            limit: 返回数量限制
            
        Returns:
            指定类型的实体列表
        """
        # ✅ 修改：验证实体类型是否有效
        valid_types = [t.value for t in NodeType]
        if entity_type not in valid_types:
            logger.warning(f"无效的实体类型: {entity_type}")
            return []
        
        query = f"""
        MATCH (n:{entity_type})
        RETURN COALESCE(n.name, n.text) as name, labels(n)[0] as label,
               id(n) as id, properties(n) as properties
        LIMIT $limit
        """
        
        results = self.run_query(query, {"limit": limit})
        return [
            GraphNode(
                id=str(r["id"]),
                name=r["name"] or "未命名",
                label=r["label"],
                properties=r["properties"] or {}
            )
            for r in results if r["name"]
        ]
    
    # ===== 关系查询方法 =====
    
    def find_relations(self, 
                      source: Optional[str] = None,
                      target: Optional[str] = None,
                      relation_type: Optional[str] = None,
                      limit: int = 50) -> List[GraphRelation]:
        """
        查找关系 - 支持关系类型验证
        
        Args:
            source: 源实体名称
            target: 目标实体名称  
            relation_type: 关系类型
            limit: 返回数量限制
            
        Returns:
            关系列表
        """
        # ✅ 修改：验证关系类型是否有效
        if relation_type:
            valid_relations = [r.value for r in RelationType]
            if relation_type not in valid_relations:
                logger.warning(f"无效的关系类型: {relation_type}")
                return []
        
        conditions = []
        params = {"limit": limit}
        
        if source:
            conditions.append("(a.name = $source OR a.text = $source)")
            params["source"] = source
        
        if target:
            conditions.append("(b.name = $target OR b.text = $target)")
            params["target"] = target
        
        if relation_type:
            rel_pattern = f"[r:{relation_type}]"
        else:
            rel_pattern = "[r]"
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
        MATCH (a)-{rel_pattern}->(b)
        {where_clause}
        RETURN COALESCE(a.name, a.text) as source, 
               COALESCE(b.name, b.text) as target, 
               type(r) as relation_type,
               properties(r) as properties
        LIMIT $limit
        """
        
        results = self.run_query(query, params)
        return [
            GraphRelation(
                source=r["source"],
                target=r["target"],
                relation_type=r["relation_type"],
                properties=r["properties"] or {}
            )
            for r in results if r["source"] and r["target"]
        ]
    
    def get_entity_neighbors(self, entity_name: str, 
                           relation_types: Optional[List[str]] = None,
                           direction: str = "both") -> Dict[str, Any]:
        """
        获取实体的邻居节点
        
        Args:
            entity_name: 实体名称
            relation_types: 关系类型列表
            direction: 方向 ("in", "out", "both")
            
        Returns:
            邻居节点信息
        """
        # ✅ 修改：验证关系类型
        if relation_types:
            valid_relations = [r.value for r in RelationType]
            relation_types = [rt for rt in relation_types if rt in valid_relations]
            if not relation_types:
                logger.warning("没有有效的关系类型")
                return {"in": [], "out": [], "all": [], "center": None}
        
        rel_filter = ""
        if relation_types:
            rel_types = "|".join(relation_types)
            rel_filter = f":{rel_types}"
        
        if direction == "in":
            pattern = f"(neighbor)-[r{rel_filter}]->(entity)"
        elif direction == "out":
            pattern = f"(entity)-[r{rel_filter}]->(neighbor)"
        else:  # both
            pattern = f"(entity)-[r{rel_filter}]-(neighbor)"
        
        query = f"""
        MATCH (entity)
        WHERE entity.name = $entity_name OR entity.text = $entity_name
        OPTIONAL MATCH {pattern}
        RETURN entity.name as center_name,
               labels(entity)[0] as center_type,
               COALESCE(neighbor.name, neighbor.text) as neighbor_name, 
               labels(neighbor)[0] as neighbor_type,
               type(r) as relation_type,
               CASE 
                 WHEN neighbor IS NULL THEN null
                 WHEN startNode(r) = entity THEN 'out'
                 ELSE 'in'
               END as direction
        """
        
        results = self.run_query(query, {"entity_name": entity_name})
        
        neighbors = {
            "in": [],
            "out": [],
            "all": [],
            "center": None
        }
        
        for r in results:
            # 设置中心节点信息
            if neighbors["center"] is None and r["center_name"]:
                neighbors["center"] = {
                    "name": r["center_name"],
                    "type": r["center_type"]
                }
            
            # 处理邻居节点
            if r["neighbor_name"]:
                neighbor_info = {
                    "name": r["neighbor_name"],
                    "type": r["neighbor_type"],
                    "relation": r["relation_type"]
                }
                
                direction_key = r["direction"]
                if direction_key:
                    neighbors[direction_key].append(neighbor_info)
                    neighbors["all"].append(neighbor_info)
        
        return neighbors
    
    # ===== 路径查询方法 =====
    
    def find_shortest_path(self, source: str, target: str, 
                          max_length: int = 5) -> Optional[List[str]]:
        """
        查找两个实体间的最短路径
        
        Args:
            source: 源实体名称
            target: 目标实体名称
            max_length: 最大路径长度
            
        Returns:
            最短路径节点列表，如果不存在返回None
        """
        query = f"""
        MATCH (source), (target)
        WHERE (source.name = $source OR source.text = $source)
          AND (target.name = $target OR target.text = $target)
        MATCH path = shortestPath((source)-[*1..{max_length}]-(target))
        RETURN [node in nodes(path) | COALESCE(node.name, node.text)] as path_nodes
        """
        
        results = self.run_query(query, {"source": source, "target": target})
        return results[0]["path_nodes"] if results else None
    
    def find_all_paths(self, source: str, target: str,
                      max_length: int = 3, limit: int = 10) -> List[List[str]]:
        """
        查找两个实体间的所有路径
        
        Args:
            source: 源实体名称
            target: 目标实体名称
            max_length: 最大路径长度
            limit: 返回路径数量限制
            
        Returns:
            路径列表，每个路径为节点名称列表
        """
        query = f"""
        MATCH (source), (target)
        WHERE (source.name = $source OR source.text = $source)
          AND (target.name = $target OR target.text = $target)
        MATCH path = (source)-[*1..{max_length}]-(target)
        RETURN [node in nodes(path) | COALESCE(node.name, node.text)] as path_nodes
        LIMIT $limit
        """
        
        results = self.run_query(query, {
            "source": source, 
            "target": target,
            "limit": limit
        })
        return [r["path_nodes"] for r in results]
    
    # ===== 子图查询方法 =====
    
    def get_subgraph(self, center_entity: str, depth: int = 2) -> SearchResult:
        """
        获取以指定实体为中心的子图
        
        Args:
            center_entity: 中心实体名称
            depth: 扩展深度
            
        Returns:
            子图搜索结果
        """
        query = f"""
        MATCH (center)
        WHERE center.name = $center_entity OR center.text = $center_entity
        CALL {{
            WITH center
            MATCH path = (center)-[*1..{depth}]-(node)
            RETURN DISTINCT nodes(path) as path_nodes, relationships(path) as path_rels
        }}
        
        // 收集所有节点
        UNWIND path_nodes as n
        WITH DISTINCT n, path_rels
        
        // 收集所有关系
        UNWIND path_rels as r
        WITH collect(DISTINCT {{
            node_id: id(n),
            node_name: COALESCE(n.name, n.text),
            node_type: labels(n)[0],
            node_props: properties(n)
        }}) as nodes,
        collect(DISTINCT {{
            rel_id: id(r),
            source: COALESCE(startNode(r).name, startNode(r).text),
            target: COALESCE(endNode(r).name, endNode(r).text),
            type: type(r),
            props: properties(r)
        }}) as relationships
        
        RETURN nodes, relationships
        """
        
        results = self.run_query(query, {"center_entity": center_entity})
        
        if not results:
            logger.warning(f"未找到实体: {center_entity}")
            return SearchResult(nodes=[], relations=[], paths=[], total_count=0)
        
        result = results[0]
        
        # 处理节点
        nodes = []
        for node_data in result["nodes"]:
            if node_data["node_name"]:
                nodes.append(GraphNode(
                    id=str(node_data["node_id"]),
                    name=node_data["node_name"],
                    label=node_data["node_type"],
                    properties=node_data["node_props"] or {}
                ))
        
        # 处理关系
        relations = []
        for rel_data in result["relationships"]:
            if rel_data["source"] and rel_data["target"]:
                relations.append(GraphRelation(
                    source=rel_data["source"],
                    target=rel_data["target"],
                    relation_type=rel_data["type"],
                    properties=rel_data["props"] or {}
                ))
        
        return SearchResult(
            nodes=nodes,
            relations=relations,
            paths=[],
            total_count=len(nodes)
        )
    
    # ===== 复杂查询方法 =====
    
    def get_disease_info(self, disease_name: str) -> Dict[str, Any]:
        """
        获取疾病的完整信息
        
        Args:
            disease_name: 疾病名称
            
        Returns:
            疾病相关的所有信息
        """
        query = """
        MATCH (disease:Disease)
        WHERE disease.name = $disease_name
        OPTIONAL MATCH (disease)-[:HAS_SYMPTOM]->(symptom)
        OPTIONAL MATCH (disease)-[:HAS_RISK_FACTOR]->(risk)
        OPTIONAL MATCH (disease)-[:TREATED_BY]->(treatment)
        OPTIONAL MATCH (disease)-[:DIAGNOSED_BY]->(diagnosis)
        OPTIONAL MATCH (disease)-[:CAN_CAUSE]->(complication)
        RETURN 
            disease.name as disease_name,
            properties(disease) as disease_props,
            collect(DISTINCT symptom.name) as symptoms,
            collect(DISTINCT risk.name) as risk_factors,
            collect(DISTINCT treatment.name) as treatments,
            collect(DISTINCT diagnosis.name) as diagnosis_methods,
            collect(DISTINCT complication.name) as complications
        """
        
        results = self.run_query(query, {"disease_name": disease_name})
        if not results:
            logger.info(f"未找到疾病: {disease_name}")
            return {}
        
        result = results[0]
        return {
            "name": result["disease_name"],
            "properties": result["disease_props"] or {},
            "symptoms": [s for s in result["symptoms"] if s],
            "risk_factors": [r for r in result["risk_factors"] if r],
            "treatments": [t for t in result["treatments"] if t],
            "diagnosis_methods": [d for d in result["diagnosis_methods"] if d],
            "complications": [c for c in result["complications"] if c]
        }
    
    def get_treatment_recommendations(self, 
                                    symptoms: List[str],
                                    risk_factors: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        根据症状和风险因素推荐治疗方案
        
        Args:
            symptoms: 症状列表
            risk_factors: 风险因素列表
            
        Returns:
            推荐的治疗方案列表
        """
        # 构建查询条件
        conditions = []
        params = {}
        
        if symptoms:
            conditions.append("symptom.name IN $symptoms")
            params["symptoms"] = symptoms
        
        if risk_factors:
            conditions.append("risk.name IN $risk_factors")
            params["risk_factors"] = risk_factors
        
        if not conditions:
            logger.warning("未提供症状或风险因素")
            return []
        
        where_clause = "WHERE " + " OR ".join(conditions)
        
        query = f"""
        MATCH (disease:Disease)-[:HAS_SYMPTOM]->(symptom)
        OPTIONAL MATCH (disease)-[:HAS_RISK_FACTOR]->(risk)
        {where_clause}
        MATCH (disease)-[:TREATED_BY]->(treatment)
        RETURN DISTINCT
            treatment.name as treatment_name,
            COALESCE(treatment.type, 'general') as treatment_type,
            properties(treatment) as treatment_props,
            count(DISTINCT disease) as relevance_score
        ORDER BY relevance_score DESC
        LIMIT 10
        """
        
        results = self.run_query(query, params)
        return [
            {
                "name": r["treatment_name"],
                "type": r["treatment_type"],
                "properties": r["treatment_props"] or {},
                "relevance_score": r["relevance_score"]
            }
            for r in results
        ]
    
    def search_similar_cases(self, 
                           symptoms: List[str],
                           demographics: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        搜索相似病例 - 基于症状匹配
        
        Args:
            symptoms: 症状列表
            demographics: 人口统计信息 (暂未使用)
            
        Returns:
            相似病例列表
        """
        if not symptoms:
            logger.warning("未提供症状信息")
            return []
        
        query = """
        MATCH (disease:Disease)-[:HAS_SYMPTOM]->(symptom)
        WHERE symptom.name IN $symptoms
        WITH disease, count(symptom) as symptom_match_count
        OPTIONAL MATCH (disease)-[:HAS_SYMPTOM]->(all_symptoms)
        WITH disease, symptom_match_count, count(all_symptoms) as total_symptoms
        WHERE total_symptoms > 0
        RETURN 
            disease.name as disease_name,
            properties(disease) as disease_props,
            symptom_match_count,
            total_symptoms,
            toFloat(symptom_match_count) / total_symptoms as similarity_score
        ORDER BY similarity_score DESC, symptom_match_count DESC
        LIMIT 5
        """
        
        results = self.run_query(query, {"symptoms": symptoms})
        return [
            {
                "disease_name": r["disease_name"],
                "properties": r["disease_props"] or {},
                "symptom_matches": r["symptom_match_count"],
                "total_symptoms": r["total_symptoms"],
                "similarity_score": round(r["similarity_score"], 3)
            }
            for r in results
        ]
    
    # ===== 统计分析方法 =====
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息 - 优化版
        
        Returns:
            统计信息字典
        """
        try:
            # 节点统计
            node_stats_query = """
            MATCH (n)
            RETURN labels(n)[0] as label, count(n) as count
            ORDER BY count DESC
            """
            
            # 关系统计
            rel_stats_query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
            """
            
            # 修改：使用COUNT{}替代size()以兼容新版本Neo4j
            degree_stats_query = """
            MATCH (n)
            WITH n, COUNT { (n)--() } as degree
            RETURN 
                min(degree) as min_degree,
                max(degree) as max_degree,
                avg(degree) as avg_degree,
                count(n) as total_nodes
            """
            
            node_results = self.run_query(node_stats_query)
            rel_results = self.run_query(rel_stats_query)
            degree_results = self.run_query(degree_stats_query)
            
            node_stats = {r["label"]: r["count"] for r in node_results}
            rel_stats = {r["type"]: r["count"] for r in rel_results}
            degree_stats = degree_results[0] if degree_results else {}
            
            return {
                "node_statistics": node_stats,
                "relationship_statistics": rel_stats,
                "degree_statistics": degree_stats,
                "total_nodes": sum(node_stats.values()),
                "total_relationships": sum(rel_stats.values())
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}")
            return {
                "node_statistics": {},
                "relationship_statistics": {},
                "degree_statistics": {},
                "total_nodes": 0,
                "total_relationships": 0
            }
    
    def get_most_connected_entities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取连接度最高的实体 - 优化版，去除重复
        
        Args:
            limit: 返回数量限制
            
        Returns:
            连接度最高的实体列表
        """
        query = """
        MATCH (n)
        WITH n, COUNT { (n)--() } as degree
        WHERE degree > 0
        WITH COALESCE(n.name, n.text) as name, labels(n)[0] as type, degree
        ORDER BY degree DESC, name
        RETURN DISTINCT name, type, degree
        LIMIT $limit
        """
        
        results = self.run_query(query, {"limit": limit})
        return [
            {
                "name": r["name"],
                "type": r["type"],
                "degree": r["degree"]
            }
            for r in results if r["name"]
        ]
    
    # ===== 数据导出方法 =====
    
    def export_subgraph_to_json(self, center_entity: str, 
                               depth: int = 2, 
                               output_file: str = "subgraph.json") -> str:
        """
        导出子图为JSON格式
        
        Args:
            center_entity: 中心实体名称
            depth: 扩展深度
            output_file: 输出文件路径
            
        Returns:
            输出文件路径
        """
        subgraph = self.get_subgraph(center_entity, depth)
        
        if not subgraph.nodes:
            logger.warning(f"子图为空，无法导出: {center_entity}")
            return ""
        
        # 转换为JSON可序列化格式
        export_data = {
            "center_entity": center_entity,
            "depth": depth,
            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "label": node.label,
                    "properties": node.properties
                }
                for node in subgraph.nodes
            ],
            "relationships": [
                {
                    "source": rel.source,
                    "target": rel.target,
                    "type": rel.relation_type,
                    "properties": rel.properties
                }
                for rel in subgraph.relations
            ],
            "statistics": {
                "node_count": len(subgraph.nodes),
                "relationship_count": len(subgraph.relations)
            }
        }
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else "."
        os.makedirs(output_dir, exist_ok=True)
        
        # 写入JSON文件
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"子图已导出到: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"导出子图失败: {str(e)}")
            return ""
    
    # ===== 新增：DeepSeek集成支持方法 =====
    
    def get_entity_context(self, entity_name: str) -> str:
        """
        获取实体的上下文信息，用于DeepSeek问答
        
        Args:
            entity_name: 实体名称
            
        Returns:
            实体的上下文描述文本
        """
        neighbors = self.get_entity_neighbors(entity_name)  # 删除depth参数
        
        if not neighbors["center"]:
            return f"未找到实体: {entity_name}"
        
        context_parts = [
            f"实体: {neighbors['center']['name']} ({neighbors['center']['type']})"
        ]
        
        if neighbors["all"]:
            context_parts.append("相关信息:")
            for neighbor in neighbors["all"][:5]:  # 限制数量
                context_parts.append(f"- {neighbor['relation']}: {neighbor['name']}")
        
        return "\n".join(context_parts)
    
    def search_entities_for_question(self, question: str, limit: int = 10) -> List[str]:
        """
        根据问题搜索相关实体，为DeepSeek提供上下文
        
        Args:
            question: 用户问题
            limit: 返回数量限制
            
        Returns:
            相关实体名称列表
        """
        # 改进：更智能的关键词提取和实体匹配
        import re
        # 提取中文词汇和关键英文单词
        keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]{2,}', question)
        all_entities = []
        
        for keyword in keywords:
            if len(keyword) > 1:  # 过滤掉单字符
                entities = self.find_entity_by_name(keyword, fuzzy=True)
                all_entities.extend([entity.name for entity in entities])
        
        # 去重并限制数量
        unique_entities = list(dict.fromkeys(all_entities))  # 保持顺序的去重
        return unique_entities[:limit]
    
    def get_question_context(self, question: str) -> str:
        """
        为问题获取图谱上下文，用于增强DeepSeek回答 - 改进版
        
        Args:
            question: 用户问题
            
        Returns:
            相关的图谱上下文文本
        """
        import re
        
        # 1. 问题类型识别
        question_type = self._identify_question_type(question)
        
        # 2. 关键实体提取
        entities = self._extract_entities_from_question(question)
        
        # 3. 如果没有找到实体，尝试模糊匹配
        if not entities:
            entities = self._fuzzy_match_entities(question)
        
        if not entities:
            return "未找到相关的图谱信息。"
        
        # 4. 根据问题类型获取相关信息
        context_parts = ["相关图谱信息:"]
        
        for entity_name in entities[:3]:  # 限制实体数量
            entity_info = self._get_contextual_info(entity_name, question_type)
            if entity_info:
                context_parts.append(f"\n{entity_info}")
        
        return "\n".join(context_parts) if len(context_parts) > 1 else "未找到相关的图谱信息。"

    def _identify_question_type(self, question: str) -> str:
        """识别问题类型"""
        symptom_keywords = ["症状", "表现", "征象", "manifestation", "symptom"]
        treatment_keywords = ["治疗", "疗法", "药物", "treatment", "therapy", "medication"]
        cause_keywords = ["原因", "病因", "引起", "导致", "cause", "reason"]
        diagnosis_keywords = ["诊断", "检查", "检测", "diagnosis", "test", "examination"]
        risk_keywords = ["风险", "危险", "因素", "risk", "factor"]
        food_keywords = ["饮食", "食物", "营养", "吃", "food", "diet", "nutrition"]
        
        question_lower = question.lower()
        
        if any(keyword in question_lower for keyword in symptom_keywords):
            return "symptom"
        elif any(keyword in question_lower for keyword in treatment_keywords):
            return "treatment"
        elif any(keyword in question_lower for keyword in cause_keywords):
            return "cause"
        elif any(keyword in question_lower for keyword in diagnosis_keywords):
            return "diagnosis"
        elif any(keyword in question_lower for keyword in risk_keywords):
            return "risk"
        elif any(keyword in question_lower for keyword in food_keywords):
            return "food"
        else:
            return "general"

    def _extract_entities_from_question(self, question: str) -> List[str]:
        """从问题中提取实体"""
        import re
        
        # 提取中文词汇和关键英文单词
        keywords = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', question)
        
        # 医学相关关键词扩展
        medical_keywords = []
        for keyword in keywords:
            if len(keyword) > 1:
                # 直接搜索
                entities = self.find_entity_by_name(keyword, fuzzy=True)
                medical_keywords.extend([entity.name for entity in entities[:2]])
                
                # 尝试相关词汇
                if "糖尿病" in keyword or "diabetes" in keyword.lower():
                    diabetes_entities = self.find_entity_by_name("糖尿病", fuzzy=True)
                    medical_keywords.extend([entity.name for entity in diabetes_entities[:2]])
        
        return list(dict.fromkeys(medical_keywords))  # 去重

    def _fuzzy_match_entities(self, question: str) -> List[str]:
        """模糊匹配实体"""
        # 预定义的疾病关键词映射
        disease_mapping = {
            "糖尿病": ["妊娠期糖尿病", "2型糖尿病"],
            "高血压": ["妊高症", "高血压"],
            "肥胖": ["肥胖症"],
            "贫血": ["缺铁性贫血"],
            "感染": ["泌尿系感染"]
        }
        
        entities = []
        question_lower = question.lower()
        
        for key, values in disease_mapping.items():
            if key in question or key.lower() in question_lower:
                for value in values:
                    found_entities = self.find_entity_by_name(value, fuzzy=False)
                    entities.extend([entity.name for entity in found_entities])
        
        return entities

    def _get_contextual_info(self, entity_name: str, question_type: str) -> str:
        """根据问题类型获取相关上下文信息 - 增强版"""
        try:
            if question_type == "symptom":
                # 查找症状信息 - 支持双向关系
                query = """
                MATCH (entity)-[r]->(target)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                  AND (type(r) = 'HAS_SYMPTOM' OR labels(target)[0] = 'Symptom')
                RETURN collect(DISTINCT target.name) as symptoms
                """
                results = self.run_query(query, {"entity_name": entity_name})
                if results and results[0]["symptoms"]:
                    symptoms = [s for s in results[0]["symptoms"] if s][:5]
                    return f"实体: {entity_name}\n症状: {', '.join(symptoms)}"
            
            elif question_type == "treatment":
                # 查找治疗信息 - 支持双向关系
                query = """
                MATCH (entity)-[r]-(target)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                  AND (type(r) = 'TREATED_BY' OR labels(target)[0] = 'Treatment')
                RETURN collect(DISTINCT target.name) as treatments
                """
                results = self.run_query(query, {"entity_name": entity_name})
                if results and results[0]["treatments"]:
                    treatments = [t for t in results[0]["treatments"] if t][:5]
                    return f"实体: {entity_name}\n治疗方法: {', '.join(treatments)}"
            
            elif question_type == "risk":
                # 查找风险因素 - 支持双向关系
                query = """
                MATCH (entity)-[r]-(target)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                  AND (type(r) = 'HAS_RISK_FACTOR' OR labels(target)[0] = 'RiskFactor')
                RETURN collect(DISTINCT target.name) as risk_factors
                """
                results = self.run_query(query, {"entity_name": entity_name})
                if results and results[0]["risk_factors"]:
                    risks = [r for r in results[0]["risk_factors"] if r][:5]
                    return f"实体: {entity_name}\n风险因素: {', '.join(risks)}"
            
            elif question_type == "food":
                # 查找食物信息 - 多策略查询
                # 策略1: 查找Food类型的节点
                food_query = """
                MATCH (entity)-[r]-(food:Food)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                RETURN collect(DISTINCT food.name) as foods
                """
                
                # 策略2: 查找RECOMMENDED_FOR关系
                recommend_query = """
                MATCH (food)-[:RECOMMENDED_FOR]-(entity)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                  AND labels(food)[0] = 'Food'
                RETURN collect(DISTINCT food.name) as foods
                """
                
                # 策略3: 查找饮食相关的治疗建议
                dietary_query = """
                MATCH (entity)-[r]-(treatment)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                  AND (treatment.name =~ '.*饮食.*|.*diet.*|.*营养.*|.*食.*' 
                       OR labels(treatment)[0] = 'Treatment')
                  AND treatment.name =~ '.*饮食.*|.*diet.*|.*营养.*|.*食.*'
                RETURN collect(DISTINCT treatment.name) as dietary_advice
                """
                
                # 尝试多种查询策略
                for query_name, query in [("食物", food_query), ("推荐", recommend_query)]:
                    results = self.run_query(query, {"entity_name": entity_name})
                    if results and results[0]["foods"]:
                        foods = [f for f in results[0]["foods"] if f and "血糖" not in f][:5]
                        if foods:
                            return f"实体: {entity_name}\n推荐食物: {', '.join(foods)}"
                
                # 如果找不到具体食物，返回饮食建议
                results = self.run_query(dietary_query, {"entity_name": entity_name})
                if results and results[0]["dietary_advice"]:
                    advice = [a for a in results[0]["dietary_advice"] if a][:3]
                    return f"实体: {entity_name}\n饮食建议: {', '.join(advice)}"
            
            elif question_type == "diagnosis":
                # 查找诊断方法
                query = """
                MATCH (entity)-[r]-(target)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                  AND (type(r) = 'DIAGNOSED_BY' OR labels(target)[0] = 'DiagnosticMethod')
                RETURN collect(DISTINCT target.name) as diagnostic_methods
                """
                results = self.run_query(query, {"entity_name": entity_name})
                if results and results[0]["diagnostic_methods"]:
                    methods = [m for m in results[0]["diagnostic_methods"] if m][:5]
                    return f"实体: {entity_name}\n诊断方法: {', '.join(methods)}"
            
            elif question_type == "cause":
                # 查找病因
                query = """
                MATCH (cause)-[:CAN_CAUSE]->(entity)
                WHERE (entity.name = $entity_name OR entity.text = $entity_name)
                RETURN collect(DISTINCT cause.name) as causes
                """
                results = self.run_query(query, {"entity_name": entity_name})
                if results and results[0]["causes"]:
                    causes = [c for c in results[0]["causes"] if c][:5]
                    return f"实体: {entity_name}\n可能病因: {', '.join(causes)}"
            
            # 如果没有找到特定类型的信息，返回通用邻居信息
            neighbors = self.get_entity_neighbors(entity_name)
            if neighbors["center"] and neighbors["all"]:
                context_parts = [f"实体: {neighbors['center']['name']} ({neighbors['center']['type']})"]
                context_parts.append("相关信息:")
                for neighbor in neighbors["all"][:3]:
                    context_parts.append(f"- {neighbor['relation']}: {neighbor['name']}")
                return "\n".join(context_parts)
            
            return ""
        except Exception as e:
            logger.error(f"获取上下文信息失败: {str(e)}")
            return ""

# ===== 工具函数 =====

def create_graph_tool(**kwargs) -> GraphTool:
    """
    创建图谱工具实例的便捷函数
    
    Args:
        **kwargs: GraphTool初始化参数
        
    Returns:
        GraphTool实例
    """
    return GraphTool(**kwargs)


def test_graph_connection(uri: str = "neo4j://127.0.0.1:7687", 
                         user: str = "neo4j", 
                         password: str = r"42810916402\Ssnx") -> bool:
    """
    测试图谱数据库连接
    
    Args:
        uri: Neo4j连接地址
        user: 用户名  
        password: 密码
        
    Returns:
        连接是否成功
    """
    try:
        with GraphTool(uri, user, password) as tool:
            stats = tool.get_graph_statistics()
            logger.info(f"连接测试成功，图谱统计: {stats['total_nodes']} 个节点，{stats['total_relationships']} 个关系")
            return True
    except Exception as e:
        logger.error(f"连接测试失败: {str(e)}")
        return False


# ===== 示例使用代码 =====

if __name__ == "__main__":
    # 测试代码
    print("🔧 图谱工具测试开始...")
    
    # 1. 测试连接
    if not test_graph_connection():
        print("❌ 数据库连接失败，请检查配置")
        exit(1)
    
    try:
        with GraphTool() as tool:
            print("\n📊 获取图谱统计信息...")
            stats = tool.get_graph_statistics()
            print(f"节点统计: {stats['node_statistics']}")
            print(f"关系统计: {stats['relationship_statistics']}")
            
            print("\n🔍 测试实体查询...")
            # 查找疾病实体
            diseases = tool.find_entities_by_type("Disease", limit=5)
            if diseases:
                print(f"找到 {len(diseases)} 个疾病:")
                for disease in diseases:
                    print(f"  - {disease.name} ({disease.label})")
                    
                # 测试疾病信息查询
                test_disease = diseases[0].name
                print(f"\n📋 获取疾病信息: {test_disease}")
                disease_info = tool.get_disease_info(test_disease)
                if disease_info:
                    print(f"症状: {disease_info.get('symptoms', [])}")
                    print(f"治疗方法: {disease_info.get('treatments', [])}")
            
            print("\n🌐 测试连接度分析...")
            top_entities = tool.get_most_connected_entities(limit=5)
            if top_entities:
                print("连接度最高的实体:")
                for entity in top_entities:
                    print(f"  - {entity['name']}: {entity['degree']} 个连接")
            
            print("\n❓ 测试问题上下文...")
            test_question = "如何诊断妊娠期糖尿病？"
            context = tool.get_question_context(test_question)
            print(f"问题: {test_question}")
            print(f"图谱上下文:\n{context}")
            
    except Exception as e:
        logger.error(f"测试过程中出现错误: {str(e)}")
        print(f"❌ 测试失败: {str(e)}")
    
    print("\n✅ 图谱工具测试完成!")
