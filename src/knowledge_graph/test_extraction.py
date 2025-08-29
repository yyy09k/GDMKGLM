import os
import json
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.knowledge_graph.knowledge_extractor import KnowledgeExtractor

def main():
    """测试知识提取功能 - 处理所有数据文件"""
    # 创建输出目录
    os.makedirs("models/knowledge", exist_ok=True)
    
    # 初始化知识提取器
    extractor = KnowledgeExtractor()
    
    # 定义所有需要处理的数据源
    data_sources = [
        ("FAQ数据", "data/processed/faq"),
        ("临床指南", "data/processed/guidelines"),
        ("PubMed文献", "data/processed/pubmed"),
        ("医学教科书", "data/processed/textbooks")
    ]
    
    total_entities = 0
    total_relations = 0
    
    # 逐一处理各个数据源的所有文件
    for source_name, source_path in data_sources:
        print(f"\n处理{source_name}...")
        if os.path.exists(source_path):
            # 处理目录下的所有文件
            result = extractor.process_directory(source_path)
            if 'error' not in result:
                entities_count = result.get('total_entities', 0)
                relations_count = result.get('total_relations', 0)
                print(f"从{source_name}中提取了 {entities_count} 个实体和 {relations_count} 个关系")
                total_entities += entities_count
                total_relations += relations_count
                
                # 显示处理的文件数量
                files_processed = result.get('files_processed', 0)
                print(f"  处理了 {files_processed} 个文件")
            else:
                print(f"{source_name}处理出错: {result['error']}")
        else:
            print(f"{source_name}目录不存在: {source_path}")
    
    # 测试文本处理功能
    print("\n测试文本处理...")
    sample_text = """
    妊娠期糖尿病（GDM）是指妊娠期间首次发现的糖代谢异常。
    患者可能出现多饮、多尿、体重减轻等症状。
    诊断通常通过口服葡萄糖耐量试验（OGTT）进行。
    治疗包括饮食控制、运动疗法和必要时的胰岛素治疗。
    血糖监测对于妊娠期糖尿病管理至关重要。
    """
    text_result = extractor.process_text(sample_text, "测试文本")
    if 'error' not in text_result:
        print(f"从测试文本中提取了 {len(text_result.get('entities', []))} 个实体和 {len(text_result.get('relations', []))} 个关系")
    else:
        print(f"文本处理出错: {text_result['error']}")
    
    # 直接保存从真实数据源提取的结果
    print("\n保存结果...")
    extractor.save_to_json("models/knowledge/gdm_knowledge.json")
    
    # 显示统计信息
    print("\n=== 完整提取统计信息 ===")
    stats = extractor.get_statistics()
    print(f"总实体数: {stats['total_entities']}")
    print(f"总关系数: {stats['total_relations']}")
    print(f"实体类型分布: {stats['entity_types']}")
    print(f"关系类型分布: {stats['relation_types']}")
    
    # 按数据源显示统计
    print(f"\n各数据源处理概况:")
    print(f"  累计实体: {total_entities}")
    print(f"  累计关系: {total_relations}")
    
    # 显示部分结果（只有当实际有数据时才显示）
    if extractor.entities:
        print(f"\n提取的部分实体 (显示前15个):")
        for i, entity in enumerate(extractor.entities[:15]):
            print(f"  {i+1}. {entity.get('entity', 'Unknown')} ({entity.get('type', 'Unknown')})")
            if 'description' in entity and entity['description']:
                description = entity['description'][:80] + "..." if len(entity['description']) > 80 else entity['description']
                print(f"     描述: {description}")
    else:
        print("\n未提取到实体")
    
    if extractor.relations:
        print(f"\n提取的部分关系 (显示前15个):")
        for i, relation in enumerate(extractor.relations[:15]):
            subject = relation.get('subject', 'Unknown')
            predicate = relation.get('predicate', 'Unknown')
            obj = relation.get('object', 'Unknown')
            print(f"  {i+1}. {subject} --{predicate}--> {obj}")
    else:
        print("\n未提取到关系")
    
    # 测试问答功能
    print("\n=== 测试问答功能 ===")
    if extractor.entities or extractor.relations:
        test_questions = [
            "什么是妊娠期糖尿病？",
            "妊娠期糖尿病有什么症状？",
            "如何诊断妊娠期糖尿病？",
            "妊娠期糖尿病的治疗方法有哪些？",
            "妊娠期糖尿病的风险因素有哪些？"
        ]
        
        for question in test_questions:
            try:
                answer = extractor.answer_question(question)
                print(f"\n问题: {question}")
                print(f"回答: {answer}")
            except Exception as e:
                print(f"问答功能测试失败 ({question}): {e}")
    else:
        print("没有提取到知识，跳过问答测试")
    
    # 检查数据质量
    print("\n=== 数据质量检查 ===")
    if extractor.entities:
        # 检查实体类型分布
        entity_types = {}
        for entity in extractor.entities:
            entity_type = entity.get('type', 'Unknown')
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        print("实体类型分布:")
        for entity_type, count in sorted(entity_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {entity_type}: {count}")
        
        if len(entity_types) > 10:
            print(f"  ... 还有 {len(entity_types) - 10} 种其他类型")
    
    if extractor.relations:
        # 检查关系类型分布  
        relation_types = {}
        for relation in extractor.relations:
            relation_type = relation.get('predicate', 'Unknown')
            relation_types[relation_type] = relation_types.get(relation_type, 0) + 1
        
        print(f"\n关系类型分布 (显示前10种):")
        for relation_type, count in sorted(relation_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {relation_type}: {count}")
        
        if len(relation_types) > 10:
            print(f"  ... 还有 {len(relation_types) - 10} 种其他类型")
    
    # 数据完整性检查
    print(f"\n=== 数据完整性检查 ===")
    print(f"实体总数: {len(extractor.entities)}")
    print(f"关系总数: {len(extractor.relations)}")
    
    # 估算知识图谱规模
    if extractor.entities and extractor.relations:
        density = len(extractor.relations) / len(extractor.entities) if extractor.entities else 0
        print(f"知识图谱密度 (关系/实体): {density:.2f}")
    
    print(f"\n=== 完整知识提取完成 ===")
    print(f"知识文件已保存到: models/knowledge/gdm_knowledge.json")

if __name__ == "__main__":
    main()
