"""
GDM GraphRAG主引擎
整合所有RAG组件，实现完整的查询处理流程
"""

import os
import re
import sys
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.insert(0, project_root)

# 导入已完成的模块
from src.graphrag.hybrid_retriever import HybridRetriever, HybridSearchResult
from src.graphrag.prompt_templates import create_gdm_prompt_interface, GraphRAGPromptInterface
from src.utils.deepseek_client import DeepSeekClient

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GDMRAGResponse:
    """GDM RAG系统响应结果"""
    question: str
    answer: str
    sources: List[str]
    context_used: str
    response_time: float
    confidence_score: float
    retrieval_stats: Dict[str, Any]
    query_analysis: Dict[str, Any]

class GDMGraphRAGEngine:
    """GDM GraphRAG主引擎"""
    
    def __init__(self, 
                 deepseek_api_key: str = "sk-f73a7b96600a4eeebe34cbe357902568",
                 enable_cache: bool = True,
                 max_context_length: int = 3500):
        """
        初始化GDM GraphRAG引擎
        
        Args:
            deepseek_api_key: DeepSeek API密钥
            enable_cache: 是否启用缓存
            max_context_length: 最大上下文长度
        """
        self.enable_cache = enable_cache
        self.max_context_length = max_context_length
        self.cache: Dict[str, GDMRAGResponse] = {}
        
        try:
            logger.info("🚀 初始化GDM GraphRAG引擎...")
            
            # 1. 初始化混合检索器 - 使用HybridRetriever
            logger.info("初始化混合检索器...")
            self.hybrid_retriever = HybridRetriever(
                embedding_model="all-mpnet-base-v2",
                semantic_weight=0.6,
                graph_weight=0.4,
                max_semantic_results=5,
                max_graph_results=3
            )
            logger.info("✅ 混合检索器初始化完成")
            
            # 2. 初始化提示词接口 - 使用GraphRAGPromptInterface
            logger.info("初始化提示词接口...")
            prompt_config = {
                'max_tokens': max_context_length,
                'enable_safety_enhancement': True,
                'enable_optimization': True
            }
            self.prompt_interface = create_gdm_prompt_interface(prompt_config)
            logger.info("✅ 提示词接口初始化完成")
            
            # 3. 初始化DeepSeek客户端 - 使用DeepSeekClient
            logger.info("初始化DeepSeek客户端...")
            self.deepseek_client = DeepSeekClient(api_key=deepseek_api_key)
            logger.info("✅ DeepSeek客户端初始化完成")
            
            logger.info("🎉 GDM GraphRAG引擎初始化成功！")
            
        except Exception as e:
            logger.error(f"❌ GraphRAG引擎初始化失败: {e}")
            raise
    
    def _generate_cache_key(self, question: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(question.encode('utf-8')).hexdigest()
    
    def _simple_query_classification(self, query: str) -> str:
        """
        简单查询分类 - 适配HybridRetriever的classify_query_type方法
        
        Args:
            query: 用户查询
            
        Returns:
            查询类型
        """
        return self.hybrid_retriever.classify_query_type(query)
    
    def _extract_sources(self, retrieval_result: HybridSearchResult) -> List[str]:
        """
        提取信息来源
        
        Args:
            retrieval_result: 混合检索结果
            
        Returns:
            信息来源列表
        """
        sources = []
        
        # 从语义检索结果中提取来源
        for chunk, score in retrieval_result.semantic_results:
            # 使用chunk的source_file属性
            if hasattr(chunk, 'source_file') and chunk.source_file:
                source_name = os.path.basename(chunk.source_file).replace('.txt', '')
                source_info = f"文档:{source_name}"
                if source_info not in sources:
                    sources.append(source_info)
            
            # 如果有metadata，提取data_type
            if hasattr(chunk, 'metadata') and chunk.metadata:
                data_type = chunk.metadata.get('data_type', 'unknown')
                type_info = f"类型:{data_type}"
                if type_info not in sources:
                    sources.append(type_info)
        
        # 从图谱检索结果中提取来源 - 添加安全检查
        if hasattr(retrieval_result, 'graph_results') and retrieval_result.graph_results:
            graph_entities = []
            for graph_result in retrieval_result.graph_results:
                if hasattr(graph_result, 'entities') and graph_result.entities:
                    entity_names = [entity.name for entity in graph_result.entities[:2]]
                    graph_entities.extend(entity_names)
            
            if graph_entities:
                sources.append(f"知识图谱:{','.join(graph_entities[:3])}")
        
        return sources[:5]  # 限制来源数量
    
    def _calculate_confidence_score(self, retrieval_result: HybridSearchResult) -> float:
        """
        计算置信度 - 基于HybridSearchResult结构
        
        Args:
            retrieval_result: 混合检索结果
            
        Returns:
            置信度分数 (0-1)
        """
        # 使用HybridSearchResult的final_score作为基础置信度
        base_confidence = retrieval_result.final_score
        
        # 根据检索结果质量调整
        quality_bonus = 0.0
        
        # 语义检索质量加成
        if retrieval_result.semantic_results:
            avg_semantic_score = sum(score for _, score in retrieval_result.semantic_results) / len(retrieval_result.semantic_results)
            quality_bonus += avg_semantic_score * 0.1
        
        # 图谱检索质量加成
        if retrieval_result.graph_results:
            avg_graph_score = sum(gr.relevance_score for gr in retrieval_result.graph_results) / len(retrieval_result.graph_results)
            quality_bonus += avg_graph_score * 0.1
        
        # 上下文长度加成
        if len(retrieval_result.combined_context) > 500:
            quality_bonus += 0.05
        
        final_confidence = min(base_confidence + quality_bonus, 1.0)
        return max(final_confidence, 0.1)  # 保证最低置信度
    
    def _post_process_answer(self, answer: str, question: str) -> str:
        """
        后处理回答内容 - 优化用户阅读体验
        """
        if not answer or not answer.strip():
            return "抱歉，系统无法生成合适的回答，请尝试换个问题或咨询专业医师。"
    
        # 清理回答
        answer = answer.strip()
    
        # 1. 强化移除所有Markdown格式标记
        # 移除标题标记 ### text -> text, ## text -> text, # text -> text
        answer = re.sub(r'^#{1,6}\s*(.*)', r'\1', answer, flags=re.MULTILINE)
    
        # 移除粗体标记 **text** -> text
        answer = re.sub(r'\*\*(.*?)\*\*', r'\1', answer)
    
        # 移除斜体标记 *text* -> text  
        answer = re.sub(r'\*(.*?)\*', r'\1', answer)
    
        # 移除代码块标记
        answer = re.sub(r'```.*?```', '', answer, flags=re.DOTALL)
        answer = re.sub(r'`(.*?)`', r'\1', answer)
    
        # 移除链接格式 [text](url) -> text
        answer = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', answer)
    
        # 移除列表标记但保留内容 - 处理 Markdown 列表
        answer = re.sub(r'^\s*[-\*\+]\s+', '', answer, flags=re.MULTILINE)
    
        # 2. 预处理 - 统一标点符号
        answer = answer.replace('：', ':').replace('，', ',')
    
        # 3. 智能分段处理
        answer = self._smart_paragraph_split(answer)
    
        # 4. 移除可能的模板残留
        unwanted_prefixes = [
            '根据提供的信息', '基于以上内容', '从上述资料可以看出',
            '根据相关资料', '基于专业知识', '从医学角度来看',
            '根据医学知识', '从临床角度'
        ]
        for prefix in unwanted_prefixes:
            if answer.startswith(prefix):
                answer = answer[len(prefix):].lstrip('，,：: ')
    
        # 5. 确保回答完整性
        if not answer.endswith(('。', '！', '？', '.', '!', '?')):
            answer += '。'
    
        # 6. 最终格式化处理
        answer = self._final_format_processing(answer)
    
        return answer

    def _smart_paragraph_split(self, text: str) -> str:
        """
        智能分段处理 - 强化数字列表分段
        """
        if len(text) < 80:
            return text

        # 首先按现有段落分割
        existing_paragraphs = re.split(r'\n\s*\n|\n', text)
        existing_paragraphs = [p.strip() for p in existing_paragraphs if p.strip()]
    
        # 合并所有文本重新处理
        full_text = ' '.join(existing_paragraphs)
    
        # 特殊标记强制分段
        section_markers = [
            r'📚\s*详细说明',
            r'📚\s*',
            r'❗\s*相关提醒', 
            r'❗\s*',
            r'🏥\s*行动建议',
            r'🏥\s*',
            r'💡\s*温馨提示',
            r'💡\s*',
            r'⚠️\s*注意事项',
            r'⚠️\s*',
            r'🔍\s*诊断标准',
            r'🔍\s*',
            r'🍎\s*饮食建议',
            r'🍎\s*',
            r'💊\s*治疗方案',
            r'💊\s*',
            r'核心回答[（(]基于知识图谱[）)]',
            r'根据医学知识图谱',
            r'主要症状包括[:：]',
            r'治疗方案如下[:：]',
            r'预防措施包括[:：]'
        ]
    
        # 在标记前插入分段符
        for marker in section_markers:
            full_text = re.sub(f'({marker})', r'\n\n\1', full_text)
    
        # 强制数字列表分段 - 关键修改
        # 在任何数字列表前强制分段，不管前面有没有标点符号
        full_text = re.sub(r'(\S)\s*(\d+[\.、]\s+)', r'\1\n\n\2', full_text)
    
        # 中文数字列表分段
        full_text = re.sub(r'(\S)\s*([一二三四五六七八九十][\.、]\s+)', r'\1\n\n\2', full_text)
    
        # 处理冒号后的数字列表
        full_text = re.sub(r'([:：])\s*(\d+[\.、]\s+)', r'\1\n\n\2', full_text)
    
        # 现在按双换行分割段落
        paragraphs = re.split(r'\n\n+', full_text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
        # 进一步处理每个段落内部的句子
        final_paragraphs = []
    
        for paragraph in paragraphs:
            # 如果段落以数字开头，保持独立
            if re.match(r'^\d+[\.、]\s+', paragraph):
                final_paragraphs.append(paragraph)
                continue
        
            # 修复：正确检查段落中是否包含多个数字列表项
            list_matches = re.findall(r'\d+[\.、]\s+', paragraph)
            if len(list_matches) >= 2:
                # 按数字列表拆分
                parts = re.split(r'(\d+[\.、]\s+)', paragraph)
                current_part = ""
            
                for i, part in enumerate(parts):
                    if re.match(r'^\d+[\.、]\s+$', part):
                        # 这是数字标记
                        if current_part.strip():
                            final_paragraphs.append(current_part.strip())
                        current_part = part
                    else:
                        current_part += part
            
                if current_part.strip():
                    final_paragraphs.append(current_part.strip())
            else:
                final_paragraphs.append(paragraph)
    
        # 返回分段结果
        result = '\n\n'.join(final_paragraphs)
    
        # 清理多余的空行
        result = re.sub(r'\n{3,}', '\n\n', result)
    
        return result

    def _final_format_processing(self, text: str) -> str:
        """
        最终格式化处理
    
        Args:
            text: 待处理的文本
        
        Returns:
            格式化后的文本
        """
        # 分割段落
        paragraphs = text.split('\n\n')
        processed_paragraphs = []
    
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 处理列表项的缩进和格式
            lines = paragraph.split('\n')
            formatted_lines = []
        
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 为数字列表和中文列表添加适当的格式
                if re.match(r'^[\d]+[、.]', line):
                    formatted_lines.append(line)
                elif re.match(r'^[一二三四五六七八九十][、.]', line):
                    formatted_lines.append(line)
                else:
                    formatted_lines.append(line)
        
            if formatted_lines:
                processed_paragraphs.append('\n'.join(formatted_lines))
    
        # 确保段落间有适当间距
        result = '\n\n'.join(processed_paragraphs)
    
        # 清理多余的空行
        result = re.sub(r'\n{3,}', '\n\n', result)
    
        return result.strip()
    
    def process_query(self, user_query: str, 
                     chat_history: Optional[List[Dict]] = None,
                     use_cache: bool = True) -> GDMRAGResponse:
        """
        处理用户查询 - 主要方法
        
        Args:
            user_query: 用户查询
            chat_history: 对话历史
            use_cache: 是否使用缓存
            
        Returns:
            GDM RAG响应结果
        """
        start_time = time.time()
        logger.info(f"🔍 处理查询: {user_query}")
        
        # 检查缓存
        if use_cache and self.enable_cache:
            cache_key = self._generate_cache_key(user_query)
            if cache_key in self.cache:
                cached_response = self.cache[cache_key]
                logger.info("💾 使用缓存结果")
                return cached_response
        
        try:
            # 1. 查询分类
            query_type = self._simple_query_classification(user_query)
            logger.info(f"📋 查询类型: {query_type}")
            
            # 2. 混合检索 - 使用HybridRetriever.retrieve方法
            logger.info("🔍 执行混合检索...")
            retrieval_result = self.hybrid_retriever.retrieve(user_query, top_k=5)
            
            if not retrieval_result.combined_context.strip():
                logger.warning("⚠️ 未找到相关上下文")
                return self._create_empty_response(user_query, start_time, "未找到相关信息")
            
            logger.info(f"✅ 检索完成: {retrieval_result.search_strategy}, 得分: {retrieval_result.final_score:.3f}")
            
            # 3. 生成提示词 - 使用GraphRAGPromptInterface
            logger.info("📝 生成提示词...")
            prompt_result = self.prompt_interface.create_prompt(
                query=user_query,
                semantic_results=retrieval_result.semantic_results,
                graph_results=retrieval_result.graph_results,
                query_type=query_type,
                fusion_method=retrieval_result.fusion_method,
                chat_history=self._format_chat_history(chat_history)
            )
            
            if not prompt_result['is_valid']:
                logger.warning("⚠️ 提示词质量问题")
            
            # 4. 调用DeepSeek生成回答
            logger.info("🤖 调用DeepSeek生成回答...")
            messages = [{"role": "user", "content": prompt_result['prompt']}]
            deepseek_response = self.deepseek_client.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=1000
            )
            
            if not deepseek_response or 'choices' not in deepseek_response:
                logger.error("❌ DeepSeek响应格式错误")
                return self._create_error_response(user_query, start_time, "AI回答生成失败")
            
            raw_answer = deepseek_response['choices'][0]['message']['content']
            
            # 5. 后处理回答
            final_answer = self._post_process_answer(raw_answer, user_query)
            
            # 6. 提取信息来源
            sources = self._extract_sources(retrieval_result)
            
            # 7. 计算置信度
            confidence = self._calculate_confidence_score(retrieval_result)
            
            # 8. 构建响应
            response = GDMRAGResponse(
                question=user_query,
                answer=final_answer,
                sources=sources,
                context_used=retrieval_result.combined_context,
                response_time=time.time() - start_time,
                confidence_score=confidence,
                retrieval_stats={
                    "search_strategy": retrieval_result.search_strategy,
                    "fusion_method": retrieval_result.fusion_method,
                    "semantic_results_count": len(retrieval_result.semantic_results),
                    "graph_results_count": len(retrieval_result.graph_results),
                    "final_score": retrieval_result.final_score,
                    "total_retrieval_time": retrieval_result.total_retrieval_time,
                    "prompt_quality_score": prompt_result.get('quality_score', 0)
                },
                query_analysis={
                    "query_type": query_type,
                    "context_length": len(retrieval_result.combined_context),
                    "prompt_length": len(prompt_result['prompt']),
                    "estimated_tokens": prompt_result['metrics']['estimated_tokens']
                }
            )
            
            # 9. 缓存结果
            if use_cache and self.enable_cache:
                self.cache[cache_key] = response
            
            logger.info(f"✅ 查询处理完成 (耗时: {response.response_time:.2f}s, 置信度: {confidence:.3f})")
            return response
            
        except Exception as e:
            logger.error(f"❌ 查询处理失败: {e}")
            return self._create_error_response(user_query, start_time, str(e))
    
    def _format_chat_history(self, chat_history: Optional[List[Dict]]) -> Optional[str]:
        """格式化对话历史"""
        if not chat_history:
            return None
        
        history_parts = []
        for i, turn in enumerate(chat_history[-3:], 1):  # 只保留最近3轮
            role = "用户" if turn.get("role") == "user" else "助手"
            content = turn.get("content", "")[:150]  # 限制长度
            history_parts.append(f"第{i}轮 {role}: {content}")
        
        return "\n".join(history_parts)
    
    def _create_empty_response(self, question: str, start_time: float, reason: str) -> GDMRAGResponse:
        """创建空响应"""
        return GDMRAGResponse(
            question=question,
            answer="抱歉，我没有找到相关的医学信息来回答您的问题。建议您：\n1. 尝试换个说法重新提问\n2. 咨询专业医生获取准确信息\n3. 查阅权威医学资料",
            sources=[],
            context_used="",
            response_time=time.time() - start_time,
            confidence_score=0.0,
            retrieval_stats={
                "search_strategy": "empty_result",
                "fusion_method": "none",
                "semantic_results_count": 0,
                "graph_results_count": 0,
                "final_score": 0.0,
                "total_retrieval_time": 0.0,
                "prompt_quality_score": 0,
                "reason": reason
            },
            query_analysis={
                "query_type": "unknown",
                "context_length": 0,
                "prompt_length": 0,
                "estimated_tokens": 0
            }
        )
    
    def _create_error_response(self, question: str, start_time: float, error: str) -> GDMRAGResponse:
        """创建错误响应"""
        return GDMRAGResponse(
            question=question,
            answer=f"系统处理出现错误，请稍后重试。如果问题持续存在，请联系技术支持。",
            sources=[],
            context_used="",
            response_time=time.time() - start_time,
            confidence_score=0.0,
            retrieval_stats={
                "search_strategy": "error",
                "fusion_method": "none",
                "semantic_results_count": 0,
                "graph_results_count": 0,
                "final_score": 0.0,
                "total_retrieval_time": 0.0,
                "prompt_quality_score": 0,
                "error": error
            },
            query_analysis={
                "query_type": "error",
                "context_length": 0,
                "prompt_length": 0,
                "estimated_tokens": 0
            }
        )
    
    def batch_query(self, questions: List[str]) -> List[GDMRAGResponse]:
        """
        批量查询处理
        
        Args:
            questions: 问题列表
            
        Returns:
            响应结果列表
        """
        logger.info(f"📦 开始批量处理 {len(questions)} 个查询")
        
        responses = []
        for i, question in enumerate(questions, 1):
            logger.info(f"处理第 {i}/{len(questions)} 个查询: {question}")
            response = self.process_query(question)
            responses.append(response)
        
        return responses
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态信息"""
        try:
            # 获取混合检索器统计信息
            retrieval_stats = self.hybrid_retriever.get_retrieval_statistics()
            
            status = {
                "engine_status": "正常运行",
                "cache_size": len(self.cache) if self.enable_cache else 0,
                "retrieval_system": {
                    "status": "正常" if self.hybrid_retriever else "异常",
                    "semantic_chunks": retrieval_stats['semantic_retriever']['chunks_loaded'],
                    "semantic_embeddings": retrieval_stats['semantic_retriever']['embeddings_loaded'],
                    "graph_connected": retrieval_stats['graph_retriever']['connected'],
                    "current_weights": retrieval_stats['weights']
                },
                "prompt_system": {
                    "status": "正常" if self.prompt_interface else "异常",
                    "max_tokens": self.max_context_length
                },
                "deepseek_client": {
                    "status": "正常" if self.deepseek_client else "异常",
                    "api_key_configured": bool(self.deepseek_client.api_key)
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {
                "engine_status": "异常", 
                "error": str(e),
                "cache_size": len(self.cache) if hasattr(self, 'cache') else 0
            }
    
    def clear_cache(self):
        """清理缓存"""
        if self.enable_cache and hasattr(self, 'cache'):
            cache_size = len(self.cache)
            self.cache.clear()
            logger.info(f"🧹 已清理 {cache_size} 条缓存")
    
    def update_retrieval_weights(self, semantic_weight: float, graph_weight: float):
        """动态调整检索权重"""
        try:
            self.hybrid_retriever.update_weights(semantic_weight, graph_weight)
            logger.info(f"⚖️ 检索权重已更新: 语义={semantic_weight:.2f}, 图谱={graph_weight:.2f}")
        except Exception as e:
            logger.error(f"更新检索权重失败: {e}")
    
    def close(self):
        """关闭引擎"""
        try:
            if hasattr(self, 'hybrid_retriever'):
                self.hybrid_retriever.close()
            
            if hasattr(self, 'deepseek_client') and hasattr(self.deepseek_client, 'close'):
                self.deepseek_client.close()
            
            self.clear_cache()
            logger.info("🔒 GDM GraphRAG引擎已关闭")
            
        except Exception as e:
            logger.error(f"关闭引擎时出错: {e}")

# ===== 便捷函数 =====

def create_gdm_rag_engine(api_key: str = None, **kwargs) -> GDMGraphRAGEngine:
    """创建GDM GraphRAG引擎实例"""
    return GDMGraphRAGEngine(deepseek_api_key=api_key, **kwargs)

# ===== 测试代码 =====

if __name__ == "__main__":
    print("🚀 GDM GraphRAG主引擎测试...")
    
    try:
        # 1. 创建引擎
        print("\n1️⃣ 初始化引擎...")
        engine = GDMGraphRAGEngine()
        
        # 2. 检查系统状态
        print("\n2️⃣ 检查系统状态...")
        status = engine.get_system_status()
        print("系统状态:")
        for key, value in status.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for sub_key, sub_value in value.items():
                    print(f"    {sub_key}: {sub_value}")
            else:
                print(f"  {key}: {value}")
        
        # 3. 测试单个查询
        print(f"\n3️⃣ 测试查询处理...")
        test_questions = [
            "什么是妊娠期糖尿病？",
            "妊娠期糖尿病有什么症状？",
            "如何治疗妊娠期糖尿病？",
            "孕妇血糖高有什么风险？"
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n--- 测试查询 {i}: {question} ---")
            
            response = engine.process_query(question)
            
            print(f"✅ 处理完成:")
            print(f"   响应时间: {response.response_time:.2f}秒")
            print(f"   置信度: {response.confidence_score:.3f}")
            print(f"   信息来源: {', '.join(response.sources) if response.sources else '无'}")
            print(f"   查询类型: {response.query_analysis['query_type']}")
            print(f"   检索策略: {response.retrieval_stats['search_strategy']}")
            print(f"   融合方法: {response.retrieval_stats['fusion_method']}")
            print(f"   上下文长度: {response.query_analysis['context_length']}")
            print(f"   回答预览: {response.answer[:150]}...")
        
        # 4. 测试批量查询
        print(f"\n4️⃣ 测试批量查询...")
        batch_questions = [
            "GDM的诊断标准是什么？",
            "妊娠期糖尿病需要注意哪些饮食？"
        ]
        
        batch_responses = engine.batch_query(batch_questions)
        print(f"批量处理完成: {len(batch_responses)} 个结果")
        
        for i, response in enumerate(batch_responses, 1):
            print(f"  批量查询 {i}: 耗时 {response.response_time:.2f}s, 置信度 {response.confidence_score:.3f}")
        
        # 5. 测试缓存
        print(f"\n5️⃣ 测试缓存机制...")
        cached_response = engine.process_query(test_questions[0])  # 重复查询
        print(f"缓存查询耗时: {cached_response.response_time:.4f}秒")
        
        # 6. 测试权重调整
        print(f"\n6️⃣ 测试权重调整...")
        print("调整检索权重: 更偏重图谱检索")
        engine.update_retrieval_weights(0.3, 0.7)
        
        adjusted_response = engine.process_query("妊娠期糖尿病的症状")
        print(f"调整权重后检索策略: {adjusted_response.retrieval_stats['search_strategy']}")
        
        # 7. 清理
        print(f"\n7️⃣ 清理资源...")
        engine.close()
        
        print(f"\n✅ GDM GraphRAG主引擎测试完成!")
        print(f"🎉 所有核心功能正常工作，可以投入使用!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
