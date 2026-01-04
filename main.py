import datetime
import hashlib
import random
import json
import os
import asyncio
import tempfile

from typing import Dict, Any, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At, Plain, Node

TRIGGERS_GOOD_NIGHT = {
    "晚安",
    "goodnight",
    "Goodnight",
    "good night",
    "Good night",
    "晚安咯",
    "wanan"
}

TRIGGERS_GOOD_MORNING = {
    "早上好",
    "goodmorning",
    "Goodmorning",
    "good morning",
    "Good morning",
    "早上好啊",
    "早安"
}

# 插件信息注册
@register(
    "astrbot_plugin_chat_banter", 
    "Bricks0411", 
    "群聊娱乐小插件，包含迫害群友、特殊问候和今日运势等功能，支持WebUI配置。", 
    "v0.1.0",
)

class ChatBanter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 配置文件路径
        self.config_file = os.path.join(
            "data", 
            "plugins", 
            "ChatBanter", 
            "config.json"
        )
        # 排行榜文件路径
        base_dir = os.path.dirname(self.config_file)
        self.rank_file = os.path.join(base_dir, "fortune_rank.json")
        # 初始化锁
        self.rank_lock = asyncio.Lock()
        # 初始化配置文件
        self.config = self.load_config()

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        pass

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        DEFAULT_CONFIG: Dict[str, Any] = {
            "features": {
                "enable_fake_message": True,
                "enable_greetings": True,
                "enable_fortune": True,
                "enable_rank": True
            },
            "fortune": {
                "max_per_day": 0,
                "prompt_for_LLM": {
                    "max_per_day": 0,
                    "prompt": [
                        "今天是 {date}，有个名字叫 {user_name} 的人，Ta 今天的运势是 {luck_level}，幸运值是 {luck_value}\n",
                        "请你锐评一下这个人今天的运势，并告诉 Ta 今天适合做什么事，不适合做什么事\n",
                        "在生成评价的过程中，严格按照下面的要求进行：\n",
                        "1.不能提起今天的幸运值数字，只能提起运势等级\n",
                        "2.评价内容必须符合给出的运势等级，不能过于夸张或贬低\n",
                        "3.如果在今天之内，这个人已经多次询问运势，请你在评价中提及这一点，并根据 Ta 的行为适当调整评价内容，允许表达不满，但需要注意分寸，不能让 Ta 感到被冒犯\n",
                        "4.生成的评价不需要过于正式，允许带有调侃和幽默风格，同时可以适当使用表情符号、颜文字等\n",
                        "5.你可以提及关于 Ta 今天可能过得怎么样，但一定要保证积极向上，即使 Ta 的运势不佳，也要给 Ta 一些鼓励和希望\n",
                        "6.评价中不允许包含AI助手/大模型等词语\n",
                        "请严格按照你的人格设定生成评价，回答需精炼简洁，尽量不超过70字\n"
                    ]
                },
                "custom_good_list": [
                    "摸鱼",
                    "喝茶",
                    "散步",
                    "聊天",
                    "听音乐"
                ],
                "custom_bad_list": [
                    "加班",
                    "写报告",
                    "开会",
                    "熬夜",
                    "赶项目"
                ],    
            },
            "greetings": {
                "good_morning": [
                    "哼，早上好呀，{user_name}。\n昨晚睡得还好吗？别、别误会，我才不是关心你，只是觉得你要是迟到会很丢脸而已。\n\n快去洗漱吃早饭，打起精神来。\n今天也要好好表现，听到了没有？"
                ],
                "good_night": [
                    "晚，晚安啦，{user_name}！\n别误会，我可不是担心你，只是……今天看你还算努力。\n早点睡，明天要是状态不好，可是会拖后腿的，知道吗？\n……还有，别熬夜想些乱七八糟的事。\n好好休息，才、才不准做噩梦呢……\n\n（小声）\n……晚安。要是做梦的话，也给我做个像样点的。"
                ]
            },
            "custom_actions": {
                "摸鱼": "摸鱼一时爽，一直摸鱼一直爽！",
                "水群": "水群可以，但别忘了正事哦~",
                "写 BUG": "今天的BUG写得怎么样了？"
            }
        }
        
        # 确保配置文件目录存在
        os.makedirs(os.path.dirname(self.config_file), exist_ok = True)
        if not os.path.exists(self.config_file):
            with open(self.config_file, "w", encoding = "utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii = False, indent = 2)
                logger.info("[info] 配置文件不存在，已创建默认配置文件。")
            return DEFAULT_CONFIG.copy()
        # 加载用户配置文件
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)

            logger.info("[info] 配置文件加载成功，正在校验结构。")
            # 递归合并默认配置和用户配置
            merged_config = self._deep_merge(DEFAULT_CONFIG, user_config)
            return merged_config

        except Exception as e:
            logger.error(f"[error] 加载配置文件失败，使用默认配置: {e}")
            return DEFAULT_CONFIG.copy()

    def save_config(self, new_config: Dict[str, Any]) -> bool:
        """保存配置文件"""
        try:
            dir_path = os.path.dirname(self.config_file)
            os.makedirs(dir_path, exist_ok = True)
            
            # 备份旧配置
            if os.path.exists(self.config_file):
                import shutil
                backup_file = self.config_file + ".bak"
                shutil.copy2(self.config_file, backup_file)
            
            # 写入新配置
            with open(self.config_file, "w", encoding = "utf-8") as f:
                json.dump(new_config, f, ensure_ascii = False, indent = 2)
            
            # 更新内存中的配置
            self.config = new_config
            logger.info("[info] 配置文件保存成功。")
            return True
        except Exception as e:
            logger.error(f"[error] 保存配置文件失败: {e}")
            return False

    def get_fortune_prompt(self) -> str:
        """获取用于生成运势评价的提示词模板"""
        fortune = self.config.get("fortune", {})
        # 获取 prompt_for_LLM 配置
        pconf = fortune.get("prompt_for_LLM", {})

        if not isinstance(pconf, dict):
            return ""

        prompt = pconf.get("prompt", [])        # 获取 prompt 字段
        # 将列表拼接为字符串
        if isinstance(prompt, list):
            return "".join(prompt)
        elif isinstance(prompt, str):
            return prompt
        return ""

    # ========== WebUI 配置相关方法 ==========

    async def get_config_data(self) -> Dict[str, Any]:
        """返回当前配置数据"""
        return self.config.copy()

    def _deep_merge(self, base: dict, patch: dict) -> dict:
        """
        递归合并配置：
        - patch 中的值会覆盖 base
        - 只覆盖提供的字段，不破坏其他嵌套结构
        """
        result = base.copy()
        for key, value in patch.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


    async def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 合并新旧配置，保留新配置中没有的旧配置
            merged_config = self._deep_merge(self.config, new_config)
            
            # 保存配置
            success = self.save_config(merged_config)
            if success:
                logger.info("[info] 配置更新成功")
            return success
        except Exception as e:
            logger.error(f"[error] 更新配置失败: {e}")
            return False

    # ========== 主要的四个功能 ==========

    # 伪造指令，基本格式为 @bot /说 @目标用户 [消息内容]
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("说")
    async def FakeMessage(self, event: AstrMessageEvent):
        """伪造群成员消息，仅供娱乐使用。"""
        # 检查功能是否启用
        features = self.config.get("features", {})
        if not features.get("enable_fake_message", True):
            logger.info("[info] 伪造消息功能未启用。")
            return
            
        messages = event.get_messages()
        # 目标用户
        target_at = None
        # 消息内容
        content_parts = []
        # 艾特列表
        at_list = []
        # 解析消息，并判断消息合法性
        for msg in messages:
            if isinstance(msg, At):
                at_list.append(msg)
            elif isinstance(msg, Plain):
                content_parts.append(msg.text)
        # 检查是否为 @bot 后跟 @目标用户
        if len(at_list) < 2:
            yield event.plain_result("谁让你艾特我了，哼(｀ω´ )")
            return
        elif len(at_list) > 2:
            yield event.plain_result("一次只能艾特一个人！")
            return
        # 获取目标用户
        target_at = at_list[1]
        if not target_at:
            yield event.plain_result("请 @ 一个用户")
            return
        
        content = "".join(content_parts).strip()
        # 去掉开头的指令
        content = content.replace("/说", "", 1).strip()
            
        if not content:
            yield event.plain_result("内容不能为空！")
            return
            
        node = Node (
            uin = target_at.qq,
            name = target_at.name,
            content = [Plain(content)]
        )
        # 写入日志
        logger.info(
            f"[fake_say] by={event.get_sender_name()} "
            f"target={target_at.qq} "
            f"content={content}"
        )
        yield event.chain_result([node])
        return

    # 注册指令的装饰器。触发关键字成功后，发送 任何包含关键字的语句 就会触发这个指令，并回复对应的内容
    @filter.event_message_type (
            filter.EventMessageType.GROUP_MESSAGE |
            filter.EventMessageType.PRIVATE_MESSAGE
    )
    async def SpecialGreeting(self, event: AstrMessageEvent):
        """这是一个 处理 早上好/晚安 的函数"""
        # 检查功能是否启用
        features = self.config.get("features", {})
        if not features.get("enable_greetings", True):
            logger.info("[info] 问候功能未启用。")
            return
            
        user_name = event.get_sender_name()                            # 发送消息的用户名称
        text = event.message_str.strip()

        if not text:
            logger.info("空消息。")
            return
        
        # 判断触发关键字
        if any(key in text for key in TRIGGERS_GOOD_MORNING):
            greetings = self.config.get("greetings", {})
            responses = greetings.get("good_morning", [])
            if responses:
                # 随机选择一条回复
                template = random.choice(responses)
                result = template.format(user_name=user_name)
            else:
                # 默认回复
                result = (
                    f"哼，早上好呀，{user_name}。\n"
                    "昨晚睡得还好吗？别、别误会，我才不是关心你，只是觉得你要是迟到会很丢脸而已。\n"

                    "\n快去洗漱吃早饭，打起精神来。\n"
                    "今天也要好好表现，听到了没有？\n"
                )
            # 日志记录
            logger.info(
                f"[goodMorning] trigger | "
                f"user={user_name} | "
                f"text={text}"
            )
            yield event.plain_result(result)                    # 发送一条纯文本消息
            return
        elif any(key in text for key in TRIGGERS_GOOD_NIGHT):
            greetings = self.config.get("greetings", {})
            responses = greetings.get("good_night", [])
            if responses:
                # 随机选择一条回复
                template = random.choice(responses)
                result = template.format(user_name=user_name)
            else:
                # 默认回复
                result = (
                    f"晚，晚安啦，{user_name}！\n"
                    "别误会，我可不是担心你，只是……今天看你还算努力。\n"
                    "早点睡，明天要是状态不好，可是会拖后腿的，知道吗？\n"
                    "……还有，别熬夜想些乱七八糟的事。\n"
                    "好好休息，才、才不准做噩梦呢……\n"

                    "\n（小声）\n"
                    "……晚安。要是做梦的话，也给我做个像样点的。"
                )
            # 日志记录
            logger.info(
                f"[goodNight] trigger | "
                f"user={user_name} | "
                f"text={text}"
            )
            yield event.plain_result(result)                   # 发送一条纯文本消息
            return

    @filter.command("今日运势", alias = {'运势'})
    async def TodayFortune(self, event: AstrMessageEvent):
        """处理今日运势，群成员艾特后输入指令触发"""
        # 检查功能是否启用
        features = self.config.get("features", {})
        if not features.get("enable_fortune", True):
            logger.info("[info] 今日运势功能未启用。")
            return
            
        user_id = str(event.get_sender_id())            # 获取用户 QQ 号
        user_name = event.get_sender_name()             # 获取用户名称

        # 检查每日查询次数限制
        fortune = self.config.get("fortune", {})
        max_queries = fortune.get("max_per_day", 0)
        if max_queries > 0:
            today = datetime.date.today().isoformat()
            query_count = await self._get_user_query_count(user_id, today)
            if query_count >= max_queries:
                yield event.plain_result(f"❌ 你今天已经查询过 {query_count} 次运势了，明天再来吧！")
                return

        # 获取日期
        today = datetime.date.today().isoformat()

        # 随机数种子：用户 QQ 号 + 日期
        seed_str = user_id + today
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        random.seed(seed)

        # 今日幸运值（由刚才的种子生成，范围为1 ~ 100）
        luck_value = random.randint(1, 100)

        luck_level = self._luck_level(luck_value)       # 返回幸运等级
        
        # 使用自定义列表或默认列表
        fortune = self.config.get("fortune", {})
        good_list = fortune.get("custom_good_list", [])
        bad_list = fortune.get("custom_bad_list", [])

        good = random.choice(good_list) if good_list else "摸鱼"
        bad = random.choice(bad_list) if bad_list else "加班"

        # 获取 provider 标识符
        provider_identifier = await self._get_provider_identifier(event)
        
        fortune_text = ""

        if not provider_identifier:
            fortune_text = "❌ 抱歉，当前无法连接到 AI 服务，请稍后再试。"
        else:
            # 生成运势评价
            fortune_text = await self._generate_fortune_evaluation(
                provider_identifier, today, user_name, luck_level, luck_value
            )
        
        # 额外逻辑：若为大吉，则诸事皆宜
        if luck_value >= 90:
            good = "诸事皆宜"
            bad = "无"

        result = (
            f"【今日运势】\n"
            f"用户：{user_name}\n"
            f"🍀 今日人品：{luck_value}\n"
            f"📈 运势：{luck_level}\n"
            f"✅ 宜：{good}\n"
            f"❌ 忌：{bad}\n"
            f"📝 今日评价：{fortune_text}\n"
        )

        yield event.plain_result(result)

        # 更新查询计数
        if max_queries > 0:
            await self._update_query_count(user_id, today)
        
        # 更新排行榜
        features = self.config.get("features", {})
        if features.get("enable_rank", True):
            await self._update_rank(user_id, user_name, luck_value, today)

    @filter.command("运势排行", alias = {'今日运势排行', '运势排行榜'})
    async def FortuneRank(self, event: AstrMessageEvent):
        """处理今日运势排行榜，群成员输入指令触发"""
        # 检查功能是否启用
        features = self.config.get("features", {})
        if not features.get("enable_rank", True):
            logger.info("[info] 运势排行榜功能未启用。")
            return
            
        # 获取日期
        today = datetime.date.today().isoformat()
        # 读取排行数据
        rank_data = self._load_rank()

        # 检查今日是否有数据
        if today not in rank_data or not rank_data[today]:
            yield event.plain_result("📊 今日还没有人抽运势哦～")
            return
        
        # 按幸运值排序，取前十名
        sorted_users = sorted(
            rank_data[today].values(),
            key = lambda x: x["luck"],
            reverse = True
        )[:10]

        medals = ["🥇", "🥈", "🥉"]
        lines = ["【今日运势排行榜】"]
        # 生成排行榜文本
        for i, user in enumerate(sorted_users):
            prefix = medals[i] if i < 3 else f"{i + 1}️⃣"
            lines.append(f"{prefix} {user['name']}  {user['luck']}")
        # 发送结果
        yield event.plain_result("\n".join(lines))

    # ========== 辅助方法 ==========

    def _extract_provider_identifier(self, provider) -> Optional[str]:
        """从 provider 对象中提取标识符"""
        # 从 provider_settings 获取
        if hasattr(provider, 'provider_settings'):
            settings = provider.provider_settings
            if isinstance(settings, dict):
                for key in ['name', 'provider_name', 'id']:
                    if key in settings and settings[key]:
                        return str(settings[key])
        
        # 从 provider_config 获取
        if hasattr(provider, 'provider_config'):
            config = provider.provider_config
            if isinstance(config, dict):
                for key in ['name', 'provider_name', 'id']:
                    if key in config and config[key]:
                        return str(config[key])
        
        # 使用类名
        import re
        class_name = type(provider).__name__
        # 去掉常见后缀
        class_name = re.sub(r'(Provider|Official|Client)$', '', class_name)
        # 驼峰转下划线小写
        identifier = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
        
        return identifier
    
    async def _get_provider_identifier(self, event) -> Optional[str]:
        """获取 provider 标识符"""
        try:
            # 获取当前正在使用的 provider
            if hasattr(event, 'unified_msg_origin'):
                provider = self.context.get_using_provider(umo=event.unified_msg_origin)
                if provider:
                    # 从 provider 的配置中获取名称
                    identifier = self._extract_provider_identifier(provider)
                    if identifier:
                        logger.info(f"[info] 获取到 provider 标识符: {identifier}")
                        return identifier
            
            # 如果没有获取到，查找所有可用的 LLM providers
            providers = self.context.get_available_providers()
            if providers:
                # 查找第一个 LLM 类型的 provider
                for prov in providers:
                    if hasattr(prov, 'type') and prov.type == 'llm':
                        identifier = self._extract_provider_identifier(prov)
                        if identifier:
                            return identifier
                
                # 如果没有明确标记为 LLM 的 provider，使用第一个
                identifier = self._extract_provider_identifier(providers[0])
                if identifier:
                    return identifier
            
            # 尝试常见的标识符
            common_identifiers = ["default", "llm", "chat", "ai"]
            for identifier in common_identifiers:
                try:
                    test_result = await self.context.llm_generate(
                        chat_provider_id=identifier,
                        prompt="test",
                    )
                    return identifier
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"[error] 获取 provider 标识符失败: {e}")
        
        return None

    async def _generate_fortune_evaluation(self, provider_id, date, user_name, luck_level, luck_value):
        """生成运势评价"""
        template_prompt = self.get_fortune_prompt()
        # 使用默认提示词模板（如果配置中没有提供）
        if not template_prompt:
            template_prompt = (
                "今天是 {date}，有个名字叫 {user_name} 的人，Ta 今天的运势是 {luck_level}，幸运值是 {luck_value}\n"
                "请你锐评一下这个人今天的运势，并告诉 Ta 今天适合做什么事，不适合做什么事\n"
                "在生成评价的过程中，严格按照下面的要求进行：\n"
                "1.不能提起今天的幸运值数字，只能提起运势等级\n"
                "2.评价内容必须符合给出的运势等级，不能过于夸张或贬低\n"
                "3.如果在今天之内，这个人已经多次询问运势，请你在评价中提及这一点，并根据 Ta 的行为适当调整评价内容，允许表达不满，但需要注意分寸，不能让 Ta 感到被冒犯\n"
                "4.生成的评价不需要过于正式，允许带有调侃和幽默风格，同时可以适当使用表情符号、颜文字等\n"
                "5.你可以提及关于 Ta 今天可能过得怎么样，但一定要保证积极向上，即使 Ta 的运势不佳，也要给 Ta 一些鼓励和希望\n"
                "6.评价中不允许包含AI助手/大模型等词语\n"
                "请严格按照你的人格设定生成评价，回答需精炼简洁，尽量不超过70字\n"
            )
        
        prompt = template_prompt.format(
            date        = date,
            user_name   = user_name,
            luck_level  = luck_level,
            luck_value  = luck_value
        )
        
        try:
            fortune_result = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            
            if hasattr(fortune_result, 'completion_text'):
                return fortune_result.completion_text
            elif isinstance(fortune_result, str):
                return fortune_result
            else:
                return "今天运势不错，但要保持乐观哦！"
                
        except Exception as e:
            logger.error(f"[error] 调用 LLM 失败: {e}")
            return "今天运势不错，但要保持乐观哦！"

    async def _get_user_query_count(self, user_id: str, date: str) -> int:
        """获取用户当天的查询次数"""
        query_file = os.path.join(os.path.dirname(self.config_file), "query_count.json")
        try:
            if os.path.exists(query_file):
                with open(query_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get(date, {}).get(user_id, 0)
        except:
            pass
        return 0

    async def _update_query_count(self, user_id: str, date: str):
        """更新用户查询次数"""
        query_file = os.path.join(os.path.dirname(self.config_file), "query_count.json")
        try:
            if os.path.exists(query_file):
                with open(query_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
            
            data.setdefault(date, {})
            data[date][user_id] = data[date].get(user_id, 0) + 1
            
            with open(query_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[error] 更新查询次数失败: {e}")

    # 幸运等级
    def _luck_level(self, value: int) -> str:
        if value >= 90:
            return "大吉"
        elif value >= 80:
            return "中吉"
        elif value >= 50:
            return "小吉"
        elif value >= 30:
            return "平"
        else:
            return "凶"
    
    # 排行榜更新：添加锁机制，保证写操作满足原子性
    async def _update_rank(self, user_id, user_name, luck, today):
        async with self.rank_lock:
            data = self._load_rank()

            data.setdefault(today, {})
            data[today][user_id] = {
                "name": user_name,
                "luck": luck
            }

            self._save_rank(data)

    # 载入排行文件（json）
    def _load_rank(self):
        if not os.path.exists(self.rank_file):
            return {}
        with open(self.rank_file, "r", encoding = "utf-8") as f:
            return json.load(f)

    # 写入排行文件
    def _save_rank(self, data):
        dir_path = os.path.dirname(self.rank_file)
        os.makedirs(dir_path, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dir_path,
            delete=False
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        os.replace(tmp_path, self.rank_file)

    # 注册指令装饰器
    @filter.command("add")
    async def GetSum(self, event: AstrMessageEvent, a: int, b: int):
        """计算两个整数的和"""
        yield event.plain_result(f"结果是：{a + b}！")

    @filter.command("sub")
    async def GetMinus(self, event: AstrMessageEvent, a: int, b: int):
        """计算两个整数的差"""
        yield event.plain_result(f"结果是：{a - b}！")

    # 插件销毁方法
    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        pass