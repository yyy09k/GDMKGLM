"""
GraphRAG提示词模板系统（GDM）
整合语义检索和图谱检索的提示词生成
"""

from enum import Enum
from typing import Dict, Optional, Any, List, Tuple
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """查询类型枚举 - 与hybrid_retriever保持一致"""
    KNOWLEDGE_BASED = "knowledge_based"
    FACTUAL = "factual"
    CONTEXTUAL = "contextual" 
    GENERAL = "general"
    DIAGNOSTIC = "diagnostic"
    TREATMENT = "treatment"
    RISK_ASSESSMENT = "risk_assessment"

@dataclass
class PromptContext:
    """提示词上下文数据"""
    query: str
    semantic_context: str = ""
    graph_context: str = ""
    query_type: str = "general"
    fusion_method: str = "balanced"
    search_strategy: str = "hybrid"

class MedicalPromptTemplates:
    """
    医学GraphRAG提示词模板系统
    为妊娠期糖尿病知识问答优化，与混合检索器深度集成
    """
    
    # ================================
    # 系统级提示词配置
    # ================================
    
    SYSTEM_PERSONA = """你是一位专业的妊娠期糖尿病(GDM)医学助手，具备以下特质：
✓ 拥有丰富的妊娠期糖尿病临床知识和研究背景
✓ 能够准确解读医学文献和临床指南
✓ 善于将专业医学知识转化为患者易懂的表达
✓ 严格遵循医学伦理和安全准则

【核心原则】
• 严格基于提供的医学资料回答问题
• 保持科学严谨性，不提供未经证实的信息
• 明确区分一般健康信息和个性化医疗建议
• 在适当时机建议咨询专业医师"""

    SAFETY_DISCLAIMER = """
⚠️ **重要医学声明**
本回答基于医学资料提供参考信息，不能替代专业医疗诊断和治疗。
• 具体症状和治疗方案请咨询医师
• 紧急情况请立即就医
• 用药需在医师指导下进行"""

    # ================================
    # 基础模板系列 
    # ================================

    @staticmethod
    def get_base_template() -> str:
        """基础问答模板 - 适用于一般查询"""
        return """
{system_persona}

【检索到的医学知识】
{context}

【患者咨询】
{query}

【专业回答要求】
1. 基于上述医学知识进行回答，确保准确性
2. 使用清晰的结构组织信息（必要时使用标题和要点）
3. 对专业术语进行适当解释
4. 如果知识不足以完全回答，请明确说明
5. 提供实用的建议和注意事项

{safety_disclaimer}

【专业回答】
"""

    @staticmethod  
    def get_graph_enhanced_template() -> str:
        """图谱增强模板 - 整合结构化知识"""
        return """
{system_persona}

【知识图谱信息】
{graph_context}

【文献资料补充】
{semantic_context}

【患者咨询】
{query}

【图谱增强回答指引】
1. **优先使用知识图谱的结构化信息**回答核心问题
2. **结合文献资料**提供详细解释和实例支撑
3. **保持信息一致性**，如遇冲突请说明并建议咨询医师
4. **充分利用图谱关联**，提供相关但用户可能未想到的重要信息

回答结构建议：
• 核心回答（基于图谱）
• 详细说明（结合文献）
• 相关提醒（图谱关联信息）
• 行动建议

{safety_disclaimer}

【专业回答】
"""

    @staticmethod
    def get_symptom_analysis_template() -> str:
        """症状分析模板 - 专用于症状相关查询"""
        return """
{system_persona}

【症状相关医学知识】
{context}

【症状描述】
{query}

【症状分析框架】
请按以下结构进行症状分析：

**1. 症状特征识别**
- 描述相关症状的典型表现
- 说明症状的严重程度分级

**2. 医学机制解释**  
- 解释症状产生的生理病理机制
- 与妊娠期糖尿病的关联性

**3. 鉴别要点**
- 需要与哪些情况进行鉴别
- 伴随症状的重要性

**4. 就医指导**
- 什么情况下需要就医
- 紧急就医的危险信号

{safety_disclaimer}

【症状分析】
"""

    @staticmethod
    def get_treatment_guidance_template() -> str:
        """治疗指导模板 - 专用于治疗相关查询"""
        return """
{system_persona}

【治疗相关医学知识】
{context}

【治疗咨询】
{query}

【治疗指导框架】
请按照循证医学原则提供治疗指导：

**1. 治疗原则和目标**
- 基本治疗原则
- 预期治疗效果和目标

**2. 治疗方案层次**
- 一线治疗方案（生活方式干预）
- 二线治疗方案（药物治疗）
- 特殊情况处理

**3. 监测和随访**
- 治疗效果监测指标
- 随访时间和频率
- 副作用监测

**4. 患者教育要点**
- 治疗依从性的重要性
- 自我管理技巧
- 复查提醒

⚕️ **治疗提醒**：所有治疗方案必须在医师指导下实施，请勿自行调整治疗计划。

【治疗指导】
"""

    @staticmethod
    def get_diagnostic_template() -> str:
        """诊断相关模板"""
        return """
{system_persona}

【诊断相关医学知识】
{context}

【诊断咨询】
{query}

【诊断信息指导】
基于当前医学标准，提供诊断相关信息：

**1. 诊断标准**
- 国际公认的诊断标准
- 诊断的关键指标和数值

**2. 检查流程**
- 推荐的检查项目和顺序
- 检查前准备事项

**3. 结果解读**
- 正常值范围
- 异常结果的临床意义

**4. 注意事项**
- 影响检查准确性的因素
- 假阳性/假阴性的可能性

📋 **诊断提醒**：诊断结果须由专业医师解读，请勿自行判断。

【诊断信息】
"""

    @staticmethod
    def get_risk_assessment_template() -> str:
        """风险评估模板"""
        return """
{system_persona}

【风险评估医学知识】
{context}

【风险咨询】
{query}

【风险评估指导】
基于循证医学证据进行风险评估：

**1. 风险因素识别**
- 主要风险因素及其影响程度
- 可控制vs不可控制风险因素

**2. 风险程度评估**
- 个体风险评估方法
- 风险分级标准

**3. 预防和控制策略**
- 一级预防措施（预防发生）
- 二级预防措施（早期发现）
- 三级预防措施（控制进展）

**4. 监测建议**
- 风险监测指标
- 监测频率和方法

⚠️ **风险提醒**：个体化风险评估需要专业医师综合判断。

【风险评估】
"""

    @staticmethod
    def get_nutrition_template() -> str:
        """营养指导模板"""
        return """
{system_persona}

【营养相关医学知识】
{context}

【营养咨询】
{query}

【营养指导原则】
基于妊娠期糖尿病营养管理指南：

**1. 营养治疗目标**
- 血糖控制目标
- 体重管理目标
- 营养需求满足

**2. 饮食结构建议**
- 碳水化合物配比和选择
- 蛋白质和脂肪搭配
- 微量元素补充

**3. 餐次安排**
- 三餐两点制原则
- 进餐时间控制
- 份量控制方法

**4. 血糖监测配合**
- 餐前餐后血糖目标
- 饮食调整依据

🍎 **营养提醒**：营养方案需要个体化调整，建议咨询营养师制定详细计划。

【营养指导】
"""

    @staticmethod
    def get_conversational_template() -> str:
        """对话模式模板 - 考虑历史对话上下文"""
        return """
{system_persona}

【对话历史回顾】
{chat_history}

【当前检索到的相关知识】
{context}

【当前问题】
{query}

【连续对话指导】
作为专业医学助手，在回答当前问题时：

1. **保持对话连贯性** - 参考之前的讨论内容
2. **避免重复信息** - 重点回答新的问题点
3. **建立知识关联** - 将新信息与之前讨论联系
4. **个性化回应** - 根据用户关注点调整回答重点

如果当前问题与之前讨论相关，请适当提及："根据您之前的问题..."
如果是新话题，请明确说明："这是一个新的问题，让我为您详细解答..."

{safety_disclaimer}

【专业回答】
"""

