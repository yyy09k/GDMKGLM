import os
import json
import pandas as pd
from pathlib import Path

def check_directory(dir_path):
    """检查目录是否存在并包含文件"""
    path = Path(dir_path)
    if not path.exists():
        return {"status": "错误", "message": f"目录不存在: {dir_path}"}
    
    files = list(path.glob("*"))
    if not files:
        return {"status": "警告", "message": f"目录为空: {dir_path}"}
    
    return {
        "status": "成功", 
        "message": f"目录包含 {len(files)} 个文件", 
        "files": [f.name for f in files]
    }

def check_json_file(file_path):
    """检查JSON文件是否有效"""
    path = Path(file_path)
    if not path.exists():
        return {"status": "错误", "message": f"文件不存在: {file_path}"}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return {"status": "成功", "message": f"JSON文件有效，包含 {len(data)} 条记录"}
        else:
            return {"status": "成功", "message": "JSON文件有效"}
    
    except Exception as e:
        return {"status": "错误", "message": f"JSON文件无效: {str(e)}"}

def check_csv_file(file_path):
    """检查CSV文件是否有效"""
    path = Path(file_path)
    if not path.exists():
        return {"status": "错误", "message": f"文件不存在: {file_path}"}
    
    try:
        df = pd.read_csv(path)
        return {"status": "成功", "message": f"CSV文件有效，包含 {len(df)} 行, {len(df.columns)} 列"}
    
    except Exception as e:
        return {"status": "错误", "message": f"CSV文件无效: {str(e)}"}

def validate_data():
    """验证所有数据文件"""
    results = {}
    
    # 检查目录
    data_dirs = ["data/guidelines", "data/pubmed", "data/textbooks", "data/faq"]
    for dir_path in data_dirs:
        results[dir_path] = check_directory(dir_path)
    
    # 检查特定文件
    files_to_check = [
        {"path": "data/pubmed/all_gdm_articles.json", "type": "json"},
        {"path": "data/faq/gdm_faqs.json", "type": "json"},
        {"path": "data/faq/gdm_faqs.csv", "type": "csv"},
        {"path": "data/textbooks/resources.json", "type": "json"}
    ]
    
    for file_info in files_to_check:
        if file_info["type"] == "json":
            results[file_info["path"]] = check_json_file(file_info["path"])
        elif file_info["type"] == "csv":
            results[file_info["path"]] = check_csv_file(file_info["path"])
    
    return results

def generate_data_summary():
    """生成数据摘要"""
    summary = {
        "guidelines": {"count": 0, "files": []},
        "pubmed": {"count": 0, "articles": []},
        "textbooks": {"count": 0, "resources": []},
        "faq": {"count": 0, "categories": {}}
    }
    
    # 统计指南文件
    guidelines_dir = Path("data/guidelines")
    if guidelines_dir.exists():
        pdf_files = list(guidelines_dir.glob("*.pdf"))
        summary["guidelines"]["count"] = len(pdf_files)
        summary["guidelines"]["files"] = [f.name for f in pdf_files]
    
    # 统计PubMed文章
    pubmed_dir = Path("data/pubmed")
    if pubmed_dir.exists():
        json_file = pubmed_dir / "all_gdm_articles.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    articles = json.load(f)
                summary["pubmed"]["count"] = len(articles)
                # 提取文章标题
                summary["pubmed"]["articles"] = [a.get("title", f"Article {i+1}") for i, a in enumerate(articles)]
            except:
                pass
    
    # 统计教科书资源
    textbooks_dir = Path("data/textbooks")
    if textbooks_dir.exists():
        resources_file = textbooks_dir / "resources.json"
        if resources_file.exists():
            try:
                with open(resources_file, "r", encoding="utf-8") as f:
                    resources = json.load(f)
                summary["textbooks"]["count"] = len(resources)
                summary["textbooks"]["resources"] = [r.get("title", f"Resource {i+1}") for i, r in enumerate(resources)]
            except:
                pass
    
    # 统计FAQ
    faq_dir = Path("data/faq")
    if faq_dir.exists():
        faq_file = faq_dir / "gdm_faqs.json"
        if faq_file.exists():
            try:
                with open(faq_file, "r", encoding="utf-8") as f:
                    faqs = json.load(f)
                summary["faq"]["count"] = len(faqs)
                # 按类别统计
                for faq in faqs:
                    category = faq.get("category", "未分类")
                    if category not in summary["faq"]["categories"]:
                        summary["faq"]["categories"][category] = 0
                    summary["faq"]["categories"][category] += 1
            except:
                pass
    
    return summary

def main():
    print("开始验证数据文件...")
    results = validate_data()
    
    # 打印验证结果
    print("\n=== 数据验证结果 ===")
    for path, result in results.items():
        status_symbol = "✓" if result["status"] == "成功" else "⚠️" if result["status"] == "警告" else "✗"
        print(f"{status_symbol} {path}: {result['message']}")
    
    # 生成数据摘要
    print("\n=== 数据摘要 ===")
    summary = generate_data_summary()
    
    print(f"临床指南: {summary['guidelines']['count']} 份")
    if summary['guidelines']['files']:
        for file in summary['guidelines']['files']:
            print(f"  - {file}")
    
    print(f"\nPubMed文章: {summary['pubmed']['count']} 篇")
    if summary['pubmed']['count'] > 0:
        print(f"  (前5篇示例)")
        for article in summary['pubmed']['articles'][:5]:
            print(f"  - {article[:80]}...")
    
    print(f"\n教科书资源: {summary['textbooks']['count']} 份")
    if summary['textbooks']['resources']:
        for resource in summary['textbooks']['resources']:
            print(f"  - {resource}")
    
    print(f"\nFAQ问答: {summary['faq']['count']} 条")
    if summary['faq']['categories']:
        print("  按类别分布:")
        for category, count in summary['faq']['categories'].items():
            print(f"  - {category}: {count} 条")
    
    # 保存摘要
    with open("data/data_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("\n数据摘要已保存到 data/data_summary.json")

if __name__ == "__main__":
    main()
