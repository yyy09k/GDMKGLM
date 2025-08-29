import os
import json
import time
import requests
from pathlib import Path

def fetch_article_details(pmid):
    """获取PubMed文章的详细信息"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    fetch_url = f"{base_url}esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
    
    try:
        response = requests.get(fetch_url)
        response.raise_for_status()
        data = response.json()
        
        # 从结果中提取信息
        result = data.get("result", {})
        article_data = result.get(pmid, {})
        
        if not article_data:
            return None
        
        # 提取标题和摘要
        title = article_data.get("title", f"PubMed Article {pmid}")
        
        # 获取摘要需要另一个API调用
        abstract_url = f"{base_url}efetch.fcgi?db=pubmed&id={pmid}&rettype=abstract&retmode=text"
        abstract_response = requests.get(abstract_url)
        abstract = abstract_response.text if abstract_response.status_code == 200 else f"Visit https://pubmed.ncbi.nlm.nih.gov/{pmid}/ for details."
        
        # 提取作者
        authors = []
        if "authors" in article_data:
            for author in article_data["authors"]:
                if "name" in author:
                    authors.append(author["name"])
        
        # 提取期刊和年份
        journal = article_data.get("fulljournalname", "")
        pub_date = article_data.get("pubdate", "")
        
        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "year": pub_date.split()[0] if pub_date else ""
        }
    
    except Exception as e:
        print(f"获取文章 {pmid} 详情时出错: {e}")
        return None

def main():
    pubmed_dir = Path("data/pubmed")
    if not pubmed_dir.exists():
        print("PubMed数据目录不存在")
        return
    
    # 获取所有单篇文章文件
    article_files = list(pubmed_dir.glob("article_*.json"))
    print(f"找到 {len(article_files)} 个文章文件")
    
    updated_count = 0
    for i, file_path in enumerate(article_files):
        print(f"处理文件 {i+1}/{len(article_files)}: {file_path.name}")
        
        # 读取当前文件
        with open(file_path, "r", encoding="utf-8") as f:
            article_data = json.load(f)
        
        pmid = article_data.get("pmid", "")
        if not pmid:
            continue
        
        # 检查是否需要更新
        if article_data.get("title") == f"PubMed Article {pmid}":
            # 获取详细信息
            print(f"  获取 PMID {pmid} 的详细信息...")
            details = fetch_article_details(pmid)
            
            if details:
                # 更新文件
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(details, f, ensure_ascii=False, indent=2)
                updated_count += 1
                print(f"  ✓ 已更新: {details.get('title', '')[:50]}...")
            
            # 避免过快请求
            time.sleep(1)
    
    print(f"\n已更新 {updated_count}/{len(article_files)} 个文章")
    
    # 更新汇总文件
    all_articles_file = pubmed_dir / "all_gdm_articles.json"
    if all_articles_file.exists():
        print("\n更新汇总文件...")
        
        # 重新收集所有更新后的文章
        updated_articles = []
        for file_path in pubmed_dir.glob("article_*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                article_data = json.load(f)
                updated_articles.append(article_data)
        
        # 保存更新后的汇总文件
        with open(all_articles_file, "w", encoding="utf-8") as f:
            json.dump(updated_articles, f, ensure_ascii=False, indent=2)
        
        print(f"汇总文件已更新，包含 {len(updated_articles)} 篇文章")

if __name__ == "__main__":
    main()
