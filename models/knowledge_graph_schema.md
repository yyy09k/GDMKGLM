# 妊娠期糖尿病知识图谱模型设计

## 实体类型

### 1. 医学概念 (MedicalConcept)
- 属性:
  - name: 概念名称
  - definition: 定义
  - source: 来源

### 2. 疾病 (Disease)
- 属性:
  - name: 疾病名称
  - icd_code: ICD编码(可选)
  - description: 描述

### 3. 症状 (Symptom)
- 属性:
  - name: 症状名称
  - description: 描述

### 4. 风险因素 (RiskFactor)
- 属性:
  - name: 风险因素名称
  - description: 描述
  - modifiable: 是否可修改(布尔值)

### 5. 诊断方法 (DiagnosticMethod)
- 属性:
  - name: 方法名称
  - description: 描述
  - normal_range: 正常范围(可选)

### 6. 治疗方法 (Treatment)
- 属性:
  - name: 治疗方法名称
  - description: 描述
  - type: 类型(药物、生活方式、手术等)

### 7. 并发症 (Complication)
- 属性:
  - name: 并发症名称
  - description: 描述
  - target: 影响对象(母亲、胎儿、新生儿)

### 8. 食物 (Food)
- 属性:
  - name: 食物名称
  - glycemic_index: 血糖指数(可选)
  - category: 类别

### 9. 指南 (Guideline)
- 属性:
  - name: 指南名称
  - organization: 发布组织
  - year: 发布年份
  - recommendation_level: 推荐级别(可选)

### 10. 问题 (Question)
- 属性:
  - text: 问题文本
  - category: 问题类别

## 关系类型

### 1. IS_A
- 描述: 表示概念的分类关系
- 连接: (MedicalConcept) -> (MedicalConcept)

### 2. HAS_SYMPTOM
- 描述: 疾病具有的症状
- 连接: (Disease) -> (Symptom)

### 3. HAS_RISK_FACTOR
- 描述: 疾病的风险因素
- 连接: (Disease) -> (RiskFactor)

### 4. DIAGNOSED_BY
- 描述: 疾病的诊断方法
- 连接: (Disease) -> (DiagnosticMethod)

### 5. TREATED_BY
- 描述: 疾病的治疗方法
- 连接: (Disease) -> (Treatment)

### 6. CAN_CAUSE
- 描述: 疾病可能导致的并发症
- 连接: (Disease) -> (Complication)

### 7. RECOMMENDED_FOR
- 描述: 推荐用于某疾病的食物
- 连接: (Food) -> (Disease)
- 属性:
  - reason: 推荐原因

### 8. CONTRAINDICATED_FOR
- 描述: 某疾病应避免的食物
- 连接: (Food) -> (Disease)
- 属性:
  - reason: 避免原因

### 9. RECOMMENDS
- 描述: 指南对某疾病的推荐
- 连接: (Guideline) -> (Disease, Treatment, DiagnosticMethod)
- 属性:
  - strength: 推荐强度
  - evidence_level: 证据级别

### 10. ANSWERS
- 描述: 回答某个问题
- 连接: (MedicalConcept, Treatment, Food, etc.) -> (Question)

## 示例查询

### 查询妊娠期糖尿病的风险因素
```cypher
MATCH (d:Disease {name: "妊娠期糖尿病"})-[:HAS_RISK_FACTOR]->(r:RiskFactor)
RETURN r.name, r.description, r.modifiable
```

### 查询妊娠期糖尿病推荐的食物
```cypher
MATCH (f:Food)-[r:RECOMMENDED_FOR]->(d:Disease {name: "妊娠期糖尿病"})
RETURN f.name, f.category, r.reason
```

### 查询某个问题的答案
```cypher
MATCH (q:Question {text: "什么是妊娠期糖尿病？"})<-[:ANSWERS]-(a)
RETURN a.name, a.definition, labels(a)[0] as type
```

## 数据存储与管理

### 数据库选择
计划使用Neo4j图数据库存储知识图谱，因其高效处理复杂关联关系的能力和成熟的查询语言(Cypher)。

### 数据导入策略
1. 从结构化资源(如指南文档)中提取的知识将通过CSV文件批量导入
2. 从非结构化文本中提取的关系将通过API逐步添加
3. 设置数据质量检查流程，确保导入数据的准确性

## 医学标准映射

为确保与医疗信息系统的互操作性，本知识图谱将采用以下标准映射：

1. **疾病编码**: 使用ICD-10/ICD-11编码系统
2. **症状术语**: 参考SNOMED CT术语集
3. **药物信息**: 映射到RxNorm标准
4. **实验室检查**: 参考LOINC标准

通过标准映射，可以实现与现有医疗系统的数据交换和集成。

## 推理能力

### 基本推理规则
1. **风险评估规则**: 基于患者特征和风险因素计算妊娠期糖尿病风险
2. **诊断支持规则**: 根据症状和检查结果推断可能的诊断
3. **治疗推荐规则**: 基于患者状况、疾病特征选择合适的治疗方案
4. **饮食建议规则**: 根据血糖控制目标推荐食物组合

### 推理实现方式
将使用组合方式实现推理能力：
1. Neo4j的原生图算法进行基本路径查询
2. Cypher查询语言的模式匹配功能
3. 外部规则引擎处理复杂医学决策逻辑
