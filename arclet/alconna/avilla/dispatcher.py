import asyncio
import contextlib
from atexit import register
from typing import Any, ClassVar, Dict, Literal, Optional, Union, get_args

from arclet.alconna.builtin import generate_duplication
from arclet.alconna.completion import CompSession
from arclet.alconna.core import Alconna
from arclet.alconna.duplication import Duplication
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.alconna.stub import ArgsStub, OptionStub, SubcommandStub
from arclet.alconna.tools import AlconnaFormat
from avilla.core import Context, Message, Notice, Selector
from avilla.core.exceptions import UnknownTarget
from avilla.standard.core.message import MessageReceived
from creart import it
from graia.amnesia.message import MessageChain
from graia.amnesia.message.element import Text
from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.entities.event import Dispatchable
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.interrupt import InterruptControl
from graia.broadcast.interrupt.waiter import Waiter
from graia.broadcast.utilles import run_always_await
from tarina import LRU, generic_isinstance, generic_issubclass
from tarina.generic import get_origin

from arclet.alconna import Arparma, Empty, output_manager

from .i18n import Lang, lang
from .model import CommandResult, CompConfig, Header, Match, Query, TConvert, TSource

reply_cache: "LRU[str, Message]" = LRU(64)
result_cache: "Dict[int, LRU[str, asyncio.Future[Optional[CommandResult]]]]" = {}
output_cache: "Dict[int, LRU[str, str]]" = {}


def get_future(alc: Alconna, source: str):
    return result_cache[alc._hash].get(source)


def set_future(alc: Alconna, source: str):
    return result_cache[alc._hash].setdefault(source, asyncio.Future())


def clear():
    for lru in result_cache.values():
        lru.clear()
    for dq in output_cache.values():
        dq.clear()
    result_cache.clear()
    output_cache.clear()


register(clear)


