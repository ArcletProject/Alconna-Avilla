from __future__ import annotations

import asyncio
import traceback
from atexit import register
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Literal, Optional, Union, get_args
from weakref import WeakKeyDictionary

from arclet.alconna import Arparma, Empty, output_manager
from arclet.alconna.args import AllParam, Args
from arclet.alconna.builtin import generate_duplication
from arclet.alconna.completion import CompSession
from arclet.alconna.core import Alconna
from arclet.alconna.duplication import Duplication
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.alconna.manager import command_manager
from arclet.alconna.stub import ArgsStub, OptionStub, SubcommandStub
from arclet.alconna.tools import AlconnaFormat, AlconnaString
from arclet.alconna.typing import CommandMeta
from avilla.core.context import Context
from avilla.standard.core.message import MessageEdited, MessageReceived
from creart import it
from graia.amnesia.message import MessageChain
from graia.amnesia.message.element import Text
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.entities.event import Dispatchable
from graia.broadcast.exceptions import ExecutionStop, PropagationCancelled
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.interrupt import InterruptControl, Waiter
from graia.broadcast.utilles import run_always_await
from tarina import LRU, generic_isinstance, generic_issubclass, lang
from tarina.generic import get_origin

from .model import CommandResult, CompConfig, Header, Match, Query, TConvert

if TYPE_CHECKING:
    result_cache: WeakKeyDictionary[Alconna, LRU[str, asyncio.Future[Optional[CommandResult]]]]
else:
    result_cache = WeakKeyDictionary()

AvillaMessageEvent = Union[MessageEdited, MessageReceived]

def get_future(alc: Alconna, source: str):
    return result_cache[alc].get(source)


def set_future(alc: Alconna, source: str):
    return result_cache[alc].setdefault(source, asyncio.Future())


def clear():
    for lru in result_cache.values():
        lru.clear()
    result_cache.clear()


register(clear)


class AlconnaOutputMessage(Dispatchable):
    """
    Alconna 信息输出事件
    如果触发的某个命令的可能输出 (帮助信息、模糊匹配、报错等), AlconnaDisptcher的send_flag为post时, 会发送该事件
    """

    def __init__(self, command: Alconna, text: str, source: Dispatchable):
        self.command = command
        self.output = text
        self.source_event = source

    class Dispatcher(BaseDispatcher):
        @classmethod
        async def catch(cls, interface: "DispatcherInterface[AlconnaOutputMessage]"):
            if interface.name == "output" and interface.annotation == str:
                return interface.event.output
            if isinstance(interface.annotation, Alconna):
                return interface.event.command
            if issubclass(interface.annotation, type(interface.event.source_event)) or isinstance(
                interface.event.source_event, interface.annotation
            ):
                return interface.event.source_event


