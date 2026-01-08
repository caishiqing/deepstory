"""
Ren'Py 离线项目生成测试

使用流式架构：
1. StoryEngine - 流式生成事件（事件包含资源 key）
2. RenpyConsumer - 等待资源就绪，下载资源，生成脚本

使用方式：
    python test_renpy.py [story_file] [project_path]
"""

import asyncio
import json
import os
import sys
from loguru import logger

from engine import (
    StoryEngine,
    StoryStartEvent,
    ChapterStartEvent,
    SceneStartEvent,
    DialogueEvent,
    NarrationEvent,
    AudioEvent,
    StoryEndEvent,
    RenpyConsumer,
    StoryInput,
)
from engine.models import Character, Relationship, StoryTags
from cache import init_redis, get_redis_client

# 资源等待超时配置（秒）
RESOURCE_TIMEOUT = 3600.0  # 1 小时


async def clear_all_redis_cache():
    """清空所有 Redis 缓存（story、tracker、task 相关）"""
    redis = get_redis_client()
    if redis is None:
        return

    # 清空所有相关缓存
    patterns = ["story:*", "tracker:*", "task:*", "queue:*"]
    deleted = 0

    for pattern in patterns:
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break

    logger.info(f"Cleared {deleted} Redis keys (all caches)")


async def monitor_task_status(engine, consumer, interval: float = 10.0):
    """监控任务队列和消费队列状态（后台任务）"""
    try:
        from cache import get_redis_client, RedisKeys
        redis = get_redis_client()

        while True:
            await asyncio.sleep(interval)

            status_parts = []

            # 1. 生产队列监控（Worker队列）
            if engine.task_manager and redis:
                queue_names = ["image_generation", "audio_processing"]
                queue_info = []

                for queue_name in queue_names:
                    # 直接查询 Redis
                    pending = await redis.llen(RedisKeys.queue(queue_name))
                    running = await redis.scard(RedisKeys.running_tasks(queue_name))

                    # 获取队列配置
                    stats = await engine.task_manager.get_queue_stats()
                    queue_stats = stats.get(queue_name, {})
                    max_jobs = queue_stats.get('max_concurrent_jobs', 0)

                    queue_info.append(f"{queue_name}[P:{pending} R:{running}/{max_jobs}]")

                status_parts.append("Workers: " + " | ".join(queue_info))

            # 2. 资源追踪器监控
            if engine.tracker:
                total = engine.tracker.total_count
                pending = engine.tracker.pending_count
                completed = total - pending
                status_parts.append(f"Resources[T:{total} P:{pending} D:{completed}]")

            # 3. 消费队列监控（asyncio.Queue）
            if hasattr(consumer, '_event_queue'):
                queue = consumer._event_queue
                queue_size = queue.qsize()
                status_parts.append(f"EventQueue[Size:{queue_size}]")

            # 4. 消费状态监控
            if hasattr(consumer, '_current_event') and consumer._current_event:
                event_type = consumer._current_event.get('type', 'unknown')
                waiting_for = consumer._current_event.get('waiting_for', '')
                status_parts.append(f"Consumer[Event:{event_type} Wait:{waiting_for}]")

            logger.info(f"📊 {' | '.join(status_parts)}")
    except asyncio.CancelledError:
        logger.debug("Task monitor stopped")
    except Exception as e:
        logger.error(f"Monitor error: {e}")