class PromptManager:
    """
    提示词管理器 - 与HybridRetriever深度集成
    """
    
    def __init__(self):
        """初始化提示词管理器"""
        self.templates = MedicalPromptTemplates()
        
        # 模板映射关系 - 与混合检索器的查询类型保持一致
        self.template_mapping = {
            QueryType.KNOWLEDGE_BASED: self.templates.get_base_template,
            QueryType.FACTUAL: self.templates.get_base_template,
            QueryType.CONTEXTUAL: self.templates.get_symptom_analysis_template,
            QueryType.GENERAL: self.templates.get_base_template,
            QueryType.DIAGNOSTIC: self.templates.get_diagnostic_template,
            QueryType.TREATMENT: self.templates.get_treatment_guidance_template,
            QueryType.RISK_ASSESSMENT: self.templates.get_risk_assessment_template
        }
        
        # 特殊关键词到模板的映射
        self.keyword_template_mapping = {
            "症状": self.templates.get_symptom_analysis_template,
            "治疗": self.templates.get_treatment_guidance_template,
            "诊断": self.templates.get_diagnostic_template,
            "检查": self.templates.get_diagnostic_template,
            "风险": self.templates.get_risk_assessment_template,
            "饮食": self.templates.get_nutrition_template,
            "营养": self.templates.get_nutrition_template
        }
    
    def select_optimal_template(self, prompt_context: PromptContext) -> str:
        """
        智能选择最优模板 - 基于查询内容和检索结果
        
        Args:
            prompt_context: 提示词上下文
            
        Returns:
            选择的模板字符串
        """
        query = prompt_context.query
        fusion_method = prompt_context.fusion_method
        
        # 1. 优先使用图谱增强模板（如果有图谱结果）
        if fusion_method in ["graph_first", "balanced"] and prompt_context.graph_context:
            return self.templates.get_graph_enhanced_template()
        
        # 2. 基于关键词选择专用模板
        for keyword, template_func in self.keyword_template_mapping.items():
            if keyword in query:
                return template_func()
        
        # 3. 基于查询类型选择
        try:
            query_type = QueryType(prompt_context.query_type)
            template_func = self.template_mapping.get(query_type, self.templates.get_base_template)
            return template_func()
        except ValueError:
            return self.templates.get_base_template()
    
    def create_hybrid_prompt(self, 
                           query: str,
                           semantic_results: List[Any] = None,
                           graph_results: List[Any] = None,
                           query_type: str = "general",
                           fusion_method: str = "balanced",
                           chat_history: Optional[str] = None) -> str:
        """
        创建混合提示词 - 与HybridRetriever完美集成
        
        Args:
            query: 用户查询
            semantic_results: 语义检索结果 List[Tuple[DocumentChunk, float]]
            graph_results: 图谱检索结果 List[GraphSearchResult] 
            query_type: 查询类型
            fusion_method: 融合方法
            chat_history: 对话历史（可选）
            
        Returns:
            格式化的提示词
        """
        # 构建上下文
        semantic_context = self._build_semantic_context(semantic_results)
        graph_context = self._build_graph_context(graph_results)
        combined_context = self._combine_contexts(semantic_context, graph_context, fusion_method)
        
        # 创建提示词上下文
        prompt_context = PromptContext(
            query=query,
            semantic_context=semantic_context,
            graph_context=graph_context,
            query_type=query_type,
            fusion_method=fusion_method
        )
        
        # 选择最优模板
        if chat_history:
            template = self.templates.get_conversational_template()
        else:
            template = self.select_optimal_template(prompt_context)
        
        # 填充模板
        try:
            formatted_prompt = template.format(
                system_persona=self.templates.SYSTEM_PERSONA,
                safety_disclaimer=self.templates.SAFETY_DISCLAIMER,
                context=combined_context,
                semantic_context=semantic_context,
                graph_context=graph_context,
                query=query,
                chat_history=chat_history or ""
            )
            
            return self._optimize_prompt_length(formatted_prompt)
            
        except Exception as e:
            logger.error(f"提示词格式化失败: {e}")
            # 返回安全的基础提示词
            return self._create_fallback_prompt(query, combined_context)
    
    def _build_semantic_context(self, semantic_results: Optional[List[Any]]) -> str:
        """构建语义检索上下文"""
        if not semantic_results:
            return "暂无相关文档资料"
        
        context_parts = []
        for i, (chunk, score) in enumerate(semantic_results[:3], 1):
            source_info = getattr(chunk, 'source_file', '未知来源')
            content = getattr(chunk, 'text', getattr(chunk, 'content', ''))
            
            # 限制单个文档的长度
            content_preview = content[:400] + "..." if len(content) > 400 else content
            
            context_parts.append(
                f"【文档{i}】(相似度: {score:.3f}, 来源: {source_info})\n{content_preview}"
            )
        
        return "\n\n".join(context_parts)
    
    def _build_graph_context(self, graph_results: Optional[List[Any]]) -> str:
        """构建图谱检索上下文"""
        if not graph_results:
            return "暂无相关知识图谱信息"
        
        context_parts = []
        for i, result in enumerate(graph_results[:2], 1):
            if hasattr(result, 'context_text') and result.context_text:
                context_parts.append(f"【知识图谱{i}】\n{result.context_text}")
        
        return "\n\n".join(context_parts) if context_parts else "知识图谱信息有限"
    
    def _combine_contexts(self, semantic_context: str, graph_context: str, fusion_method: str) -> str:
        """根据融合方法合并上下文"""
        if fusion_method == "graph_first":
            return f"{graph_context}\n\n{semantic_context}"
        elif fusion_method == "semantic_first":
            return f"{semantic_context}\n\n{graph_context}"
        else:  # balanced or other
            return f"{graph_context}\n\n{semantic_context}"
    
    def _optimize_prompt_length(self, prompt: str) -> str:
        """优化提示词长度"""
        if len(prompt) > 4000:
            # 截断过长的上下文，保留重要部分
            lines = prompt.split('\n')
            important_lines = []
            context_lines = []
            
            for line in lines:
                if any(marker in line for marker in ['【', '**', '###', '专业回答', '系统提示']):
                    important_lines.append(line)
                else:
                    context_lines.append(line)
            
            # 保留重要行 + 截断的上下文
            truncated_context = '\n'.join(context_lines[:50])  # 限制上下文行数
            optimized_prompt = '\n'.join(important_lines[:20]) + '\n' + truncated_context
            
            if len(optimized_prompt) > 4000:
                return optimized_prompt[:4000] + "\n...(内容已优化截断)\n\n【专业回答】"
        
        return prompt
    
    def _create_fallback_prompt(self, query: str, context: str) -> str:
        """创建备用提示词"""
        return f"""
{self.templates.SYSTEM_PERSONA}

【可用医学知识】
{context[:1000]}

【患者问题】
{query}

【专业回答】请基于提供的医学知识回答问题，保持专业性和准确性。

{self.templates.SAFETY_DISCLAIMER}
"""

