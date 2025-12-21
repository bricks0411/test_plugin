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
    "test_plugin", 
    "Bricks0411", 
    "测试插件——仅供学习用", 
    "0.0.3"
)

class RussianRoulette(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 伪造指令，基本格式为 @bot /说 @目标用户 [消息内容]
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("说")
    async def FakeMessage(self, event: AstrMessageEvent):
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
        if len(at_list) != 2:
            yield event.plain_result("谁让你艾特我了，哼(｀ω´ )")
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
    async def handleMessages(self, event: AstrMessageEvent):
        """这是一个 处理 早上好/晚安 的函数"""                           # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        # message_str = event.message_str                              # 用户发的纯文本消息字符串
        # message_chain = event.get_messages()                         # 用户所发的消息的消息链 # from astrbot.api.message_components import *

        user_name = event.get_sender_name()                            # 发送消息的用户名称
        text = event.message_str.strip()

        if not text:
            logger.info("空消息。")
            return
        
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

    # 注册指令装饰器
    @filter.command("add")
    async def GetSum(self, event: AstrMessageEvent, a: int, b: int):
        yield event.plain_result(f"结果是：{a + b}！")

    @filter.command("sub")
    async def GetMinus(self, event: AstrMessageEvent, a: int, b: int):
        yield event.plain_result(f"结果是：{a - b}！")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
