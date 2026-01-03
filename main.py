import datetime
import hashlib
import random
import json
import os
import asyncio
import tempfile

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
    name = "ChatBanter", 
    author = "Bricks0411", 
    desc = "群聊娱乐小插件，包含迫害群友、特殊问候和今日运势等功能。", 
    version = "0.0.5",
    repo = "https://github.com/bricks0411/ChatBanter.git"
)

class ChatBanter(Star):
    def __init__(self, context: Context):
        self.rank_file = os.path.join(
            "data", 
            "plugins",
            "test_plugin-main",
            "fortune_rank.json"
        )
        # 初始化锁
        self.rank_lock = asyncio.Lock()
        # 初始化配置文件
        self.config = self.load_config()
        super().__init__(context)

    def load_config(self):
        """可选择实现同步的配置加载方法，当插件被加载/启用时会调用该方法。"""
        if not os.path.exists(self.config_file):
            logger.info("[info] 配置文件不存在，创建默认配置文件。")
            dir_path = os.path.dirname(self.config_file)
            default_config = {
                "fortune_prompt_for_LLM": {
                    "今天是 {date}，有个名字叫 {user_name} 的人，Ta 今天的运势是 {luck_level}，幸运值是 {luck_value}\n",
                    "请你锐评一下这个人今天的运势，并告诉 Ta 今天适合做什么事，不适合做什么事\n"
                    "在生成评价的过程中，严格按照下面的要求进行：\n"
                    "1.不能提起今天的幸运值数字，只能提起运势等级\n"
                    "2.评价内容必须符合给出的运势等级，不能过于夸张或贬低\n"
                    "3.如果在今天之内，这个人已经多次询问运势，请你在评价中提及这一点，并根据 Ta 的行为适当调整评价内容，允许表达不满，但需要注意分寸，不能让 Ta 感到被冒犯\n"
                    "4.生成的评价不需要过于正式，允许带有调侃和幽默风格，同时可以适当使用表情符号、颜文字等\n"
                    "5.你可以提及关于 Ta 今天可能过得怎么样，但一定要保证积极向上，即使 Ta 的运势不佳，也要给 Ta 一些鼓励和希望\n"
                    "6.评价中不允许包含AI助手/大模型等词语\n"
                    "请严格按照你的人格设定生成评价，回答需精炼简洁，尽量不超过70字\n"
                }
            }
            os.makedirs(dir_path, exist_ok = True)
            with open(self.config_file, "w", encoding = "utf-8") as f:
                json.dump(default_config, f, ensure_ascii = False, indent = 2)
            return default_config
        
        with open(self.config_file, "r", encoding = "utf-8") as f:
            logger.info("[info] 配置文件加载成功。")
            return json.load(f)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 伪造指令，基本格式为 @bot /说 @目标用户 [消息内容]
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("说")
    async def FakeMessage(self, event: AstrMessageEvent):
        """伪造群成员消息，仅供娱乐使用。"""                             # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
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
        """这是一个 处理 早上好/晚安 的函数"""                             # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        # message_str = event.message_str                              # 用户发的纯文本消息字符串
        # message_chain = event.get_messages()                         # 用户所发的消息的消息链 # from astrbot.api.message_components import *

        user_name = event.get_sender_name()                            # 发送消息的用户名称
        text = event.message_str.strip()

        if not text:
            logger.info("空消息。")
            return
        
        # 判断触发关键字
        if any(key in text for key in TRIGGERS_GOOD_MORNING):
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
        user_id = str(event.get_sender_id())            # 获取用户 QQ 号
        user_name = event.get_sender_name()             # 获取用户名称

        # 获取日期
        today = datetime.date.today().isoformat()

        # 随机数种子：用户 QQ 号 + 日期
        seed_str = user_id + today
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
        random.seed(seed)

        # 今日幸运值（由刚才的种子生成，范围为1 ~ 100）
        luck_value = random.randint(1, 100)

        luck_level = self._luck_level(luck_value)       # 返回幸运等级
        good = random.choice(self._good_list())         # 返回今日宜做的事情
        bad = random.choice(self._bad_list())           # 返回今日忌做的事情

        template_prompt = self.config.get("fortune_prompt_for_LLM", "")
        if template_prompt:
            logger.info("[info] 运势提示词读取成功！使用自定义提示词。")
            prompt = template_prompt.format(
                date = today,
                user_name = user_name,
                luck_level = luck_level,
                luck_value = luck_value
            )
        else:
            logger.warning("[info] 未在配置文件中找到运势提示词，使用默认提示词。")
            prompt = (
                f"今天是 {today}，有个名字叫 {user_name} 的人，Ta 今天的运势是 {luck_level}，幸运值是 {luck_value}\n"
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
        # 调用 LLM 接口，传入 prompt，获取评价内容
        # 伪代码示例：
        # evaluation = await call_LLM_api(prompt)
        # result += f"\n📝 今日评价：{evaluation}"

        fortune_result = await self.context.llm_generate(
            chat_provider = provider_id,
            prompt = prompt,
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
            f"📝 今日评价：{fortune_result.completion_text}\n"
        )

        yield event.plain_result(result)

        await self._update_rank(user_id, user_name, luck_value, today)


    @filter.command("运势排行", alias = {'今日运势排行', '运势排行榜'})
    async def FortuneRank(self, event: AstrMessageEvent):
        """处理今日运势排行榜，群成员输入指令触发"""
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

    # 列表：宜    
    def _good_list(self):
        return [
            "摸鱼",
            "水群",
            "写 BUG",
            "拖延",
            "看番",
            "打游戏",
            "加训",
            "发呆"
        ]

    # 列表：忌
    def _bad_list(self):
        return [
            "写文档",
            "改需求",
            "修 BUG",
            "加班",
            "早起",
            "开会",
            "摆烂",
            "调戏 Asuka"
        ]

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

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
