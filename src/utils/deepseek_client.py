import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from openai import OpenAI
import hashlib
import time
from datetime import datetime

# 获取项目根目录的绝对路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# 确保日志目录存在
os.makedirs(LOGS_DIR, exist_ok=True)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, "deepseek_api.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("deepseek_client")

class DeepSeekClient:
    """DeepSeek API客户端"""
    
    def __init__(self, api_key: str = "sk-f73a7b96600a4eeebe34cbe357902568"):
        """初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥，如果为None则从环境变量获取
        """
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未提供，请设置DEEPSEEK_API_KEY环境变量或直接传入api_key")
        
        # 初始化OpenAI客户端，使用DeepSeek的API地址
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
        
        # 确保缓存目录存在
        self.cache_dir = "models/knowledge/cache"
        self.incremental_dir = os.path.join(self.cache_dir, "incremental")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.incremental_dir, exist_ok=True)
        
        # 加载已处理文件的哈希记录
        self.processed_files_record = os.path.join(self.cache_dir, "processed_files.json")
        self.processed_files = self._load_processed_files()
        
        logger.info("DeepSeek客户端初始化完成")
    
    def _load_processed_files(self) -> Dict[str, str]:
        """加载已处理文件的哈希记录"""
        if os.path.exists(self.processed_files_record):
            try:
                with open(self.processed_files_record, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载已处理文件记录失败: {e}")
        return {}
    
    def _save_processed_files(self):
        """保存已处理文件的哈希记录"""
        try:
            with open(self.processed_files_record, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存已处理文件记录失败: {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return ""
    
    def _split_long_text(self, text: str, max_length: int = 8000, overlap: int = 500) -> List[str]:
        """将长文本分割成多个片段，保持语义完整性
        
        Args:
            text: 输入文本
            max_length: 每个片段的最大长度
            overlap: 片段间的重叠长度
            
        Returns:
            文本片段列表
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_length
            
            # 如果不是最后一个片段，尝试在句号、问号、感叹号处分割
            if end < len(text):
                # 寻找最近的句子结束符
                sentence_endings = ['.', '。', '!', '！', '?', '？', '\n\n']
                best_split = end
                
                for i in range(end - 200, end + 200):
                    if i >= len(text):
                        break
                    if text[i] in sentence_endings:
                        best_split = i + 1
                        break
                
                end = best_split
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 设置下一个片段的起始位置，考虑重叠
            start = max(start + max_length - overlap, end)
            
            if start >= len(text):
                break
        
        logger.info(f"长文本已分割为 {len(chunks)} 个片段")
        return chunks
    
    def _merge_extraction_results(self, results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并多个提取结果
        
        Args:
            results_list: 提取结果列表
            
        Returns:
            合并后的结果
        """
        merged_entities = []
        merged_relations = []
        entity_dedup = set()  # 用于去重
        relation_dedup = set()
        
        for result in results_list:
            # 合并实体，去重
            for entity in result.get('entities', []):
                entity_key = f"{entity.get('entity', '')}-{entity.get('type', '')}"
                if entity_key not in entity_dedup and entity.get('entity'):
                    entity_dedup.add(entity_key)
                    merged_entities.append(entity)
            
            # 合并关系，去重
            for relation in result.get('relations', []):
                relation_key = f"{relation.get('subject', '')}-{relation.get('predicate', '')}-{relation.get('object', '')}"
                if relation_key not in relation_dedup and all([relation.get('subject'), relation.get('predicate'), relation.get('object')]):
                    relation_dedup.add(relation_key)
                    merged_relations.append(relation)
        
        return {
            'entities': merged_entities,
            'relations': merged_relations
        }

    def chat_completion(self, 
                       messages: List[Dict[str, str]], 
                       model: str = "deepseek-chat", 
                       temperature: float = 0.7,
                       max_tokens: int = 1000) -> Dict[str, Any]:
        """调用DeepSeek聊天补全API
        
        Args:
            messages: 消息列表，格式为[{"role": "user", "content": "你好"}]
            model: 模型名称
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数
            
        Returns:
            API响应结果
        """
        try:
            logger.info(f"发送请求到DeepSeek API: {model}, temperature={temperature}")
            
            # 使用OpenAI客户端调用API
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 转换为字典格式，与原代码兼容
            result = {
                "choices": [
                    {
                        "message": {
                            "content": response.choices[0].message.content
                        }
                    }
                ],
                "model": response.model,
                "id": response.id,
                "usage": {
                    "total_tokens": response.usage.total_tokens
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"API请求失败: {str(e)}")
            raise Exception(f"DeepSeek API请求失败: {str(e)}")
    
    def _create_enhanced_entity_prompt(self, text: str, context: str = "") -> str:
        """创建增强的实体提取prompt"""
        base_prompt = f"""请从以下与妊娠期糖尿病相关的医学文本中提取关键实体。

请严格按照以下实体类型分类：
1. MedicalConcept: 医学概念（如血糖控制、糖代谢、胰岛素抵抗等）
2. Disease: 疾病名称（如妊娠期糖尿病、2型糖尿病、妊高症等）
3. Symptom: 临床症状（如多饮、多尿、体重增加等）
4. RiskFactor: 风险因素（如高龄产妇、肥胖、糖尿病家族史等）
5. DiagnosticMethod: 诊断方法（如OGTT、空腹血糖、糖化血红蛋白等）
6. Treatment: 治疗方法（如胰岛素治疗、饮食控制、运动疗法等）
7. Complication: 并发症（如巨大儿、新生儿低血糖、产后出血等）
8. Food: 食物类型（如全麦面包、低脂牛奶、高纤维食物等）
9. Guideline: 医学指南（如ADA指南、ACOG推荐、中华医学会指南等）
10. Question: 常见问题（患者或医生可能提出的问题）

提取要求：
- 确保每个实体都有明确的医学含义
- 避免提取过于宽泛或模糊的概念
- 优先提取与妊娠期糖尿病直接相关的实体
- 对于Complication类型，必须标明影响对象（母亲/胎儿/新生儿）
- 对于Food类型，尽可能包含血糖指数相关信息

以JSON格式返回，格式严格如下：
[
  {{
    "entity": "具体实体名称",
    "type": "上述10种类型之一",
    "description": "简洁准确的医学描述",
    "attributes": {{
      // 根据实体类型选择性添加以下属性：
      "icd_code": "ICD-10编码（仅Disease类型）",
      "modifiable": true/false, // 是否可改变（仅RiskFactor类型）
      "normal_range": "正常参考范围（仅DiagnosticMethod类型）",
      "type": "治疗类型（仅Treatment类型）",
      "target": "影响对象（仅Complication类型）",
      "glycemic_index": "血糖指数（仅Food类型）",
      "organization": "发布组织（仅Guideline类型）",
      "confidence": "high/medium/low" // 提取置信度
    }}
  }}
]"""

        if context:
            base_prompt += f"\n\n上下文信息：{context}\n"
        
        base_prompt += f"\n\n文本内容：\n{text}\n\n请仅返回标准JSON格式，确保JSON格式正确且可解析。"
        
        return base_prompt
    
    def _create_enhanced_relation_prompt(self, text: str, entities: List[Dict] = None) -> str:
        """创建增强的关系提取prompt"""
        base_prompt = f"""请从以下医学文本中提取实体间的语义关系，形成医学知识三元组。

请严格按照以下关系类型分类：
1. IS_A: 概念分类关系（如：妊娠期糖尿病 IS_A 内分泌疾病）
2. HAS_SYMPTOM: 疾病症状关系（如：妊娠期糖尿病 HAS_SYMPTOM 多尿）
3. HAS_RISK_FACTOR: 风险因素关系（如：妊娠期糖尿病 HAS_RISK_FACTOR 高龄产妇）
4. DIAGNOSED_BY: 诊断方法关系（如：妊娠期糖尿病 DIAGNOSED_BY OGTT）
5. TREATED_BY: 治疗方法关系（如：妊娠期糖尿病 TREATED_BY 胰岛素治疗）
6. CAN_CAUSE: 因果关系（如：妊娠期糖尿病 CAN_CAUSE 巨大儿）
7. RECOMMENDED_FOR: 推荐关系（如：低GI食物 RECOMMENDED_FOR 妊娠期糖尿病）
8. CONTRAINDICATED_FOR: 禁忌关系（如：高糖食物 CONTRAINDICATED_FOR 妊娠期糖尿病）
9. RECOMMENDS: 指南推荐（如：ADA指南 RECOMMENDS 产后筛查）
10. ANSWERS: 问答关系（如：饮食控制 ANSWERS "如何管理血糖"）

提取要求：
- 确保关系在文本中有明确支撑
- 优先提取临床意义重大的关系
- 避免提取过于显而易见或无意义的关系
- 确保主体和客体都是有意义的医学实体

以JSON格式返回：
[
  {{
    "subject": "主体实体名称",
    "predicate": "上述10种关系类型之一", 
    "object": "客体实体名称",
    "attributes": {{
      "evidence": "支撑该关系的文本片段",
      "confidence": "high/medium/low",
      "strength": "strong/moderate/weak", // 关系强度
      "source": "信息来源"
    }}
  }}
]"""

        if entities:
            entity_names = [e.get('entity', '') for e in entities if e.get('entity')]
            if entity_names:
                base_prompt += f"\n\n可参考的实体：{', '.join(entity_names[:20])}等"
        
        base_prompt += f"\n\n文本内容：\n{text}\n\n请仅返回标准JSON格式。"
        
        return base_prompt
    
    def _robust_json_parse(self, json_str: str, expected_type: str = "list") -> Any:
        """健壮的JSON解析方法"""
        try:
            # 清理JSON字符串
            json_str = json_str.strip()
            
            # 提取JSON部分
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].strip()
            
            # 尝试直接解析
            try:
                result = json.loads(json_str)
                if expected_type == "list" and isinstance(result, list):
                    return result
                elif expected_type == "dict" and isinstance(result, dict):
                    return result
                else:
                    logger.warning(f"JSON解析结果类型不匹配，期望{expected_type}，实际{type(result)}")
                    return [] if expected_type == "list" else {}
            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败，尝试修复: {str(e)}")
                
                # 尝试修复常见的JSON问题
                fixed_json = self._fix_json_string(json_str)
                
                try:
                    result = json.loads(fixed_json)
                    logger.info("JSON修复成功")
                    return result if isinstance(result, (list, dict)) else ([] if expected_type == "list" else {})
                except:
                    logger.warning("JSON修复失败，尝试正则提取")
                    return self._extract_json_objects(json_str, expected_type)
                    
        except Exception as e:
            logger.error(f"JSON解析完全失败: {str(e)}")
            return [] if expected_type == "list" else {}
    
    def _fix_json_string(self, json_str: str) -> str:
        """修复常见的JSON格式问题"""
        # 移除多余的逗号
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # 修复未闭合的括号
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')
        if open_brackets > close_brackets:
            json_str += ']' * (open_brackets - close_brackets)
        
        # 修复未闭合的引号（简单处理）
        quote_count = json_str.count('"')
        if quote_count % 2 == 1:
            json_str += '"'
        
        return json_str
    
    def _extract_json_objects(self, text: str, expected_type: str) -> Any:
        """使用正则表达式提取JSON对象"""
        if expected_type == "list":
            # 尝试提取JSON对象
            pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(pattern, text)
            
            objects = []
            for match in matches:
                try:
                    obj = json.loads(match)
                    objects.append(obj)
                except:
                    continue
            
            return objects
        
        return {} if expected_type == "dict" else []
    
    def _quality_check_entities(self, entities: List[Dict]) -> Tuple[List[Dict], Dict]:
        """对提取的实体进行质量检查"""
        valid_entities = []
        quality_issues = {
            "missing_required_fields": 0,
            "invalid_entity_types": 0,
            "duplicate_entities": 0,
            "low_quality_descriptions": 0
        }
        
        valid_entity_types = {
            "MedicalConcept", "Disease", "Symptom", "RiskFactor", 
            "DiagnosticMethod", "Treatment", "Complication", 
            "Food", "Guideline", "Question"
        }
        
        seen_entities = set()
        
        for entity in entities:
            # 检查必需字段
            if not all(key in entity for key in ["entity", "type", "description"]):
                quality_issues["missing_required_fields"] += 1
                continue
            
            # 检查实体类型有效性
            if entity["type"] not in valid_entity_types:
                quality_issues["invalid_entity_types"] += 1
                continue
            
            # 检查重复实体
            entity_key = f"{entity['entity']}-{entity['type']}"
            if entity_key in seen_entities:
                quality_issues["duplicate_entities"] += 1
                continue
            
            seen_entities.add(entity_key)
            
            # 检查描述质量
            if len(entity["description"]) < 10:
                quality_issues["low_quality_descriptions"] += 1
                # 但仍保留该实体
            
            valid_entities.append(entity)
        
        return valid_entities, quality_issues
    
    def _quality_check_relations(self, relations: List[Dict]) -> Tuple[List[Dict], Dict]:
        """对提取的关系进行质量检查"""
        valid_relations = []
        quality_issues = {
            "missing_required_fields": 0,
            "invalid_relation_types": 0,
            "duplicate_relations": 0,
            "self_relations": 0
        }
        
        valid_relation_types = {
            "IS_A", "HAS_SYMPTOM", "HAS_RISK_FACTOR", "DIAGNOSED_BY",
            "TREATED_BY", "CAN_CAUSE", "RECOMMENDED_FOR", 
            "CONTRAINDICATED_FOR", "RECOMMENDS", "ANSWERS"
        }
        
        seen_relations = set()
        
        for relation in relations:
            # 检查必需字段
            if not all(key in relation for key in ["subject", "predicate", "object"]):
                quality_issues["missing_required_fields"] += 1
                continue
            
            # 检查关系类型有效性
            if relation["predicate"] not in valid_relation_types:
                quality_issues["invalid_relation_types"] += 1
                continue
            
            # 检查自指关系
            if relation["subject"] == relation["object"]:
                quality_issues["self_relations"] += 1
                continue
            
            # 检查重复关系
            relation_key = f"{relation['subject']}-{relation['predicate']}-{relation['object']}"
            if relation_key in seen_relations:
                quality_issues["duplicate_relations"] += 1
                continue
            
            seen_relations.add(relation_key)
            valid_relations.append(relation)
        
        return valid_relations, quality_issues
    
    def _handle_zero_extraction(self, text: str, extraction_type: str) -> List[Dict]:
        """处理零提取情况的特殊逻辑"""
        logger.warning(f"检测到零提取情况 - {extraction_type}")
        
        # 简化的提取策略
        if extraction_type == "entities":
            simplified_prompt = f"""从以下文本中提取3-5个最重要的医学概念，以JSON格式返回：
[{{"entity": "概念名", "type": "MedicalConcept", "description": "简短描述"}}]

文本：{text[:2000]}"""

        else:  # relations
            simplified_prompt = f"""从以下文本中提取2-3个最明显的医学关系，以JSON格式返回：
[{{"subject": "主体", "predicate": "IS_A", "object": "客体"}}]

文本：{text[:2000]}"""
        
        try:
            messages = [{"role": "user", "content": simplified_prompt}]
            response = self.chat_completion(messages, temperature=0.3, max_tokens=800)
            content = response["choices"][0]["message"]["content"]
            
            result = self._robust_json_parse(content, "list")
            logger.info(f"简化提取获得 {len(result)} 个{extraction_type}")
            return result
            
        except Exception as e:
            logger.error(f"简化提取也失败: {str(e)}")
            return []

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取实体（支持长文本处理和质量检查）"""
        
        # 长文本处理
        if len(text) > 8000:
            logger.info(f"文本过长({len(text)}字符)，进行分片处理")
            chunks = self._split_long_text(text)
            
            all_results = []
            for i, chunk in enumerate(chunks):
                logger.info(f"处理第 {i+1}/{len(chunks)} 个片段")
                chunk_result = self._extract_entities_single_chunk(chunk)
                if chunk_result:
                    all_results.append({"entities": chunk_result})
                
                # 添加延迟避免API频率限制
                if i < len(chunks) - 1:
                    time.sleep(1)
            
            # 合并结果
            merged_result = self._merge_extraction_results(all_results)
            entities = merged_result["entities"]
        else:
            entities = self._extract_entities_single_chunk(text)
        
        # 质量检查
        valid_entities, quality_issues = self._quality_check_entities(entities)
        
        # 记录质量问题
        if quality_issues:
            logger.warning(f"实体提取质量问题: {quality_issues}")
        
        # 零提取特殊处理
        if not valid_entities and len(text) > 100:
            logger.warning("实体提取结果为空，尝试简化提取")
            fallback_entities = self._handle_zero_extraction(text, "entities")
            valid_entities, _ = self._quality_check_entities(fallback_entities)
        
        logger.info(f"最终提取了 {len(valid_entities)} 个有效实体")
        return valid_entities
    
    def _extract_entities_single_chunk(self, text: str) -> List[Dict[str, Any]]:
        """从单个文本片段中提取实体"""
        prompt = self._create_enhanced_entity_prompt(text)
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.chat_completion(messages, temperature=0.1, max_tokens=2000)
            content = response["choices"][0]["message"]["content"]
            entities = self._robust_json_parse(content, "list")
            return entities
            
        except Exception as e:
            logger.error(f"单片段实体提取失败: {str(e)}")
            return []
    
    def extract_relations(self, text: str, entities: List[Dict] = None) -> List[Dict[str, Any]]:
        """从文本中提取关系（支持长文本处理和质量检查）"""
        
        # 长文本处理
        if len(text) > 8000:
            logger.info(f"关系提取: 文本过长({len(text)}字符)，进行分片处理")
            chunks = self._split_long_text(text)
            
            all_results = []
            for i, chunk in enumerate(chunks):
                logger.info(f"处理关系提取第 {i+1}/{len(chunks)} 个片段")
                chunk_result = self._extract_relations_single_chunk(chunk, entities)
                if chunk_result:
                    all_results.append({"relations": chunk_result})
                
                # 添加延迟避免API频率限制
                if i < len(chunks) - 1:
                    time.sleep(1)
            
            # 合并结果
            merged_result = self._merge_extraction_results(all_results)
            relations = merged_result["relations"]
        else:
            relations = self._extract_relations_single_chunk(text, entities)
        
        # 质量检查
        valid_relations, quality_issues = self._quality_check_relations(relations)
        
        # 记录质量问题
        if quality_issues:
            logger.warning(f"关系提取质量问题: {quality_issues}")
        
        # 零提取特殊处理
        if not valid_relations and len(text) > 100:
            logger.warning("关系提取结果为空，尝试简化提取")
            fallback_relations = self._handle_zero_extraction(text, "relations")
            valid_relations, _ = self._quality_check_relations(fallback_relations)
        
        logger.info(f"最终提取了 {len(valid_relations)} 个有效关系")
        return valid_relations
    
    def _extract_relations_single_chunk(self, text: str, entities: List[Dict] = None) -> List[Dict[str, Any]]:
        """从单个文本片段中提取关系"""
        prompt = self._create_enhanced_relation_prompt(text, entities)
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = self.chat_completion(messages, temperature=0.1, max_tokens=2000)
            content = response["choices"][0]["message"]["content"]
            relations = self._robust_json_parse(content, "list")
            return relations
            
        except Exception as e:
            logger.error(f"单片段关系提取失败: {str(e)}")
            return []

    def answer_medical_question(self, question: str, context: str = "") -> str:
        """回答妊娠期糖尿病相关的医学问题
        
        Args:
            question: 医学问题
            context: 提供的上下文信息
            
        Returns:
            回答
        """
        if context:
            prompt = f"""作为妊娠期糖尿病领域的专家，请根据以下上下文信息回答问题。
            
            上下文信息:
            {context}
            
            问题: {question}
            
            请提供简洁专业的回答，确保医学信息准确可靠。可引用权威的妊娠期糖尿病指南(如ADA、ACOG或中国妇产科学会指南等)。
            """
        else:
            prompt = f"""作为妊娠期糖尿病领域的专家，请回答以下问题:
            
            问题: {question}
            
            请提供简洁专业的回答，确保医学信息准确可靠。引用权威的妊娠期糖尿病指南。如果无法确定答案，请明确说明，不要提供不确定的信息。
            """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            logger.info(f"回答医学问题: {question[:100]}...")
            response = self.chat_completion(messages, temperature=0.3)
            answer = response["choices"][0]["message"]["content"]
            return answer
        except Exception as e:
            logger.error(f"回答问题失败: {str(e)}")
            return f"抱歉，处理您的问题时出现错误: {str(e)}"
    
    def evaluate_extraction_quality(self, entities: List[Dict], relations: List[Dict], 
                                   entity_quality_issues: Dict = None, 
                                   relation_quality_issues: Dict = None) -> Dict[str, Any]:
        """评估提取结果的质量（增强版）
    
        Args:
            entities: 提取的实体列表
            relations: 提取的关系列表
            entity_quality_issues: 实体质量问题统计
            relation_quality_issues: 关系质量问题统计
        
        Returns:
            详细的评估结果
        """
        quality_metrics = {
            "timestamp": datetime.now().isoformat(),
            "entity_counts_by_type": {},
            "relation_counts_by_type": {},
            "entity_completeness": 0,
            "relation_completeness": 0,
            "overall_quality_score": 0,
            "quality_issues": {
                "entities": entity_quality_issues or {},
                "relations": relation_quality_issues or {}
            },
            "recommendations": []
        }
    
        # 统计不同类型实体数量
        for entity in entities:
            entity_type = entity.get("type", "unknown")
            if entity_type not in quality_metrics["entity_counts_by_type"]:
                quality_metrics["entity_counts_by_type"][entity_type] = 0
            quality_metrics["entity_counts_by_type"][entity_type] += 1
    
        # 统计不同类型关系数量
        for relation in relations:
            relation_type = relation.get("predicate", "unknown")
            if relation_type not in quality_metrics["relation_counts_by_type"]:
                quality_metrics["relation_counts_by_type"][relation_type] = 0
            quality_metrics["relation_counts_by_type"][relation_type] += 1
    
        # 计算实体属性完整度
        complete_entities = 0
        for entity in entities:
            if "entity" in entity and "type" in entity and "description" in entity:
                if "attributes" in entity and isinstance(entity["attributes"], dict):
                    complete_entities += 1
    
        if entities:
            quality_metrics["entity_completeness"] = round(complete_entities / len(entities), 2)
    
        # 计算关系属性完整度
        complete_relations = 0
        for relation in relations:
            if all(key in relation for key in ["subject", "predicate", "object"]):
                if "attributes" in relation and isinstance(relation["attributes"], dict):
                    complete_relations += 1
    
        if relations:
            quality_metrics["relation_completeness"] = round(complete_relations / len(relations), 2)
    
        # 计算整体质量分数
        entity_score = len(entities) * quality_metrics["entity_completeness"]
        relation_score = len(relations) * quality_metrics["relation_completeness"]
        total_score = entity_score + relation_score
        
        if entities or relations:
            quality_metrics["overall_quality_score"] = round(total_score / (len(entities) + len(relations)), 2)
        
        # 生成改进建议
        recommendations = []
        
        if quality_metrics["entity_completeness"] < 0.7:
            recommendations.append("建议改进实体属性完整度，补充更多实体特征信息")
        
        if quality_metrics["relation_completeness"] < 0.7:
            recommendations.append("建议改进关系属性完整度，添加更多关系上下文信息")
        
        if len(entities) < 5:
            recommendations.append("实体数量较少，建议检查文本内容或调整提取策略")
        
        if len(relations) < 3:
            recommendations.append("关系数量较少，建议优化关系提取prompt或检查文本质量")
        
        # 检查实体类型分布
        entity_types = set(quality_metrics["entity_counts_by_type"].keys())
        expected_types = {"Disease", "Symptom", "Treatment", "DiagnosticMethod"}
        missing_types = expected_types - entity_types
        if missing_types:
            recommendations.append(f"缺失重要实体类型：{', '.join(missing_types)}")
        
        quality_metrics["recommendations"] = recommendations
        
        return quality_metrics

    def _should_reprocess_file(self, file_path: str) -> bool:
        """判断文件是否需要重新处理（增量处理逻辑）"""
        file_hash = self._get_file_hash(file_path)
        if not file_hash:
            return True
        
        cached_hash = self.processed_files.get(file_path)
        if cached_hash != file_hash:
            logger.info(f"文件已修改，需要重新处理: {file_path}")
            return True
        
        # 检查缓存文件是否存在
        cache_file = self._get_cache_file_path(file_path)
        if not os.path.exists(cache_file):
            logger.info(f"缓存文件不存在，需要重新处理: {file_path}")
            return True
        
        logger.info(f"文件未修改，跳过处理: {file_path}")
        return False
    
    def _get_cache_file_path(self, file_path: str) -> str:
        """获取缓存文件路径"""
        file_name = os.path.basename(file_path)
        return os.path.join(self.cache_dir, f"{file_name}.json")
    
    def _load_cached_result(self, file_path: str) -> Optional[Dict[str, Any]]:
        """加载缓存的处理结果"""
        cache_file = self._get_cache_file_path(file_path)
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
                logger.info(f"成功加载缓存结果: {cache_file}")
                return result
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")
            return None
    
    def _save_incremental_result(self, file_path: str, result: Dict[str, Any]):
        """保存增量处理结果"""
        # 保存到主缓存
        cache_file = self._get_cache_file_path(file_path)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存主缓存失败: {e}")
        
        # 保存到增量缓存（按日期分组）
        date_str = datetime.now().strftime("%Y-%m-%d")
        incremental_file = os.path.join(self.incremental_dir, f"{date_str}.json")
        
        try:
            # 加载当天的增量数据
            daily_data = {}
            if os.path.exists(incremental_file):
                with open(incremental_file, 'r', encoding='utf-8') as f:
                    daily_data = json.load(f)
            
            # 添加新的处理结果
            daily_data[file_path] = {
                "timestamp": datetime.now().isoformat(),
                "entity_count": len(result.get("entities", [])),
                "relation_count": len(result.get("relations", [])),
                "quality_score": result.get("quality_metrics", {}).get("overall_quality_score", 0)
            }
            
            # 保存更新后的数据
            with open(incremental_file, 'w', encoding='utf-8') as f:
                json.dump(daily_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"增量结果已保存: {incremental_file}")
            
        except Exception as e:
            logger.error(f"保存增量缓存失败: {e}")

    def process_file(self, file_path: str, force_reprocess: bool = False) -> Dict[str, Any]:
        """处理单个文件，提取实体和关系（支持增量处理）
        
        Args:
            file_path: 文件路径
            force_reprocess: 是否强制重新处理
            
        Returns:
            包含实体和关系的字典
        """
        
        # 增量处理逻辑
        if not force_reprocess and not self._should_reprocess_file(file_path):
            cached_result = self._load_cached_result(file_path)
            if cached_result:
                return cached_result
        
        logger.info(f"开始处理文件: {file_path}")
        start_time = time.time()
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            
            if not text.strip():
                logger.warning(f"文件为空: {file_path}")
                return {
                    "entities": [],
                    "relations": [],
                    "error": "文件内容为空",
                    "quality_metrics": {}
                }
            
            # 提取实体
            logger.info("开始提取实体...")
            entities = self.extract_entities(text)
            
            # 提取关系（传入实体信息以提高关系提取质量）
            logger.info("开始提取关系...")
            relations = self.extract_relations(text, entities)
            
            # 评估质量
            logger.info("开始质量评估...")
            quality_metrics = self.evaluate_extraction_quality(entities, relations)
            
            # 计算处理时间
            processing_time = round(time.time() - start_time, 2)
            quality_metrics["processing_time_seconds"] = processing_time
            
            result = {
                "entities": entities,
                "relations": relations,
                "quality_metrics": quality_metrics,
                "source": file_path,
                "processed_at": datetime.now().isoformat(),
                "text_length": len(text)
            }
            
            # 保存结果
            self._save_incremental_result(file_path, result)
            
            # 更新已处理文件记录
            file_hash = self._get_file_hash(file_path)
            if file_hash:
                self.processed_files[file_path] = file_hash
                self._save_processed_files()
            
            logger.info(f"文件处理完成: {file_path}, 耗时: {processing_time}秒")
            logger.info(f"提取结果: {len(entities)}个实体, {len(relations)}个关系")
            
            return result
            
        except Exception as e:
            logger.error(f"处理文件 {file_path} 失败: {str(e)}")
            
            # 尝试保存已获取的部分结果
            error_result = {
                "entities": [],
                "relations": [],
                "error": str(e),
                "source": file_path,
                "processed_at": datetime.now().isoformat()
            }
            
            try:
                # 如果在某个步骤失败，保存已完成的部分
                if 'entities' in locals():
                    error_result["entities"] = entities
                if 'relations' in locals():
                    error_result["relations"] = relations
                if 'quality_metrics' in locals():
                    error_result["quality_metrics"] = quality_metrics
                
                self._save_incremental_result(file_path, error_result)
                logger.info(f"已保存错误结果到缓存")
                
            except Exception as inner_e:
                logger.error(f"保存错误结果也失败: {str(inner_e)}")
            
            return error_result
    
    def batch_process_files(self, file_paths: List[str], max_files: int = None) -> Dict[str, Any]:
        """批量处理文件
        
        Args:
            file_paths: 文件路径列表
            max_files: 最大处理文件数量限制
            
        Returns:
            批量处理结果统计
        """
        if max_files:
            file_paths = file_paths[:max_files]
        
        logger.info(f"开始批量处理 {len(file_paths)} 个文件")
        
        batch_results = {
            "total_files": len(file_paths),
            "processed_files": 0,
            "skipped_files": 0,
            "failed_files": 0,
            "total_entities": 0,
            "total_relations": 0,
            "processing_start": datetime.now().isoformat(),
            "file_results": {}
        }
        
        for i, file_path in enumerate(file_paths):
            logger.info(f"处理进度: {i+1}/{len(file_paths)} - {file_path}")
            
            try:
                result = self.process_file(file_path)
                
                if "error" in result:
                    batch_results["failed_files"] += 1
                else:
                    batch_results["processed_files"] += 1
                    batch_results["total_entities"] += len(result.get("entities", []))
                    batch_results["total_relations"] += len(result.get("relations", []))
                
                # 保存简化的文件结果
                batch_results["file_results"][file_path] = {
                    "status": "error" if "error" in result else "success",
                    "entity_count": len(result.get("entities", [])),
                    "relation_count": len(result.get("relations", [])),
                    "quality_score": result.get("quality_metrics", {}).get("overall_quality_score", 0)
                }
                
            except Exception as e:
                logger.error(f"批量处理文件失败: {file_path} - {str(e)}")
                batch_results["failed_files"] += 1
                batch_results["file_results"][file_path] = {
                    "status": "error",
                    "error": str(e)
                }
            
            # 添加处理间隔，避免API频率限制
            if i < len(file_paths) - 1:
                time.sleep(2)
        
        batch_results["processing_end"] = datetime.now().isoformat()
        
        # 保存批量处理报告
        report_file = os.path.join(self.cache_dir, f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(batch_results, f, ensure_ascii=False, indent=2)
            logger.info(f"批量处理报告已保存: {report_file}")
        except Exception as e:
            logger.error(f"保存批量处理报告失败: {e}")
        
        logger.info(f"批量处理完成: 成功{batch_results['processed_files']}个, 失败{batch_results['failed_files']}个")
        
        return batch_results

if __name__ == "__main__":
    # 确保目录存在
    os.makedirs("models/knowledge/cache", exist_ok=True)
    
    try:
        # 初始化客户端
        client = DeepSeekClient()
        
        # 处理项目中的所有数据源文件
        data_sources = [
            {"name": "FAQ", "path": "data/processed/faq"},
            {"name": "临床指南", "path": "data/processed/guidelines"},
            {"name": "PubMed文献", "path": "data/processed/pubmed"},
            {"name": "教科书资料", "path": "data/processed/textbooks"}
        ]
        
        all_files = []
        source_file_mapping = {}  # 记录每个文件属于哪个数据源
        
        # 收集所有数据源的文件
        for source in data_sources:
            files = list(Path(source["path"]).glob("**/*.txt"))
            if files:
                source_files = [str(f) for f in files]
                all_files.extend(source_files)
                
                # 记录文件与数据源的映射关系
                for file_path in source_files:
                    source_file_mapping[file_path] = source["name"]
                
                print(f"发现 {len(files)} 个{source['name']}文件")
            else:
                print(f"未找到{source['name']}文件 ({source['path']})")
        
        if all_files:
            print(f"\n总共发现 {len(all_files)} 个文件")
            
            # 按数据源分别进行单文件测试演示
            print("\n=== 各数据源单文件处理演示 ===")
            tested_sources = set()
            
            for file_path in all_files:
                source_name = source_file_mapping[file_path]
                
                # 每个数据源只测试一个文件
                if source_name not in tested_sources:
                    tested_sources.add(source_name)
                    
                    print(f"\n--- 测试{source_name}数据源 ---")
                    result = client.process_file(file_path)
                    
                    print(f"处理文件: {os.path.basename(file_path)}")
                    print(f"文件路径: {file_path}")
                    print(f"提取结果: {len(result['entities'])} 个实体, {len(result['relations'])} 个关系")
                    
                    # 打印质量评估结果
                    quality = result.get("quality_metrics", {})
                    print(f"质量评估:")
                    print(f"  - 整体质量分数: {quality.get('overall_quality_score', 0)}")
                    print(f"  - 实体属性完整度: {quality.get('entity_completeness', 0) * 100:.1f}%")
                    print(f"  - 关系属性完整度: {quality.get('relation_completeness', 0) * 100:.1f}%")
                    print(f"  - 处理时间: {quality.get('processing_time_seconds', 0)}秒")
                    
                    # 显示前3个实体示例
                    entities = result.get('entities', [])
                    if entities:
                        print(f"  实体示例 (前3个):")
                        for i, entity in enumerate(entities[:3]):
                            print(f"    {i+1}. {entity.get('entity', 'N/A')} ({entity.get('type', 'Unknown')})")
                    
                    # 显示前3个关系示例
                    relations = result.get('relations', [])
                    if relations:
                        print(f"  关系示例 (前3个):")
                        for i, relation in enumerate(relations[:3]):
                            print(f"    {i+1}. {relation.get('subject', 'N/A')} -> {relation.get('predicate', 'N/A')} -> {relation.get('object', 'N/A')}")
                    
                    # 如果已经测试了所有数据源，就退出
                    if len(tested_sources) == len(data_sources):
                        break
            
            # 混合批量处理演示（每个数据源选一个文件）
            print(f"\n=== 混合批量处理演示 ===")
            sample_files = []
            for source in data_sources:
                source_files = [f for f in all_files if source_file_mapping[f] == source["name"]]
                if source_files:
                    sample_files.append(source_files[0])  # 每个数据源选第一个文件
            
            if len(sample_files) > 1:
                print(f"选择 {len(sample_files)} 个不同数据源的文件进行批量处理:")
                for file_path in sample_files:
                    source_name = source_file_mapping[file_path]
                    print(f"  - {source_name}: {os.path.basename(file_path)}")
                
                batch_result = client.batch_process_files(sample_files)
                
                print(f"\n批量处理结果:")
                print(f"  - 总文件数: {batch_result['total_files']}")
                print(f"  - 成功处理: {batch_result['processed_files']}")
                print(f"  - 处理失败: {batch_result['failed_files']}")
                print(f"  - 总提取实体: {batch_result['total_entities']}")
                print(f"  - 总提取关系: {batch_result['total_relations']}")
                
                # 显示各文件的处理结果
                print(f"\n各文件处理详情:")
                for file_path, file_result in batch_result['file_results'].items():
                    source_name = source_file_mapping[file_path]
                    status = file_result['status']
                    print(f"  {source_name} - {os.path.basename(file_path)}: {status}")
                    if status == 'success':
                        print(f"    实体: {file_result['entity_count']}, 关系: {file_result['relation_count']}, 质量: {file_result['quality_score']}")
            
            # 数据源统计总结
            print(f"\n=== 数据源统计总结 ===")
            source_stats = {}
            for file_path in all_files:
                source_name = source_file_mapping[file_path]
                if source_name not in source_stats:
                    source_stats[source_name] = 0
                source_stats[source_name] += 1
            
            for source_name, count in source_stats.items():
                print(f"{source_name}: {count} 个文件")
        
        else:
            print("未找到任何文件进行处理")
        
        print("\n=== DeepSeek API客户端增强版测试完成！===")
        print("\n新增功能:")
        print("✓ 长文本自动分片处理")
        print("✓ 增强的实体和关系提取prompt")
        print("✓ 完善的质量检查机制")
        print("✓ 增量处理和缓存机制") 
        print("✓ 零提取特殊处理逻辑")
        print("✓ 批量处理支持")
        print("✓ 多数据源全面测试")
        
    except Exception as e:
        logger.error(f"运行测试时出错: {str(e)}", exc_info=True)
        print(f"错误: {str(e)}")
        print("请检查API密钥是否正确设置，可以通过以下方式设置:")
        print("  Windows (PowerShell): $env:DEEPSEEK_API_KEY='your-api-key'")
        print("  Linux/Mac: export DEEPSEEK_API_KEY='your-api-key'")
