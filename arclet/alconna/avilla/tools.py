import inspect
import re
from functools import lru_cache
from typing import Any, Callable, Hashable, Literal, Optional, Union

from arclet.alconna.tools import AlconnaFormat
from arclet.alconna.tools.construct import AlconnaString, FuncMounter, MountConfig
from arclet.alconna.typing import CommandMeta, ShortcutArgs
from avilla.core import Context, MessageReceived, Notice, Summary, elements
from avilla.core.tools.filter import Filter
from graia.amnesia.message import Element, MessageChain, Text
from graia.broadcast import Decorator, DecoratorInterface, DispatcherInterface
from graia.broadcast.builtin.decorators import Depend
from graia.broadcast.builtin.derive import Derive
from graia.broadcast.exceptions import ExecutionStop
from graia.saya.builtins.broadcast.shortcut import T_Callable, listen
from graia.saya.factory import BufferModifier, SchemaWrapper, buffer_modifier, ensure_buffer, factory
from nepattern import BasePattern, Empty, MatchMode, parser
from tarina import gen_subclass, is_awaitable

from arclet.alconna import Alconna, AllParam, Namespace

from .dispatcher import AlconnaDispatcher, CommandResult
from .model import CompConfig
from .saya import AlconnaSchema


def fetch_name(path: str = "name"):
    """
    在可能的命令输入中获取目标的名字

    要求 Alconna 命令中含有 Args[path;O:[str, At]] 参数
    """

    async def __wrapper__(ctx: Context, result: CommandResult[MessageReceived]):
        arp = result.result
        if t := arp.all_matched_args.get(path, None):
            return (
                t.target.pattern.get("display") or (await ctx.pull(Summary, target=ctx.client)).name
                if isinstance(t, Notice)
                else t
            )
        else:
            return (await ctx.pull(Summary, target=ctx.client)).name

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


def shortcuts(mapping: Optional[dict[str, ShortcutArgs]] = None, **kwargs: ShortcutArgs):
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
    alconna: Union[Alconna, str],
    send_error: bool = False,
    post: bool = False,
    patterns: Optional[list[str]] = None,
    comp_session: Optional[CompConfig] = None,
    need_tome: bool = False,
    remove_tome: bool = False,
    merge_reply: Union[bool, Literal["left", "right"]] = False,
) -> SchemaWrapper:
    """
    saya-util 形式的注册一个消息事件监听器并携带 AlconnaDispatcher

    请将其放置在装饰器的顶层

    Args:
        alconna (Alconna | str): 使用的 Alconna 命令
        send_error (bool, optional): 是否发送错误信息
        post (bool, optional): 是否以事件发送输出信息
        patterns (list[str] | None, optional): 在可能的以 Avilla 为基础框架时使用的 selector 匹配模式
        comp_session (CompConfig | None, optional): 是否使用补全会话
        need_tome (bool, optional): 是否需要 @ 机器人
        remove_tome (bool, optional): 是否移除 @ 机器人
        merge_reply (bool | "left" | "right", optional): 是否将引用的原消息合并到指令内
    """

    def wrapper(func: Callable, buffer: dict[str, Any]) -> AlconnaSchema:
        if isinstance(alconna, str):
            custom_args = {v.name: v.annotation for v in inspect.signature(func).parameters.values()}
            cmd = AlconnaFormat(alconna, custom_args)
        else:
            cmd = alconna
        dispatcher = AlconnaDispatcher(
            cmd,
            send_flag="post" if post else "reply",  # type: ignore
            skip_for_unmatch=not send_error,
            comp_session=comp_session,
            need_tome=need_tome,
            remove_tome=remove_tome,
            merge_reply=merge_reply,
        )
        _filter = Filter().cx.client
        _dispatchers = buffer.setdefault("dispatchers", [])
        if patterns:
            _dispatchers.append(_filter.follows(*patterns))
        _dispatchers.append(dispatcher)
        listen(MessageReceived)(func)
        return AlconnaSchema(dispatcher.command)

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


def prefixed(pat: BasePattern):
    if pat.mode not in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
        return pat
    new_pat = pat.copy()
    new_pat.regex_pattern = re.compile(f"^{new_pat.pattern}")
    return new_pat


def suffixed(pat: BasePattern):
    if pat.mode not in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
        return pat
    new_pat = pat.copy()
    new_pat.regex_pattern = re.compile(f"{new_pat.pattern}$")
    return new_pat


