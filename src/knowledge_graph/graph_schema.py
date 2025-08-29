"""
妊娠期糖尿病知识图谱模式定义
定义节点类型、关系类型和属性结构
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

class NodeType(Enum):
    """节点类型枚举"""
    MEDICAL_CONCEPT = "MedicalConcept"
    DISEASE = "Disease"
    SYMPTOM = "Symptom"
    RISK_FACTOR = "RiskFactor"
    DIAGNOSTIC_METHOD = "DiagnosticMethod"
    TREATMENT = "Treatment"
    COMPLICATION = "Complication"
    FOOD = "Food"
    GUIDELINE = "Guideline"
    QUESTION = "Question"

class RelationType(Enum):
    """关系类型枚举"""
    IS_A = "IS_A"
    HAS_SYMPTOM = "HAS_SYMPTOM"
    HAS_RISK_FACTOR = "HAS_RISK_FACTOR"
    DIAGNOSED_BY = "DIAGNOSED_BY"
    TREATED_BY = "TREATED_BY"
    CAN_CAUSE = "CAN_CAUSE"
    RECOMMENDED_FOR = "RECOMMENDED_FOR"
    CONTRAINDICATED_FOR = "CONTRAINDICATED_FOR"
    RECOMMENDS = "RECOMMENDS"
    ANSWERS = "ANSWERS"

@dataclass
class NodeSchema:
    """节点模式定义"""
    node_type: NodeType
    required_properties: List[str]
    optional_properties: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)

@dataclass
class RelationshipSchema:
    """关系模式定义"""
    relationship_type: RelationType
    source_types: List[NodeType]
    target_types: List[NodeType]
    required_properties: List[str] = field(default_factory=list)
    optional_properties: List[str] = field(default_factory=list)

class GDMKnowledgeGraphSchema:
    """妊娠期糖尿病知识图谱模式"""
    
    def __init__(self):
        self.node_schemas = self._define_node_schemas()
        self.relationship_schemas = self._define_relationship_schemas()
    
    def _define_node_schemas(self) -> Dict[NodeType, NodeSchema]:
        """定义所有节点类型的模式"""
        return {
            NodeType.MEDICAL_CONCEPT: NodeSchema(
                node_type=NodeType.MEDICAL_CONCEPT,
                required_properties=["name", "description"],  # 修改：去掉definition和source作为必需属性
                optional_properties=["definition", "source", "confidence"],
                constraints=["CREATE CONSTRAINT medical_concept_name_unique IF NOT EXISTS FOR (n:MedicalConcept) REQUIRE n.name IS UNIQUE"],
                indexes=["CREATE INDEX medical_concept_name IF NOT EXISTS FOR (n:MedicalConcept) ON (n.name)"]
            ),
            
            NodeType.DISEASE: NodeSchema(
                node_type=NodeType.DISEASE,
                required_properties=["name", "description"],
                optional_properties=["icd_code", "confidence"],
                constraints=["CREATE CONSTRAINT disease_name_unique IF NOT EXISTS FOR (n:Disease) REQUIRE n.name IS UNIQUE"],
                indexes=[
                    "CREATE INDEX disease_name IF NOT EXISTS FOR (n:Disease) ON (n.name)",
                    "CREATE INDEX disease_icd IF NOT EXISTS FOR (n:Disease) ON (n.icd_code)"
                ]
            ),
            
            NodeType.SYMPTOM: NodeSchema(
                node_type=NodeType.SYMPTOM,
                required_properties=["name", "description"],
                optional_properties=["confidence"],
                constraints=["CREATE CONSTRAINT symptom_name_unique IF NOT EXISTS FOR (n:Symptom) REQUIRE n.name IS UNIQUE"],
                indexes=["CREATE INDEX symptom_name IF NOT EXISTS FOR (n:Symptom) ON (n.name)"]
            ),
            
            NodeType.RISK_FACTOR: NodeSchema(
                node_type=NodeType.RISK_FACTOR,
                required_properties=["name", "description", "modifiable"],
                optional_properties=["confidence"],
                constraints=["CREATE CONSTRAINT risk_factor_name_unique IF NOT EXISTS FOR (n:RiskFactor) REQUIRE n.name IS UNIQUE"],
                indexes=["CREATE INDEX risk_factor_name IF NOT EXISTS FOR (n:RiskFactor) ON (n.name)"]
            ),
            
            NodeType.DIAGNOSTIC_METHOD: NodeSchema(
                node_type=NodeType.DIAGNOSTIC_METHOD,
                required_properties=["name", "description"],
                optional_properties=["normal_range", "confidence"],
                constraints=["CREATE CONSTRAINT diagnostic_method_name_unique IF NOT EXISTS FOR (n:DiagnosticMethod) REQUIRE n.name IS UNIQUE"],
                indexes=["CREATE INDEX diagnostic_method_name IF NOT EXISTS FOR (n:DiagnosticMethod) ON (n.name)"]
            ),
            
            NodeType.TREATMENT: NodeSchema(
                node_type=NodeType.TREATMENT,
                required_properties=["name", "description", "type"],
                optional_properties=["confidence"],
                constraints=["CREATE CONSTRAINT treatment_name_unique IF NOT EXISTS FOR (n:Treatment) REQUIRE n.name IS UNIQUE"],
                indexes=[
                    "CREATE INDEX treatment_name IF NOT EXISTS FOR (n:Treatment) ON (n.name)",
                    "CREATE INDEX treatment_type IF NOT EXISTS FOR (n:Treatment) ON (n.type)"
                ]
            ),
            
            NodeType.COMPLICATION: NodeSchema(
                node_type=NodeType.COMPLICATION,
                required_properties=["name", "description", "target"],
                optional_properties=["confidence"],
                constraints=["CREATE CONSTRAINT complication_name_unique IF NOT EXISTS FOR (n:Complication) REQUIRE n.name IS UNIQUE"],
                indexes=[
                    "CREATE INDEX complication_name IF NOT EXISTS FOR (n:Complication) ON (n.name)",
                    "CREATE INDEX complication_target IF NOT EXISTS FOR (n:Complication) ON (n.target)"
                ]
            ),
            
            NodeType.FOOD: NodeSchema(
                node_type=NodeType.FOOD,
                required_properties=["name", "description"],  # 修改：去掉category作为必需属性
                optional_properties=["glycemic_index", "category", "confidence"],
                constraints=["CREATE CONSTRAINT food_name_unique IF NOT EXISTS FOR (n:Food) REQUIRE n.name IS UNIQUE"],
                indexes=[
                    "CREATE INDEX food_name IF NOT EXISTS FOR (n:Food) ON (n.name)",
                    "CREATE INDEX food_category IF NOT EXISTS FOR (n:Food) ON (n.category)"
                ]
            ),
            
            NodeType.GUIDELINE: NodeSchema(
                node_type=NodeType.GUIDELINE,
                required_properties=["name", "description"],  # 修改：去掉organization和year作为必需属性
                optional_properties=["organization", "year", "recommendation_level", "confidence"],
                constraints=["CREATE CONSTRAINT guideline_name_unique IF NOT EXISTS FOR (n:Guideline) REQUIRE n.name IS UNIQUE"],
                indexes=[
                    "CREATE INDEX guideline_name IF NOT EXISTS FOR (n:Guideline) ON (n.name)",
                    "CREATE INDEX guideline_org IF NOT EXISTS FOR (n:Guideline) ON (n.organization)"
                ]
            ),
            
            NodeType.QUESTION: NodeSchema(
                node_type=NodeType.QUESTION,
                required_properties=["text", "description"],  # 修改：使用text而不是name，去掉category作为必需属性
                optional_properties=["category", "confidence"],
                constraints=["CREATE CONSTRAINT question_text_unique IF NOT EXISTS FOR (n:Question) REQUIRE n.text IS UNIQUE"],
                indexes=["CREATE INDEX question_text IF NOT EXISTS FOR (n:Question) ON (n.text)"]
            )
        }
    
    def _define_relationship_schemas(self) -> Dict[RelationType, RelationshipSchema]:
        """定义所有关系类型的模式"""
        return {
            RelationType.IS_A: RelationshipSchema(
                relationship_type=RelationType.IS_A,
                source_types=[NodeType.MEDICAL_CONCEPT, NodeType.DISEASE],  # 修改：扩展源类型
                target_types=[NodeType.MEDICAL_CONCEPT, NodeType.DISEASE],
                optional_properties=["confidence", "source", "evidence", "strength"]
            ),
            
            RelationType.HAS_SYMPTOM: RelationshipSchema(
                relationship_type=RelationType.HAS_SYMPTOM,
                source_types=[NodeType.DISEASE],
                target_types=[NodeType.SYMPTOM],
                optional_properties=["frequency", "severity", "confidence", "evidence", "strength", "source"]
            ),
            
            RelationType.HAS_RISK_FACTOR: RelationshipSchema(
                relationship_type=RelationType.HAS_RISK_FACTOR,
                source_types=[NodeType.DISEASE],
                target_types=[NodeType.RISK_FACTOR],
                optional_properties=["strength", "evidence_level", "confidence", "evidence", "source"]
            ),
            
            RelationType.DIAGNOSED_BY: RelationshipSchema(
                relationship_type=RelationType.DIAGNOSED_BY,
                source_types=[NodeType.DISEASE],
                target_types=[NodeType.DIAGNOSTIC_METHOD],
                optional_properties=["sensitivity", "specificity", "timing", "confidence", "evidence", "strength", "source"]
            ),
            
            RelationType.TREATED_BY: RelationshipSchema(
                relationship_type=RelationType.TREATED_BY,
                source_types=[NodeType.DISEASE],
                target_types=[NodeType.TREATMENT],
                optional_properties=["effectiveness", "evidence_level", "confidence", "evidence", "strength", "source"]
            ),
            
            RelationType.CAN_CAUSE: RelationshipSchema(
                relationship_type=RelationType.CAN_CAUSE,
                source_types=[NodeType.DISEASE, NodeType.TREATMENT],  # 修改：扩展源类型
                target_types=[NodeType.COMPLICATION, NodeType.DISEASE, NodeType.MEDICAL_CONCEPT],  # 修改：扩展目标类型
                optional_properties=["probability", "severity", "timing", "confidence", "evidence", "strength", "source"]
            ),
            
            RelationType.RECOMMENDED_FOR: RelationshipSchema(
                relationship_type=RelationType.RECOMMENDED_FOR,
                source_types=[NodeType.FOOD, NodeType.TREATMENT],  # 修改：扩展源类型
                target_types=[NodeType.DISEASE],
                optional_properties=["reason", "strength", "evidence_level", "confidence", "evidence", "source"]  # 修改：reason改为可选
            ),
            
            RelationType.CONTRAINDICATED_FOR: RelationshipSchema(  # 修改：使用CONTRAINDICATED_FOR
                relationship_type=RelationType.CONTRAINDICATED_FOR,
                source_types=[NodeType.FOOD, NodeType.TREATMENT],  # 修改：扩展源类型
                target_types=[NodeType.DISEASE],
                optional_properties=["reason", "severity", "alternative", "confidence", "evidence", "strength", "source"]  # 修改：reason改为可选
            ),
            
            RelationType.RECOMMENDS: RelationshipSchema(
                relationship_type=RelationType.RECOMMENDS,
                source_types=[NodeType.GUIDELINE],
                target_types=[NodeType.DISEASE, NodeType.TREATMENT, NodeType.DIAGNOSTIC_METHOD],
                optional_properties=["strength", "evidence_level", "year", "context", "confidence", "evidence", "source"]  # 修改：改为可选属性
            ),
            
            RelationType.ANSWERS: RelationshipSchema(
                relationship_type=RelationType.ANSWERS,
                source_types=[NodeType.MEDICAL_CONCEPT, NodeType.TREATMENT, NodeType.FOOD, NodeType.DISEASE, NodeType.COMPLICATION],
                target_types=[NodeType.QUESTION],
                optional_properties=["confidence", "completeness", "evidence", "strength", "source"]
            )
        }
    
    def get_cypher_constraints(self) -> List[str]:
        """生成所有约束的Cypher语句"""
        constraints = []
        for schema in self.node_schemas.values():
            constraints.extend(schema.constraints)
        return constraints
    
    def get_cypher_indexes(self) -> List[str]:
        """生成所有索引的Cypher语句"""
        indexes = []
        for schema in self.node_schemas.values():
            indexes.extend(schema.indexes)
        return indexes
    
    @staticmethod
    def generate_cypher_schema() -> str:
        """生成Neo4j Cypher模式定义
        
        Returns:
            Cypher语句
        """
        schema = GDMKnowledgeGraphSchema()
        
        cypher_lines = []
        cypher_lines.append("// 妊娠期糖尿病知识图谱模式定义")
        cypher_lines.append("// 创建约束")
        
        # 添加约束
        for constraint in schema.get_cypher_constraints():
            cypher_lines.append(constraint + ";")
        
        cypher_lines.append("")
        cypher_lines.append("// 创建索引")
        
        # 添加索引
        for index in schema.get_cypher_indexes():
            cypher_lines.append(index + ";")
        
        return "\n".join(cypher_lines)
    
    @staticmethod
    def generate_neo4j_import_script(knowledge_file: str = "models/knowledge/gdm_knowledge.json") -> str:
        """生成Neo4j导入脚本
        
        Args:
            knowledge_file: 知识文件路径
            
        Returns:
            Cypher导入脚本
        """
        import_script = f"""
