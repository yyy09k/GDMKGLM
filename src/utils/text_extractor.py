import os
import json
import re
import traceback
import fitz  # PyMuPDF
import xml.etree.ElementTree as ET
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """从医学指南PDF文件中提取文本"""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        # 添加文件名作为标题
        filename = Path(pdf_path).stem
        
        # 处理每一页
        for page_num, page in enumerate(doc):
            # 使用"text"模式获取更整洁的文本流
            page_text = page.get_text("text")
            
            # 跳过空页面
            if page_text.strip():
                text_parts.append(page_text)
        
        # 合并所有文本，用双换行分隔页面
        full_text = "\n\n".join(text_parts)
        
        # 基本清理
        # 删除连续多个换行符
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)
        # 删除连续多个空格
        full_text = re.sub(r' {2,}', ' ', full_text)
        
        return full_text.strip()
    except Exception as e:
        print(f"无法从PDF提取文本 {pdf_path}: {str(e)}")
        traceback.print_exc()  # 打印详细错误信息
        return ""

def extract_text_from_xml(xml_path):
    """从XML文件中提取文本"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # 获取所有文本内容，包括混合内容
        def get_text_content(element):
            text = element.text or ""
            for child in element:
                text += get_text_content(child)
            if element.tail:
                text += element.tail
            return text
        
        # 提取标题
        title = ""
        title_elements = root.findall(".//article-title")
        if title_elements:
            title = get_text_content(title_elements[0])
        
        # 提取摘要
        abstract = ""
        abstract_elements = root.findall(".//abstract")
        if abstract_elements:
            abstract = get_text_content(abstract_elements[0])
        
        # 提取正文
        body_text = ""
        body_elements = root.findall(".//body")
        if body_elements:
            body_text = get_text_content(body_elements[0])
        
        # 组合所有文本
        full_text = f"TITLE: {title}\n\nABSTRACT: {abstract}\n\nCONTENT: {body_text}"
        
        # 清理文本
        full_text = re.sub(r'\s+', ' ', full_text)  # 替换多个空白为单个空格
        
        return full_text.strip()
    except Exception as e:
        print(f"无法从XML提取文本 {xml_path}: {str(e)}")
        return ""

def process_guidelines():
    """处理指南文献"""
    guidelines_dir = Path("data/guidelines")
    output_dir = Path("data/processed/guidelines")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # 处理PDF文件
    for pdf_file in guidelines_dir.glob("*.pdf"):
        print(f"处理指南文献: {pdf_file.name}")
        text = extract_text_from_pdf(pdf_file)
        
        if text:
            # 保存提取的文本
            output_file = output_dir / f"{pdf_file.stem}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)
            
            # 添加到结果
            results.append({
                "source": pdf_file.name,
                "text_file": output_file.name,
                "text_length": len(text),
                "type": "guideline"
            })
        else:
            print(f"警告: 未能从 {pdf_file.name} 提取文本")
    
    # 保存处理结果
    with open(output_dir / "guidelines_index.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def process_textbooks():
    """处理教科书资源"""
    textbooks_dir = Path("data/textbooks")
    output_dir = Path("data/processed/textbooks")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # 处理XML文件
    for xml_file in textbooks_dir.glob("*.xml"):
        print(f"处理教科书资源: {xml_file.name}")
        text = extract_text_from_xml(xml_file)
        
        if text:
            # 保存提取的文本
            output_file = output_dir / f"{xml_file.stem}.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)
            
            # 添加到结果
            results.append({
                "source": xml_file.name,
                "text_file": output_file.name,
                "text_length": len(text),
                "type": "textbook"
            })
    
    # 处理资源元数据
    resources_file = textbooks_dir / "resources.json"
    if resources_file.exists():
        try:
            with open(resources_file, "r", encoding="utf-8") as f:
                resources = json.load(f)
            
            # 将元数据与提取的文本关联
            for result in results:
                source_id = result["source"].replace("PMC", "").replace(".xml", "")
                for resource in resources:
                    if resource.get("pmc_id") == source_id:
                        result["title"] = resource.get("title", "")
                        result["source_name"] = resource.get("source", "")
                        break
        except:
            pass
    
    # 保存处理结果
    with open(output_dir / "textbooks_index.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def process_pubmed_articles():
    """处理PubMed文章"""
    pubmed_dir = Path("data/pubmed")
    output_dir = Path("data/processed/pubmed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # 处理汇总文件
    all_articles_file = pubmed_dir / "all_gdm_articles.json"
    if all_articles_file.exists():
        try:
            with open(all_articles_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
            
            for article in articles:
                pmid = article.get("pmid", "")
                title = article.get("title", "")
                abstract = article.get("abstract", "")
                
                if pmid and (title or abstract):
                    # 创建文本文件
                    content = f"Title: {title}\n\nAbstract: {abstract}"
                    output_file = output_dir / f"article_{pmid}.txt"
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    
                    # 添加到结果
                    results.append({
                        "pmid": pmid,
                        "title": title,
                        "text_file": output_file.name,
                        "text_length": len(content),
                        "year": article.get("year", ""),
                        "journal": article.get("journal", ""),
                        "type": "pubmed_article"
                    })
        except Exception as e:
            print(f"处理PubMed文章时出错: {str(e)}")
    
    # 保存处理结果
    with open(output_dir / "pubmed_index.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def process_faqs():
    """处理FAQ数据"""
    faq_dir = Path("data/faq")
    output_dir = Path("data/processed/faq")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # 处理JSON文件
    faq_file = faq_dir / "gdm_faqs.json"
    if faq_file.exists():
        try:
            with open(faq_file, "r", encoding="utf-8") as f:
                faqs = json.load(f)
            
            # 按类别组织FAQ
            categories = {}
            for faq in faqs:
                category = faq.get("category", "未分类")
                if category not in categories:
                    categories[category] = []
                categories[category].append(faq)
            
            # 为每个类别创建文本文件
            for category, category_faqs in categories.items():
                content = f"# {category} FAQ\n\n"
                for faq in category_faqs:
                    content += f"Q: {faq.get('question', '')}\n"
                    content += f"A: {faq.get('answer', '')}\n\n"
                
                # 保存文本
                safe_category = category.replace(" ", "_").replace("/", "_")
                output_file = output_dir / f"faq_{safe_category}.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)
                
                # 添加到结果
                results.append({
                    "category": category,
                    "text_file": output_file.name,
                    "text_length": len(content),
                    "faq_count": len(category_faqs),
                    "type": "faq"
                })
            
            # 创建一个包含所有FAQ的文件
            all_content = "# 妊娠期糖尿病常见问题解答\n\n"
            for faq in faqs:
                all_content += f"类别: {faq.get('category', '未分类')}\n"
                all_content += f"Q: {faq.get('question', '')}\n"
                all_content += f"A: {faq.get('answer', '')}\n\n"
            
            # 保存所有FAQ
            all_output_file = output_dir / "all_faqs.txt"
            with open(all_output_file, "w", encoding="utf-8") as f:
                f.write(all_content)
            
            # 添加到结果
            results.append({
                "category": "全部",
                "text_file": all_output_file.name,
                "text_length": len(all_content),
                "faq_count": len(faqs),
                "type": "faq_all"
            })
        
        except Exception as e:
            print(f"处理FAQ时出错: {str(e)}")
    
    # 保存处理结果
    with open(output_dir / "faq_index.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def main():
    print("开始数据预处理...")
    
    # 创建处理后的数据目录
    os.makedirs("data/processed", exist_ok=True)
    
    # 处理各类数据
    guidelines_results = process_guidelines()
    print(f"处理了 {len(guidelines_results)} 份临床指南")
    
    textbooks_results = process_textbooks()
    print(f"处理了 {len(textbooks_results)} 份教科书资源")
    
    pubmed_results = process_pubmed_articles()
    print(f"处理了 {len(pubmed_results)} 篇PubMed文章")
    
    faq_results = process_faqs()
    print(f"处理了 {len(faq_results)} 个FAQ类别")
    
    # 创建总索引
    all_documents = []
    all_documents.extend(guidelines_results)
    all_documents.extend(textbooks_results)
    all_documents.extend(pubmed_results)
    all_documents.extend(faq_results)
    
    with open("data/processed/all_documents_index.json", "w", encoding="utf-8") as f:
        json.dump(all_documents, f, ensure_ascii=False, indent=2)
    
    print(f"\n总计处理了 {len(all_documents)} 个文档")
    print("预处理完成，结果保存在 data/processed/ 目录")

if __name__ == "__main__":
    main()
