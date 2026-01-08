"""
故事数据访问对象
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.story import Story
from backend.db.models.user import User
from backend.utils.id_generator import generate_story_id


class StoryDAO:
    """故事 DAO"""

    @staticmethod
    async def create(
        session: AsyncSession,
        prompt_id: str,
        user_id: str,
        story_type: str
    ) -> Story:
        """
        创建故事

        Args:
            session: 数据库会话
            prompt_id: 创意ID
            user_id: 用户ID
            story_type: 故事类型

        Returns:
            Story: 新创建的故事对象
        """
        story = Story(
            id=generate_story_id(),
            prompt_id=prompt_id,
            user_id=user_id,
            type=story_type,
            status="pending",
            visibility="draft",
        )

        session.add(story)
        await session.flush()

        return story

    @staticmethod
    async def get_by_id(session: AsyncSession, story_id: str) -> Optional[Story]:
        """根据ID获取故事"""
        result = await session.execute(
            select(Story).where(Story.id == story_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_status(
        session: AsyncSession,
        story_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """更新故事状态"""
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return False

        story.status = status
        if error_message:
            story.error_message = error_message

        await session.flush()
        return True

    @staticmethod
    async def update_content(
        session: AsyncSession,
        story_id: str,
        title: Optional[str] = None,
        think: Optional[str] = None,
        script: Optional[str] = None
    ) -> bool:
        """更新故事内容"""
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return False

        if title:
            story.title = title
        if think:
            story.think = think
        if script:
            story.script = script

        await session.flush()
        return True

    @staticmethod
    async def publish(session: AsyncSession, story_id: str) -> bool:
        """发布故事"""
        story = await StoryDAO.get_by_id(session, story_id)
        if not story:
            return False

        story.visibility = "published"
        await session.flush()
        return True

    @staticmethod
    async def get_user_stories(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Story]:
        """获取用户的故事列表"""
        result = await session.execute(
            select(Story)
            .where(Story.user_id == user_id)
            .order_by(Story.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def get_published_stories(
        session: AsyncSession,
        story_type: Optional[str] = None,
        sort: str = "latest",
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Story], int]:
        """
        获取已发布的故事列表（广场）
        
        Args:
            session: 数据库会话
            story_type: 故事类型筛选（linear/interactive）
            sort: 排序方式（latest/popular/recommended）
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            (故事列表, 总数)
        """
        # 基础查询：只返回已发布且作者状态正常的故事
        query = select(Story).join(User, Story.user_id == User.id).where(
            and_(
                Story.visibility == "published",
                User.status == "active"
            )
        )
        
        # 类型筛选
        if story_type:
            query = query.where(Story.type == story_type)
        
        # 排序
        if sort == "popular":
            # 按热度排序：综合播放数、点赞数、收藏数
            query = query.order_by(
                desc(Story.play_count + Story.like_count * 2 + Story.favorite_count * 3)
            )
        elif sort == "recommended":
            # TODO: 实现个性化推荐算法
            # 暂时使用热度排序
            query = query.order_by(
                desc(Story.play_count + Story.like_count * 2 + Story.favorite_count * 3)
            )
        else:  # latest
            query = query.order_by(desc(Story.published_at))
        
        # 获取总数
        count_query = select(func.count()).select_from(Story).join(User, Story.user_id == User.id).where(
            and_(
                Story.visibility == "published",
                User.status == "active"
            )
        )
        if story_type:
            count_query = count_query.where(Story.type == story_type)
        
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        result = await session.execute(query.limit(limit).offset(offset))
        stories = list(result.scalars().all())
        
        return stories, total

    @staticmethod
    async def search_stories(
        session: AsyncSession,
        keyword: str,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Story], int]:
        """
        全文搜索故事
        
        Args:
            session: 数据库会话
            keyword: 搜索关键词
            limit: 每页数量
            offset: 偏移量
            
        Returns:
            (故事列表, 总数)
        """
        from sqlalchemy import text
        
        # 使用 pg_jieba 全文搜索
        # 搜索范围：故事标题
        search_condition = func.to_tsvector('jiebacfg', Story.title).op('@@')(
            func.to_tsquery('jiebacfg', keyword)
        )
        
        # 基础查询：只搜索已发布且作者状态正常的故事
        query = select(Story).join(User, Story.user_id == User.id).where(
            and_(
                Story.visibility == "published",
                User.status == "active",
                or_(
                    search_condition,
                    Story.title.ilike(f"%{keyword}%")  # 备用：模糊搜索
                )
            )
        ).order_by(desc(Story.published_at))
        
        # 获取总数
        count_query = select(func.count()).select_from(Story).join(User, Story.user_id == User.id).where(
            and_(
                Story.visibility == "published",
                User.status == "active",
                or_(
                    search_condition,
                    Story.title.ilike(f"%{keyword}%")
                )
            )
        )
        
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        result = await session.execute(query.limit(limit).offset(offset))
        stories = list(result.scalars().all())
        
        return stories, total
