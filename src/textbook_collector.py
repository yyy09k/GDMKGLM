import os
import requests
import json
from pathlib import Path

def download_pmc_article(pmc_id, output_dir):
    """从PubMed Central下载开放获取文章"""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    fetch_url = f"{base_url}efetch.fcgi?db=pmc&id={pmc_id}&retmode=xml"
    
    try:
        response = requests.get(fetch_url)
        response.raise_for_status()
        
        output_file = Path(output_dir) / f"PMC{pmc_id}.xml"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        print(f"✓ 成功下载 PMC{pmc_id}")
        return True
    except Exception as e:
        print(f"✗ 下载 PMC{pmc_id} 失败: {str(e)}")
        return False

def create_textbook_resources():
    """创建教科书资源列表"""
    # 这些是与妊娠期糖尿病相关的开放获取教科书章节
    textbook_resources = [
        {
            "title": "Gestational Diabetes Mellitus",
            "source": "Endotext",
            "pmc_id": "7144926",
            "url": "https://www.ncbi.nlm.nih.gov/books/NBK279010/"
        },
        {
            "title": "Diabetes Mellitus in Pregnancy",
            "source": "StatPearls",
            "pmc_id": "9036566",
            "url": "https://www.ncbi.nlm.nih.gov/books/NBK551666/"
        },
        {
            "title": "Screening and Diagnosis of Gestational Diabetes Mellitus",
            "source": "NCBI Bookshelf",
            "pmc_id": "4283661",
            "url": "https://www.ncbi.nlm.nih.gov/books/NBK279079/"
        },
        {
            "title": "Management of Diabetes in Pregnancy",
            "source": "ADA Standards of Care",
            "pmc_id": "8722516",
            "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8722516/"
        },
        {
            "title": "Nutrition Therapy for Adults With Diabetes or Prediabetes",
            "source": "ADA Guidelines",
            "pmc_id": "7011201",
            "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7011201/"
        }
    ]
    
    # 保存资源列表
    with open("data/textbooks/resources.json", "w", encoding="utf-8") as f:
        json.dump(textbook_resources, f, ensure_ascii=False, indent=2)
    
    return textbook_resources

def main():
    # 创建目录
    os.makedirs("data/textbooks", exist_ok=True)
    
    # 创建资源列表
    resources = create_textbook_resources()
    print(f"已创建 {len(resources)} 个教科书资源条目")
    
    # 下载资源
    success_count = 0
    for resource in resources:
        print(f"\n下载: {resource['title']}...")
        if download_pmc_article(resource["pmc_id"], "data/textbooks"):
            success_count += 1
    
    print(f"\n成功下载 {success_count}/{len(resources)} 个教科书资源")
    print("\n注意: 可能需要手动访问以下网站获取更多资源:")
    print("1. PubMed Central: https://www.ncbi.nlm.nih.gov/pmc/")
    print("2. NCBI Bookshelf: https://www.ncbi.nlm.nih.gov/books/")
    print("3. 搜索关键词: gestational diabetes, GDM, pregnancy diabetes")

if __name__ == "__main__":
    main()
