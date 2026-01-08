"""
创意数据访问对象
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.story_prompt import StoryPrompt
from backend.utils.id_generator import generate_prompt_id


class PromptDAO:
    """创意 DAO"""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: str,
        logline: str,
        characters: list,
        character_inputs: list,
        relationships: Optional[list],
        themes: dict
    ) -> StoryPrompt:
        """
        创建创意

        Args:
            session: 数据库会话
            user_id: 用户ID
            logline: 一句话梗概
            characters: 角色ID列表
            character_inputs: 用户输入的角色原始信息
            relationships: 角色关系列表
            themes: 主题配置

        Returns:
            StoryPrompt: 新创建的创意对象
        """
        prompt = StoryPrompt(
            id=generate_prompt_id(),
            user_id=user_id,
            logline=logline,
            characters=characters,
            character_inputs=character_inputs,
            relationships=relationships or [],
            themes=themes,
        )

        session.add(prompt)
        await session.flush()

        return prompt

    @staticmethod
    async def get_by_id(session: AsyncSession, prompt_id: str) -> Optional[StoryPrompt]:
        """根据ID获取创意"""
        result = await session.execute(
            select(StoryPrompt).where(StoryPrompt.id == prompt_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_prompts(
        session: AsyncSession,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[StoryPrompt]:
        """获取用户的创意列表"""
        result = await session.execute(
            select(StoryPrompt)
            .where(StoryPrompt.user_id == user_id)
            .order_by(StoryPrompt.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    @staticmethod
    async def update(
        session: AsyncSession,
        prompt_id: str,
        logline: Optional[str] = None,
        characters: Optional[list] = None,
        character_inputs: Optional[list] = None,
        relationships: Optional[list] = None,
        themes: Optional[dict] = None
    ) -> bool:
        """更新创意"""
        prompt = await PromptDAO.get_by_id(session, prompt_id)
        if not prompt:
            return False

        if logline is not None:
            prompt.logline = logline
        if characters is not None:
            prompt.characters = characters
        if character_inputs is not None:
            prompt.character_inputs = character_inputs
        if relationships is not None:
            prompt.relationships = relationships
        if themes is not None:
            prompt.themes = themes

        await session.flush()
        return True
