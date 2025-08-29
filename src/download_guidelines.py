import os
import requests
from pathlib import Path

def download_file(url, filename):
    """下载文件并保存到指定位置"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # 检查请求是否成功
        
        file_path = Path(filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"✓ 成功下载: {filename}")
        return True
    except Exception as e:
        print(f"✗ 下载失败 {url}: {str(e)}")
        return False

def main():
    # 创建目录
    os.makedirs("data/guidelines", exist_ok=True)
    
    # 指南URLs (这些是公开可访问的GDM指南)
    guidelines = [
        {
            "name": "ADA Standards of Care 2023",
            "url": "https://diabetesjournals.org/care/issue/46/Supplement_1",
            "filename": "data/guidelines/ADA_2023_Standards.pdf"
        },
        {
            "name": "NICE Guideline - Diabetes in Pregnancy",
            "url": "https://www.nice.org.uk/guidance/ng3/resources/diabetes-in-pregnancy-management-from-preconception-to-the-postnatal-period-pdf-51038446021",
            "filename": "data/guidelines/NICE_Diabetes_Pregnancy.pdf"
        },
        {
            "name": "IDF GDM Model of Care",
            "url": "https://www.idf.org/our-activities/care-prevention/gdm/gdm-model-of-care.html",
            "filename": "data/guidelines/IDF_GDM_Model.pdf"
        }
    ]
    
    # 下载文件
    success_count = 0
    for guide in guidelines:
        print(f"正在下载: {guide['name']}...")
        if download_file(guide["url"], guide["filename"]):
            success_count += 1
    
    print(f"\n成功下载 {success_count}/{len(guidelines)} 份指南")
    print("\n注意: 某些指南可能需要手动下载，请访问以下网站:")
    print("1. ADA: https://professional.diabetes.org/")
    print("2. ACOG: https://www.acog.org/clinical/clinical-guidance/practice-bulletin/articles/2018/02/gestational-diabetes-mellitus")
    print("3. 中国妇产科学会: http://www.csog.net/")

if __name__ == "__main__":
    main()
