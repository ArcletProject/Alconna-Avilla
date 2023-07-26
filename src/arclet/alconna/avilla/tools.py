from __future__ import annotations

import inspect
from functools import lru_cache
from typing import Any, Callable, TypedDict

from arclet.alconna import Alconna
from arclet.alconna.tools import AlconnaFormat, AlconnaString
from arclet.alconna.tools.construct import FuncMounter
from avilla.core.context import Context
from avilla.core.elements import Notice
from avilla.core.tools.filter import Filter
from avilla.standard.core.message import MessageEdited, MessageReceived
from avilla.standard.core.profile import Summary
from graia.amnesia.message import Element, MessageChain
from graia.amnesia.message.element import Text
from graia.broadcast import (
    Decorator,
    DecoratorInterface,
)
from graia.broadcast.builtin.decorators import Depend
from graia.broadcast.builtin.derive import Derive
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.saya.factory import (
    BufferModifier,
    SchemaWrapper,
    buffer_modifier,
    ensure_buffer,
    factory,
)
from nepattern import AllParam, BasePattern, Empty, type_parser
from tarina import gen_subclass, is_awaitable
from typing_extensions import NotRequired

from .dispatcher import AlconnaDispatcher, CommandResult
from .model import CompConfig
from .saya import AlconnaSchema
from .utils import T_Callable, listen


class GraiaShortcutArgs(TypedDict):
    command: MessageChain
    args: NotRequired[list[Any]]
    fuzzy: NotRequired[bool]


def fetch_name(path: str = "name"):
    """
    在可能的命令输入中获取目标的名字

    要求 Alconna 命令中含有 Args[path;O:[str, At]] 参数
    """

    async def __wrapper__(ctx: Context, result: CommandResult[MessageReceived]):
        arp = result.result
        if t := arp.all_matched_args.get(path, None):
            return (
                t.target.pattern.get("display")
                or (await ctx.pull(Summary, target=result.source.context.client)).name
                if isinstance(t, Notice)
                else t
            )
        else:
            return (await ctx.pull(Summary, target=result.source.context.client)).name

    return Depend(__wrapper__)


def match_path(path: str):
    """
    当 Arpamar 解析成功后, 依据 path 是否存在以继续执行事件处理

    当 path 为 ‘$main’ 时表示认定当且仅当主命令匹配
    """

    def __wrapper__(result: CommandResult):
        if path == "$main":
            if not result.result.components:
                return True
            raise ExecutionStop
        else:
            if result.result.query(path, "\0") == "\0":
                raise ExecutionStop
            return True

    return Depend(__wrapper__)


def match_value(path: str, value: Any, or_not: bool = False):
    """
    当 Arpamar 解析成功后, 依据查询 path 得到的结果是否符合传入的值以继续执行事件处理

    当 or_not 为真时允许查询 path 失败时继续执行事件处理
    """

    def __wrapper__(result: CommandResult):
        if result.result.query(path) == value:
            return True
        if or_not and result.result.query(path, Empty) == Empty:
            return True
        raise ExecutionStop

    return Depend(__wrapper__)


def shortcuts(
    mapping: dict[str, GraiaShortcutArgs] | None = None, **kwargs: GraiaShortcutArgs
):
    def wrapper(func: T_Callable) -> T_Callable:
        kwargs.update(mapping or {})
        if hasattr(func, "__alc_shortcuts__"):
            getattr(func, "__alc_shortcuts__", {}).update(kwargs)
        else:
            setattr(func, "__alc_shortcuts__", kwargs)
        return func

    return wrapper


