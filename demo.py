import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class NarrativeEvent:
    """叙事事件，资源用 Future 占位"""
    event_id: str
    text: str
    voice_future: asyncio.Future[str]      # 配音 URL 的 Future
    image_future: asyncio.Future[str]      # 图片 URL 的 Future
    character: Optional[str] = None

class NarrativeEngine:
    def __init__(self):
        self.narrative_queue: asyncio.Queue[NarrativeEvent] = asyncio.Queue()
        self.narrative_lock = asyncio.Event()
        self.narrative_lock.set()  # 初始释放
    
    async def produce_dialogue(self, dialogue_text: str, character: str):
        """生产一条对话（资源并发生成，事件立即入队）"""
        loop = asyncio.get_event_loop()
        
        # 1. 创建 Future 占位符
        voice_future = loop.create_future()
        image_future = loop.create_future()
        
        # 2. 立即创建事件并入队（此时资源还没生成完）
        event = NarrativeEvent(
            event_id=f"dialogue_{id(voice_future)}",
            text=dialogue_text,
            voice_future=voice_future,
            image_future=image_future,
            character=character,
        )
        await self.narrative_queue.put(event)
        print(f"📝 事件入队: {dialogue_text[:20]}...")
        
        # 3. 并发启动资源生产任务（非阻塞）
        asyncio.create_task(self._generate_voice(dialogue_text, voice_future))
        asyncio.create_task(self._generate_image(character, image_future))
    
    async def _generate_voice(self, text: str, future: asyncio.Future):
        """配音生成（模拟耗时操作）"""
        await asyncio.sleep(2)  # 模拟 TTS API 调用
        voice_url = f"https://tts.api/voice_{hash(text)}.mp3"
        future.set_result(voice_url)
        print(f"🎤 配音完成: {voice_url}")
    
    async def _generate_image(self, character: str, future: asyncio.Future):
        """立绘生成（模拟耗时操作）"""
        await asyncio.sleep(3)  # 模拟 AI 生图 API 调用
        image_url = f"https://img.api/{character}_{hash(character)}.png"
        future.set_result(image_url)
        print(f"🖼️ 图片完成: {image_url}")
    
    async def consume_narrative(self):
        """叙事消费者（顺序播放）"""
        while True:
            # 1. 从队列取事件（顺序）
            event = await self.narrative_queue.get()
            print(f"\n▶️ 开始处理: {event.text[:20]}...")
            
            # 2. 等待该事件的所有资源就绪
            voice_url, image_url = await asyncio.gather(
                event.voice_future,
                event.image_future,
            )
            print(f"✅ 资源就绪: voice={voice_url}, image={image_url}")
            
            # 3. 获取叙事锁（保证顺序播放）
            await self.narrative_lock.wait()
            self.narrative_lock.clear()
            
            # 4. 播放（阻塞直到完成或用户点击）
            await self._play_dialogue(event.text, voice_url, image_url)
            
            # 5. 释放叙事锁
            self.narrative_lock.set()
            self.narrative_queue.task_done()
    
    async def _play_dialogue(self, text: str, voice_url: str, image_url: str):
        """播放对话（模拟）"""
        print(f"🗣️ 播放对话: {text}")
        await asyncio.sleep(1)  # 模拟播放时间
        print(f"✔️ 播放完成")

# 使用示例
async def main():
    engine = NarrativeEngine()
    
    # 启动消费者
    consumer_task = asyncio.create_task(engine.consume_narrative())
    
    # 快速生产多个对话（几乎同时）
    await engine.produce_dialogue("你好，欢迎来到这个世界。", "narrator")
    await engine.produce_dialogue("我是你的向导，艾莉丝。", "alice")
    await engine.produce_dialogue("接下来的旅程会很有趣。", "alice")
    
    # 等待所有事件处理完
    await engine.narrative_queue.join()
    consumer_task.cancel()

asyncio.run(main())
