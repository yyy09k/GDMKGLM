import os
import json
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import sys
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.utils.deepseek_client import DeepSeekClient

class KnowledgeExtractor:
    """知识提取器，从医学文本中提取实体和关系"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化知识提取器
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量获取
        """
        self.client = DeepSeekClient(api_key)
        self.entities = []  # 存储提取的实体
        self.relations = []  # 存储提取的关系
    
    def _should_reprocess_file(self, file_path: str) -> bool:
        """判断文件是否需要重新处理（直接使用DeepSeekClient逻辑）"""
        return self.client._should_reprocess_file(file_path)
    
    def _load_cached_result(self, file_path: str) -> Optional[Dict[str, Any]]:
        """加载缓存的处理结果（直接使用DeepSeekClient逻辑）"""
        return self.client._load_cached_result(file_path)
    
    def process_file(self, file_path: str, force_reprocess: bool = False) -> Dict[str, Any]:
        """处理单个文件，提取实体和关系
        
        Args:
            file_path: 文件路径
            force_reprocess: 是否强制重新处理
            
        Returns:
            提取结果字典，包含实体和关系
        """
        print(f"处理文件: {file_path}")
        
        try:
            # 使用DeepSeekClient的process_file方法
            result = self.client.process_file(file_path, force_reprocess)
           
            # 合并到总结果
            self._add_to_results(result)
            
            return result
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            return {"entities": [], "relations": [], "error": str(e)}
    
    def process_directory(self, dir_path: str, limit: Optional[int] = None, 
                         file_pattern: str = "*.txt") -> Dict[str, Any]:
        """处理目录下的所有文件
        
        Args:
            dir_path: 目录路径
            limit: 最大处理文件数
            file_pattern: 文件模式匹配
            
        Returns:
            处理结果统计
        """
        if not os.path.exists(dir_path):
            print(f"目录不存在: {dir_path}")
            return {"error": f"目录不存在: {dir_path}"}
        
        path = Path(dir_path)
        files = list(path.glob(f"**/{file_pattern}"))
        
        if limit:
            files = files[:limit]
        
        print(f"在 {dir_path} 中找到 {len(files)} 个文件")
        
        if not files:
            return {"entities": [], "relations": [], "processed_files": 0}
        
        # 使用DeepSeekClient的批量处理功能
        file_paths = [str(f) for f in files]
        batch_result = self.client.batch_process_files(file_paths, max_files=limit)
        
        # 统计结果
        total_entities = 0
        total_relations = 0
        
        for file_path in file_paths:
            # 从缓存加载每个文件的详细结果
            cached_result = self.client._load_cached_result(file_path)
            if cached_result and 'entities' in cached_result and 'relations' in cached_result:
                # 合并到总结果
                self._add_to_results(cached_result)
                total_entities += len(cached_result.get("entities", []))
                total_relations += len(cached_result.get("relations", []))
        
        summary = {
            "processed_files": batch_result.get('processed_files', 0),
            "failed_files": batch_result.get('failed_files', 0),
            "total_entities": total_entities,
            "total_relations": total_relations,
            "batch_result": batch_result
        }
        
        print(f"目录处理完成: 成功 {summary['processed_files']} 个文件，"
              f"提取 {summary['total_entities']} 个实体，{summary['total_relations']} 个关系")
        
        return summary
    
    def _add_to_results(self, result: Dict[str, Any]) -> None:
        """添加提取结果到总结果
        
        Args:
            result: 提取结果字典
        """
        
        '''使用DeepSeekClient的合并逻辑
        current_results = [{"entities": self.entities, "relations": self.relations}]
        new_results = [{"entities": result.get("entities", []), "relations": result.get("relations", [])}]
    
        merged = self.client._merge_extraction_results(current_results + new_results)
        self.entities = merged["entities"]
        self.relations = merged["relations"]
        '''
        # 直接合并实体，避免重复
        existing_entity_keys = set()
        for entity in self.entities:
            key = f"{entity.get('entity', '')}-{entity.get('type', '')}"
            existing_entity_keys.add(key)
        
        for entity in result.get("entities", []):
            key = f"{entity.get('entity', '')}-{entity.get('type', '')}"
            if key not in existing_entity_keys and entity.get('entity'):
                self.entities.append(entity)
                existing_entity_keys.add(key)
        
        # 直接合并关系，避免重复
        existing_relation_keys = set()
        for relation in self.relations:
            key = f"{relation.get('subject', '')}-{relation.get('predicate', '')}-{relation.get('object', '')}"
            existing_relation_keys.add(key)
        
        for relation in result.get("relations", []):
            key = f"{relation.get('subject', '')}-{relation.get('predicate', '')}-{relation.get('object', '')}"
            if key not in existing_relation_keys and all([relation.get('subject'), relation.get('predicate'), relation.get('object')]):
                self.relations.append(relation)
                existing_relation_keys.add(key)
    
    def process_text(self, text: str, source_name: str = "text_input") -> Dict[str, Any]:
        """直接处理文本内容
        
        Args:
            text: 输入文本
            source_name: 文本来源标识
            
        Returns:
            提取结果
        """
        if not text.strip():
            return {"entities": [], "relations": [], "error": "文本为空"}
        
        print(f"处理文本内容 ({len(text)} 字符)")
        
        try:
            # 提取实体
            print("开始提取实体...")
            entities = self.client.extract_entities(text)
            
            # 提取关系
            print("开始提取关系...")
            relations = self.client.extract_relations(text, entities)
            
            # 使用DeepSeekClient的质量检查
            valid_entities, entity_quality_issues = self.client._quality_check_entities(entities)
            valid_relations, relation_quality_issues = self.client._quality_check_relations(relations)
        
            # 评估质量
            quality_metrics = self.client.evaluate_extraction_quality(
                valid_entities, valid_relations, entity_quality_issues, relation_quality_issues
            )
        
            result = {
                "entities": valid_entities,
                "relations": valid_relations,
                "quality_metrics": quality_metrics,
                "source": source_name,
                "processed_at": datetime.now().isoformat(),
                "text_length": len(text)
            }
            
            # 合并到总结果
            self._add_to_results(result)
            
            print(f"文本处理完成: {len(entities)} 个实体, {len(relations)} 个关系")
            return result
            
        except Exception as e:
            print(f"处理文本时出错: {e}")
            return {"entities": [], "relations": [], "error": str(e)}
    
    def save_to_json(self, output_file: str) -> None:
        """保存提取结果到JSON文件
        
        Args:
            output_file: 输出文件路径
        """
        result = {
            "entities": self.entities,
            "relations": self.relations,
            "extraction_summary": {
                "total_entities": len(self.entities),
                "total_relations": len(self.relations),
                "entity_types": self._get_entity_type_stats(),
                "relation_types": self._get_relation_type_stats(),
                "extracted_at": datetime.now().isoformat()
            }
        }
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {output_file}")
        print(f"提取了 {len(self.entities)} 个实体和 {len(self.relations)} 个关系")
    
    def _get_entity_type_stats(self) -> Dict[str, int]:
        """获取实体类型统计"""
        stats = {}
        for entity in self.entities:
            entity_type = entity.get("type", "Unknown")
            stats[entity_type] = stats.get(entity_type, 0) + 1
        return stats
    
    def _get_relation_type_stats(self) -> Dict[str, int]:
        """获取关系类型统计"""
        stats = {}
        for relation in self.relations:
            relation_type = relation.get("predicate", "Unknown")
            stats[relation_type] = stats.get(relation_type, 0) + 1
        return stats
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取提取统计信息"""
        '''
        try:
            # 检查DeepSeekClient是否有get_cache_info方法
            if hasattr(self.client, 'get_cache_info'):
                cache_info = self.client.get_cache_info()
            else:
                # 如果没有该方法，提供基本的缓存信息
                cache_info = {
                    "note": "Cache info not available from DeepSeekClient",
                    "cache_methods_available": [
                        method for method in dir(self.client) 
                        if 'cache' in method.lower() and not method.startswith('_')
                    ]
                }
        except Exception as e:
            # 如果调用失败，提供错误信息
            cache_info = {
                "error": f"Failed to get cache info: {str(e)}",
                "note": "Cache info not available"
            }
        '''
        return {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "entity_types": self._get_entity_type_stats(),
            "relation_types": self._get_relation_type_stats(),
            # "cache_info": cache_info
        }
    
    def clear_cache(self):
        """清空缓存"""
        try:
            self.client.clear_cache()  # 使用DeepSeekClient的清空缓存方法
            print("缓存已清空")
        except Exception as e:
            print(f"清空缓存失败: {e}")
    
    def reset_results(self):
        """重置提取结果"""
        self.entities = []
        self.relations = []
        print("提取结果已重置")
        
    def answer_question(self, question: str, context: str = "") -> str:
        """回答医学问题，利用DeepSeekClient的问答功能
    
        Args:
            question: 医学问题
            context: 上下文信息
        
        Returns:
            回答结果
        """
        # 可以从已提取的知识中构建上下文
        if not context and (self.entities or self.relations):
            context_entities = [e.get("entity", "") for e in self.entities[:10]]
            context = f"相关医学概念: {', '.join(context_entities)}"
    
        return self.client.answer_medical_question(question, context)

# 使用示例
if __name__ == "__main__":
    # 创建知识提取器
    extractor = KnowledgeExtractor()
    
    # 示例1: 处理单个文件
    print("=== 示例1: 处理单个文件 ===")
    if os.path.exists("data/processed/faq"):
        faq_files = list(Path("data/processed/faq").glob("*.txt"))
        if faq_files:
            result = extractor.process_file(str(faq_files[0]))
            print(f"处理结果: {len(result.get('entities', []))} 个实体, "
                  f"{len(result.get('relations', []))} 个关系")
    
    # 示例2: 处理目录
    print("\n=== 示例2: 处理目录 ===")
    if os.path.exists("data/processed/faq"):
        dir_result = extractor.process_directory("data/processed/faq", limit=2)
        print(f"目录处理结果: {dir_result}")
    
    # 示例3: 直接处理文本
    print("\n=== 示例3: 直接处理文本 ===")
    sample_text = """
    妊娠期糖尿病（GDM）是指妊娠期间首次发现的糖代谢异常。
    患者可能出现多饮、多尿等症状。
    诊断通常通过OGTT检查进行。
    治疗包括饮食控制和胰岛素治疗。
    """
    text_result = extractor.process_text(sample_text, "示例文本")
    print(f"文本处理结果: {len(text_result.get('entities', []))} 个实体, "
          f"{len(text_result.get('relations', []))} 个关系")
    
    # 保存结果
    print("\n=== 保存结果 ===")
    extractor.save_to_json("models/knowledge/gdm_knowledge.json")
    
    # 显示统计信息
    print("\n=== 统计信息 ===")
    stats = extractor.get_statistics()
    print(f"总实体数: {stats['total_entities']}")
    print(f"总关系数: {stats['total_relations']}")
    print(f"实体类型分布: {stats['entity_types']}")
    print(f"关系类型分布: {stats['relation_types']}")
    
    print("\n=== 知识提取器测试完成 ===")