@factory
def alcommand(
    alconna: Alconna | str,
    guild: bool = True,
    private: bool = True,
    send_error: bool = False,
    post: bool = False,
    patterns: list[str] | None = None,
    comp_session: CompConfig | None = None,
) -> SchemaWrapper:
    """
    saya-util 形式的注册一个消息事件监听器并携带 AlconnaDispatcher

    请将其放置在装饰器的顶层

    Args:
        alconna (Alconna | str): 使用的 Alconna 命令
        guild (bool, optional): 命令是否群聊可用
        private (bool, optional): 命令是否私聊可用
        send_error (bool, optional): 是否发送错误信息
        post (bool, optional): 是否以事件发送输出信息
        patterns (list[str] | None, optional): 在可能的以 Avilla 为基础框架时使用的 selector 匹配模式
        comp_session (CompConfig | None, optional): 是否使用补全会话
    """
    if isinstance(alconna, str):
        if not alconna.strip():
            raise ValueError(alconna)
        parts = alconna.split(";")
        _factory = AlconnaString(parts[0])
        for part in parts[1:]:
            _head = part.split(" ", 1)[0]
            _factory.option(_head.lstrip(" ").lstrip("-"), part.lstrip())
        alconna = _factory.build()
    dispatcher = AlconnaDispatcher(
        alconna,
        send_flag="post" if post else "reply",  # type: ignore
        skip_for_unmatch=not send_error,
        comp_session=comp_session,
    )

    def wrapper(func: Callable, buffer: dict[str, Any]) -> AlconnaSchema:
        _filter = Filter().cx.client
        _dispatchers = buffer.setdefault("dispatchers", [])
        if patterns:
            _dispatchers.append(_filter.follows(*patterns))
        if dispatcher:
            _dispatchers.append(dispatcher)
        listen(MessageReceived, MessageEdited)(func)
        return AlconnaSchema(dispatcher.command)

    return wrapper


@factory
def from_command(
    format_command: str,
    args: dict[str, type | BasePattern] | None = None,
    post: bool = False,
) -> SchemaWrapper:
    """
    saya-util 形式的仅注入一个 AlconnaDispatcher, 事件监听部分自行处理

    Args:
        format_command: 格式化命令字符串
        args: 格式化填入内容
        post: 是否以事件发送输出信息
    """

    def wrapper(func: Callable, buffer: dict[str, Any]):
        custom_args = {
            v.name: v.annotation for v in inspect.signature(func).parameters.values()
        }
        custom_args.update(args or {})
        cmd = AlconnaFormat(format_command, custom_args)
        buffer.setdefault("dispatchers", []).append(
            AlconnaDispatcher(cmd, send_flag="post" if post else "reply")  # type: ignore
        )
        return AlconnaSchema(cmd)

    return wrapper


_seminal = type("_seminal", (object,), {})


@buffer_modifier
def assign(path: str, value: Any = _seminal, or_not: bool = False) -> BufferModifier:
    """
    match_path 与 match_value 的合并形式
    """

    def wrapper(buffer: dict[str, Any]):
        if value == _seminal:
            if or_not:
                buffer.setdefault("decorators", []).append(match_path("$main"))
            buffer.setdefault("decorators", []).append(match_path(path))
        else:
            buffer.setdefault("decorators", []).append(match_value(path, value, or_not))

    return wrapper


@lru_cache()
def search_element(name: str):
    for i in gen_subclass(Element):
        if i.__name__ == name:
            return i


def _get_filter_out() -> list[type[Element]]:
    res = []
    for i in ["Source", "Quote", "File"]:
        if t := search_element(i):
            res.append(t)
    return res


class MatchPrefix(Decorator, Derive[MessageChain]):
    pre = True

    def __init__(self, prefix: Any, extract: bool = False):  # noqa
        """
        利用 NEPattern 的前缀匹配

        Args:
            prefix: 检测的前缀, 支持格式有 a|b , ['a', At(...)] 等
            extract: 是否为提取模式, 默认为 False
        """
        pattern = type_parser(prefix)
        if pattern in (AllParam, Empty):
            raise ValueError(prefix)
        self.pattern = pattern.prefixed()
        self.extract = extract

    async def target(self, interface: DecoratorInterface):
        return await self(
            await interface.dispatcher_interface.lookup_param(
                "message_chain", MessageChain, None
            ),
            interface.dispatcher_interface,
        )

    async def __call__(
        self, chain: MessageChain, interface: DispatcherInterface
    ) -> MessageChain:
        header = chain.include(*_get_filter_out())
        rest: MessageChain = chain.exclude(*_get_filter_out())
        if not rest.content:
            raise ExecutionStop
        elem = rest.content[0]
        if isinstance(elem, Text) and (res := self.pattern.validate(elem.text)).success:
            if self.extract:
                return MessageChain([Text(str(res.value))])
            elem.text = elem.text[len(str(res.value)) :].lstrip()
            return header + rest
        elif self.pattern.validate(elem).success:
            if self.extract:
                return MessageChain([elem])
            rest.content.remove(elem)
            return header + rest
        raise ExecutionStop


