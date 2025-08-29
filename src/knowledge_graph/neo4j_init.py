"""
Neo4j数据库初始化脚本 - 修复版本
解决编码问题、内存溢出和关系匹配问题
"""

import os
import sys
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase
import unicodedata

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    from .graph_schema import GDMKnowledgeGraphSchema, NodeType, RelationType
except ImportError:
    # 如果是直接运行脚本，尝试相对导入
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    from graph_schema import GDMKnowledgeGraphSchema, NodeType, RelationType

# 设置日志 - 修复编码问题
os.makedirs("logs", exist_ok=True)

# 防止重复日志
if not logging.getLogger("neo4j_init").handlers:
    # 现有的日志配置代码
    pass

# 创建自定义的Handler来处理编码问题
class SafeFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding='utf-8', delay=False):
        super().__init__(filename, mode, encoding, delay)
    
    def emit(self, record):
        try:
            # 清理记录中的特殊字符
            if hasattr(record, 'msg') and isinstance(record.msg, str):
                record.msg = self._clean_text(record.msg)
            if hasattr(record, 'args') and record.args:
                cleaned_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        cleaned_args.append(self._clean_text(arg))
                    else:
                        cleaned_args.append(arg)
                record.args = tuple(cleaned_args)
            super().emit(record)
        except (UnicodeEncodeError, UnicodeDecodeError):
            # 如果仍然有编码问题，使用安全的替代方法
            try:
                if hasattr(record, 'msg'):
                    record.msg = str(record.msg).encode('ascii', 'ignore').decode('ascii')
                super().emit(record)
            except:
                pass  # 忽略无法处理的日志

    def _clean_text(self, text):
        """清理文本中的特殊字符"""
        if not isinstance(text, str):
            return text
        # 移除或替换特殊的Unicode字符
        text = unicodedata.normalize('NFKD', text)
        # 替换特殊空格字符
        text = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F-\u206F]', ' ', text)
        return text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        SafeFileHandler("logs/neo4j_init.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("neo4j_init")

class Neo4jInitializer:
    """Neo4j数据库初始化器 - 增强版"""
    
    def __init__(self, uri: str = "neo4j://127.0.0.1:7687", 
                 username: str = "neo4j", 
                 password: str = r"42810916402\Ssnx"):  # ✅ 修复：使用原始字符串
        """初始化Neo4j连接"""
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.schema = GDMKnowledgeGraphSchema()
        self.batch_size = 100  # 批处理大小
        self._connect()
    
    def _connect(self):
        """建立数据库连接"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            # 测试连接
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"成功连接到Neo4j: {self.uri}")
        except Exception as e:
            logger.error(f"连接Neo4j失败: {str(e)}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")
    
    def _clean_text(self, text):
        """清理文本中的特殊字符"""
        if not isinstance(text, str):
            return text
        # 标准化Unicode字符
        text = unicodedata.normalize('NFKD', text)
        # 替换特殊空格字符
        text = re.sub(r'[\u2000-\u200F\u2028-\u202F\u205F-\u206F]', ' ', text)
        # 移除控制字符
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        return text.strip()
    
    def run_query(self, query: str, parameters: Optional[dict] = None):
        """执行Cypher查询 - 优化版本"""
        try:
            # ✅ 修复：使用 execute_query 方法提高性能
            result = self.driver.execute_query(query, parameters or {})
            return result.records
        except Exception as e:
            logger.error(f"查询执行失败: {str(e)}")
            logger.error(f"查询: {query[:100]}...")  # 只显示前100个字符
            logger.error(f"参数: {parameters}")
            raise
    
    def clear_database(self):
        """清空数据库 - 优化版本"""
        logger.info("开始清空数据库...")
        
        try:
            # ✅ 修复：使用更高效的批量删除
            while True:
                result = self.driver.execute_query(
                    "MATCH (n) WITH n LIMIT 1000 DETACH DELETE n RETURN count(*) as deleted"
                )
                deleted_count = result.records[0]['deleted']
                if deleted_count == 0:
                    break
                logger.info(f"已删除 {deleted_count} 个节点")
        except Exception as e:
            logger.error(f"清空数据库失败: {str(e)}")
            raise
        
        logger.info("数据库已清空")
    
    def init_schema(self):
        """初始化图谱模式"""
        logger.info("开始初始化Neo4j模式...")
        
        # 首先创建约束
        constraints = self.schema.get_cypher_constraints()
        for constraint in constraints:
            try:
                self.driver.execute_query(constraint)
                logger.info(f"约束创建成功: {constraint[:50]}...")
            except Exception as e:
                # ✅ 修复：检查约束是否已存在
                if "already exists" in str(e).lower() or "equivalent constraint already exists" in str(e).lower():
                    logger.info(f"约束已存在，跳过: {constraint[:50]}...")
                else:
                    logger.warning(f"约束创建失败: {str(e)}")
        
        # 然后创建索引
        indexes = self.schema.get_cypher_indexes()
        for index in indexes:
            try:
                self.driver.execute_query(index)
                logger.info(f"索引创建成功: {index[:50]}...")
            except Exception as e:
                # ✅ 修复：检查索引是否已存在
                if "already exists" in str(e).lower() or "equivalent index already exists" in str(e).lower():
                    logger.info(f"索引已存在，跳过: {index[:50]}...")
                else:
                    logger.warning(f"索引创建失败: {str(e)}")
        
        logger.info("Neo4j模式初始化完成")
    
    def import_knowledge(self, knowledge_file: str = "models/knowledge/gdm_knowledge.json"):
        """导入知识到Neo4j"""
        if not os.path.exists(knowledge_file):
            raise ValueError(f"知识文件不存在: {knowledge_file}")
        
        logger.info(f"从 {knowledge_file} 导入知识...")
        self.import_knowledge_data(knowledge_file)
        logger.info("知识导入完成")
    
    def import_knowledge_data(self, knowledge_file: str = "models/knowledge/gdm_knowledge.json"):
        """导入知识数据 - 优化版本"""
        knowledge_path = Path(knowledge_file)
        if not knowledge_path.exists():
            logger.error(f"知识文件不存在: {knowledge_file}")
            return
        
        try:
            with open(knowledge_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            entities = data.get('entities', [])
            relations = data.get('relations', [])
            
            # 分批处理实体
            entities_imported = self._import_entities_batch(entities, str(knowledge_file))
            
            # 分批处理关系
            relations_imported = self._import_relations_batch(relations, str(knowledge_file))
            
            logger.info(f"知识导入完成: {entities_imported} 个实体, {relations_imported} 个关系")
            
        except Exception as e:
            logger.error(f"导入知识文件失败 {knowledge_file}: {str(e)}")
    
    def _import_entities_batch(self, entities: List[Dict[str, Any]], source: str) -> int:
        """批量导入实体数据"""
        imported_count = 0
        total_entities = len(entities)
        
        logger.info(f"开始导入 {total_entities} 个实体...")
        
        # 按节点类型分组
        entities_by_type = {}
        for entity in entities:
            entity_type = entity.get('type', '')
            if entity_type:
                if entity_type not in entities_by_type:
                    entities_by_type[entity_type] = []
                entities_by_type[entity_type].append(entity)
        
        # 分类型批量导入
        for entity_type, type_entities in entities_by_type.items():
            logger.info(f"导入 {entity_type} 类型节点: {len(type_entities)} 个")
            
            # 分批处理
            for i in range(0, len(type_entities), self.batch_size):
                batch = type_entities[i:i + self.batch_size]
                imported_count += self._import_entity_batch(batch, entity_type, source)
        
        logger.info(f"实体导入完成: {imported_count}/{total_entities}")
        return imported_count
    
    def _import_entity_batch(self, entities_batch: List[Dict[str, Any]], entity_type: str, source: str) -> int:
        """导入单个批次的实体 - 优化版本"""
        if not entities_batch:
            return 0
        
        try:
            # 准备批量数据
            batch_data = []
            for entity in entities_batch:
                entity_name = self._clean_text(entity.get('entity', ''))
                description = self._clean_text(entity.get('description', ''))
                attributes = entity.get('attributes', {})
                
                if not entity_name:
                    continue
                
                # 清理属性值
                cleaned_attributes = {}
                for key, value in attributes.items():
                    if isinstance(value, str):
                        cleaned_attributes[key] = self._clean_text(value)
                    else:
                        cleaned_attributes[key] = value
                
                if entity_type == 'Question':
                    properties = {
                        'text': entity_name,
                        'description': description,
                        'category': cleaned_attributes.get('category', 'general'),
                        'source': source
                    }
                    properties.update(cleaned_attributes)
                    batch_data.append({'text': entity_name, 'properties': properties})
                else:
                    properties = {
                        'name': entity_name,
                        'description': description,
                        'source': source
                    }
                    properties.update(cleaned_attributes)
                    batch_data.append({'name': entity_name, 'properties': properties})
            
            if not batch_data:
                return 0
            
            # ✅ 修复：使用事务执行批量插入
            if entity_type == 'Question':
                cypher = f"""
                UNWIND $batch_data as item
                MERGE (n:{entity_type} {{text: item.text}})
                SET n += item.properties
                RETURN count(n) as created_count
                """
            else:
                cypher = f"""
                UNWIND $batch_data as item
                MERGE (n:{entity_type} {{name: item.name}})
                SET n += item.properties
                RETURN count(n) as created_count
                """
            
            result = self.driver.execute_query(cypher, {'batch_data': batch_data})
            created_count = result.records[0]['created_count']
            return created_count
                
        except Exception as e:
            logger.error(f"批量导入实体失败 ({entity_type}): {str(e)}")
            return 0
    
    def _import_relations_batch(self, relations: List[Dict[str, Any]], source: str) -> int:
        """批量导入关系数据 - 修复版本"""
        imported_count = 0
        total_relations = len(relations)
        
        logger.info(f"开始导入 {total_relations} 个关系...")
        
        # 按关系类型分组
        relations_by_type = {}
        for relation in relations:
            predicate = relation.get('predicate', '')
            if predicate:
                if predicate not in relations_by_type:
                    relations_by_type[predicate] = []
                relations_by_type[predicate].append(relation)
        
        # 分类型批量导入
        for rel_type, type_relations in relations_by_type.items():
            if rel_type not in [rel.value for rel in RelationType]:
                logger.warning(f"跳过不支持的关系类型: {rel_type}")
                continue
            
            logger.info(f"导入 {rel_type} 关系: {len(type_relations)} 个")
            
            # 分批处理
            type_imported = 0
            for i in range(0, len(type_relations), self.batch_size):
                batch = type_relations[i:i + self.batch_size]
                batch_success = self._import_relation_batch(batch, rel_type, source)
                type_imported += batch_success
            
            logger.info(f"{rel_type} 关系导入完成: {type_imported}/{len(type_relations)}")
            imported_count += type_imported
        
        logger.info(f"关系导入完成: {imported_count}/{total_relations}")
        return imported_count
    
    def _import_relation_batch(self, relations_batch: List[Dict[str, Any]], rel_type: str, source: str) -> int:
        """导入单个批次的关系 - 修复版本"""
        if not relations_batch:
            return 0
        
        success_count = 0
        
        try:
            # 准备批量数据
            batch_data = []
            for relation in relations_batch:
                subject = self._clean_text(relation.get('subject', ''))
                object_name = self._clean_text(relation.get('object', ''))
                
                if not subject or not object_name:
                    continue
                
                # 清理属性
                cleaned_attributes = {'source': source}
                attributes = relation.get('attributes', {})
                for key, value in attributes.items():
                    if isinstance(value, str):
                        cleaned_attributes[key] = self._clean_text(value)
                    else:
                        cleaned_attributes[key] = value
                
                batch_data.append({
                    'subject': subject,
                    'object': object_name,
                    'properties': cleaned_attributes
                })
            
            if not batch_data:
                return 0
            
            # ✅ 改进的匹配策略 - 分步骤执行
            # 第一步：精确匹配
            exact_match_cypher = f"""
            UNWIND $batch_data as item
            OPTIONAL MATCH (a) WHERE a.name = item.subject OR a.text = item.subject
            OPTIONAL MATCH (b) WHERE b.name = item.object OR b.text = item.object
            WITH item, a, b
            WHERE a IS NOT NULL AND b IS NOT NULL
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += item.properties
            RETURN count(r) as created_count
            """
            
            result = self.run_query(exact_match_cypher, {'batch_data': batch_data})
            exact_matches = result[0]['created_count'] if result else 0
            
            # 第二步：对于未匹配的，尝试模糊匹配
            if exact_matches < len(batch_data):
                fuzzy_match_cypher = f"""
                UNWIND $batch_data as item
                // 检查是否已经存在精确匹配的关系
                OPTIONAL MATCH (existing_a)-[existing_r:{rel_type}]->(existing_b)
                WHERE (existing_a.name = item.subject OR existing_a.text = item.subject)
                  AND (existing_b.name = item.object OR existing_b.text = item.object)
                
                // 如果不存在，尝试模糊匹配
                WITH item WHERE existing_r IS NULL
                OPTIONAL MATCH (a) WHERE 
                    toLower(replace(a.name, ' ', '')) = toLower(replace(item.subject, ' ', '')) OR
                    toLower(replace(coalesce(a.text, ''), ' ', '')) = toLower(replace(item.subject, ' ', ''))
                OPTIONAL MATCH (b) WHERE 
                    toLower(replace(b.name, ' ', '')) = toLower(replace(item.object, ' ', '')) OR
                    toLower(replace(coalesce(b.text, ''), ' ', '')) = toLower(replace(item.object, ' ', ''))
                
                WITH item, a, b
                WHERE a IS NOT NULL AND b IS NOT NULL
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += item.properties
                RETURN count(r) as created_count
                """
                
                fuzzy_result = self.run_query(fuzzy_match_cypher, {'batch_data': batch_data})
                fuzzy_matches = fuzzy_result[0]['created_count'] if fuzzy_result else 0
                success_count = exact_matches + fuzzy_matches
            else:
                success_count = exact_matches
            
            # 详细记录失败信息
            failed_count = len(batch_data) - success_count
            if failed_count > 0:
                logger.warning(f"批次中 {failed_count}/{len(batch_data)} 个{rel_type}关系创建失败")
                
                # 分析失败原因（但不输出太多详细信息）
                if failed_count > len(batch_data) * 0.3:  # 如果失败率超过30%，才详细分析
                    self._analyze_failed_relations(batch_data[:3], rel_type)  # 只分析前3个样本
                    
        except Exception as e:
            logger.error(f"批量导入关系失败 ({rel_type}): {str(e)}")
            return 0
        
        return success_count

    def _analyze_failed_relations(self, batch_data: List[Dict], rel_type: str):
        """分析关系创建失败的原因"""
        try:
            # 检查缺失的节点
            all_subjects = [item['subject'] for item in batch_data]
            all_objects = [item['object'] for item in batch_data]
            
            # 查询存在的节点
            existing_query = """
            UNWIND $names as name
            OPTIONAL MATCH (n) WHERE n.name = name OR n.text = name
            RETURN name, n IS NOT NULL as exists
            """
            
            subject_results = self.run_query(existing_query, {'names': all_subjects})
            object_results = self.run_query(existing_query, {'names': all_objects})
            
            missing_subjects = [r['name'] for r in subject_results if not r['exists']]
            missing_objects = [r['name'] for r in object_results if not r['exists']]
            
            if missing_subjects:
                logger.debug(f"{rel_type} 缺失的主语节点示例: {missing_subjects[:3]}")
            if missing_objects:
                logger.debug(f"{rel_type} 缺失的宾语节点示例: {missing_objects[:3]}")
                
        except Exception as e:
            logger.debug(f"分析失败关系时出错: {str(e)}")
    
    # ==================== 可视化支持功能 - 优化版本 ====================
    
    def export_for_visualization(self, output_file: str = "visualization/graph_data.json", 
                               max_nodes: int = 500, 
                               node_types: List[str] = None,
                               include_orphans: bool = False) -> Dict[str, Any]:
        """导出图数据用于前端可视化 - 优化版本"""
        logger.info(f"开始导出可视化数据到 {output_file}...")
        
        try:
            # 构建节点查询
            if include_orphans:
                # 包含孤立节点
                if node_types:
                    nodes_query = """
                    MATCH (n)
                    WHERE any(label IN labels(n) WHERE label IN $node_types)
                    RETURN 
                        id(n) as id,
                        labels(n) as labels,
                        COALESCE(n.name, n.text) as name,
                        n.description as description,
                        properties(n) as properties
                    LIMIT $max_nodes
                    """
                    node_results = self.run_query(nodes_query, {
                        'node_types': node_types, 
                        'max_nodes': max_nodes
                    })
                else:
                    nodes_query = """
                    MATCH (n)
                    RETURN 
                        id(n) as id,
                        labels(n) as labels,
                        COALESCE(n.name, n.text) as name,
                        n.description as description,
                        properties(n) as properties
                    LIMIT $max_nodes
                    """
                    node_results = self.run_query(nodes_query, {'max_nodes': max_nodes})
            else:
                # 不包含孤立节点
                if node_types:
                    nodes_query = """
                    MATCH (n)
                    WHERE (n)--() AND any(label IN labels(n) WHERE label IN $node_types)
                    RETURN 
                        id(n) as id,
                        labels(n) as labels,
                        COALESCE(n.name, n.text) as name,
                        n.description as description,
                        properties(n) as properties
                    LIMIT $max_nodes
                    """
                    node_results = self.run_query(nodes_query, {
                        'node_types': node_types,
                        'max_nodes': max_nodes
                    })
                else:
                    nodes_query = """
                    MATCH (n)
                    WHERE (n)--()
                    RETURN 
                        id(n) as id,
                        labels(n) as labels,
                        COALESCE(n.name, n.text) as name,
                        n.description as description,
                        properties(n) as properties
                    LIMIT $max_nodes
                    """
                    node_results = self.run_query(nodes_query, {'max_nodes': max_nodes})
            
            # 获取节点ID集合用于关系过滤
            node_ids = [record['id'] for record in node_results]
            
            # 查询关系数据（只包含导出节点之间的关系）
            if node_ids:
                relationships_query = """
                MATCH (a)-[r]->(b)
                WHERE id(a) IN $node_ids AND id(b) IN $node_ids
                RETURN 
                    id(r) as id,
                    id(a) as source,
                    id(b) as target,
                    type(r) as type,
                    properties(r) as properties
                """
                
                rel_results = self.run_query(relationships_query, {'node_ids': node_ids})
            else:
                rel_results = []
            
            # 转换为D3.js兼容格式
            visualization_data = self._convert_to_d3_format(node_results, rel_results)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 写入JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(visualization_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"可视化数据导出完成: {len(visualization_data['nodes'])} 节点, {len(visualization_data['links'])} 关系")
            
            return visualization_data
            
        except Exception as e:
            logger.error(f"导出可视化数据失败: {str(e)}")
            raise
    
    def _convert_to_d3_format(self, node_results: List[dict], rel_results: List[dict]) -> Dict[str, Any]:
        """转换为D3.js兼容的数据格式"""
        
        # 节点颜色映射
        node_colors = {
            'Disease': '#e74c3c',
            'Symptom': '#f39c12', 
            'RiskFactor': '#e67e22',
            'Treatment': '#27ae60',
            'Food': '#2ecc71',
            'DiagnosticMethod': '#3498db',
            'Complication': '#9b59b6',
            'Guideline': '#34495e',
            'Question': '#1abc9c',
            'MedicalConcept': '#95a5a6'
        }
        
        # 转换节点
        nodes = []
        for record in node_results:
            labels = record['labels']
            primary_label = labels[0] if labels else 'Unknown'
            
            # 清理节点名称
            node_name = record['name'] or f"Node_{record['id']}"
            node_name = self._clean_text(node_name)
            
            # 清理描述
            description = record['description'] or ''
            description = self._clean_text(description)
            
            node = {
                'id': record['id'],
                'name': node_name,
                'label': primary_label,
                'labels': labels,
                'description': description,
                'color': node_colors.get(primary_label, '#bdc3c7'),
                'size': self._calculate_node_size(primary_label),
                'properties': record['properties'] or {}
            }
            nodes.append(node)
        
        # 转换关系
        links = []
        for record in rel_results:
            link = {
                'id': record['id'],
                'source': record['source'],
                'target': record['target'],
                'type': record['type'],
                'label': record['type'],
                'properties': record['properties'] or {},
                'strength': record['properties'].get('strength', 1.0) if record['properties'] else 1.0
            }
            links.append(link)
        
        return {
            'nodes': nodes,
            'links': links,
            'meta': {
                'total_nodes': len(nodes),
                'total_links': len(links),
                'node_types': list(set(node['label'] for node in nodes)),
                'link_types': list(set(link['type'] for link in links)),
                'export_timestamp': int(__import__('time').time() * 1000), 
                'color_scheme': node_colors
            }
        }
    
    def _calculate_node_size(self, node_type: str) -> int:
        """根据节点类型计算可视化尺寸"""
        size_mapping = {
            'Disease': 20,
            'Symptom': 15,
            'Treatment': 18,
            'Food': 12,
            'RiskFactor': 16,
            'DiagnosticMethod': 14,
            'Complication': 17,
            'Guideline': 13,
            'Question': 11,
            'MedicalConcept': 10
        }
        return size_mapping.get(node_type, 10)
    
    def export_subgraph_for_visualization(self, center_node: str, max_depth: int = 2, 
                                        output_file: str = "visualization/subgraph_data.json") -> Dict[str, Any]:
        """导出以特定节点为中心的子图用于可视化"""
        logger.info(f"导出以 '{center_node}' 为中心的子图 (深度={max_depth})...")
        
        try:
            # 查询子图数据
            subgraph_query = f"""
            MATCH path = (center)-[*1..{max_depth}]-(connected)
            WHERE center.name = $center_node OR center.text = $center_node
            WITH nodes(path) as path_nodes, relationships(path) as path_rels
            UNWIND path_nodes as n
            WITH collect(DISTINCT n) as all_nodes, path_rels
            UNWIND path_rels as r
            WITH all_nodes, collect(DISTINCT r) as all_rels
            
            UNWIND all_nodes as node
            WITH all_rels, 
                 collect({{
                    id: id(node),
                    labels: labels(node),
                    name: COALESCE(node.name, node.text),
                    description: node.description,
                    properties: properties(node)
                 }}) as nodes
            
            UNWIND all_rels as rel
            RETURN nodes,
                   collect({{
                       id: id(rel),
                       source: id(startNode(rel)),
                       target: id(endNode(rel)),
                       type: type(rel),
                       properties: properties(rel)
                   }}) as relationships
            """
            
            result = self.run_query(subgraph_query, {'center_node': center_node})
            
            if result:
                record = result[0]
                visualization_data = self._convert_to_d3_format(
                    record['nodes'], 
                    record['relationships']
                )
                
                # 标记中心节点
                for node in visualization_data['nodes']:
                    if node['name'] == center_node:
                        node['is_center'] = True
                        node['size'] = node['size'] * 1.5  # 中心节点更大
                        break
                
                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                # 写入文件
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(visualization_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"子图导出完成: {len(visualization_data['nodes'])} 节点, {len(visualization_data['links'])} 关系")
                return visualization_data
            else:
                logger.warning(f"未找到节点: {center_node}")
                return {'nodes': [], 'links': [], 'meta': {}}
                
        except Exception as e:
            logger.error(f"导出子图失败: {str(e)}")
            raise
    
    def generate_visualization_html(self, 
                                  graph_data_file: str = "visualization/graph_data.json",
                                  output_file: str = "visualization/knowledge_graph.html") -> str:
        """生成知识图谱可视化HTML文件"""
        logger.info(f"生成可视化HTML文件: {output_file}")
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # HTML模板
            html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>妊娠期糖尿病知识图谱</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        
        .controls {
            padding: 15px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .control-group {
            display: inline-block;
            margin-right: 20px;
        }
        
        .control-group label {
            display: inline-block;
            width: 80px;
            font-weight: bold;
        }
        
        .control-group select, .control-group input {
            width: 150px;
            padding: 5px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        #graph {
            width: 100%;
            height: 600px;
            border: 1px solid #ddd;
        }
        
        .info-panel {
            position: absolute;
            top: 80px;
            right: 20px;
            width: 300px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            display: none;
            z-index: 1000;
        }
        
        .info-panel h3 {
            margin-top: 0;
            color: #333;
        }
        
        .node {
            stroke: #fff;
            stroke-width: 2px;
            cursor: pointer;
        }
        
        .link {
            fill: none;
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 1px;
        }
        
        .node-label {
            fill: #333;
            font-size: 12px;
            text-anchor: middle;
            pointer-events: none;
        }
        
        .link-label {
            fill: #666;
            font-size: 10px;
            text-anchor: middle;
            pointer-events: none;
        }
        
        .stats {
            padding: 15px;
            background: #f8f9fa;
            border-top: 1px solid #dee2e6;
            text-align: center;
        }
        
        .stat-item {
            display: inline-block;
            margin: 0 20px;
            text-align: center;
        }
        
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .stat-label {
            font-size: 12px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>妊娠期糖尿病知识图谱</h1>
            <p>交互式知识图谱可视化</p>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label>节点类型:</label>
                <select id="nodeTypeFilter">
                    <option value="">全部</option>
                </select>
            </div>
            
            <div class="control-group">
                <label>搜索:</label>
                <input type="text" id="searchInput" placeholder="输入节点名称...">
            </div>
            
            <div class="control-group">
                <label>链接强度:</label>
                <input type="range" id="linkStrengthSlider" min="0" max="2" step="0.1" value="1">
            </div>
            
            <button onclick="resetGraph()">重置视图</button>
            <button onclick="exportGraph()">导出图片</button>
        </div>
        
        <div style="position: relative;">
            <svg id="graph"></svg>
            <div id="infoPanel" class="info-panel">
                <h3 id="infoTitle">节点信息</h3>
                <div id="infoContent"></div>
            </div>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <div class="stat-number" id="nodeCount">0</div>
                <div class="stat-label">节点数量</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="linkCount">0</div>
                <div class="stat-label">关系数量</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="nodeTypeCount">0</div>
                <div class="stat-label">节点类型</div>
            </div>
        </div>
    </div>

    <script>
        // 图数据和可视化变量
        let graphData = {nodes: [], links: []};
        let svg, simulation, nodes, links, nodeLabels, linkLabels;
        let width = 1160, height = 600;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            initVisualization();
            loadGraphData();
        });
        
        function initVisualization() {
            svg = d3.select("#graph")
                .attr("width", width)
                .attr("height", height);
            
            // 创建力导向布局
            simulation = d3.forceSimulation()
                .force("link", d3.forceLink().id(d => d.id).distance(100))
                .force("charge", d3.forceManyBody().strength(-300))
                .force("center", d3.forceCenter(width / 2, height / 2))
                .force("collision", d3.forceCollide().radius(30));
        }
        
        function loadGraphData() {
            d3.json("graph_data.json").then(function(data) {
                graphData = data;
                updateStats();
                populateNodeTypeFilter();
                renderGraph();
                setupEventListeners();
            }).catch(function(error) {
                console.error("加载图数据失败:", error);
                // 使用示例数据
                graphData = {
                    nodes: [
                        {id: 1, name: "妊娠期糖尿病", label: "Disease", color: "#e74c3c", size: 20},
                        {id: 2, name: "高血糖", label: "Symptom", color: "#f39c12", size: 15},
                        {id: 3, name: "胰岛素治疗", label: "Treatment", color: "#27ae60", size: 18}
                    ],
                    links: [
                        {source: 1, target: 2, type: "HAS_SYMPTOM", label: "具有症状"},
                        {source: 1, target: 3, type: "TREATED_BY", label: "治疗方法"}
                    ]
                };
                updateStats();
                populateNodeTypeFilter();
                renderGraph();
                setupEventListeners();
            });
        }
        
        function renderGraph() {
            // 清除之前的元素
            svg.selectAll("*").remove();
            
            // 创建链接
            links = svg.selectAll(".link")
                .data(graphData.links)
                .enter().append("line")
                .attr("class", "link")
                .attr("stroke-width", d => Math.sqrt(d.strength || 1));
            
            // 创建节点
            nodes = svg.selectAll(".node")
                .data(graphData.nodes)
                .enter().append("circle")
                .attr("class", "node")
                .attr("r", d => d.size || 10)
                .attr("fill", d => d.color || "#999")
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended));
            
            // 节点标签
            nodeLabels = svg.selectAll(".node-label")
                .data(graphData.nodes)
                .enter().append("text")
                .attr("class", "node-label")
                .text(d => d.name.length > 10 ? d.name.substring(0, 10) + "..." : d.name);
            
            // 链接标签
            linkLabels = svg.selectAll(".link-label")
                .data(graphData.links)
                .enter().append("text")
                .attr("class", "link-label")
                .text(d => d.label || d.type);
            
            // 节点点击事件
            nodes.on("click", function(event, d) {
                showNodeInfo(d);
            });
            
            // 更新仿真
            simulation.nodes(graphData.nodes);
            simulation.force("link").links(graphData.links);
            simulation.on("tick", ticked);
            simulation.restart();
        }
        
        function ticked() {
            links
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            nodes
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            nodeLabels
                .attr("x", d => d.x)
                .attr("y", d => d.y + 5);
            
            linkLabels
                .attr("x", d => (d.source.x + d.target.x) / 2)
                .attr("y", d => (d.source.y + d.target.y) / 2);
        }
        
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        function showNodeInfo(node) {
            const panel = document.getElementById('infoPanel');
            const title = document.getElementById('infoTitle');
            const content = document.getElementById('infoContent');
            
            title.textContent = node.name;
            
            let html = `
                <p><strong>类型:</strong> ${node.label}</p>
                <p><strong>描述:</strong> ${node.description || '暂无描述'}</p>
            `;
            
            if (node.properties) {
                html += '<h4>属性:</h4><ul>';
                for (const [key, value] of Object.entries(node.properties)) {
                    if (key !== 'name' && key !== 'description') {
                        html += `<li><strong>${key}:</strong> ${value}</li>`;
                    }
                }
                html += '</ul>';
            }
            
            content.innerHTML = html;
            panel.style.display = 'block';
        }
        
        function updateStats() {
            document.getElementById('nodeCount').textContent = graphData.nodes.length;
            document.getElementById('linkCount').textContent = graphData.links.length;
            
            const nodeTypes = [...new Set(graphData.nodes.map(n => n.label))];
            document.getElementById('nodeTypeCount').textContent = nodeTypes.length;
        }
        
        function populateNodeTypeFilter() {
            const select = document.getElementById('nodeTypeFilter');
            const nodeTypes = [...new Set(graphData.nodes.map(n => n.label))];
            
            nodeTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type;
                option.textContent = type;
                select.appendChild(option);
            });
        }
        
        function setupEventListeners() {
            // 节点类型筛选
            document.getElementById('nodeTypeFilter').addEventListener('change', function() {
                filterByNodeType(this.value);
            });
            
            // 搜索功能
            document.getElementById('searchInput').addEventListener('input', function() {
                searchNodes(this.value);
            });
            
            // 链接强度调节
            document.getElementById('linkStrengthSlider').addEventListener('input', function() {
                adjustLinkStrength(this.value);
            });
            
            // 点击空白处隐藏信息面板
            document.addEventListener('click', function(event) {
                if (!event.target.closest('.node') && !event.target.closest('.info-panel')) {
                    document.getElementById('infoPanel').style.display = 'none';
                }
            });
        }
        
        function filterByNodeType(type) {
            nodes.style("opacity", d => type === "" || d.label === type ? 1 : 0.1);
            nodeLabels.style("opacity", d => type === "" || d.label === type ? 1 : 0.1);
        }
        
        function searchNodes(query) {
            if (!query) {
                nodes.style("opacity", 1);
                nodeLabels.style("opacity", 1);
                return;
            }
            
            nodes.style("opacity", d => 
                d.name.toLowerCase().includes(query.toLowerCase()) ? 1 : 0.1
            );
            nodeLabels.style("opacity", d => 
                d.name.toLowerCase().includes(query.toLowerCase()) ? 1 : 0.1
            );
        }
        
        function adjustLinkStrength(strength) {
            simulation.force("link").strength(parseFloat(strength));
            simulation.restart();
        }
        
        function resetGraph() {
            document.getElementById('nodeTypeFilter').value = '';
            document.getElementById('searchInput').value = '';
            document.getElementById('linkStrengthSlider').value = '1';
            
            nodes.style("opacity", 1);
            nodeLabels.style("opacity", 1);
            links.style("opacity", 1);
            
            simulation.alpha(1).restart();
        }
        
        function exportGraph() {
            // 创建下载链接
            const svgData = new XMLSerializer().serializeToString(svg.node());
            const canvas = document.createElement("canvas");
            const ctx = canvas.getContext("2d");
            const img = new Image();
            
            canvas.width = width;
            canvas.height = height;
            
            img.onload = function() {
                ctx.drawImage(img, 0, 0);
                const link = document.createElement("a");
                link.download = "knowledge_graph.png";
                link.href = canvas.toDataURL();
                link.click();
            };
            
            const blob = new Blob([svgData], {type: "image/svg+xml;charset=utf-8"});
            const url = URL.createObjectURL(blob);
            img.src = url;
        }
    </script>
</body>
</html>
            """
            
            # 写入HTML文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_template)
            
            logger.info(f"HTML可视化文件已生成: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"生成HTML文件失败: {str(e)}")
            raise
    
    # ✅ 新增：上下文管理器支持
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
    
    # ==================== 统计和查询功能 ====================
    
    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息 - 修复版本"""
        try:
            # 获取节点统计
            node_stats_query = """
            MATCH (n)
            RETURN labels(n) as labels, count(n) as count
            ORDER BY count DESC
            """
            node_results = self.run_query(node_stats_query)
            node_stats = {}
            total_nodes = 0
            for record in node_results:
                labels = record['labels']
                count = record['count']
                total_nodes += count
                for label in labels:
                    if label not in node_stats:
                        node_stats[label] = 0
                    node_stats[label] += count
            
            # 获取关系统计
            rel_stats_query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
            """
            rel_results = self.run_query(rel_stats_query)
            rel_stats = {}
            total_relationships = 0
            for record in rel_results:
                rel_type = record['type']
                count = record['count']
                rel_stats[rel_type] = count
                total_relationships += count
            
            # ✅ 修复：使用 COUNT{} 替代 size()
            degree_query = """
            MATCH (n)
            WITH n, COUNT { (n)--() } as degree
            RETURN 
                min(degree) as min_degree,
                max(degree) as max_degree,
                avg(degree) as avg_degree,
                count(case when degree = 0 then 1 end) as isolated_nodes
            """
            degree_result = self.run_query(degree_query)
            degree_stats = degree_result[0] if degree_result else {}
            
            # 获取连通性统计 - 简化版本
            connectivity_query = """
            MATCH (n)
            WHERE EXISTS { (n)--() }
            RETURN count(n) as connected_nodes
            """
            connectivity_result = self.run_query(connectivity_query)
            connectivity_stats = connectivity_result[0] if connectivity_result else {}
            
            return {
                'total_nodes': total_nodes,
                'total_relationships': total_relationships,
                'node_stats': node_stats,
                'relationship_stats': rel_stats,
                'degree_stats': {
                    'min_degree': degree_stats.get('min_degree', 0),
                    'max_degree': degree_stats.get('max_degree', 0), 
                    'avg_degree': round(degree_stats.get('avg_degree', 0), 2),
                    'isolated_nodes': degree_stats.get('isolated_nodes', 0)
                },
                'connectivity_stats': {
                    'connected_nodes': connectivity_stats.get('connected_nodes', 0),
                    'largest_component_size': connectivity_stats.get('connected_nodes', 0)  # 简化处理
                }
            }
            
        except Exception as e:
            logger.error(f"获取数据库统计失败: {str(e)}")
            return {}
    
    def find_similar_entities(self, entity_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """查找相似实体"""
        try:
            # 使用模糊匹配查找相似实体
            query = """
            MATCH (n)
            WHERE (n.name CONTAINS $partial_name OR n.text CONTAINS $partial_name)
               OR (toLower(n.name) CONTAINS toLower($partial_name) OR toLower(n.text) CONTAINS toLower($partial_name))
            RETURN 
                COALESCE(n.name, n.text) as name,
                labels(n) as labels,
                n.description as description,
                id(n) as id
            ORDER BY 
                CASE 
                    WHEN n.name = $entity_name OR n.text = $entity_name THEN 0
                    WHEN toLower(n.name) = toLower($entity_name) OR toLower(n.text) = toLower($entity_name) THEN 1
                    ELSE 2
                END,
                length(COALESCE(n.name, n.text))
            LIMIT $limit
            """
            
            results = self.run_query(query, {
                'entity_name': entity_name,
                'partial_name': entity_name,
                'limit': limit
            })
            
            return [dict(record) for record in results]
            
        except Exception as e:
            logger.error(f"查找相似实体失败: {str(e)}")
            return []
    
    def get_entity_neighbors(self, entity_name: str, max_hops: int = 1) -> Dict[str, Any]:
        """获取实体的邻居节点"""
        try:
            query = f"""
            MATCH (center)-[r*1..{max_hops}]-(neighbor)
            WHERE center.name = $entity_name OR center.text = $entity_name
            WITH center, neighbor, r
            RETURN 
                COALESCE(center.name, center.text) as center_name,
                labels(center) as center_labels,
                COALESCE(neighbor.name, neighbor.text) as neighbor_name,
                labels(neighbor) as neighbor_labels,
                neighbor.description as neighbor_description,
                [rel in r | type(rel)] as relationship_path,
                length(r) as distance
            ORDER BY distance, neighbor_name
            """
            
            results = self.run_query(query, {'entity_name': entity_name})
            
            if not results:
                return {'center': None, 'neighbors': []}
            
            # 组织结果
            center_info = None
            neighbors = []
            
            for record in results:
                if center_info is None:
                    center_info = {
                        'name': record['center_name'],
                        'labels': list(record['center_labels'])
                    }
                
                neighbors.append({
                    'name': record['neighbor_name'],
                    'labels': list(record['neighbor_labels']),
                    'description': record['neighbor_description'],
                    'relationship_path': list(record['relationship_path']),
                    'distance': record['distance']
                })
            
            return {
                'center': center_info,
                'neighbors': neighbors
            }
            
        except Exception as e:
            logger.error(f"获取实体邻居失败: {str(e)}")
            return {'center': None, 'neighbors': []}


def main():
    """主函数 - 完整的数据库初始化流程"""
    initializer = None
    try:
        # ✅ 使用上下文管理器确保连接正确关闭
        with Neo4jInitializer() as initializer:
            logger.info("开始完整的Neo4j数据库初始化...")
            
            # 步骤1: 清空数据库（可选）
            # ✅ 修复：处理非交互环境
            clear_db = False
            try:
                # 检查是否在交互环境中
                if sys.stdin.isatty():
                    user_input = input("是否清空现有数据库？(y/n): ").lower().strip()
                    clear_db = user_input == 'y'
                else:
                    # 非交互环境，默认不清空
                    logger.info("非交互环境，跳过数据库清空步骤")
            except (EOFError, KeyboardInterrupt):
                logger.info("用户取消操作")
                clear_db = False
                
            if clear_db:
                logger.info("步骤 1/5: 清空现有数据...")
                initializer.clear_database()
            else:
                logger.info("步骤 1/5: 跳过清空数据库")
            
            # 步骤2: 初始化模式
            logger.info("步骤 2/5: 初始化图谱模式...")
            initializer.init_schema()
            
            # 步骤3: 导入知识数据
            knowledge_files = [
                "models/knowledge/gdm_knowledge.json",
                "models/knowledge/diabetes_knowledge.json",
                "models/knowledge/medical_qa.json"
            ]
            
            logger.info("步骤 3/5: 导入知识数据...")
            for knowledge_file in knowledge_files:
                if os.path.exists(knowledge_file):
                    logger.info(f"导入知识文件: {knowledge_file}")
                    initializer.import_knowledge_data(knowledge_file)
                else:
                    logger.warning(f"知识文件不存在，跳过: {knowledge_file}")
            
            # 步骤4: 导出可视化数据
            logger.info("步骤 4/5: 导出可视化数据...")
            initializer.export_for_visualization(
                output_file="visualization/graph_data.json",
                max_nodes=1000,
                include_orphans=False
            )
            
            # ✅ 新增步骤5: 生成HTML可视化文件
            logger.info("步骤 5/5: 生成HTML可视化文件...")
            html_file = initializer.generate_visualization_html()
            logger.info(f"可视化HTML文件已生成: {html_file}")
            
            # 获取并显示统计信息
            stats = initializer.get_database_stats()
            logger.info("=" * 50)
            logger.info("数据库统计信息:")
            logger.info(f"总节点数: {stats.get('total_nodes', 0)}")
            logger.info(f"总关系数: {stats.get('total_relationships', 0)}")
            logger.info(f"节点类型分布: {stats.get('node_stats', {})}")
            logger.info(f"关系类型分布: {stats.get('relationship_stats', {})}")
            logger.info("=" * 50)
            
            logger.info("Neo4j数据库初始化完成！")
            logger.info(f"请打开浏览器访问: file://{os.path.abspath(html_file)}")
            
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise
    finally:
        logger.info("数据库连接已安全关闭")

if __name__ == "__main__":
    main()