// 妊娠期糖尿病知识图谱导入脚本
// 知识文件: {knowledge_file}

// 清空现有数据 (可选)
MATCH (n) DETACH DELETE n;

// 加载JSON文件并创建实体
CALL apoc.load.json('file://{knowledge_file}') YIELD value
WITH value
UNWIND value.entities as entity
CALL {{
  WITH entity
  // 为Question类型创建特殊处理
  CALL apoc.do.when(
    entity.type = 'Question',
    'CALL apoc.create.node([entity.type], {{
      text: entity.entity,
      category: COALESCE(entity.attributes.category, "general"),
      description: entity.description
    }} + COALESCE(entity.attributes, {{}})) YIELD node RETURN node',
    'CALL apoc.create.node([entity.type], {{
      name: entity.entity,
      description: entity.description
    }} + COALESCE(entity.attributes, {{}})) YIELD node RETURN node',
    {{entity: entity}}
  ) YIELD value
  RETURN value.node as node
}} IN TRANSACTIONS OF 100 ROWS;

// 加载JSON文件并创建关系
CALL apoc.load.json('file://{knowledge_file}') YIELD value
WITH value
UNWIND value.relations as relation
CALL {{
  WITH relation
  // 查找主体和客体节点
  MATCH (s) WHERE s.name = relation.subject OR s.text = relation.subject
  MATCH (o) WHERE o.name = relation.object OR o.text = relation.object
  WITH s, o, relation
  
  // 创建关系，保留所有属性包括strength
  CALL apoc.create.relationship(s, relation.predicate, 
    COALESCE(relation.attributes, {{}}) + {{source: 'imported'}}, o) 
  YIELD rel
  RETURN rel
}} IN TRANSACTIONS OF 100 ROWS;

