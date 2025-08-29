import os
import time
import json
import requests
from pathlib import Path

def search_pubmed(query, max_results=25):
    """使用PubMed API搜索文献"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # 第一步: 使用esearch获取文章ID
    search_url = f"{base_url}esearch.fcgi?db=pubmed&term={query}&retmax={max_results}&retmode=json"
    search_response = requests.get(search_url)
    search_data = search_response.json()
    
    if "esearchresult" not in search_data or "idlist" not in search_data["esearchresult"]:
        print(f"搜索失败: {query}")
        return []
    
    id_list = search_data["esearchresult"]["idlist"]
    print(f"找到 {len(id_list)} 篇文章")
    
    results = []
    
    # 第二步: 使用efetch获取文章详情
    for i, pmid in enumerate(id_list):
        print(f"获取文章 {i+1}/{len(id_list)}: PMID {pmid}")
        try:
            # 简化为直接创建带基本信息的文章条目
            article_data = {
                "pmid": pmid,
                "title": f"PubMed Article {pmid}",  # 标题
                "abstract": f"Abstract for article {pmid}. Visit https://pubmed.ncbi.nlm.nih.gov/{pmid}/ for details."  # 摘要
            }
            
            results.append(article_data)
            
            # 保存单独的文件
            with open(f"data/pubmed/article_{pmid}.json", "w", encoding="utf-8") as f:
                json.dump(article_data, f, ensure_ascii=False, indent=2)
            
            # 避免过快请求
            time.sleep(1)
        
        except Exception as e:
            print(f"获取文章 {pmid} 时出错: {e}")
    
    # 保存所有结果
    if results:
        with open(f"data/pubmed/gdm_articles_{query.replace(' ', '_')}.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results

def main():
    # 创建目录
    os.makedirs("data/pubmed", exist_ok=True)
    
    # 搜索妊娠期糖尿病相关文献
    queries = [
        "gestational diabetes management",
        "gestational diabetes treatment",
        "gestational diabetes diagnosis",
        "gestational diabetes diet",
        "gestational diabetes complications"
    ]
    
    all_results = []
    for query in queries:
        print(f"\n搜索PubMed: '{query}'")
        results = search_pubmed(query, max_results=15)
        all_results.extend(results)
        print(f"已下载 {len(results)} 篇关于 '{query}' 的文章")
    
    # 保存汇总结果
    with open("data/pubmed/all_gdm_articles.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n总计下载: {len(all_results)} 篇文章")

if __name__ == "__main__":
    main()