class AlconnaOutputMessage(Dispatchable):
    """
    Alconna 信息输出事件
    如果触发的某个命令的可能输出 (帮助信息、模糊匹配、报错等), AlconnaDisptcher的send_flag为post时, 会发送该事件
    """

    def __init__(self, command: Alconna, otype: str, text: str, source: Dispatchable):
        self.command = command
        self.output = text
        self.otype = otype
        self.source_event = source

    class Dispatcher(BaseDispatcher):

        @classmethod
        async def catch(cls, interface: "DispatcherInterface[AlconnaOutputMessage]"):
            if interface.name == "output" and interface.annotation == str:
                return interface.event.output
            if interface.name in ("otype", "output_type", "type"):
                return interface.event.otype
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

    default_send_handler: ClassVar[TConvert] = lambda _, x: MessageChain([Text(x)])

    def is_tome(self, message: MessageChain, account: Selector):
        if message.content and isinstance(message[0], Notice):
            notice: Notice = message.get_first(Notice)
            if notice.target.last_value == account.last_value:
                return True
        return False

    def tome_remove(self, message: MessageChain, account: Selector):
        message = MessageChain(message.content.copy())
        message.content.remove(message.get_first(Notice))
        if message.content and isinstance(message.content[0], Text):
            text = message.content[0].text.lstrip()  # type: ignore
            if not text:
                message.content.pop(0)
            else:
                message.content[0] = Text(text)
        return message

    async def reply_merge(self, message: MessageChain, source: MessageReceived):
        if not source.message.reply:
            return message
        source_id = f"{source.message.id}@{source.context.account.route}"
        if not (origin := reply_cache.get(source_id)):
            try:
                origin = await source.context.pull(Message, source.message.reply)
            except (NotImplementedError, UnknownTarget, RuntimeError):
                return message
            else:
                reply_cache[source_id] = origin
        if self.merge_reply is True or self.merge_reply == "right":
            return message.extend(origin.content, copy=True)
        return origin.content.extend(message, copy=True)

    def completion_waiter(self, source: MessageReceived, priority: int = 15) -> Waiter:
        @Waiter.create_using_function(
            [MessageReceived],
            block_propagation=True,
            priority=priority,
        )
        async def waiter(event: MessageReceived):
            if event.context.client == source.context.client:
                msg = event.message.content
                if self.is_tome(msg, event.context.self):
                    msg = self.tome_remove(msg, event.context.self)
                return await self._waiter(msg)

        return waiter  # type: ignore

    async def send(
        self,
        output_type: str,
        output_text: Optional[str],
        source: MessageReceived,
    ) -> None:
        ctx: Context = source.context
        help_message: MessageChain = await run_always_await(
            self.converter,
            output_type,
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
        need_tome: bool = False,
        remove_tome: bool = False,
        merge_reply: Union[bool, Literal["left", "right"]] = False,
    ):
        """
        构造 Alconna调度器
        Args:
            command (Alconna): Alconna实例
            send_flag ("reply" | "post" | "stay"): 输出信息的发送方式
            skip_for_unmatch (bool): 当指令匹配失败时是否跳过对应的事件监听器, 默认为 True
            comp_session (CompConfig, optional): 补全会话配置, 不传入则不启用补全会话
            message_converter: (TConvert, optional): 输出信息转换函数, 用于自定义将字符串转为消息链
            need_tome (bool, optional): 是否需要 @自己, 默认为 False
            remove_tome (bool, optional): 是否移除首部的 @自己，默认为 False
            merge_reply (bool | "left" | "right", optional): 是否将引用的原消息合并到指令内
        """
        super().__init__()
        self.need_tome = need_tome
        self.command = command
        self.send_flag = send_flag
        self.skip_for_unmatch = skip_for_unmatch
        self.comp_session = comp_session
        self.converter = message_converter or self.__class__.default_send_handler
        self.remove_tome = remove_tome
        self.merge_reply = merge_reply
        self._interface = CompSession(self.command)
        result_cache.setdefault(command._hash, LRU(10))
        output_cache.setdefault(command._hash, LRU(10))
        self._comp_help = ""
        self._waiter = lambda _: _
        if self.comp_session is not None:
            _tab = self.comp_session.get("tab") or ".tab"
            _enter = self.comp_session.get("enter") or ".enter"
            _exit = self.comp_session.get("exit") or ".exit"
            disables = self.comp_session.get("disables", set())
            hides = self.comp_session.get("hides", set())
            hide_tabs = self.comp_session.get("hide_tabs", False)
            if self.comp_session.get("lite", False):
                hide_tabs = True
                hides = {"tab", "enter", "exit"}
            hides |= disables
            if len(hides) < 3:
                template = f"\n\n{{}}{{}}{{}}{Lang.completion.avilla.other()}\n"
                self._comp_help = template.format(
                    (Lang.completion.avilla.tab(cmd=_tab) + "\n") if "tab" not in hides else "",
                    (Lang.completion.avilla.enter(cmd=_enter) + "\n") if "enter" not in hides else "",
                    (Lang.completion.avilla.exit(cmd=_exit) + "\n") if "exit" not in hides else "",
                )

            async def _(message: MessageChain):
                msg = str(message).lstrip()
                if msg.startswith(_exit) and "exit" not in disables:
                    if msg == _exit:
                        return False
                    return lang.require("analyser", "param_unmatched").format(target=msg.replace(_exit, "", 1))

                elif msg.startswith(_enter) and "enter" not in disables:
                    if msg == _enter:
                        return True
                    return lang.require("analyser", "param_unmatched").format(target=msg.replace(_enter, "", 1))

                elif msg.startswith(_tab) and "tab" not in disables:
                    offset = msg.replace(_tab, "", 1).lstrip() or 1
                    try:
                        offset = int(offset)
                    except ValueError:
                        return lang.require("analyser", "param_unmatched").format(target=offset)
                    else:
                        self._interface.tab(offset)
                        return f"* {self._interface.current()}" if hide_tabs else "\n".join(self._interface.lines())
                else:
                    return message

            self._waiter = _
        with contextlib.suppress(LookupError):
            self.need_tome = self.need_tome
            self.remove_tome = self.remove_tome

    async def handle(self, source: Optional[MessageReceived], msg: MessageChain, dii: DispatcherInterface[TSource]):
        inc = it(InterruptControl)
        if self.comp_session is None or not source:
            return self.command.parse(msg)  # type: ignore
        res = None
        with self._interface:
            res = self.command.parse(msg)  # type: ignore
        if res:
            return res
        res = Arparma(self.command.path, msg, False, error_info=SpecialOptionTriggered("completion"))
        waiter = self.completion_waiter(source, self.comp_session.get("priority", 10))
        while self._interface.available:
            await self.send("completion", f"{str(self._interface)}{self._comp_help}", source)
            while True:
                try:
                    ans = await inc.wait(waiter, timeout=self.comp_session.get("timeout", 60))
                except asyncio.TimeoutError:
                    await self.output(dii, res, Lang.completion.avilla.timeout(), source)
                    self._interface.exit()
                    return res
                if ans is False:
                    await self.output(dii, res, Lang.completion.avilla.exited(), source)
                    self._interface.exit()
                    return res
                if isinstance(ans, str):
                    await self.output(dii, res, ans, source)
                    continue
                _res = self._interface.enter(None if ans is True else ans)
                if _res.result:
                    res = _res.result
                elif _res.exception and not isinstance(_res.exception, SpecialOptionTriggered):
                    await self.output(dii, res, str(_res.exception), source)
                break
        self._interface.exit()
        return res

    async def output(
        self,
        dii: DispatcherInterface,
        result: Arparma[MessageChain],
        output_text: Optional[str],
        source: Optional[MessageReceived],
    ):
        otype = str(result.error_info) if isinstance(result.error_info, SpecialOptionTriggered) else "error"
        if not source or (result.matched or not output_text):
            return CommandResult(result, otype, None, source)
        if self.send_flag == "stay":
            return CommandResult(result, otype, output_text, source)
        if self.send_flag == "reply":
            await self.send(otype, output_text, source)
        elif self.send_flag == "post":
            dii.broadcast.postEvent(AlconnaOutputMessage(self.command, otype, output_text, source), source)
        return CommandResult(result, otype, None, source)

    async def lookup_source(
        self,
        interface: DispatcherInterface[MessageReceived],
    ) -> MessageChain:
        message = interface.event.message.content
        if self.merge_reply:
            message = await self.reply_merge(message, interface.event)
        is_tome = self.is_tome(message, interface.event.context.self)
        if self.need_tome and not is_tome:
            raise ExecutionStop
        if is_tome and self.remove_tome:
            return self.tome_remove(message, interface.event.context.self)
        return message

    async def beforeExecution(self, interface: DispatcherInterface[MessageReceived]):
        message = await self.lookup_source(interface)
        try:
            source = interface.event
        except LookupError:
            source = None
        source_id = f"{source.message.id}@{source.context.account.route}" if source else "_"
        if future := get_future(self.command, source_id):
            await future
            if not (_property := future.result()):
                raise ExecutionStop
        else:
            fut = set_future(self.command, source_id)
            with output_manager.capture(self.command.name) as cap:
                output_manager.set_action(lambda x: x, self.command.name)
                try:
                    _res = await self.handle(source, message, interface)
                except Exception as e:
                    _res = Arparma(self.command.path, message, False, error_info=e)
                may_help_text: Optional[str] = cap.get("output", None)
            if not _res.head_matched:
                fut.set_result(None)
                raise ExecutionStop
            if not may_help_text and not _res.matched and self.skip_for_unmatch:
                fut.set_result(None)
                raise ExecutionStop
            if not may_help_text and _res.error_info:
                may_help_text = repr(_res.error_info)
            if may_help_text is not None:
                output_cache[self.command._hash][source_id] = may_help_text
            _property = await self.output(interface, _res, may_help_text, source)
            fut.set_result(_property)
        if not _property.result.matched and not _property.output:
            raise ExecutionStop
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
