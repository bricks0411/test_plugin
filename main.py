from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At, Plain, Node

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

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    @filter.command("add")
    async def GetSum(self, event: AstrMessageEvent, a: int, b: int):
        yield event.plain_result(f"结果是：{a + b}！")

    @filter.command("sub")
    async def GetMinus(self, event: AstrMessageEvent, a: int, b: int):
        yield event.plain_result(f"结果是：{a - b}！")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def Fake_say(self, event: AstrMessageEvent, *args):
        messages = event.get_messages()

        logger.debug(
            f"[fake_say] 收到消息 | "
            f"session={event.session_id} | "
            f"sender={event.get_sender_name()} | "
            f"chain={messages}"
        )

        if len(messages) < 2:
            logger.debug("[fake_say] 消息长度不足，忽略")
            return
        
        if not isinstance(messages[0], At):
            logger.debug("[fake_say] 不是 At 消息，忽略")
            return
        
        if not isinstance(messages[1], Plain):
            logger.debug("[fake_say] 不是文本消息，忽略")
            return
        
        text = messages[1].text.strip()
        if not text.startswith("说"):
            logger.debug("[fake_say] 不是以“说”开头，忽略")
            return
        
        content = text[1:].strip()
        if not content:
            logger.debug("[fake_say] 发送失败！内容为空。")
            yield event.plain_result("内容不能为空！")
            return
        
        at_target = messages[0]

        node = Node (
            uin = at_target.qq,
            name = at_target.name,
            content = [Plain(content)]
        )

        logger.info(
            f"[fake_say] 触发伪造发言 | "
            f"target_uin={at_target.qq} | "
            f"target_name={at_target.name} | "
            f"content={content}"
        )
        yield event.chain_result([node])


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
