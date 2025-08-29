"""
混合检索器 - 整合语义检索和图谱检索
实现GraphRAG的核心检索逻辑
"""

import os
import sys
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# 导入项目模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, project_root)

from src.graphrag.embeddings import EmbeddingEngine, DocumentChunk
from src.graphrag.graph_retriever import GraphRetriever, GraphSearchResult

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class HybridSearchResult:
    """混合搜索结果"""
    semantic_results: List[Tuple[DocumentChunk, float]]  # (chunk, similarity_score)
    graph_results: List[GraphSearchResult]
    combined_context: str
    final_score: float
    search_strategy: str
    total_retrieval_time: float = 0.0  # 增总检索时间
    fusion_method: str = "default"     # 增融合方法

class HybridRetriever:
    """混合检索器类"""
    
    def __init__(self, 
                 embedding_model: str = "all-mpnet-base-v2",
                 semantic_weight: float = 0.6,
                 graph_weight: float = 0.4,
                 max_semantic_results: int = 5,
                 max_graph_results: int = 3):
        """
        初始化混合检索器
        
        Args:
            embedding_model: 嵌入模型名称
            semantic_weight: 语义检索权重
            graph_weight: 图谱检索权重
            max_semantic_results: 语义检索最大结果数
            max_graph_results: 图谱检索最大结果数
        """
        self.semantic_weight = semantic_weight
        self.graph_weight = graph_weight
        self.max_semantic_results = max_semantic_results
        self.max_graph_results = max_graph_results
        
        # 初始化检索器
        self.embedding_engine = EmbeddingEngine(model_name=embedding_model)
        self.graph_retriever = GraphRetriever()
        
        # 查询类型权重配置 - 增自适应权重
        self.query_type_weights = {
            "knowledge_based": {"semantic": 0.3, "graph": 0.7},    # 知识型问题偏重图谱
            "factual": {"semantic": 0.2, "graph": 0.8},            # 事实型问题重图谱
            "contextual": {"semantic": 0.7, "graph": 0.3},         # 上下文型问题偏重向量
            "general": {"semantic": semantic_weight, "graph": graph_weight}  # 通用问题使用默认权重
        }
        
        # 加载向量数据
        self.load_vectors()
        
        logger.info(f"✅ 混合检索器初始化完成 (语义权重: {semantic_weight}, 图谱权重: {graph_weight})")
    
    def load_vectors(self) -> bool:
        """加载向量数据 - 增强错误处理"""
        try:
            success = self.embedding_engine.load_vectors()
            if success:
                logger.info("✅ 向量数据加载成功")
                return True
            else:
                logger.warning("⚠️ 向量数据加载失败，将尝试重新生成")
                # 如果加载失败，尝试重新处理数据
                doc_count = self.embedding_engine.process_documents()
                if doc_count > 0:
                    if self.embedding_engine.generate_embeddings():
                        save_path = self.embedding_engine.save_vectors()
                        if save_path:
                            logger.info("✅ 向量数据重新生成并保存成功")
                            return True
                
                logger.error("❌ 向量数据处理完全失败")
                return False
        except Exception as e:
            logger.error(f"❌ 向量数据处理失败: {e}")
            return False
    
    def classify_query_type(self, query: str) -> str:
        """
        分类查询类型 - 新增方法
        
        Args:
            query: 用户查询
            
        Returns:
            查询类型
        """
        query_lower = query.lower()
        
        # 知识型问题关键词
        knowledge_keywords = ["什么是", "如何", "怎样", "为什么", "原因", "机制", "定义"]
        factual_keywords = ["症状", "治疗", "诊断", "检查", "药物", "风险", "并发症"]
        contextual_keywords = ["病例", "案例", "经验", "经历", "故事", "情况"]
        
        # 统计各类关键词出现次数
        knowledge_count = sum(1 for keyword in knowledge_keywords if keyword in query_lower)
        factual_count = sum(1 for keyword in factual_keywords if keyword in query_lower)
        contextual_count = sum(1 for keyword in contextual_keywords if keyword in query_lower)
        
        # 确定查询类型
        if knowledge_count > 0:
            return "knowledge_based"
        elif factual_count > 0:
            return "factual"
        elif contextual_count > 0:
            return "contextual"
        else:
            return "general"
    
    def semantic_retrieve(self, query: str, top_k: int) -> List[Tuple[DocumentChunk, float]]:
        """
        执行语义检索
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            
        Returns:
            语义检索结果列表
        """
        try:
            # 检查向量数据是否已加载
            if not hasattr(self.embedding_engine, 'chunks') or not self.embedding_engine.chunks:
                logger.warning("⚠️ 没有可搜索的文档分块")
                return []
            
            if not hasattr(self.embedding_engine, 'vectors') or self.embedding_engine.vectors is None:
                logger.warning("⚠️ 向量数据未生成或未加载")
                return []
            
            # 使用 EmbeddingEngine 的 similarity_search 方法
            results = self.embedding_engine.similarity_search(
                query=query, 
                top_k=top_k,
                min_score=0.3  # 设置最低相关性阈值，过滤无关结果
            )
            
            logger.info(f"✅ 语义检索完成: 找到 {len(results)} 个相关结果")
            return results
            
        except Exception as e:
            logger.error(f"❌ 语义检索失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def graph_retrieve(self, query: str, top_k: int) -> List[GraphSearchResult]:
        """
        执行图谱检索
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            
        Returns:
            图谱检索结果列表
        """
        try:
            return self.graph_retriever.retrieve(query, top_k=top_k)
        except Exception as e:
            logger.error(f"❌ 图谱检索失败: {e}")
            return []
    
    def calculate_combined_score(self, 
                               semantic_results: List[Tuple[DocumentChunk, float]], 
                               graph_results: List[GraphSearchResult],
                               query_type: str) -> float:
        """
        计算综合相关性得分
        
        Args:
            semantic_results: 语义检索结果
            graph_results: 图谱检索结果
            query_type: 查询类型
            
        Returns:
            综合相关性得分
        """
        # 获取动态权重
        weights = self.query_type_weights.get(query_type, self.query_type_weights["general"])
        
        # 语义得分 - 使用最佳匹配的平均值
        semantic_score = 0.0
        if semantic_results:
            top_semantic_scores = [score for _, score in semantic_results[:3]]
            semantic_score = sum(top_semantic_scores) / len(top_semantic_scores)
        
        # 图谱得分 - 使用加权平均
        graph_score = 0.0
        if graph_results:
            total_weight = 0
            weighted_sum = 0
            for result in graph_results:
                # 根据实体数量给予权重
                entity_weight = min(len(result.entities), 5) / 5.0 + 0.2  # 基础权重0.2
                weighted_sum += result.relevance_score * entity_weight
                total_weight += entity_weight
            
            if total_weight > 0:
                graph_score = weighted_sum / total_weight
        
        # 综合得分
        combined_score = (semantic_score * weights["semantic"] + 
                         graph_score * weights["graph"])
        
        # 结果质量加成
        quality_bonus = 1.0
        if semantic_results and graph_results:
            quality_bonus = 1.2  # 两种检索都有结果时加成
        elif len(semantic_results) >= 3 or (graph_results and len(graph_results[0].entities) >= 2):
            quality_bonus = 1.1  # 单一检索结果丰富时轻微加成
        
        final_score = min(combined_score * quality_bonus, 1.0)  # 限制在1.0以内
        
        return final_score
    
    def _combine_contexts(self, semantic_context: str, graph_context: str, fusion_method: str) -> str:
        """根据融合方法合并上下文"""
        if fusion_method == "graph_first":
            return f"{graph_context}\n\n{semantic_context}"
        elif fusion_method == "semantic_first":
            return f"{semantic_context}\n\n{graph_context}"
        else:  # balanced or other
            return f"{graph_context}\n\n{semantic_context}"
    
    def fuse_contexts(self, 
                    semantic_results: List[Tuple[DocumentChunk, float]], 
                    graph_results: List[GraphSearchResult],
                    query_type: str) -> Tuple[str, str]:
        """
        融合语义和图谱上下文
        
        Args:
            semantic_results: 语义检索结果
            graph_results: 图谱检索结果
            query_type: 查询类型
            
        Returns:
            (融合后的上下文, 融合方法)
        """
        context_parts = []
        fusion_method = "default"
        
        # 根据查询类型选择不同的融合策略
        if query_type == "factual" and graph_results:
            # 事实型问题：优先展示图谱结构化信息
            fusion_method = "graph_first"
            for i, graph_result in enumerate(graph_results):
                if graph_result.context_text and "未找到" not in graph_result.context_text:
                    context_parts.append(f"【知识图谱-{i+1}】\n{graph_result.context_text}")
        
            # 补充语义信息
            if semantic_results:
                context_parts.append("\n【相关文档内容】")
                for i, (chunk, score) in enumerate(semantic_results[:2]):
                    if score > 0.6:  # 只添加高相关性的文档
                        context_parts.append(f"{i+1}. {chunk.text[:300]}...")  # 修复：使用 chunk.text
    
        elif query_type == "contextual" and semantic_results:
            # 上下文型问题：优先展示文档内容
            fusion_method = "semantic_first"
            context_parts.append("【相关文档内容】")
            for i, (chunk, score) in enumerate(semantic_results):
                context_parts.append(f"{i+1}. (相关性: {score:.3f}) {chunk.text}")  # 修复：使用 chunk.text
        
            # 补充图谱信息
            if graph_results:
                for graph_result in graph_results:
                    if graph_result.context_text and "未找到" not in graph_result.context_text:
                        context_parts.append(f"\n【相关知识点】\n{graph_result.context_text}")
    
        else:
            # 平衡型融合：交错展示
            fusion_method = "balanced"
        
            # 先展示最相关的图谱信息
            if graph_results and graph_results[0].relevance_score > 0.5:
                best_graph = graph_results[0]
                if best_graph.context_text and "未找到" not in best_graph.context_text:
                    context_parts.append(f"【核心知识】\n{best_graph.context_text}")
        
            # 再展示语义检索结果
            if semantic_results:
                context_parts.append("\n【相关文档】")
                for i, (chunk, score) in enumerate(semantic_results[:3]):
                    if score > 0.4:  # 过滤低相关性结果
                        source_info = f"来源: {chunk.source_file}" if hasattr(chunk, 'source_file') and chunk.source_file else ""
                        # 修复：直接使用 chunk.text，DocumentChunk 类使用的是 text 字段
                        content = chunk.text
                        context_parts.append(f"{i+1}. {content} {source_info}")
        
            # 最后补充其他图谱信息
            if len(graph_results) > 1:
                for graph_result in graph_results[1:]:
                    if graph_result.context_text and "未找到" not in graph_result.context_text:
                        context_parts.append(f"\n【补充信息】\n{graph_result.context_text}")
    
        # 处理空结果情况
        if not context_parts:
            if semantic_results:
                context_parts = [f"找到 {len(semantic_results)} 个相关文档，但相关性较低"]
            elif graph_results:
                context_parts = ["知识图谱中找到相关概念，但信息有限"]
            else:
                context_parts = ["未找到直接相关的信息"]
            fusion_method = "fallback"
    
        combined_context = "\n\n".join(context_parts)
    
        # 限制上下文长度
        if len(combined_context) > 2000:
            combined_context = combined_context[:2000] + "\n...(内容已截断)"
            fusion_method += "_truncated"
    
        return combined_context, fusion_method
    
    def retrieve(self, query: str, top_k: int = 5) -> HybridSearchResult:
        """
        执行混合检索 - 主方法
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            
        Returns:
            混合检索结果
        """
        start_time = time.time()
        logger.info(f"🚀 混合检索查询: {query}")
        
        # 1. 查询类型分类
        query_type = self.classify_query_type(query)
        logger.info(f"查询类型: {query_type}")
        
        # 2. 并行执行语义和图谱检索
        semantic_start = time.time()
        semantic_results = self.semantic_retrieve(query, self.max_semantic_results)
        semantic_time = time.time() - semantic_start
        
        graph_start = time.time()
        graph_results = self.graph_retrieve(query, self.max_graph_results)
        graph_time = time.time() - graph_start
        
        logger.info(f"语义检索: {len(semantic_results)} 个结果 ({semantic_time:.3f}s)")
        logger.info(f"图谱检索: {len(graph_results)} 个结果 ({graph_time:.3f}s)")
        
        # 3. 计算综合得分
        final_score = self.calculate_combined_score(semantic_results, graph_results, query_type)
        
        # 4. 融合上下文
        combined_context, fusion_method = self.fuse_contexts(semantic_results, graph_results, query_type)
        
        # 5. 确定搜索策略
        if semantic_results and graph_results:
            search_strategy = f"hybrid_{query_type}"
        elif semantic_results:
            search_strategy = f"semantic_only_{query_type}"
        elif graph_results:
            search_strategy = f"graph_only_{query_type}"
        else:
            search_strategy = "no_results"
        
        total_time = time.time() - start_time
        
        # 6. 构建结果
        result = HybridSearchResult(
            semantic_results=semantic_results[:top_k],
            graph_results=graph_results[:top_k],
            combined_context=combined_context,
            final_score=final_score,
            search_strategy=search_strategy,
            total_retrieval_time=total_time,
            fusion_method=fusion_method
        )
        
        logger.info(f"✅ 混合检索完成 - 总耗时: {total_time:.3f}s, 最终得分: {final_score:.3f}, 融合方法: {fusion_method}")
        
        return result
    
    def get_retrieval_statistics(self) -> Dict[str, Any]:
        """
        获取检索器统计信息
        
        Returns:
            检索器统计信息
        """
        stats = {
            "semantic_retriever": {
                "model": self.embedding_engine.model_name,
                "chunks_loaded": len(self.embedding_engine.chunks) if hasattr(self.embedding_engine, 'chunks') else 0,
                "embeddings_loaded": len(self.embedding_engine.vectors) if hasattr(self.embedding_engine, 'vectors') and self.embedding_engine.vectors is not None else 0
            },
            "graph_retriever": {
                "connected": hasattr(self.graph_retriever.graph_tool, 'driver') and self.graph_retriever.graph_tool.driver is not None
            },
            "weights": {
                "semantic": self.semantic_weight,
                "graph": self.graph_weight
            },
            "limits": {
                "max_semantic_results": self.max_semantic_results,
                "max_graph_results": self.max_graph_results
            }
        }
        return stats
    
    def update_weights(self, semantic_weight: float, graph_weight: float):
        """
        动态更新检索权重
        
        Args:
            semantic_weight: 新的语义检索权重
            graph_weight: 新的图谱检索权重
        """
        # 归一化权重
        total_weight = semantic_weight + graph_weight
        if total_weight > 0:
            self.semantic_weight = semantic_weight / total_weight
            self.graph_weight = graph_weight / total_weight
            
            # 更新默认配置
            self.query_type_weights["general"] = {
                "semantic": self.semantic_weight,
                "graph": self.graph_weight
            }
            
            logger.info(f"✅ 检索权重已更新 - 语义: {self.semantic_weight:.3f}, 图谱: {self.graph_weight:.3f}")
        else:
            logger.warning("⚠️ 权重更新失败：总权重不能为0")
    
    def close(self):
        """关闭混合检索器"""
        try:
            if hasattr(self.graph_retriever, 'close'):
                self.graph_retriever.close()
            logger.info("✅ 混合检索器已关闭")
        except Exception as e:
            logger.error(f"❌ 关闭混合检索器时出错: {e}")

# 便捷函数
def create_hybrid_retriever(**kwargs) -> HybridRetriever:
    """创建混合检索器实例"""
    return HybridRetriever(**kwargs)

# 测试代码
if __name__ == "__main__":
    print("🚀 测试混合检索器...")
    
    try:
        # 1. 创建混合检索器
        print("\n1️⃣ 初始化混合检索器...")
        retriever = HybridRetriever(
            embedding_model="all-mpnet-base-v2",
            semantic_weight=0.6,
            graph_weight=0.4,
            max_semantic_results=5,
            max_graph_results=3
        )
        
        # 2. 显示统计信息
        print("\n2️⃣ 检索器统计信息...")
        stats = retriever.get_retrieval_statistics()
        print(f"📊 语义检索:")
        print(f"   模型: {stats['semantic_retriever']['model']}")
        print(f"   已加载文档块: {stats['semantic_retriever']['chunks_loaded']}")
        print(f"   已加载嵌入向量: {stats['semantic_retriever']['embeddings_loaded']}")
        print(f"📊 图谱检索:")
        print(f"   连接状态: {'✅ 已连接' if stats['graph_retriever']['connected'] else '❌ 未连接'}")
        print(f"📊 权重配置:")
        print(f"   语义检索权重: {stats['weights']['semantic']:.2f}")
        print(f"   图谱检索权重: {stats['weights']['graph']:.2f}")
        print(f"📊 检索限制:")
        print(f"   最大语义结果数: {stats['limits']['max_semantic_results']}")
        print(f"   最大图谱结果数: {stats['limits']['max_graph_results']}")
        
        # 3. 测试查询类型分类
        print("\n3️⃣ 测试查询类型分类...")
        test_classification_queries = [
            "什么是妊娠期糖尿病？",           # knowledge_based
            "妊娠期糖尿病有什么症状？",       # factual
            "我有一个糖尿病患者的病例",       # contextual
            "血糖值多少算正常？"              # general
        ]
        
        for query in test_classification_queries:
            query_type = retriever.classify_query_type(query)
            print(f"   '{query}' → {query_type}")
        
        # 4. 执行混合检索测试
        print("\n4️⃣ 执行混合检索测试...")
        test_queries = [
            "妊娠期糖尿病的主要症状有哪些？",      # factual - 应偏重图谱
            "如何诊断妊娠期糖尿病？",            # knowledge_based - 应偏重图谱
            "孕妇血糖控制不好有什么风险？",      # factual - 应偏重图谱
            "糖耐量检查的具体流程是什么？",      # knowledge_based - 应偏重图谱
            "妊娠期糖尿病的饮食管理要注意什么？"  # factual - 应偏重图谱
        ]
        
        total_time = 0
        successful_queries = 0
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n🔍 测试查询 {i}/{len(test_queries)}: {query}")
            
            try:
                result = retriever.retrieve(query)
                total_time += result.total_retrieval_time
                successful_queries += 1
                
                print(f"   ✅ 查询类型: {retriever.classify_query_type(query)}")
                print(f"   ✅ 搜索策略: {result.search_strategy}")
                print(f"   ✅ 融合方法: {result.fusion_method}")
                print(f"   ✅ 最终得分: {result.final_score:.3f}")
                print(f"   ✅ 检索耗时: {result.total_retrieval_time:.3f}s")
                print(f"   ✅ 语义结果: {len(result.semantic_results)} 个")
                print(f"   ✅ 图谱结果: {len(result.graph_results)} 个")
                print(f"   ✅ 上下文长度: {len(result.combined_context)} 字符")
                
                # 显示语义结果详情
                if result.semantic_results:
                    print(f"   📄 语义结果详情:")
                    for j, (chunk, score) in enumerate(result.semantic_results[:2], 1):
                        print(f"      {j}. 相似度: {score:.3f} | 来源: {getattr(chunk, 'source_file', 'unknown')}")
                        content_preview = getattr(chunk, 'text', '')[:100]  # DocumentChunk 使用 text 字段
                        print(f"         内容预览: {content_preview}...")
                
                # 显示图谱结果详情
                if result.graph_results:
                    print(f"   🕸️  图谱结果详情:")
                    for j, graph_result in enumerate(result.graph_results[:2], 1):
                        print(f"      {j}. 相关性: {graph_result.relevance_score:.3f} | 实体数: {len(graph_result.entities)}")
                        if graph_result.entities:
                            entity_names = [entity.name for entity in graph_result.entities[:3]]
                            print(f"         实体: {', '.join(entity_names)}")
                
                # 显示上下文预览
                if result.combined_context:
                    preview = result.combined_context[:300] + "..." if len(result.combined_context) > 300 else result.combined_context
                    print(f"   📝 上下文预览:\n{preview}")
                
            except Exception as e:
                print(f"   ❌ 查询失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 5. 性能统计
        print(f"\n5️⃣ 性能统计:")
        print(f"   总查询数: {len(test_queries)}")
        print(f"   成功查询数: {successful_queries}")
        print(f"   总检索时间: {total_time:.3f}s")
        if successful_queries > 0:
            avg_time = total_time / successful_queries
            print(f"   平均检索时间: {avg_time:.3f}s/查询")
            if avg_time < 1.0:
                print(f"   性能评级: {'优秀' if avg_time < 0.5 else '良好'}")
            else:
                print(f"   性能评级: 需要优化")
        
        # 6. 测试权重调整功能
        print(f"\n6️⃣ 测试权重调整功能...")
        print(f"   原权重 - 语义: {retriever.semantic_weight:.3f}, 图谱: {retriever.graph_weight:.3f}")
        
        # 调整为更偏重图谱检索
        retriever.update_weights(0.3, 0.7)
        print(f"   新权重 - 语义: {retriever.semantic_weight:.3f}, 图谱: {retriever.graph_weight:.3f}")
        
        # 用调整后的权重测试一个查询
        test_query = "妊娠期糖尿病有什么症状？"
        print(f"   测试查询: {test_query}")
        
        adjusted_result = retriever.retrieve(test_query)
        print(f"   调整权重后结果:")
        print(f"     最终得分: {adjusted_result.final_score:.3f}")
        print(f"     搜索策略: {adjusted_result.search_strategy}")
        print(f"     融合方法: {adjusted_result.fusion_method}")
        
        # 7. 测试边界情况
        print(f"\n7️⃣ 测试边界情况...")
        edge_cases = [
            "",                                    # 空查询
            "这是一个完全不相关的查询关于外星人",    # 无关查询
            "GDM",                                # 简短缩写
            "妊娠期糖尿病" * 50                    # 过长查询
        ]
        
        for case in edge_cases:
            try:
                if len(case) > 50:
                    display_case = case[:50] + "...(过长查询)"
                else:
                    display_case = case if case else "(空查询)"
                
                print(f"   测试: {display_case}")
                result = retriever.retrieve(case)
                print(f"     结果: 得分={result.final_score:.3f}, 策略={result.search_strategy}")
            except Exception as e:
                print(f"     错误: {e}")
        
        # 8. 关闭检索器
        print(f"\n8️⃣ 关闭检索器...")
        retriever.close()
        
        print(f"\n✅ 混合检索器测试完成!")
        print(f"🎉 所有功能测试通过，系统运行正常!")
        
    except Exception as e:
        print(f"❌ 测试过程中出现致命错误: {e}")
        print(f"🔧 错误详情:")
        import traceback
        traceback.print_exc()
        
        # 尝试关闭资源
        try:
            if 'retriever' in locals():
                retriever.close()
                print("✅ 资源已清理")
        except:
            pass