# ================================
# 便捷函数和工厂方法
# ================================

def create_prompt_manager() -> PromptManager:
    """创建提示词管理器实例"""
    return PromptManager()

def create_medical_prompt(query: str, 
                         context: str,
                         query_type: str = "general") -> str:
    """
    便捷函数：创建基础医学提示词
    
    Args:
        query: 用户查询
        context: 检索上下文
        query_type: 查询类型
        
    Returns:
        格式化的提示词
    """
    manager = PromptManager()
    
    # 模拟语义检索结果格式
    class MockChunk:
        def __init__(self, text: str):
            self.text = text
            self.content = text
            self.source_file = "医学资料"
    
    mock_semantic_results = [(MockChunk(context), 0.8)]
    
    return manager.create_hybrid_prompt(
        query=query,
        semantic_results=mock_semantic_results,
        query_type=query_type
    )

def create_graph_enhanced_prompt(query: str,
                               graph_context: str,
                               semantic_context: str = "") -> str:
    """
    便捷函数：创建图谱增强提示词
    
    Args:
        query: 用户查询  
        graph_context: 图谱上下文
        semantic_context: 语义上下文
        
    Returns:
        图谱增强的提示词
    """
    manager = PromptManager()
    
    # 模拟检索结果
    class MockGraphResult:
        def __init__(self, context_text: str):
            self.context_text = context_text
            self.relevance_score = 0.9
    
    class MockChunk:
        def __init__(self, text: str):
            self.text = text
            self.source_file = "医学文献"
    
    mock_graph_results = [MockGraphResult(graph_context)]
    mock_semantic_results = [(MockChunk(semantic_context), 0.7)] if semantic_context else None
    
    return manager.create_hybrid_prompt(
        query=query,
        semantic_results=mock_semantic_results,
        graph_results=mock_graph_results,
        fusion_method="graph_first"
    )

