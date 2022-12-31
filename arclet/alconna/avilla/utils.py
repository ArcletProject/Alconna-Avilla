from __future__ import annotations

import inspect
from typing import Any, Callable, Generator, TypeVar

from arclet.alconna import Alconna, AlconnaGroup
from arclet.alconna.graia.dispatcher import AlconnaDispatcher
from arclet.alconna.graia.model import AlconnaProperty
from arclet.alconna.graia.saya import AlconnaSchema
from arclet.alconna.tools import AlconnaString
from avilla.core.context import Context
from avilla.core.elements import Notice
from avilla.core.tools.filter import Filter
from avilla.spec.core.message import MessageReceived
from avilla.spec.core.profile import Summary
from graia.broadcast.builtin.decorators import Depend
from graia.broadcast.entities.decorator import Decorator
from graia.broadcast.entities.event import Dispatchable
from graia.saya.builtins.broadcast import ListenerSchema
from graia.saya.factory import SchemaWrapper, factory
from nepattern import BasePattern, PatternModel, UnionArg
from nepattern.main import INTEGER

T = TypeVar("T")


def gen_subclass(cls: type[T]) -> Generator[type[T], Any, Any]:
    yield cls
    for sub in cls.__subclasses__():
        yield from gen_subclass(sub)


@factory
def listen(*event: type[Dispatchable] | str) -> SchemaWrapper:
    """在当前 Saya Channel 中监听指定事件

    Args:
        *event (Union[Type[Dispatchable], str]): 事件类型或事件名称

    Returns:
        Callable[[T_Callable], T_Callable]: 装饰器
    """
    EVENTS: dict[str, type[Dispatchable]] = {
        e.__name__: e for e in gen_subclass(Dispatchable)
    }
    events: list[type[Dispatchable]] = [
        e if isinstance(e, type) else EVENTS[e] for e in event
    ]

    def wrapper(func: Callable, buffer: dict[str, Any]) -> ListenerSchema:
        decorator_map: dict[str, Decorator] = buffer.pop("decorator_map", {})
        buffer["inline_dispatchers"] = buffer.pop("dispatchers", [])
        if decorator_map:
            sig = inspect.signature(func)
            for param in sig.parameters.values():
                if decorator := decorator_map.get(param.name):
                    setattr(param, "_default", decorator)
            func.__signature__ = sig
        return ListenerSchema(listening_events=events, **buffer)

    return wrapper


NoticeID = (
    UnionArg(
        [
            BasePattern(
                model=PatternModel.TYPE_CONVERT,
                origin=int,
                alias="Notice",
                accepts=[Notice],
                converter=lambda _, x: int(x.target.pattern["member"]),
            ),
            BasePattern(
                r"@(\d+)",
                model=PatternModel.REGEX_CONVERT,
                origin=int,
                alias="@xxx",
                accepts=[str],
            ),
            INTEGER,
        ]
    )
    @ "notice_id"
)
"""
内置类型，允许传入提醒元素(Notice)或者'@xxxx'式样的字符串或者数字, 返回数字
"""


def fetch_name(path: str = "name"):
    """
    在可能的命令输入中获取目标的名字

    要求 Alconna 命令中含有 Args[path;O:[str, At]] 参数
    """

    async def __wrapper__(ctx: Context, result: AlconnaProperty[MessageReceived]):
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


@factory
def alcommand(
    alconna: Alconna | AlconnaGroup | str,
    guild: bool = True,
    private: bool = True,
    send_error: bool = False,
    post: bool = False,
    private_name: str = "friend",
    guild_name: str = "group",
) -> SchemaWrapper:
    """
    saya-util 形式的注册一个消息事件监听器并携带 AlconnaDispatcher

    请将其放置在装饰器的顶层

    Args:
        alconna: 使用的 Alconna 命令
        guild: 命令是否群聊可用
        private: 命令是否私聊可用
        send_error: 是否发送错误信息
        post: 是否以事件发送输出信息
        private_name: 私聊事件下消息场景名称
        guild_name: 群聊事件下消息场景名称
    """
    if isinstance(alconna, str):
        if not alconna.strip():
            raise ValueError(alconna)
        cmds = alconna.split(";")
        alconna = AlconnaString(cmds[0], *cmds[1:])
    if alconna.meta.example and "$" in alconna.meta.example:
        alconna.meta.example = alconna.meta.example.replace("$", alconna.headers[0])

    def wrapper(func: Callable, buffer: dict[str, Any]):
        _filter = Filter().scene
        _dispatchers = buffer.setdefault("dispatchers", [])
        if not guild:
            _dispatchers.append(_filter.follows(private_name))
        if not private:
            _dispatchers.append(_filter.follows(guild_name))
        _dispatchers.append(
            AlconnaDispatcher(
                alconna, send_flag="post" if post else "reply", skip_for_unmatch=not send_error  # type: ignore
            )
        )
        listen(MessageReceived)(func)  # noqa
        return AlconnaSchema(alconna)

    return wrapper


__all__ = ["NoticeID", "fetch_name", "alcommand"]