async def main(story_file: str, project_path: str):
    """主函数"""
    # 1. 加载故事数据
    logger.info(f"Loading story: {story_file}")
    with open(story_file, encoding="utf-8") as f:
        story_data = json.load(f)
        story_data["characters"] = story_data["roles"]

    # 将字典转换为 StoryInput 模型
    story_input = StoryInput(
        logline=story_data.get("logline", ""),
        characters=[Character(**char) for char in story_data.get("characters", [])],
        tags=StoryTags(**story_data.get("tags", {})),
        relationships=[Relationship(**rel) for rel in story_data.get("relationships", [])] if story_data.get("relationships") else None
    )

    # 生成请求 ID
    import hashlib
    request_id = hashlib.md5(story_file.encode()).hexdigest()[:8]

    # 2. 初始化 Redis
    try:
        await init_redis()
        logger.info("Redis initialized")
    except Exception as e:
        logger.warning(f"Redis init failed: {e}")

    # 3. 清空所有缓存
    await clear_all_redis_cache()

    # 4. 创建引擎
    engine = StoryEngine(
        story_input=story_input,
        request_id=request_id,
        narration_voice="story-tell-man"
    )

    try:
        # 5. 初始化引擎
        await engine.initialize()

        # 6. 创建 Ren'Py 脚本生成器（继承了流式消费功能）
        renpy_consumer = RenpyConsumer(engine.tracker, project_path)

        # 7. 清空任务队列
        cleared = await engine.task_manager.clear_all_queues()
        logger.info(f"Cleared task queues: {cleared}")

        # 8. 启动 Workers 处理任务队列
        await engine.task_manager.start_workers({
            "image_generation": 2,  # 2个图像生成worker
            "audio_processing": 3   # 3个音频处理worker
        })
        logger.info("✅ Workers started successfully")

        # 9. 启动任务监控（后台任务，传入 consumer 用于监控消费队列）
        monitor_task = asyncio.create_task(monitor_task_status(engine, renpy_consumer, interval=10.0))
        logger.info("Started background task monitor (every 10 seconds)")

        # 10. 流式处理事件（顺序等待资源就绪，与 SSE 逻辑一致）
        logger.info("Processing events (waiting for resources)...")
        event_count = 0
        current_chapter = None
        current_scene = None
        story_prompt_saved = False  # 标记故事提示词是否已保存

        # 为了提高下载速度，我们可以创建一个下载任务池
        download_tasks = set()

        # 使用 RenpyConsumer 的流式功能等待资源就绪（超时 3600 秒）
        async for event in renpy_consumer.stream(engine):
            event_count += 1
            logger.debug(f"Event: {event.event_type}")

            # 收到第一个事件时，think 和 script 已完成，立刻保存故事提示词
            if not story_prompt_saved:
                os.makedirs("logs/scripts", exist_ok=True)
                story_name = os.path.splitext(os.path.basename(story_file))[0]
                with open(f"logs/scripts/{story_name}.txt", "w", encoding="utf-8") as f:
                    f.write(engine.story_prompt)
                logger.info(f"✅ Story prompt saved: logs/scripts/{story_name}.txt")
                story_prompt_saved = True

            # 根据事件类型处理并添加到 Ren'Py 脚本
            if isinstance(event, ChapterStartEvent):
                # 结束上一个章节
                if current_chapter is not None:
                    logger.info(f"📕 Chapter {current_chapter} ended")

                # 开始新章节
                current_chapter = event.chapter_index
                logger.info("=" * 80)
                logger.info(f"📖 Chapter {event.chapter_index} started: {event.title}")
                logger.info("=" * 80)
                renpy_consumer.add_chapter(event.chapter_index, event.title)

            elif isinstance(event, SceneStartEvent):
                # 结束上一个场景
                if current_scene is not None:
                    logger.info(f"🎬 Scene {current_scene} ended")

                # 开始新场景
                current_scene = event.scene_index
                logger.info("-" * 80)
                logger.info(f"🎬 Scene {event.scene_index} started: {event.title}")
                logger.info(f"   Location: {event.location}, Time: {event.time}")
                logger.info("-" * 80)
                # 下载背景图（如果有 URL）
                if event.background_url:
                    # 使用异步任务下载，不阻塞事件推送逻辑
                    task = asyncio.create_task(renpy_consumer.download_and_save(
                        url=event.background_url,
                        resource_type="image",
                        tag="bg",
                        attribute=event.bg_id,
                        key=event.background_key
                    ))
                    download_tasks.add(task)
                    task.add_done_callback(download_tasks.discard)
                renpy_consumer.add_scene(event.scene_index, event.bg_id)

            elif isinstance(event, AudioEvent):
                # 下载音频（如果有 URL）
                if event.audio_url:
                    tag_prefix = {"music": "m", "ambient": "a", "sound": "s"}.get(event.channel, "x")
                    task = asyncio.create_task(renpy_consumer.download_and_save(
                        url=event.audio_url,
                        resource_type="audio",
                        tag=tag_prefix,
                        key=event.audio_key
                    ))
                    download_tasks.add(task)
                    task.add_done_callback(download_tasks.discard)
                    renpy_consumer.add_audio(event.channel, event.audio_key)

            elif isinstance(event, DialogueEvent):
                # 下载配音（如果有 URL）
                if event.voice_url:
                    task = asyncio.create_task(renpy_consumer.download_and_save(
                        url=event.voice_url,
                        resource_type="voice",
                        tag="d",
                        key=event.voice_key
                    ))
                    download_tasks.add(task)
                    task.add_done_callback(download_tasks.discard)

                # 下载立绘（如果有 URL），使用完整 result 按需下载情绪图片
                if event.image_url:
                    # 优先使用完整 result（PortraitResourceResult，包含所有情绪图片）
                    result = getattr(event, '_portrait_result', None) or getattr(event, '_image_result', None)
                    task = asyncio.create_task(renpy_consumer.download_and_save(
                        result=result if result else event.image_url,
                        url=event.image_url if not result else None,
                        resource_type="image",
                        tag=event.character_tag,
                        attribute=event.emotion,  # 传入情绪，用于按需下载
                        key=event.image_key
                    ))
                    download_tasks.add(task)
                    task.add_done_callback(download_tasks.discard)

                renpy_consumer.add_dialogue(
                    event.character,
                    event.character_tag,
                    event.text,
                    event.emotion,
                    voice_key=event.voice_key
                )

            elif isinstance(event, NarrationEvent):
                # 下载旁白配音（如果有 URL）
                if event.voice_url:
                    task = asyncio.create_task(renpy_consumer.download_and_save(
                        url=event.voice_url,
                        resource_type="voice",
                        tag="n",
                        key=event.voice_key
                    ))
                    download_tasks.add(task)
                    task.add_done_callback(download_tasks.discard)

                renpy_consumer.add_narration(event.text, voice_key=event.voice_key)

            elif isinstance(event, StoryEndEvent):
                # 结束最后一个场景和章节
                if current_scene is not None:
                    logger.info(f"🎬 Scene {current_scene} ended")
                if current_chapter is not None:
                    logger.info(f"📕 Chapter {current_chapter} ended")

                logger.info("=" * 80)
                logger.info("🎉 Story completed!")
                logger.info("=" * 80)
                renpy_consumer.add_ending()

        # 停止任务监控
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # 等待所有剩余下载任务完成
        if download_tasks:
            logger.info(f"Waiting for {len(download_tasks)} remaining downloads...")
            await asyncio.gather(*download_tasks, return_exceptions=True)

        logger.info("=" * 80)
        logger.info(f"✅ Processed {event_count} events")
        logger.info(f"✅ Downloaded resources: {renpy_consumer.downloaded_count}")
        logger.info(f"✅ Downloading resources: {renpy_consumer.downloading_count}")
        logger.info("=" * 80)

        # 11. 生成脚本（使用已下载的资源，缺失的资源会被跳过）
        logger.info("Generating Ren'Py script...")
        renpy_consumer.save_script(engine.title or "故事开始")

        # 12. 打印最终统计
        logger.info("=" * 80)
        logger.info("🎊 Generation completed successfully!")
        logger.info("=" * 80)
        logger.info(f"📊 Statistics:")
        logger.info(f"  - Total events: {event_count}")
        logger.info(f"  - Downloaded resources: {renpy_consumer.downloaded_count}")
        logger.info(f"  - Project path: {project_path}")
        logger.info(f"  - Script file: {project_path}/script.rpy")
        logger.info("=" * 80)

    finally:
        # 13. 关闭引擎
        if engine:
            await engine.shutdown()
        logger.info("🏁 Engine shutdown complete")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        story_file = sys.argv[1]
        project_path = sys.argv[2]
    else:
        story_file = r"data/草鞋权贵.json"
        project_path = "projects/demo/game"

    asyncio.run(main(story_file, project_path))
