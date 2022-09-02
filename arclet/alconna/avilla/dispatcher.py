import sys
from typing import (
    Callable,
    Optional,
    TypedDict,
    Union,
    Any,
    Coroutine,
    ClassVar
)
from arclet.alconna import (
    output_manager,
    Arpamar,
)
from arclet.alconna.core import Alconna, AlconnaGroup

from graia.broadcast.exceptions import ExecutionStop, PropagationCancelled
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.utilles import run_always_await

from graia.amnesia.message import MessageChain

from arclet.alconna.graia.dispatcher import output_cache, AlconnaProperty, AlconnaDispatcher

from avilla.core.event import AvillaEvent
from avilla.core.event.message import MessageReceived
from avilla.core.relationship import Relationship
from avilla.core.message import Message
from avilla.core.utilles.selector import Selector


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

    @property
    def ctx(self) -> Selector:
        return self.source_event.ctx


class _AlconnaLocalStorage(TypedDict):
    alconna_result: AlconnaProperty[MessageReceived]


class AvillaAlconnaDispatcher(AlconnaDispatcher):

    async def beforeExecution(self, interface: DispatcherInterface):
        async def send_output(
            result: Arpamar,
            output_text: Optional[str] = None,
            source: Optional[MessageReceived] = None,
        ) -> AlconnaProperty[MessageReceived]:

            id_ = id(source) if source else 0
            cache = output_cache.setdefault(id_, {})
            if self.command not in cache:
                cache.clear()
                cache[self.command] = True
                if result.matched is False and output_text:
                    if source and self.send_flag == "reply":
                        rs: Relationship = await source.account.get_relationship(source.ctx)
                        help_message: MessageChain = await run_always_await(
                            self.send_handler, output_text
                        )
                        await rs.send_message(help_message)
                        return AlconnaProperty(result, None, source)
                    if source and self.send_flag == "post":
                        rs: Relationship = await source.account.get_relationship(source.ctx)
                        dispatchers = [AvillaOutputDispatcher(self.command, output_text, source)]
                        for listener in interface.broadcast.default_listener_generator(
                            AvillaAlconnaOutputMessage
                        ):
                            await interface.broadcast.Executor(
                                listener, dispatchers=dispatchers
                            )
                            listener.oplog.clear()
                        return AlconnaProperty(result, None, source)
                return AlconnaProperty(result, output_text, source)
            return AlconnaProperty(result, None, source)

        message: Message = await interface.lookup_param(
            "message", Message, None
        )
        if not self.allow_quote and message.reply:
            raise ExecutionStop

        may_help_text = None

        def _h(string):
            nonlocal may_help_text
            may_help_text = string

        try:
            output_manager.set_action(_h, self.command.name)
            _res = self.command.parse(message.content)
        except Exception as e:
            _res = Arpamar(
                self.command.commands[0] if self.command._group else self.command
            )
            _res.head_matched = False
            _res.matched = False
            _res.error_info = repr(e)
            _res.error_data = []
        if (
            not may_help_text
            and not _res.matched
            and ((not _res.head_matched) or self.skip_for_unmatch)
        ):
            raise ExecutionStop
        if not may_help_text and _res.error_info:
            may_help_text = (
                str(_res.error_info).strip("'").strip("\\n").split("\\n")[-1]
            )
        if not may_help_text and _res.matched:
            output_cache.clear()
            sys.audit("success_analysis", self.command)
        try:
            _property = await send_output(_res, may_help_text, interface.event)
        except LookupError:
            _property = await send_output(_res, may_help_text, None)
        local_storage: _AlconnaLocalStorage = interface.local_storage  # type: ignore
        if not _res.matched and not _property.output_text:
            raise PropagationCancelled
        local_storage["alconna_result"] = _property
        return