class AlconnaDispatcher(BaseDispatcher):
    @classmethod
    def from_format(cls, command: str, args: Optional[Dict[str, Any]] = None):
        return cls(AlconnaFormat(command, args), send_flag="reply")

    @classmethod
    def from_command(cls, command: str, *options: str):
        factory = AlconnaString(command)
        for option in options:
            factory.option(option)
        return cls(factory.build(), send_flag="reply")

    default_send_handler: ClassVar[TConvert] = lambda _, x: MessageChain([Text(x)])

    @staticmethod
    def completion_waiter(self, source: AvillaMessageEvent, priority: int = 15) -> Waiter:
        @Waiter.create_using_function(
            [MessageReceived],
            block_propagation=True,
            priority=priority,
        )
        async def waiter(event: MessageReceived):
            if event.context.client == source.context.client:
                return event.message.content

        return waiter  # type: ignore

    async def send(
        self,
        result: Arparma[MessageChain],
        output_text: str | None = None,
        source: AvillaMessageEvent | None = None,
    ) -> None:
        ctx: Context = source.context
        help_message: MessageChain = await run_always_await(
            self.converter,
            str(result.error_info) if isinstance(result.error_info, SpecialOptionTriggered) else "help",
            output_text,
        )
        await ctx.scene.send_message(help_message)


    def __init__(
        self,
        command: Alconna,
        *,
        send_flag: Literal["reply", "post", "stay"] = "reply",
        skip_for_unmatch: bool = True,
        comp_session: Optional[CompConfig] = None,
        message_converter: Optional[TConvert] = None,
    ):
        """
        构造 Alconna调度器
        Args:
            command (Alconna): Alconna实例
            send_flag ("reply", "post", "stay"): 输出信息的发送方式
            skip_for_unmatch (bool): 当指令匹配失败时是否跳过对应的事件监听器, 默认为 True
            comp_session (CompConfig, optional): 补全会话配置, 不传入则不启用补全会话
        """
        super().__init__()
        self.command = command
        self.send_flag = send_flag
        self.skip_for_unmatch = skip_for_unmatch
        self.comp_session = comp_session
        self.converter = message_converter or self.__class__.default_send_handler
        result_cache.setdefault(command, LRU(10))

    async def handle(self, source: Optional[Dispatchable], msg: MessageChain):
        inc = it(InterruptControl)
        interface = CompSession(self.command)
        if self.comp_session is None or not source:
            return self.command.parse(msg)  # type: ignore
        res = None
        with interface:
            res = self.command.parse(msg)  # type: ignore
        if res:
            return res
        _tab = Alconna(
            self.comp_session.get("tab", ".tab"), Args["offset", int, 1], [],
            meta=CommandMeta(compact=True, hide=True)
        )
        _enter = Alconna(
            self.comp_session.get("enter", ".enter"), Args["content", AllParam, []], [],
            meta=CommandMeta(compact=True, hide=True)
        )
        _exit = Alconna(
            self.comp_session.get("exit", ".exit"), [],
            meta=CommandMeta(compact=True, hide=True)
        )

        def _clear():
            command_manager.delete(_tab)
            command_manager.delete(_enter)
            command_manager.delete(_exit)
            interface.clear()

        while interface.available:
            res = Arparma(self.command.path, msg, False, error_info=SpecialOptionTriggered("completion"))
            await self.send(res, str(interface), source)
            await self.send(
                res,
                f"{lang.require('comp/graia', 'tab').format(cmd=_tab.command)}\n"
                f"{lang.require('comp/graia', 'enter').format(cmd=_enter.command)}\n"
                f"{lang.require('comp/graia', 'exit').format(cmd=_exit.command)}",
                source,
            )
            while True:
                waiter = self.completion_waiter(source ,self.comp_session.get('priority', 10))  # type: ignore
                try:
                    ans: MessageChain = await inc.wait(
                        waiter, timeout=self.comp_session.get('timeout', 30)
                    )
                except asyncio.TimeoutError:
                    _clear()
                    await self.send(res, lang.require("comp/graia", "timeout"), source)
                    return res
                if _exit.parse(ans).matched:
                    await self.send(res, lang.require("comp/graia", "exited"), source)
                    _clear()
                    return res
                if (mat := _tab.parse(ans)).matched:
                    interface.tab(mat.offset)
                    lite = self.comp_session.get("lite", True)
                    await self.send(res, interface.current() if lite else str(interface), source)
                    continue
                if (mat := _enter.parse(ans)).matched:
                    content = list(mat.content)
                    if not content or not content[0]:
                        content = None
                    try:
                        with interface:
                            res = interface.enter(content)
                    except Exception as e:
                        traceback.print_exc()
                        await self.send(res, str(e), source)
                        continue
                    break
                else:
                    await self.send(res, interface.current(), source)
        _clear()
        return res

    async def output(
        self,
        dii: DispatcherInterface,
        result: Arparma[MessageChain],
        output_text: Optional[str] = None,
        source: Optional[Dispatchable] = None,
    ):
        if not source or (result.matched or not output_text):
            return CommandResult(result, None, source)
        if self.send_flag == "stay":
            return CommandResult(result, output_text, source)
        if self.send_flag == "reply":
            await self.send(result, output_text, source)
        elif self.send_flag == "post":
            dii.broadcast.postEvent(AlconnaOutputMessage(self.command, output_text, source), source)
        return CommandResult(result, None, source)

    async def beforeExecution(self, interface: DispatcherInterface[AvillaMessageEvent]):
        message: MessageChain = interface.event.message.content
        source = interface.event
        if future := get_future(self.command, source.message.id if source else "_"):
            await future
            if not (_property := future.result()):
                raise ExecutionStop
        else:
            fut = set_future(self.command, source.message.id if source else "_")
            with output_manager.capture(self.command.name) as cap:
                output_manager.set_action(lambda x: x, self.command.name)
                try:
                    _res = await self.handle(source, message)
                except Exception as e:
                    _res = Arparma(self.command.path, message, False, error_info=e)
                may_help_text: Optional[str] = cap.get("output", None)
            if not may_help_text and not _res.matched and ((not _res.head_matched) or self.skip_for_unmatch):
                fut.set_result(None)
                raise ExecutionStop
            if not may_help_text and _res.error_info:
                may_help_text = repr(_res.error_info)
            _property = await self.output(interface, _res, may_help_text, source)
            fut.set_result(_property)
        if not _property.result.matched and not _property.output:
            raise PropagationCancelled
        interface.local_storage["alconna_result"] = _property
        return

    async def catch(self, interface: DispatcherInterface):
        res: CommandResult = interface.local_storage["alconna_result"]
        default_duplication = generate_duplication(self.command)(res.result)
        if interface.annotation is Duplication:
            return default_duplication
        if generic_issubclass(Duplication, interface.annotation):
            return interface.annotation(res.result)
        if generic_issubclass(get_origin(interface.annotation), CommandResult):
            return res
        if interface.annotation is ArgsStub:
            arg = ArgsStub(self.command.args)
            arg.set_result(res.result.all_matched_args)
            return arg
        if interface.annotation is OptionStub:
            return default_duplication.option(interface.name)
        if interface.annotation is SubcommandStub:
            return default_duplication.subcommand(interface.name)
        if generic_issubclass(get_origin(interface.annotation), Arparma):
            return res.result
        if interface.annotation is str and interface.name == "output":
            return res.output
        if generic_issubclass(interface.annotation, Alconna):
            return self.command
        if interface.annotation is Header:
            return Header(res.result.header, bool(res.result.header))
        if interface.annotation is Match:
            r = res.result.all_matched_args.get(interface.name, Empty)
            return Match(r, r != Empty)
        if get_origin(interface.annotation) is Match:
            r = res.result.all_matched_args.get(interface.name, Empty)
            return Match(r, generic_isinstance(r, get_args(interface.annotation)[0]))
        if isinstance(interface.default, Query):
            q = Query(interface.default.path, interface.default.result)
            result = res.result.query(q.path, Empty)
            if interface.annotation is Query:
                q.available = result != Empty
            elif get_origin(interface.annotation) is Query:
                q.available = generic_isinstance(result, get_args(interface.annotation)[0])
            if q.available:
                q.result = result
            elif interface.default.result != Empty:
                q.available = True
            return q
        if interface.name in res.result.all_matched_args:
            if generic_isinstance(res.result.all_matched_args[interface.name], interface.annotation):
                return res.result.all_matched_args[interface.name]
            return