class MatchSuffix(Decorator, Derive[MessageChain]):
    pre = True

    def __init__(self, suffix: Any, extract: bool = False):  # noqa
        """
        利用 NEPattern 的后缀匹配

        Args:
            suffix: 检测的前缀, 支持格式有 a|b , ['a', At(...)] 等
            extract: 是否为提取模式, 默认为 False
        """
        pattern = type_parser(suffix)
        if pattern in (AllParam, Empty):
            raise ValueError(suffix)
        self.pattern = pattern.suffixed()
        self.extract = extract

    async def target(self, interface: DecoratorInterface):
        return await self(
            await interface.dispatcher_interface.lookup_param(
                "message_chain", MessageChain, None
            ),
            interface.dispatcher_interface,
        )

    async def __call__(
        self, chain: MessageChain, interface: DispatcherInterface
    ) -> MessageChain:
        header = chain.include(*_get_filter_out())
        rest: MessageChain = chain.exclude(*_get_filter_out())
        if not rest.content:
            raise ExecutionStop
        elem = rest.content[-1]
        if isinstance(elem, Text) and (res := self.pattern.validate(elem.text)).success:
            if self.extract:
                return MessageChain([Text(str(res.value))])
            elem.text = elem.text[: elem.text.rfind(str(res.value))].rstrip()
            return header + rest
        elif self.pattern.validate(elem).success:
            if self.extract:
                return MessageChain([elem])
            rest.content.remove(elem)
            return header + rest
        raise ExecutionStop


@buffer_modifier
def startswith(
    prefix: Any, include: bool = False, bind: str | None = None
) -> BufferModifier:
    """
    MatchPrefix 的 shortcut形式

    Args:
        prefix: 需要匹配的前缀
        include: 指示是否仅返回匹配部分, 默认为 False
        bind: 指定注入返回值的参数名称
    """
    decorator = MatchPrefix(prefix, include)

    def wrapper(buffer: dict[str, Any]):
        if bind:
            buffer.setdefault("decorator_map", {})[bind] = decorator
        else:
            buffer.setdefault("decorators", []).append(decorator)

    return wrapper


@buffer_modifier
def endswith(
    suffix: Any, include: bool = False, bind: str | None = None
) -> BufferModifier:
    """
    MatchSuffix 的 shortcut形式

    Args:
        suffix: 需要匹配的前缀
        include: 指示是否仅返回匹配部分, 默认为 False
        bind: 指定注入返回值的参数名称
    """
    decorator = MatchSuffix(suffix, include)

    def wrapper(buffer: dict[str, Any]):
        if bind:
            buffer.setdefault("decorator_map", {})[bind] = decorator
        else:
            buffer.setdefault("decorators", []).append(decorator)

    return wrapper


def funcommand(
    name: str | None = None,
    prefixes: list[str] | None = None,
    guild: bool = True,
    private: bool = True,
    patterns: list[str] | None = None,
):
    _config = {"raise_exception": False}
    if name:
        _config["command"] = name
    if prefixes:
        _config["prefixes"] = prefixes

    def wrapper(func: T_Callable) -> T_Callable:
        buffer = ensure_buffer(func)
        alc = FuncMounter(func, config=_config)

        async def _wrapper(ctx: Context, message: MessageChain):
            try:
                arp, res = alc.exec(message)
            except Exception as e:
                await ctx.scene.send_message(str(e))
                return
            if arp.matched:
                if is_awaitable(res):
                    res = await res
                if isinstance(res, (str, MessageChain)):
                    await ctx.scene.send_message(res)

        _filter = Filter().cx.client
        _dispatchers = buffer.setdefault("dispatchers", [])
        if patterns:
            _dispatchers.append(_filter.follows(*patterns))
        listen(MessageReceived, MessageEdited)(_wrapper)
        return func

    return wrapper


__all__ = [
    "fetch_name",
    "match_path",
    "alcommand",
    "match_value",
    "from_command",
    "shortcuts",
    "assign",
    "startswith",
    "MatchPrefix",
    "endswith",
    "MatchSuffix",
    "funcommand",
]