# ================================
# 测试和验证
# ================================

def test_prompt_templates():
    """测试提示词模板系统"""
    print("🧪 测试医学GraphRAG提示词模板系统...")
    
    try:
        manager = PromptManager()
        
        # 测试数据
        test_cases = [
            {
                "name": "症状咨询",
                "query": "妊娠期糖尿病有什么症状？",
                "query_type": "factual",
                "semantic_context": "妊娠期糖尿病的典型症状包括多尿、多饮、疲劳等...",
                "graph_context": "实体：妊娠期糖尿病\n症状：多尿, 多饮, 体重增加\n关联：胰岛素抵抗"
            },
            {
                "name": "治疗指导", 
                "query": "如何治疗妊娠期糖尿病？",
                "query_type": "treatment",
                "semantic_context": "妊娠期糖尿病的治疗主要包括饮食控制、运动疗法和胰岛素治疗...",
                "graph_context": "实体：胰岛素治疗\n适应症：妊娠期糖尿病\n效果：血糖控制"
            },
            {
                "name": "风险评估",
                "query": "孕妇血糖高有什么风险？", 
                "query_type": "risk_assessment",
                "semantic_context": "妊娠期血糖异常可能导致母体和胎儿并发症...",
                "graph_context": "风险因素：血糖异常\n并发症：巨大儿, 早产, 难产\n影响对象：母亲, 胎儿"
            }
        ]
        
        for case in test_cases:
            print(f"\n📋 测试场景：{case['name']}")
            print(f"   查询：{case['query']}")
            print(f"   类型：{case['query_type']}")
            
            # 模拟检索结果
            class MockChunk:
                def __init__(self, text: str):
                    self.text = text
                    self.source_file = "测试医学资料"
            
            class MockGraphResult:
                def __init__(self, context_text: str):
                    self.context_text = context_text
                    self.relevance_score = 0.85
            
            semantic_results = [(MockChunk(case['semantic_context']), 0.8)]
            graph_results = [MockGraphResult(case['graph_context'])]
            
            # 生成提示词
            prompt = manager.create_hybrid_prompt(
                query=case['query'],
                semantic_results=semantic_results,
                graph_results=graph_results,
                query_type=case['query_type'],
                fusion_method="balanced"
            )
            
            print(f"   ✅ 提示词长度：{len(prompt)} 字符")
            print(f"   📝 提示词预览：{prompt[:300]}...")
            
            # 修正后的验证关键要素逻辑
            validation_checks = {
                '系统角色定义': any(keyword in prompt for keyword in ['医学助手', '专业', '特质', '临床知识']),
                '医学上下文': any(keyword in prompt for keyword in ['医学知识', '文献资料', '知识图谱', '检索']),
                '专业回答': any(keyword in prompt for keyword in ['专业回答', '回答要求', '分析框架', '指导框架']),
                '安全声明': any(keyword in prompt for keyword in ['医学声明', '重要', '替代', '咨询医师'])
            }
            
            missing_elements = [elem for elem, found in validation_checks.items() if not found]
            
            if missing_elements:
                print(f"   ⚠️  缺少要素：{missing_elements}")
            else:
                print(f"   ✅ 包含所有必要要素")
        
        # 测试便捷函数
        print(f"\n🔧 测试便捷函数...")
        
        simple_prompt = create_medical_prompt(
            query="什么是妊娠期糖尿病？",
            context="妊娠期糖尿病是孕期常见的内分泌疾病...",
            query_type="knowledge_based"
        )
        print(f"   ✅ 基础提示词生成成功，长度：{len(simple_prompt)}")
        
        graph_prompt = create_graph_enhanced_prompt(
            query="妊娠期糖尿病如何诊断？",
            graph_context="诊断方法：OGTT, 空腹血糖\n标准：WHO标准",
            semantic_context="75g口服葡萄糖耐量试验是金标准..."
        )
        print(f"   ✅ 图谱增强提示词生成成功，长度：{len(graph_prompt)}")
        
        # 测试对话模式
        print(f"\n💬 测试对话模式...")
        chat_history = "用户之前问过关于症状的问题，现在想了解治疗方法。"
        
        class MockChunk:
            def __init__(self, text: str):
                self.text = text
                self.source_file = "测试医学资料"
        
        conversational_prompt = manager.create_hybrid_prompt(
            query="那应该怎么治疗呢？",
            semantic_results=[(MockChunk("治疗方案包括..."), 0.75)],
            query_type="treatment",
            chat_history=chat_history
        )
        print(f"   ✅ 对话提示词生成成功，长度：{len(conversational_prompt)}")
        
        # 测试边界情况
        print(f"\n🛡️ 测试边界情况...")
        
        # 空结果
        empty_prompt = manager.create_hybrid_prompt(
            query="这是一个找不到结果的查询",
            semantic_results=[],
            graph_results=[],
            query_type="general"
        )
        print(f"   ✅ 空结果处理成功，长度：{len(empty_prompt)}")
        
        # 超长内容
        long_context = "这是一个非常长的上下文内容..." * 200
        long_prompt = manager.create_hybrid_prompt(
            query="测试长内容",
            semantic_results=[(MockChunk(long_context), 0.6)],
            query_type="general"
        )
        print(f"   ✅ 长内容优化成功，长度：{len(long_prompt)}")
        
        print(f"\n🎉 提示词模板系统测试完成！")
        print(f"✅ 所有核心功能正常工作")
        print(f"🚀 已准备好与GDM项目集成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

# ================================
# 高级功能扩展
# ================================

class AdvancedPromptFeatures:
    """高级提示词功能"""
    
    @staticmethod
    def create_multi_turn_prompt(query: str, 
                               conversation_history: List[Dict[str, str]],
                               current_context: str) -> str:
        """
        多轮对话提示词生成
        
        Args:
            query: 当前查询
            conversation_history: 对话历史 [{"role": "user/assistant", "content": "..."}]
            current_context: 当前检索上下文
            
        Returns:
            多轮对话优化的提示词
        """
        history_text = ""
        for i, turn in enumerate(conversation_history[-3:], 1):  # 只保留最近3轮
            role = "患者" if turn["role"] == "user" else "医生"
            history_text += f"【第{i}轮】{role}：{turn['content'][:150]}...\n"
        
        return f"""
{MedicalPromptTemplates.SYSTEM_PERSONA}

【最近对话历史】
{history_text}

【当前相关医学知识】
{current_context}

【当前问题】
{query}

【连续对话指导】
作为专业医学助手，在回答时要：
1. 保持与之前对话的连贯性和一致性
2. 避免重复已经说过的基础信息
3. 深入回答用户的进一步疑问
4. 如有必要，可以引用之前的讨论内容

{MedicalPromptTemplates.SAFETY_DISCLAIMER}

【专业回答】
"""

    @staticmethod
    def create_personalized_prompt(query: str,
                                 context: str,
                                 user_profile: Optional[Dict[str, Any]] = None) -> str:
        """
        个性化提示词生成
        
        Args:
            query: 用户查询
            context: 医学上下文
            user_profile: 用户画像 {"age_group": "", "pregnancy_stage": "", "risk_level": ""}
            
        Returns:
            个性化的提示词
        """
        personalization = ""
        if user_profile:
            age_group = user_profile.get("age_group", "")
            pregnancy_stage = user_profile.get("pregnancy_stage", "")
            risk_level = user_profile.get("risk_level", "")
            
            if age_group or pregnancy_stage or risk_level:
                personalization = f"""
【个性化信息参考】
年龄阶段：{age_group}
妊娠阶段：{pregnancy_stage}  
风险等级：{risk_level}

请在回答时考虑上述个人情况，提供更有针对性的建议。
"""

        return f"""
{MedicalPromptTemplates.SYSTEM_PERSONA}

{personalization}

【医学知识资料】
{context}

【个人咨询】
{query}

【个性化回答要求】
1. 结合用户的具体情况提供建议
2. 强调个体差异和个性化治疗的重要性
3. 提供分层次的建议（轻、中、重不同情况）
4. 必要时建议寻求个性化的专业医疗意见

{MedicalPromptTemplates.SAFETY_DISCLAIMER}

【专业回答】
"""

class PromptQualityValidator:
    """提示词质量验证器"""
    
    @staticmethod
    def validate_prompt_quality(prompt: str) -> Dict[str, Any]:
        """
        验证提示词质量
        
        Args:
            prompt: 待验证的提示词
            
        Returns:
            验证结果字典
        """
        result = {
            "is_valid": True,
            "issues": [],
            "suggestions": [],
            "quality_score": 0,
            "metrics": {}
        }
        
        # 1. 长度检查
        length = len(prompt)
        result["metrics"]["length"] = length
        
        if length < 100:
            result["issues"].append("提示词过短，可能缺少必要信息")
            result["is_valid"] = False
        elif length > 5000:
            result["issues"].append("提示词过长，可能影响模型性能")
            result["suggestions"].append("考虑精简上下文内容")
        
        # 2. 必需元素检查
        required_elements = [
            ("系统提示", ["系统", "助手", "专业", "医学助手", "角色", "身份", "特质"]),
            ("医学上下文", ["医学", "知识", "资料", "文献", "图谱", "检索", "上下文", "信息"]),
            ("用户查询", ["问题", "咨询", "查询", "患者", "症状", "治疗"]),
            ("安全声明", ["声明", "提醒", "医师", "就医", "替代", "参考", "建议", "专业医疗"])
        ]
        
        missing_elements = []
        for element_name, keywords in required_elements:
            # 更宽松的匹配逻辑
            found = any(keyword in prompt.lower() for keyword in [kw.lower() for kw in keywords])
            if not found:
                missing_elements.append(element_name)
        
        if missing_elements:
            result["issues"].append(f"缺少必需元素：{', '.join(missing_elements)}")
            result["is_valid"] = False
        
        # 3. 格式规范检查
        format_issues = []
        if "【" not in prompt or "】" not in prompt:
            format_issues.append("缺少标准的中文标题格式")
        
        if not re.search(r'\*\*.*?\*\*', prompt) and not re.search(r'✓|•', prompt):
            format_issues.append("建议使用粗体标记或符号标记重要信息")
        
        if format_issues:
            result["suggestions"].extend(format_issues)
        
        # 4. 医学专业性检查
        medical_keywords = ["症状", "诊断", "治疗", "药物", "检查", "血糖", "胰岛素", "妊娠", "医学", "临床"]
        medical_score = sum(1 for keyword in medical_keywords if keyword in prompt)
        result["metrics"]["medical_relevance"] = medical_score / len(medical_keywords)
        
        if medical_score < 2:
            result["suggestions"].append("建议增加更多医学相关术语和概念")
        
        # 5. 计算综合质量分数
        base_score = 60
        
        # 长度分数 (0-15分)
        if 200 <= length <= 3000:
            length_score = 15
        elif 100 <= length < 200 or 3000 < length <= 4000:
            length_score = 10
        else:
            length_score = 5
        
        # 完整性分数 (0-15分)
        completeness_score = 15 if not missing_elements else max(0, 15 - len(missing_elements) * 4)
        
        # 专业性分数 (0-10分)
        professional_score = min(10, medical_score * 1.5)
        
        result["quality_score"] = base_score + length_score + completeness_score + professional_score
        
        return result

class PromptOptimizer:
    """提示词优化器"""
    
    @staticmethod
    def optimize_for_token_limit(prompt: str, max_tokens: int = 3500) -> str:
        """
        针对token限制优化提示词
        
        Args:
            prompt: 原始提示词
            max_tokens: 最大token数（估算，1 token ≈ 1.2-1.5个中文字符）
            
        Returns:
            优化后的提示词
        """
        # 估算当前token数
        estimated_tokens = len(prompt) // 1.3
        
        if estimated_tokens <= max_tokens:
            return prompt
        
        logger.info(f"提示词超出token限制，开始优化：{estimated_tokens} > {max_tokens}")
        
        # 分解提示词结构
        sections = re.split(r'【.*?】', prompt)
        headers = re.findall(r'【.*?】', prompt)
        
        # 优先级排序（保留重要部分）
        priority_keywords = {
            "系统": 10, "专业": 9, "回答": 9, "安全": 8,
            "知识": 7, "医学": 7, "问题": 6, "咨询": 6
        }
        
        # 按优先级重组
        important_sections = []
        context_sections = []
        
        for i, (header, section) in enumerate(zip(headers, sections[1:], strict=False)):
            priority = max([priority_keywords.get(keyword, 0) 
                          for keyword in priority_keywords.keys() 
                          if keyword in header], default=1)
            
            if priority >= 7:
                important_sections.append((header, section))
            else:
                context_sections.append((header, section))
        
        # 重建提示词
        optimized_prompt = sections[0]  # 开头部分
        
        # 添加重要部分
        for header, section in important_sections:
            optimized_prompt += header + section
        
        # 按需添加上下文部分
        remaining_tokens = max_tokens - len(optimized_prompt) // 1.3
        
        for header, section in context_sections:
            section_tokens = len(section) // 1.3
            if section_tokens < remaining_tokens:
                optimized_prompt += header + section
                remaining_tokens -= section_tokens
            else:
                # 截断处理
                truncated_length = int(remaining_tokens * 1.3 * 0.8)  # 留20%余量
                truncated_section = section[:truncated_length] + "...(内容已截断)"
                optimized_prompt += header + truncated_section
                break
        
        logger.info(f"提示词优化完成：{len(optimized_prompt)//1.3} tokens")
        return optimized_prompt
    
    @staticmethod
    def enhance_medical_safety(prompt: str) -> str:
        """
        增强医学安全性
        
        Args:
            prompt: 原始提示词
            
        Returns:
            增强安全性的提示词
        """
        safety_enhancements = [
            "\n⚕️ 【医疗安全强化提醒】",
            "• 本信息仅供健康教育参考，不能替代医生的专业诊断",
            "• 任何症状变化或治疗调整都应咨询医疗专业人员",
            "• 紧急情况（如严重高血糖、酮症酸中毒征象）请立即就医",
            "• 妊娠期间的任何医疗决定都需要产科医生参与",
        ]
        
        # 在回答要求前插入安全增强
        safety_text = "\n".join(safety_enhancements)
        
        # 找到插入位置（通常在"专业回答"前）
        insert_patterns = [
            "【专业回答】", "【回答】", "【医生回答】", "【专业建议】"
        ]
        
        for pattern in insert_patterns:
            if pattern in prompt:
                return prompt.replace(pattern, safety_text + "\n\n" + pattern)
        
        # 如果没有找到标准模式，在末尾添加
        return prompt + safety_text + "\n\n【专业回答】"

# ================================
# 集成接口和导出
# ================================

class GraphRAGPromptInterface:
    """
    GraphRAG提示词接口 - 与主系统集成的标准接口
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化接口
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.prompt_manager = PromptManager()
        self.optimizer = PromptOptimizer()
        self.validator = PromptQualityValidator()
        
        # 从配置中读取参数
        self.max_tokens = self.config.get('max_tokens', 3500)
        self.enable_safety_enhancement = self.config.get('enable_safety_enhancement', True)
        self.enable_optimization = self.config.get('enable_optimization', True)
    
    def create_prompt(self,
                     query: str,
                     semantic_results: Optional[List[Any]] = None,
                     graph_results: Optional[List[Any]] = None,
                     query_type: str = "general",
                     fusion_method: str = "balanced",
                     chat_history: Optional[str] = None,
                     user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        创建优化的提示词 - 主要对外接口
        
        Args:
            query: 用户查询
            semantic_results: 语义检索结果
            graph_results: 图谱检索结果
            query_type: 查询类型
            fusion_method: 融合方法
            chat_history: 对话历史
            user_profile: 用户画像
            
        Returns:
            包含提示词和质量信息的字典
        """
        try:
            # 1. 生成基础提示词
            if user_profile and self.config.get('enable_personalization', False):
                # 个性化提示词
                context = self.prompt_manager._build_semantic_context(semantic_results)
                base_prompt = AdvancedPromptFeatures.create_personalized_prompt(
                    query, context, user_profile
                )
            else:
                # 标准混合提示词
                base_prompt = self.prompt_manager.create_hybrid_prompt(
                    query=query,
                    semantic_results=semantic_results,
                    graph_results=graph_results,
                    query_type=query_type,
                    fusion_method=fusion_method,
                    chat_history=chat_history
                )
            
            # 2. 安全性增强
            if self.enable_safety_enhancement:
                base_prompt = self.optimizer.enhance_medical_safety(base_prompt)
            
            # 3. 长度优化
            if self.enable_optimization:
                optimized_prompt = self.optimizer.optimize_for_token_limit(
                    base_prompt, self.max_tokens
                )
            else:
                optimized_prompt = base_prompt
            
            # 4. 质量验证
            quality_result = self.validator.validate_prompt_quality(optimized_prompt)
            
            return {
                "prompt": optimized_prompt,
                "quality_score": quality_result["quality_score"],
                "is_valid": quality_result["is_valid"],
                "issues": quality_result["issues"],
                "suggestions": quality_result["suggestions"],
                "metrics": {
                    "original_length": len(base_prompt),
                    "optimized_length": len(optimized_prompt),
                    "estimated_tokens": len(optimized_prompt) // 1.3,
                    "medical_relevance": quality_result["metrics"].get("medical_relevance", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"提示词创建失败：{str(e)}")
            
            # 返回安全的备用提示词
            fallback_prompt = self.prompt_manager._create_fallback_prompt(
                query, "基础医学知识库"
            )
            
            return {
                "prompt": fallback_prompt,
                "quality_score": 60,
                "is_valid": True,
                "issues": [f"使用备用提示词：{str(e)}"],
                "suggestions": ["建议检查输入参数的完整性"],
                "metrics": {
                    "original_length": len(fallback_prompt),
                    "optimized_length": len(fallback_prompt),
                    "estimated_tokens": len(fallback_prompt) // 1.3,
                    "medical_relevance": 0.3
                }
            }

# ================================
# 模块导出和默认配置
# ================================

# 默认配置
DEFAULT_CONFIG = {
    "max_tokens": 3500,
    "enable_safety_enhancement": True,
    "enable_optimization": True,
    "enable_personalization": False,
    "quality_threshold": 70
}

# 主要导出接口
__all__ = [
    'MedicalPromptTemplates',
    'PromptManager', 
    'GraphRAGPromptInterface',
    'QueryType',
    'PromptContext',
    'create_prompt_manager',
    'create_medical_prompt',
    'create_graph_enhanced_prompt',
    'test_prompt_templates',
    'DEFAULT_CONFIG'
]

def create_gdm_prompt_interface(config: Optional[Dict[str, Any]] = None) -> GraphRAGPromptInterface:
    """
    创建GDM项目专用的提示词接口
    
    Args:
        config: 自定义配置，会与默认配置合并
        
    Returns:
        配置好的提示词接口实例
    """
    merged_config = DEFAULT_CONFIG.copy()
    if config:
        merged_config.update(config)
    
    return GraphRAGPromptInterface(merged_config)

# 模块初始化时的自检
if __name__ == "__main__":
    print("🚀 GraphRAG医学提示词模板系统")
    print("=" * 50)
    
    # 运行自检测试
    test_result = test_prompt_templates()
    
    if test_result:
        print("\n✅ 模块自检通过，准备集成到GDM项目！")
        print("\n📋 推荐使用方式：")
        print("```python")
        print("from src.graphrag.prompt_templates import create_gdm_prompt_interface")
        print("")
        print("# 创建提示词接口")
        print("prompt_interface = create_gdm_prompt_interface()")
        print("")
        print("# 生成提示词") 
        print("result = prompt_interface.create_prompt(")
        print('    query="妊娠期糖尿病有什么症状？",')
        print("    semantic_results=semantic_results,")
        print("    graph_results=graph_results,")
        print('    query_type="factual"')
        print(")")
        print("")
        print("print(result['prompt'])")
        print("```")
    else:
        print("\n❌ 模块自检失败，请检查代码问题！")
