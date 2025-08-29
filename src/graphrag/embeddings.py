"""
嵌入处理模块
向量化引擎 - 医学文档的向量化处理
"""
import os
import json
import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """文档分块数据类"""
    chunk_id: str
    text: str
    source_file: str
    metadata: Dict[str, Any]
    vector: Optional[np.ndarray] = None

class EmbeddingEngine:
    """向量化引擎类"""
    
    def __init__(self, 
                 model_name: str = "all-mpnet-base-v2",#"NeuML/pubmedbert-base-embeddings" 医学专用模型,但电脑缓存不下来，可考虑后续改进
                 chunk_size: int = 512,
                 overlap_size: int = 50):
        """
        初始化向量化引擎
        
        Args:
            model_name: 向量化模型名称（使用医学专用模型）
            chunk_size: 分块大小
            overlap_size: 重叠大小
        """
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.model = None
        self.chunks: List[DocumentChunk] = []
        self.vectors: Optional[np.ndarray] = None
        
        # 设置存储路径
        self.vector_store_path = Path("models/vectors")
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        
        # 医学术语保护模式 - 关键医学实体不被分割
        self.medical_entities = [
            r'妊娠期糖尿病[^。]*?。',  # GDM相关
            r'gestational diabetes mellitus[^。]*?。',
            r'血糖[监测|控制|管理][^。]*?。',  # 血糖相关
            r'胰岛素[治疗|注射|使用][^。]*?。',  # 胰岛素相关
            r'孕期[营养|管理|保健][^。]*?。',  # 孕期相关
            r'围产期[并发症|管理][^。]*?。',  # 围产期相关
        ]
        
        # 设置模型缓存策略
        self._setup_cache_strategy()
        
        # 加载模型（带缓存检查）
        self._load_model_with_cache_check()
    
    def _setup_cache_strategy(self):
        """设置模型缓存策略"""
        # 设置Hugging Face缓存目录（确保持久化）
        cache_dir = os.path.expanduser("~/.cache/huggingface")
        os.makedirs(cache_dir, exist_ok=True)
        
        # 设置环境变量
        os.environ['TRANSFORMERS_CACHE'] = cache_dir
        os.environ['HF_HOME'] = cache_dir
        
        logger.info(f"📁 模型缓存目录: {cache_dir}")
    
    def _check_model_cached(self, model_name):
        """检查模型是否已经缓存到本地 - 使用 local_files_only"""
        try:
            start_time = time.time()
        
            # 使用 local_files_only=True 强制离线模式
            model = SentenceTransformer(model_name, local_files_only=True)
            load_time = time.time() - start_time
        
            logger.info(f"✅ 模型已缓存，离线加载时间: {load_time:.2f}秒")
            return model
        
        except Exception as e:
            logger.info(f"模型未完整缓存，需要下载: {str(e)[:100]}...")
            return None
    
    def _download_model_once(self, model_name):
        """一次性下载模型到缓存 - 不使用 local_files_only"""
        logger.info(f"正在下载模型到本地缓存: {model_name}")
        logger.info("⚠️  首次下载需要网络连接，下载后可离线使用")
        logger.info("💡 如果下载失败，请检查网络连接或代理设置")
    
        try:
            # 下载时不使用 local_files_only，允许网络访问
            model = SentenceTransformer(model_name)
            logger.info("✅ 模型下载并缓存成功！")
            logger.info("🎉 下次启动将从本地缓存加载，无需网络连接")
            return model
        except Exception as e:
            logger.error(f"❌ 模型下载失败: {e}")
            logger.error("💡 解决建议：")
            logger.error("   1. 检查网络连接")
            logger.error("   2. 如果在国内，可能需要使用代理")
            logger.error("   3. 或运行 python download_models.py 预下载")
            raise
    
    def _load_model_with_cache_check(self):
        """带缓存检查的模型加载 - 优先使用稳定模型"""
        
        # 按稳定性排序的模型列表
        model_candidates = [
            "all-mpnet-base-v2",          # 420MB - 质量好（当前使用的）
            "all-MiniLM-L6-v2",           # 22MB - 最稳定
            "paraphrase-MiniLM-L6-v2",    # 22MB - 备选
            "NeuML/pubmedbert-base-embeddings"  # 438MB - 医学专用（最后尝试）
        ]
        
        for i, model_name in enumerate(model_candidates, 1):
            try:
                logger.info(f"尝试模型 {i}/{len(model_candidates)}: {model_name}")
                
                # 首先检查是否已缓存
                cached_model = self._check_model_cached(model_name)
                
                if cached_model:
                    # 使用缓存的模型
                    self.model = cached_model
                    self.model_name = model_name
                    logger.info(f"✅ 从本地缓存加载模型: {model_name}")
                else:
                    # 需要下载
                    self.model = self._download_model_once(model_name)
                    self.model_name = model_name
                
                # 验证模型功能
                logger.info("验证模型功能...")
                test_vector = self.model.encode(["测试文本", "妊娠期糖尿病"])
                
                logger.info(f"✅ 模型加载成功: {model_name}")
                logger.info(f"   向量维度: {test_vector.shape}")
                logger.info(f"   设备: {self.model.device}")
                
                return  # 成功后退出
                
            except Exception as e:
                logger.warning(f"❌ 模型 {model_name} 失败: {str(e)[:100]}...")
                
                # 如果是文件损坏，尝试清理缓存
                if "No such file or directory" in str(e) or "FileNotFoundError" in str(e):
                    logger.info(f"检测到缓存文件损坏，清理 {model_name} 缓存...")
                    try:
                        import shutil
                        cache_path = os.path.expanduser(
                            f"~/.cache/huggingface/hub/models--{model_name.replace('/', '--')}"
                        )
                        if os.path.exists(cache_path):
                            shutil.rmtree(cache_path)
                            logger.info("缓存已清理")
                    except Exception as cleanup_e:
                        logger.warning(f"缓存清理失败: {cleanup_e}")
                
                continue  # 尝试下一个模型
        
        # 所有模型都失败了
        logger.error("❌ 所有预设模型都加载失败")
        logger.error("💡 解决方案：")
        logger.error("   1. 检查网络连接")
        logger.error("   2. 运行 python download_models.py 预下载模型")
        logger.error("   3. 或在有网络环境下先运行一次")
        raise Exception("无法加载任何向量化模型，请检查网络连接或预下载模型")
    
    def _smart_text_chunking(self, text: str, source_file: str = "") -> List[str]:
        """
        智能医学文本分块 - 保持医学术语和概念完整性
        
        Args:
            text: 输入文本
            source_file: 源文件名
            
        Returns:
            分块后的文本列表
        """
        if not text.strip():
            return []
        
        # 清理文本
        text = re.sub(r'\n+', '\n', text)  # 合并多个换行
        text = re.sub(r'\s+', ' ', text)   # 合并多个空格
        
        # 按句子分割（支持中英文标点）
        sentence_pattern = r'[。.!！？?；;]\s*'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return [text] if len(text) <= self.chunk_size else self._force_split(text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # 估算加入这个句子后的长度
            temp_chunk = current_chunk + sentence + "。"
            
            if len(temp_chunk) <= self.chunk_size:
                current_chunk = temp_chunk
            else:
                # 当前块已满，保存并开始新块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 如果单个句子太长，强制分割
                if len(sentence) > self.chunk_size:
                    forced_chunks = self._force_split(sentence)
                    chunks.extend(forced_chunks)
                    current_chunk = ""
                else:
                    current_chunk = sentence + "。"
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # 添加重叠处理
        if len(chunks) > 1 and self.overlap_size > 0:
            chunks = self._add_overlap(chunks)
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _force_split(self, text: str) -> List[str]:
        """强制分割过长文本"""
        chunks = []
        words = text.split()
        
        current_chunk_words = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length <= self.chunk_size:
                current_chunk_words.append(word)
                current_length += word_length + 1  # +1 for space
            else:
                if current_chunk_words:
                    chunks.append(' '.join(current_chunk_words))
                current_chunk_words = [word]
                current_length = word_length
        
        if current_chunk_words:
            chunks.append(' '.join(current_chunk_words))
        
        return chunks
    
    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """为分块添加重叠内容"""
        if len(chunks) <= 1:
            return chunks
        
        overlapped_chunks = [chunks[0]]  # 第一个块不需要重叠
        
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            current_chunk = chunks[i]
            
            # 从前一个块末尾提取重叠内容
            prev_words = prev_chunk.split()
            if len(prev_words) > self.overlap_size:
                overlap_words = prev_words[-self.overlap_size:]
                overlap_text = ' '.join(overlap_words)
                
                # 添加重叠内容到当前块
                overlapped_chunk = f"{overlap_text} {current_chunk}"
                overlapped_chunks.append(overlapped_chunk)
            else:
                overlapped_chunks.append(current_chunk)
        
        return overlapped_chunks
    
    def process_documents(self, data_dir: str = "data/processed") -> int:
        """
        处理所有文档并生成分块
        
        Args:
            data_dir: 数据目录路径
            
        Returns:
            处理的文档数量
        """
        logger.info("开始处理文档...")
        
        processed_count = 0
        chunk_id = 0
        
        # 处理各类医学数据
        data_types = ["guidelines", "pubmed", "textbooks", "faq"]
        
        for data_type in data_types:
            type_dir = Path(data_dir) / data_type
            if not type_dir.exists():
                logger.warning(f"目录不存在: {type_dir}")
                continue
            
            logger.info(f"处理 {data_type} 数据...")
            
            # 遍历所有文本文件
            for text_file in type_dir.glob("*.txt"):
                try:
                    with open(text_file, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                    
                    if not text_content.strip():
                        logger.warning(f"空文件: {text_file}")
                        continue
                    
                    # 智能分块处理
                    chunks = self._smart_text_chunking(text_content, str(text_file))
                    
                    for i, chunk_text in enumerate(chunks):
                        chunk = DocumentChunk(
                            chunk_id=f"{data_type}_{chunk_id}",
                            text=chunk_text,
                            source_file=str(text_file),
                            metadata={
                                "data_type": data_type,
                                "source_name": text_file.stem,
                                "chunk_index": i,
                                "chunk_length": len(chunk_text),
                                "total_chunks_in_doc": len(chunks)
                            }
                        )
                        self.chunks.append(chunk)
                        chunk_id += 1
                    
                    processed_count += 1
                    logger.info(f"✅ {text_file.name}: {len(chunks)} 个分块")
                
                except Exception as e:
                    logger.error(f"❌ 处理文件失败 {text_file}: {e}")
        
        logger.info(f"📄 文档处理完成！{processed_count} 个文件，{len(self.chunks)} 个分块")
        return processed_count
    
    def generate_embeddings(self, batch_size: int = 32) -> bool:
        """
        批量生成向量嵌入
        
        Args:
            batch_size: 批处理大小
            
        Returns:
            是否成功生成向量
        """
        if not self.chunks:
            logger.error("没有待处理的文档分块")
            return False
        
        if not self.model:
            logger.error("向量化模型未加载")
            return False
        
        logger.info(f"🚀 开始生成 {len(self.chunks)} 个分块的向量...")
        
        try:
            # 提取所有文本
            texts = [chunk.text for chunk in self.chunks]
            
            # 批量生成向量（显示进度）
            vectors = self.model.encode(
                texts, 
                show_progress_bar=True, 
                batch_size=batch_size,
                convert_to_numpy=True
            )
            
            # 存储向量到每个分块
            for i, chunk in enumerate(self.chunks):
                chunk.vector = vectors[i]
            
            # 保存向量矩阵
            self.vectors = np.array(vectors)
            
            logger.info(f"✅ 向量生成完成！维度: {self.vectors.shape}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 向量生成失败: {e}")
            return False
    
    def save_vectors(self, filename: str = "medical_document_vectors.pkl") -> str:
        """
        保存向量数据
        
        Args:
            filename: 保存文件名
            
        Returns:
            保存文件路径
        """
        if not self.chunks or not self.vectors is not None:
            logger.error("没有向量数据可保存")
            return ""
        
        save_path = self.vector_store_path / filename
        
        try:
            # 准备保存数据
            save_data = {
                "metadata": {
                    "model_name": self.model_name,
                    "chunk_size": self.chunk_size,
                    "overlap_size": self.overlap_size,
                    "total_chunks": len(self.chunks),
                    "vector_dimension": self.vectors.shape[1] if self.vectors is not None else 0,
                    "version": "2.0"
                },
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "source_file": chunk.source_file,
                        "metadata": chunk.metadata,
                        "vector": chunk.vector.tolist() if chunk.vector is not None else None
                    }
                    for chunk in self.chunks
                ]
            }
            
            # 保存为pickle格式
            with open(save_path, 'wb') as f:
                pickle.dump(save_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # 保存摘要信息为JSON
            summary_path = save_path.with_suffix('.json')
            summary_data = {
                "summary": save_data["metadata"],
                "data_type_distribution": self._get_type_distribution(),
                "sample_chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text_preview": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                        "source": chunk.metadata.get("source_name", ""),
                        "data_type": chunk.metadata.get("data_type", "")
                    }
                    for chunk in self.chunks[:5]
                ]
            }
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 向量数据已保存: {save_path}")
            logger.info(f"📋 摘要信息已保存: {summary_path}")
            
            return str(save_path)
            
        except Exception as e:
            logger.error(f"❌ 保存向量失败: {e}")
            return ""
    
    def load_vectors(self, filename: str = "medical_document_vectors.pkl") -> bool:
        """
        加载向量数据
        
        Args:
            filename: 向量文件名
            
        Returns:
            是否成功加载
        """
        load_path = self.vector_store_path / filename
        
        if not load_path.exists():
            logger.error(f"向量文件不存在: {load_path}")
            return False
        
        try:
            with open(load_path, 'rb') as f:
                data = pickle.load(f)
            
            # 加载元数据
            if "metadata" in data:
                metadata = data["metadata"]
                logger.info(f"📋 加载向量数据版本: {metadata.get('version', 'unknown')}")
                logger.info(f"📊 模型: {metadata.get('model_name', 'unknown')}")
                logger.info(f"📏 向量维度: {metadata.get('vector_dimension', 'unknown')}")
            
            # 重构分块数据
            self.chunks = []
            for chunk_data in data["chunks"]:
                chunk = DocumentChunk(
                    chunk_id=chunk_data["chunk_id"],
                    text=chunk_data["text"],
                    source_file=chunk_data["source_file"],
                    metadata=chunk_data["metadata"],
                    vector=np.array(chunk_data["vector"]) if chunk_data["vector"] else None
                )
                self.chunks.append(chunk)
            
            # 重构向量矩阵
            if self.chunks and self.chunks[0].vector is not None:
                self.vectors = np.array([chunk.vector for chunk in self.chunks])
            
            logger.info(f"✅ 成功加载 {len(self.chunks)} 个向量分块")
            return True
            
        except Exception as e:
            logger.error(f"❌ 加载向量失败: {e}")
            return False
    
    def similarity_search(self, 
                         query: str, 
                         top_k: int = 5, 
                         filter_type: Optional[str] = None,
                         min_score: float = 0.0) -> List[Tuple[DocumentChunk, float]]:
        """
        语义相似度搜索
        
        Args:
            query: 查询文本
            top_k: 返回最相似的K个结果
            filter_type: 过滤文档类型 ('guidelines', 'pubmed', 'textbooks', 'faq')
            min_score: 最小相似度分数阈值
            
        Returns:
            相似度最高的分块列表，格式为 (chunk, similarity_score)
        """
        if not self.chunks or self.vectors is None:
            logger.warning("没有可搜索的向量数据")
            return []
        
        if not self.model:
            logger.error("向量化模型未加载")
            return []
        
        try:
            # 生成查询向量
            query_vector = self.model.encode([query], convert_to_numpy=True)
            
            # 计算余弦相似度
            similarities = np.dot(self.vectors, query_vector.T).flatten()
            
            # 应用过滤条件
            valid_results = []
            for i, (chunk, score) in enumerate(zip(self.chunks, similarities)):
                # 类型过滤
                if filter_type and chunk.metadata.get('data_type') != filter_type:
                    continue
                
                # 分数过滤
                if score < min_score:
                    continue
                
                valid_results.append((i, chunk, float(score)))
            
            # 按相似度排序
            valid_results.sort(key=lambda x: x[2], reverse=True)
            
            # 返回top-k结果
            top_results = valid_results[:top_k]
            
            return [(chunk, score) for _, chunk, score in top_results]
            
        except Exception as e:
            logger.error(f"❌ 相似度搜索失败: {e}")
            return []
    
    def _get_type_distribution(self) -> Dict[str, int]:
        """获取文档类型分布"""
        type_counts = {}
        for chunk in self.chunks:
            doc_type = chunk.metadata.get('data_type', 'unknown')
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        return type_counts
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取向量库统计信息
        
        Returns:
            统计信息字典
        """
        if not self.chunks:
            return {"total_chunks": 0, "status": "empty"}
        
        lengths = [len(chunk.text) for chunk in self.chunks]
        
        stats = {
            "basic_info": {
                "total_chunks": len(self.chunks),
                "model_name": self.model_name,
                "chunk_size": self.chunk_size,
                "overlap_size": self.overlap_size,
                "vector_dimension": self.vectors.shape[1] if self.vectors is not None else 0
            },
            "type_distribution": self._get_type_distribution(),
            "text_statistics": {
                "min_length": min(lengths),
                "max_length": max(lengths),
                "avg_length": sum(lengths) / len(lengths),
                "total_characters": sum(lengths)
            },
            "status": "ready" if self.vectors is not None else "vectors_not_generated"
        }
        
        return stats
    
    def clear_data(self):
        """清空所有数据"""
        self.chunks.clear()
        self.vectors = None
        logger.info("🧹 向量数据已清空")

# 便捷函数
def create_embedding_engine(**kwargs) -> EmbeddingEngine:
    """创建向量化引擎实例"""
    return EmbeddingEngine(**kwargs)

# 测试代码
if __name__ == "__main__":
    print("🚀 启动医学文档向量化引擎...")
    
    # 创建引擎
    engine = EmbeddingEngine()
    
    # 处理文档
    count = engine.process_documents()
    print(f"📄 处理了 {count} 个文档文件")
    
    if count > 0:
        # 生成向量
        if engine.generate_embeddings():
            print(f"🎯 生成了 {len(engine.chunks)} 个分块的向量")
            
            # 显示统计信息
            stats = engine.get_statistics()
            print(f"\n📊 向量库统计信息:")
            print(f"   总分块数: {stats['basic_info']['total_chunks']}")
            print(f"   向量维度: {stats['basic_info']['vector_dimension']}")
            print(f"   平均长度: {stats['text_statistics']['avg_length']:.0f} 字符")
            print(f"   类型分布: {stats['type_distribution']}")
            
            # 保存向量
            save_path = engine.save_vectors()
            if save_path:
                print(f"💾 向量已保存到: {save_path}")
                
                # 测试搜索
                print(f"\n🔍 测试搜索功能:")
                test_queries = [
                    "妊娠期糖尿病的症状",
                    "血糖监测方法",
                    "孕期营养管理"
                ]
                
                for query in test_queries:
                    results = engine.similarity_search(query, top_k=2)
                    print(f"\n查询: '{query}'")
                    for i, (chunk, score) in enumerate(results, 1):
                        print(f"  {i}. 相似度: {score:.3f} | 类型: {chunk.metadata['data_type']}")
                        print(f"     内容: {chunk.text[:80]}...")
        
    print("\n✅ 向量化引擎测试完成!")