// 验证导入结果
MATCH (n) 
RETURN labels(n)[0] as node_type, count(n) as count 
ORDER BY count DESC;

MATCH ()-[r]->() 
RETURN type(r) as relationship_type, count(r) as count 
ORDER BY count DESC;

// 检查关系类型匹配情况
MATCH ()-[r]->() 
WHERE NOT type(r) IN ['IS_A', 'HAS_SYMPTOM', 'HAS_RISK_FACTOR', 'DIAGNOSED_BY', 'TREATED_BY', 'CAN_CAUSE', 'RECOMMENDED_FOR', 'CONTRAINDICATED_FOR', 'RECOMMENDS', 'ANSWERS']
RETURN DISTINCT type(r) as unmapped_relationship_types;
"""
        return import_script
    
    def validate_node(self, node_type: str, properties: Dict[str, Any]) -> bool:
        """验证节点是否符合模式定义"""
        try:
            node_enum = NodeType(node_type)
            schema = self.node_schemas[node_enum]
            
            # 检查必需属性
            for prop in schema.required_properties:
                if prop not in properties:
                    return False
            
            return True
        except (ValueError, KeyError):
            return False
    
    def validate_relationship(self, rel_type: str, source_type: str, target_type: str) -> bool:
        """验证关系是否符合模式定义"""
        try:
            rel_enum = RelationType(rel_type)
            source_enum = NodeType(source_type)
            target_enum = NodeType(target_type)
            
            schema = self.relationship_schemas[rel_enum]
            
            return (source_enum in schema.source_types and 
                   target_enum in schema.target_types)
        except (ValueError, KeyError):
            return False
    
    def get_entity_types(self) -> List[Dict[str, Any]]:
        """获取实体类型定义
        
        Returns:
            实体类型列表
        """
        entity_types = []
        for node_type, schema in self.node_schemas.items():
            properties = []
            
            # 添加必需属性
            for prop in schema.required_properties:
                prop_type = "boolean" if prop == "modifiable" else "string"
                properties.append({
                    "name": prop,
                    "type": prop_type,
                    "description": f"{prop}",
                    "required": True
                })
            
            # 添加可选属性
            for prop in schema.optional_properties:
                prop_type = "number" if prop == "glycemic_index" else "string"
                properties.append({
                    "name": prop,
                    "type": prop_type, 
                    "description": f"{prop}",
                    "required": False
                })
            
            entity_types.append({
                "name": node_type.value,
                "description": f"{node_type.value}实体",
                "properties": properties
            })
        
        return entity_types
    
    def get_relation_types(self) -> List[Dict[str, Any]]:
        """获取关系类型定义
        
        Returns:
            关系类型列表
        """
        relation_types = []
        for rel_type, schema in self.relationship_schemas.items():
            properties = []
            
            # 添加必需属性
            for prop in schema.required_properties:
                properties.append({
                    "name": prop,
                    "type": "string",
                    "description": f"{prop}",
                    "required": True
                })
            
            # 添加可选属性
            for prop in schema.optional_properties:
                properties.append({
                    "name": prop,
                    "type": "string",
                    "description": f"{prop}",
                    "required": False
                })
            
            relation_types.append({
                "name": rel_type.value,
                "description": f"{rel_type.value}关系",
                "source": [t.value for t in schema.source_types],
                "target": [t.value for t in schema.target_types],
                "properties": properties
            })
        
        return relation_types

# 全局模式实例
gdm_schema = GDMKnowledgeGraphSchema()

if __name__ == "__main__":
    # 测试模式定义
    schema = GDMKnowledgeGraphSchema()
    
    print("=== 妊娠期糖尿病知识图谱模式定义 ===\n")
    
    print("节点类型:")
    for node_type, node_schema in schema.node_schemas.items():
        print(f"- {node_type.value}: {len(node_schema.required_properties)} 个必需属性, {len(node_schema.optional_properties)} 个可选属性")
    
    print(f"\n关系类型:")
    for rel_type, rel_schema in schema.relationship_schemas.items():
        source_types = [t.value for t in rel_schema.source_types]
        target_types = [t.value for t in rel_schema.target_types]
        print(f"- {rel_type.value}: {source_types} -> {target_types}")
    
    print(f"\nCypher约束数量: {len(schema.get_cypher_constraints())}")
    print(f"Cypher索引数量: {len(schema.get_cypher_indexes())}")
    
    # 测试验证功能
    print(f"\n验证测试:")
    print(f"Disease节点验证: {schema.validate_node('Disease', {'name': '妊娠期糖尿病', 'description': '描述'})}")
    print(f"HAS_SYMPTOM关系验证: {schema.validate_relationship('HAS_SYMPTOM', 'Disease', 'Symptom')}")
    
    # 生成Cypher模式
    print(f"\n=== Cypher模式定义 ===")
    print(schema.generate_cypher_schema())
