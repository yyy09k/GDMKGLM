""" 
GDM GraphRAG Web系统
"""
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates  
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
import sys
import os
from datetime import datetime
from pathlib import Path

# 导入GraphRAG引擎
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from graphrag.gdm_graphrag_engine import GDMGraphRAGEngine

# 全局引擎变量
engine = None

def check_model_cache_status():
    """检查模型缓存状态"""
    print("🔍 检查embedding模型缓存状态...")
    
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_cache = cache_dir / "models--sentence-transformers--all-mpnet-base-v2"
    
    print(f"📁 检查路径: {model_cache}")
    
    if model_cache.exists():
        print("✅ 发现模型缓存目录")
        
        # 检查快照目录
        snapshots_dir = model_cache / "snapshots"
        if snapshots_dir.exists():
            snapshots = list(snapshots_dir.glob("*"))
            if snapshots:
                print(f"✅ 发现 {len(snapshots)} 个快照")
                
                # 检查关键文件
                for snapshot in snapshots:
                    # 检查模型权重文件
                    model_files = (
                        list(snapshot.rglob("*.safetensors")) + 
                        list(snapshot.rglob("*.bin"))
                    )
                    # 检查配置文件
                    config_files = list(snapshot.rglob("config*.json"))
                    
                    if model_files and config_files:
                        print(f"✅ 模型完整缓存: 权重文件 {len(model_files)} 个, 配置文件 {len(config_files)} 个")
                        
                        # 实际测试离线加载
                        return _test_offline_loading()
                
                print("⚠️  缓存不完整: 缺少必要文件")
                return False
            else:
                print("⚠️  快照目录为空")
                return False
        else:
            print("⚠️  未找到快照目录")
            return False
    else:
        print("❌ 未找到模型缓存目录")
        return False

def _test_offline_loading():
    """测试离线加载功能 - 使用 local_files_only"""
    print("🔍 测试离线加载...")
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # 使用 local_files_only=True 强制从缓存加载
        model = SentenceTransformer("all-mpnet-base-v2", local_files_only=True)
        
        # 简单测试
        test_result = model.encode(["测试"], convert_to_tensor=True)
        
        print("✅ 离线加载测试成功！模型就绪")
        print(f"   向量维度: {test_result.shape}")
        return True
        
    except Exception as e:
        print(f"❌ 离线加载测试失败: {str(e)[:100]}...")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 新的推荐方式"""
    # 启动时初始化
    global engine
    print("🚀 启动GDM GraphRAG引擎...")
    try:
        engine = GDMGraphRAGEngine()
        print("✅ 引擎启动成功！")
    except Exception as e:
        print(f"❌ 引擎启动失败: {e}")
    
    yield  # 应用运行中
    
    # 关闭时清理资源
    if engine:
        try:
            engine.close()  # 使用正确的close方法而不是shutdown
            print("🔒 引擎已关闭")
        except Exception as e:
            print(f"❌ 引擎关闭失败: {e}")

# 创建应用 - 使用lifespan参数
app = FastAPI(
    title="GDM GraphRAG智能问答系统",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """主页面"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(query: str = Form(...)):
    """处理对话请求"""
    if not engine:
        return JSONResponse({
            "success": False,
            "answer": "系统未就绪，请稍后再试"
        })
    
    if not query.strip():
        return JSONResponse({
            "success": False, 
            "answer": "请输入您的问题"
        })
    
    try:
        print(f"🔍 处理查询: {query}")
        result = engine.process_query(query)
        
        return JSONResponse({
            "success": True,
            "query": query,
            "answer": result.answer,
            "confidence": round(result.confidence_score, 3),  # 修正：使用confidence_score
            "response_time": f"{result.response_time:.2f}s",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "sources": result.sources,
            "query_type": result.query_analysis.get("query_type", "unknown")
        })
        
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        return JSONResponse({
            "success": False,
            "answer": "处理您的问题时出现了错误，请重试。"
        })

@app.get("/health")
async def health():
    """系统状态检查"""
    return JSONResponse({
        "status": "healthy" if engine else "not ready",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    import uvicorn
    # 检查模型缓存状态
    if not check_model_cache_status():
        sys.exit(1)
    
    print("🚀 启动GDM Web系统...")
    print("📍 访问: http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)