from contextlib import suppress
from typing import Optional, Union

from arclet.alconna import Arparma
from arclet.alconna.core import Alconna, AlconnaGroup
from arclet.alconna.graia.dispatcher import AlconnaDispatcher, output_cache
from arclet.alconna.graia.model import AlconnaProperty
from avilla.core.context import Context
from avilla.core.event import AvillaEvent
from avilla.spec.core.message import MessageReceived
from graia.amnesia.message import MessageChain
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.utilles import run_always_await


class AvillaOutputDispatcher(BaseDispatcher):
    def __init__(
        self, command: Union[Alconna, AlconnaGroup], text: str, source: MessageReceived
    ):
        self.command = command
        self.output = text
        self.source_event = source

    async def catch(self, interface: "DispatcherInterface"):
        if interface.name == "output" and interface.annotation == str:
            return self.output
        if isinstance(interface.annotation, (Alconna, AlconnaGroup)):
            return self.command
        if (
            issubclass(interface.annotation, MessageReceived)
            or interface.annotation is MessageReceived
        ):
            return self.source_event


class AvillaAlconnaOutputMessage(AvillaEvent):
    """
    Alconna - Avilla 信息输出事件
    如果触发的某个命令的可能输出 (帮助信息、模糊匹配、报错等), AlconnaDisptcher的send_flag为post时, 会发送该事件
    """

    command: Union[Alconna, AlconnaGroup]
    """命令"""

    output: str
    """输出信息"""

    source_event: MessageReceived
    """来源事件"""


async def _send_output(
    self: AlconnaDispatcher,
    result: Arparma,
    output_text: Optional[str] = None,
    source: Optional[MessageReceived] = None,
) -> AlconnaProperty[MessageReceived]:
    if not isinstance(source, MessageReceived) or (result.matched or not output_text):
        return AlconnaProperty(result, None, source)
    id_ = id(source) if source else 0
    cache = output_cache.setdefault(id_, set())
    if self.command in cache:
        return AlconnaProperty(result, None, source)
    cache.clear()
    cache.add(self.command)
    if self.send_flag == "stay":
        return AlconnaProperty(result, output_text, source)
    if self.send_flag == "reply":
        ctx: Context = source.context
        help_message: MessageChain = await run_always_await(
            self.send_handler, output_text
        )
        await ctx.scene.send_message(help_message)
    elif self.send_flag == "post":
        with suppress(LookupError):
            interface = DispatcherInterface.ctx.get()
            dispatchers = [AvillaOutputDispatcher(self.command, output_text, source)]
            for listener in interface.broadcast.default_listener_generator(
                AvillaAlconnaOutputMessage
            ):
                await interface.broadcast.Executor(listener, dispatchers=dispatchers)
                listener.oplog.clear()
            return AlconnaProperty(result, None, source)
    return AlconnaProperty(result, None, source)


AlconnaDispatcher.send_output = _send_output
