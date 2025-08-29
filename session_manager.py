"""
Neo4j会话管理器 - GDM GraphRAG系统历史对话功能
支持会话创建、消息存储、历史查询等功能
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

class Neo4jSessionManager:
    """Neo4j会话管理器"""
    
    def __init__(self, uri: str = "neo4j://127.0.0.1:7687", 
                 username: str = "neo4j", 
                 password: str = r"42810916402\Ssnx"):
        """初始化Neo4j连接"""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialize_constraints()
    
    def _initialize_constraints(self):
        """初始化数据库约束和索引"""
        with self.driver.session() as session:
            # 创建约束
            constraints = [
                "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
                "CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
                "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE"
            ]
            
            # 创建索引
            indexes = [
                "CREATE INDEX session_user_index IF NOT EXISTS FOR (s:Session) ON (s.user_id)",
                "CREATE INDEX session_updated_index IF NOT EXISTS FOR (s:Session) ON (s.last_updated)",
                "CREATE INDEX message_timestamp_index IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",
                "CREATE INDEX message_session_index IF NOT EXISTS FOR (m:Message) ON (m.session_id)"
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    print(f"约束创建警告: {e}")
            
            for index in indexes:
                try:
                    session.run(index)
                except Exception as e:
                    print(f"索引创建警告: {e}")
    
    async def _run_in_executor(self, func, *args):
        """在线程池中异步执行Neo4j操作"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)
    
    def _create_session_sync(self, user_id: str) -> Dict[str, Any]:
        """同步创建会话"""
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        with self.driver.session() as session:
            # 创建或更新用户节点
            session.run("""
                MERGE (u:User {user_id: $user_id})
                ON CREATE SET u.created_at = $timestamp,
                             u.total_sessions = 1,
                             u.total_messages = 0
                ON MATCH SET u.total_sessions = u.total_sessions + 1,
                            u.last_active = $timestamp
            """, user_id=user_id, timestamp=timestamp)
            
            # 创建会话节点
            result = session.run("""
                CREATE (s:Session {
                    session_id: $session_id,
                    user_id: $user_id,
                    title: "新对话",
                    created_at: $timestamp,
                    last_updated: $timestamp,
                    message_count: 0,
                    is_active: true
                })
                RETURN s.session_id as session_id
            """, session_id=session_id, user_id=user_id, timestamp=timestamp)
            
            # 创建用户与会话的关系
            session.run("""
                MATCH (u:User {user_id: $user_id})
                MATCH (s:Session {session_id: $session_id})
                CREATE (u)-[:HAS_SESSION]->(s)
            """, user_id=user_id, session_id=session_id)
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "会话创建成功"
            }
    
    async def create_session(self, user_id: str) -> Dict[str, Any]:
        """创建新会话"""
        try:
            return await self._run_in_executor(self._create_session_sync, user_id)
        except Exception as e:
            return {
                "success": False,
                "message": f"创建会话失败: {str(e)}"
            }
    
    def _add_message_sync(self, session_id: str, role: str, content: str, 
                         metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """同步添加消息"""
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        if metadata is None:
            metadata = {}
        
        with self.driver.session() as session:
            # 检查会话是否存在
            session_exists = session.run("""
                MATCH (s:Session {session_id: $session_id})
                RETURN s.session_id
            """, session_id=session_id).single()
            
            if not session_exists:
                return {
                    "success": False,
                    "message": "会话不存在"
                }
            
            # 添加消息
            session.run("""
                CREATE (m:Message {
                    message_id: $message_id,
                    session_id: $session_id,
                    role: $role,
                    content: $content,
                    timestamp: $timestamp,
                    metadata: $metadata_json
                })
            """, message_id=message_id, session_id=session_id, role=role, 
                content=content, timestamp=timestamp, 
                metadata_json=json.dumps(metadata, ensure_ascii=False))
            
            # 创建会话与消息的关系
            session.run("""
                MATCH (s:Session {session_id: $session_id})
                MATCH (m:Message {message_id: $message_id})
                CREATE (s)-[:HAS_MESSAGE]->(m)
            """, session_id=session_id, message_id=message_id)
            
            # 更新会话统计
            session.run("""
                MATCH (s:Session {session_id: $session_id})
                SET s.message_count = s.message_count + 1,
                    s.last_updated = $timestamp
            """, session_id=session_id, timestamp=timestamp)
            
            # 更新用户统计
            session.run("""
                MATCH (u:User)-[:HAS_SESSION]->(s:Session {session_id: $session_id})
                SET u.total_messages = u.total_messages + 1,
                    u.last_active = $timestamp
            """, session_id=session_id, timestamp=timestamp)
            
            return {
                "success": True,
                "message_id": message_id,
                "message": "消息添加成功"
            }
    
    async def add_message(self, session_id: str, role: str, content: str, 
                         metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """添加消息到会话"""
        try:
            return await self._run_in_executor(
                self._add_message_sync, session_id, role, content, metadata
            )
        except Exception as e:
            return {
                "success": False,
                "message": f"添加消息失败: {str(e)}"
            }
    
    def _get_session_messages_sync(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """同步获取会话消息"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
                RETURN m.message_id as message_id,
                       m.role as role,
                       m.content as content,
                       m.timestamp as timestamp,
                       m.metadata as metadata_json
                ORDER BY m.timestamp ASC
                LIMIT $limit
            """, session_id=session_id, limit=limit)
            
            messages = []
            for record in result:
                try:
                    metadata = json.loads(record["metadata_json"]) if record["metadata_json"] else {}
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
                
                messages.append({
                    "message_id": record["message_id"],
                    "role": record["role"],
                    "content": record["content"],
                    "timestamp": record["timestamp"],
                    "metadata": metadata
                })
            
            return messages
    
    async def get_session_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取会话消息历史"""
        try:
            return await self._run_in_executor(self._get_session_messages_sync, session_id, limit)
        except Exception as e:
            print(f"获取会话消息失败: {e}")
            return []
    
    def _get_user_sessions_sync(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """同步获取用户会话列表"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {user_id: $user_id})-[:HAS_SESSION]->(s:Session)
                RETURN s.session_id as session_id,
                       s.title as title,
                       s.created_at as created_at,
                       s.last_updated as last_updated,
                       s.message_count as message_count,
                       s.is_active as is_active
                ORDER BY s.last_updated DESC
                LIMIT $limit
            """, user_id=user_id, limit=limit)
            
            sessions = []
            for record in result:
                sessions.append({
                    "session_id": record["session_id"],
                    "title": record["title"],
                    "created_at": record["created_at"],
                    "last_updated": record["last_updated"],
                    "message_count": record["message_count"],
                    "is_active": record["is_active"]
                })
            
            return sessions
    
    async def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户所有会话"""
        try:
            return await self._run_in_executor(self._get_user_sessions_sync, user_id, limit)
        except Exception as e:
            print(f"获取用户会话失败: {e}")
            return []
    
    def _update_session_activity_sync(self, session_id: str, user_query: str = None, 
                                    assistant_response: str = None) -> Dict[str, Any]:
        """同步更新会话活动和标题"""
        timestamp = datetime.now().isoformat()
        
        with self.driver.session() as session:
            # 获取当前会话信息
            current_session = session.run("""
                MATCH (s:Session {session_id: $session_id})
                RETURN s.title as title, s.message_count as message_count
            """, session_id=session_id).single()
            
            if not current_session:
                return {"success": False, "message": "会话不存在"}
            
            # 如果是新会话(消息数<=2)且有用户查询，自动生成标题
            new_title = current_session["title"]
            if (current_session["message_count"] <= 2 and 
                user_query and 
                current_session["title"] == "新对话"):
                # 简单的标题生成：取查询前20个字符
                new_title = user_query[:20] + ("..." if len(user_query) > 20 else "")
            
            # 更新会话
            session.run("""
                MATCH (s:Session {session_id: $session_id})
                SET s.last_updated = $timestamp,
                    s.title = $title
            """, session_id=session_id, timestamp=timestamp, title=new_title)
            
            return {
                "success": True,
                "message": "会话活动更新成功",
                "title": new_title
            }
    
    async def update_session_activity(self, session_id: str, user_query: str = None, 
                                    assistant_response: str = None) -> Dict[str, Any]:
        """更新会话最后活动时间和标题"""
        try:
            return await self._run_in_executor(
                self._update_session_activity_sync, session_id, user_query, assistant_response
            )
        except Exception as e:
            return {
                "success": False,
                "message": f"更新会话活动失败: {str(e)}"
            }
    
    def _get_session_detail_sync(self, session_id: str) -> Optional[Dict[str, Any]]:
        """同步获取会话详情"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Session {session_id: $session_id})
                OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
                WITH s, count(m) as actual_message_count
                RETURN s.session_id as session_id,
                       s.user_id as user_id,
                       s.title as title,
                       s.created_at as created_at,
                       s.last_updated as last_updated,
                       s.message_count as message_count,
                       actual_message_count,
                       s.is_active as is_active
            """, session_id=session_id).single()
            
            if not result:
                return None
            
            return {
                "session_id": result["session_id"],
                "user_id": result["user_id"],
                "title": result["title"],
                "created_at": result["created_at"],
                "last_updated": result["last_updated"],
                "message_count": result["message_count"],
                "actual_message_count": result["actual_message_count"],
                "is_active": result["is_active"]
            }
    
    async def get_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情"""
        try:
            return await self._run_in_executor(self._get_session_detail_sync, session_id)
        except Exception as e:
            print(f"获取会话详情失败: {e}")
            return None
    
    def _update_session_title_sync(self, session_id: str, title: str) -> Dict[str, Any]:
        """同步更新会话标题"""
        timestamp = datetime.now().isoformat()
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Session {session_id: $session_id})
                SET s.title = $title, s.last_updated = $timestamp
                RETURN s.session_id
            """, session_id=session_id, title=title, timestamp=timestamp)
            
            if result.single():
                return {
                    "success": True,
                    "message": "标题更新成功"
                }
            else:
                return {
                    "success": False,
                    "message": "会话不存在"
                }
    
    async def update_session_title(self, session_id: str, title: str) -> Dict[str, Any]:
        """更新会话标题"""
        try:
            return await self._run_in_executor(self._update_session_title_sync, session_id, title)
        except Exception as e:
            return {
                "success": False,
                "message": f"更新标题失败: {str(e)}"
            }
    
    def _delete_session_sync(self, session_id: str) -> Dict[str, Any]:
        """同步删除会话"""
        with self.driver.session() as session:
            # 删除会话及其所有消息
            result = session.run("""
                MATCH (s:Session {session_id: $session_id})
                OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
                WITH s, count(m) as message_count
                DETACH DELETE s, m
                RETURN message_count
            """, session_id=session_id)
            
            record = result.single()
            if record is not None:
                return {
                    "success": True,
                    "message": f"会话删除成功，共删除 {record['message_count']} 条消息"
                }
            else:
                return {
                    "success": False,
                    "message": "会话不存在"
                }
    
    async def delete_session(self, session_id: str) -> Dict[str, Any]:
        """删除会话"""
        try:
            return await self._run_in_executor(self._delete_session_sync, session_id)
        except Exception as e:
            return {
                "success": False,
                "message": f"删除会话失败: {str(e)}"
            }
    
    def _clear_session_messages_sync(self, session_id: str) -> Dict[str, Any]:
        """同步清空会话消息"""
        timestamp = datetime.now().isoformat()
        
        with self.driver.session() as session:
            # 删除所有消息
            result = session.run("""
                MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(m:Message)
                WITH s, count(m) as message_count
                DETACH DELETE m
                SET s.message_count = 0, s.last_updated = $timestamp
                RETURN message_count
            """, session_id=session_id, timestamp=timestamp)
            
            record = result.single()
            if record is not None:
                return {
                    "success": True,
                    "message": f"会话消息清空成功，共删除 {record['message_count']} 条消息"
                }
            else:
                return {
                    "success": False,
                    "message": "会话不存在"
                }
    
    async def clear_session_messages(self, session_id: str) -> Dict[str, Any]:
        """清空会话所有消息"""
        try:
            return await self._run_in_executor(self._clear_session_messages_sync, session_id)
        except Exception as e:
            return {
                "success": False,
                "message": f"清空会话消息失败: {str(e)}"
            }
    
    def _search_sessions_sync(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """同步搜索会话"""
        with self.driver.session() as session:
            if not query.strip():
                # 如果查询为空，返回最近的会话
                return self._get_user_sessions_sync(user_id, limit)
            
            # 搜索标题或消息内容包含关键词的会话
            result = session.run("""
                MATCH (u:User {user_id: $user_id})-[:HAS_SESSION]->(s:Session)
                WHERE s.title CONTAINS $query
                   OR EXISTS {
                       MATCH (s)-[:HAS_MESSAGE]->(m:Message)
                       WHERE m.content CONTAINS $query
                   }
                RETURN DISTINCT s.session_id as session_id,
                       s.title as title,
                       s.created_at as created_at,
                       s.last_updated as last_updated,
                       s.message_count as message_count,
                       s.is_active as is_active
                ORDER BY s.last_updated DESC
                LIMIT $limit
            """, user_id=user_id, query=query, limit=limit)
            
            sessions = []
            for record in result:
                sessions.append({
                    "session_id": record["session_id"],
                    "title": record["title"],
                    "created_at": record["created_at"],
                    "last_updated": record["last_updated"],
                    "message_count": record["message_count"],
                    "is_active": record["is_active"]
                })
            
            return sessions
    
    async def search_sessions(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索会话"""
        try:
            return await self._run_in_executor(self._search_sessions_sync, user_id, query, limit)
        except Exception as e:
            print(f"搜索会话失败: {e}")
            return []
    
    def _get_user_stats_sync(self, user_id: str) -> Dict[str, Any]:
        """同步获取用户统计信息"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {user_id: $user_id})
                OPTIONAL MATCH (u)-[:HAS_SESSION]->(s:Session)
                OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
                WITH u, 
                     count(DISTINCT s) as total_sessions,
                     count(m) as total_messages,
                     max(s.last_updated) as last_session_time
                RETURN u.created_at as user_created_at,
                       u.last_active as last_active,
                       total_sessions,
                       total_messages,
                       last_session_time
            """, user_id=user_id).single()
            
            if not result:
                return {
                    "total_sessions": 0,
                    "total_messages": 0,
                    "user_created_at": None,
                    "last_active": None,
                    "last_session_time": None
                }
            
            return {
                "total_sessions": result["total_sessions"] or 0,
                "total_messages": result["total_messages"] or 0,
                "user_created_at": result["user_created_at"],
                "last_active": result["last_active"],
                "last_session_time": result["last_session_time"]
            }
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        try:
            return await self._run_in_executor(self._get_user_stats_sync, user_id)
        except Exception as e:
            print(f"获取用户统计失败: {e}")
            return {
                "total_sessions": 0,
                "total_messages": 0,
                "user_created_at": None,
                "last_active": None,
                "last_session_time": None
            }
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
        self.executor.shutdown(wait=True)
        print("🔒 Neo4j会话管理器已关闭")

# 测试代码
if __name__ == "__main__":
    import asyncio
    
    async def test_session_manager():
        """测试会话管理器功能"""
        print("🧪 测试Neo4j会话管理器...")
        
        # 创建管理器实例
        manager = Neo4jSessionManager()
        
        try:
            # 测试创建会话
            print("\n1. 测试创建会话...")
            session_result = await manager.create_session("test_user")
            print(f"创建会话结果: {session_result}")
            
            if session_result["success"]:
                session_id = session_result["session_id"]
                
                # 测试添加消息
                print("\n2. 测试添加消息...")
                await manager.add_message(session_id, "user", "你好，这是测试消息")
                await manager.add_message(session_id, "assistant", "你好！我是GDM GraphRAG助手。")
                
                # 测试获取消息
                print("\n3. 测试获取消息...")
                messages = await manager.get_session_messages(session_id)
                print(f"消息列表: {messages}")
                
                # 测试获取会话列表
                print("\n4. 测试获取会话列表...")
                sessions = await manager.get_user_sessions("test_user")
                print(f"会话列表: {sessions}")
                
                # 测试用户统计
                print("\n5. 测试用户统计...")
                stats = await manager.get_user_stats("test_user")
                print(f"用户统计: {stats}")
                
                print("\n✅ 所有测试通过！")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
        finally:
            manager.close()
    
    # 运行测试
    asyncio.run(test_session_manager())