class MatchPrefix(Decorator, Derive[MessageChain]):
    pre = True

    def __init__(self, prefix: Any, extract: bool = False):  # noqa
        """
        利用 NEPattern 的前缀匹配

        Args:
            prefix: 检测的前缀, 支持格式有 a|b , ['a', At(...)] 等
            extract: 是否为提取模式, 默认为 False
        """
        pattern = BasePattern(prefix, mode=MatchMode.REGEX_MATCH) if isinstance(prefix, str) else parser(prefix)
        if pattern in (AllParam, Empty):
            raise ValueError(prefix)
        self.pattern = prefixed(pattern)
        self.extract = extract

    async def target(self, interface: DecoratorInterface):  # type: ignore
        return await self(
            await interface.dispatcher_interface.lookup_param("message_chain", MessageChain, None),
            interface.dispatcher_interface,
        )

    async def __call__(self, chain: MessageChain, interface: DispatcherInterface) -> MessageChain:
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
        pattern = BasePattern(suffix, mode=MatchMode.REGEX_MATCH) if isinstance(suffix, str) else parser(suffix)
        if pattern in (AllParam, Empty):
            raise ValueError(suffix)
        self.pattern = suffixed(pattern)
        self.extract = extract

    async def target(self, interface: DecoratorInterface):  # type: ignore
        return await self(
            await interface.dispatcher_interface.lookup_param("message_chain", MessageChain, None),
            interface.dispatcher_interface,
        )

    async def __call__(self, chain: MessageChain, interface: DispatcherInterface) -> MessageChain:
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
def startswith(prefix: Any, include: bool = False, bind: Optional[str] = None) -> BufferModifier:
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
def endswith(suffix: Any, include: bool = False, bind: Optional[str] = None) -> BufferModifier:
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
    name: Optional[str] = None,
    prefixes: Optional[list[str]] = None,
    patterns: Optional[list[str]] = None,
):
    _config: MountConfig = {"raise_exception": False}
    if name:
        _config["command"] = name
    if prefixes:
        _config["prefixes"] = prefixes

    def wrapper(func: T_Callable) -> T_Callable:
        buffer = ensure_buffer(func)
        alc = FuncMounter(func, config=_config)

        async def listener(ctx: Context, message: MessageChain):
            try:
                arp = alc.parse(message)
            except Exception as e:
                await ctx.scene.send_message(str(e))
                return
            if arp.matched and (res := alc.exec_result.get(func.__name__)):
                if isinstance(res, Hashable) and is_awaitable(res):
                    res = await res
                if isinstance(res, (str, MessageChain)):
                    await ctx.scene.send_message(res)

        _filter = Filter().cx.client
        _dispatchers = buffer.setdefault("dispatchers", [])
        if patterns:
            _dispatchers.append(_filter.follows(*patterns))
        listen(MessageReceived)(listener)
        return func

    return wrapper


element_mapping = {
    "Text": elements.Text,
    "Notice": elements.Notice,
    "At": elements.Notice,
    "NoticeAll": elements.NoticeAll,
    "Image": elements.Picture,
    "Picture": elements.Picture,
    "Audio": elements.Audio,
    "Video": elements.Video,
    "File": elements.File,
    "Face": elements.Face,
}


class AvillaCommand(AlconnaString):
    @staticmethod
    def args_gen(pattern: str, types: dict):
        return AlconnaString.args_gen(pattern, {**types, **element_mapping})

    def namespace(self, ns: Union[str, Namespace]):
        self.buffer["namespace"] = ns
        return self

    def build(
        self,
    ):
        ns = self.buffer.pop("namespace", None)
        alc = Alconna(*self.buffer.values(), *self.options, namespace=ns, meta=self.meta)
        for action in self.actions:
            alc.bind()(action)
        for key, args, kwargs in self.shortcuts:
            alc.shortcut(key, args, **kwargs)  # type: ignore
        return alc

    def __call__(self, func=None):
        params = self.buffer.pop("$params", {})
        if not func:
            if self.actions:

                async def _func(ctx: Context, cmd: Alconna):
                    for res in cmd.exec_result.values():
                        if isinstance(res, Hashable) and is_awaitable(res):
                            res = await res
                        if isinstance(res, (str, MessageChain)):
                            await ctx.scene.send_message(res)

                func = _func
            else:
                return
        return alcommand(self.build(), **params)(func)


def Command(
    command: str,
    help_text: Optional[str] = None,
    meta: Optional[CommandMeta] = None,
    send_error: bool = False,
    post: bool = False,
    patterns: Optional[list[str]] = None,
    comp_session: Optional[CompConfig] = None,
    need_tome: bool = False,
    remove_tome: bool = False,
    merge_reply: Union[bool, Literal["left", "right"]] = False,
):
    cmd = AvillaCommand(command, help_text, meta)
    cmd.buffer["$params"] = {
        "send_error": send_error,
        "post": post,
        "patterns": patterns,
        "comp_session": comp_session,
        "need_tome": need_tome,
        "remove_tome": remove_tome,
        "merge_reply": merge_reply,
    }
    return cmd


__all__ = [
    "fetch_name",
    "match_path",
    "alcommand",
    "match_value",
    "shortcuts",
    "assign",
    "startswith",
    "MatchPrefix",
    "endswith",
    "MatchSuffix",
    "funcommand",
    "Command",
]
