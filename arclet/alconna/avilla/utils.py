import inspect
from typing import Union, Dict, Optional
from nepattern import PatternModel, BasePattern
from graia.saya.cube import Cube
from graia.saya.builtins.broadcast import ListenerSchema
from graia.saya import Channel
from graiax.shortcut.saya import ensure_cube_as_listener, Wrapper, T_Callable
from graia.broadcast.builtin.decorators import Depend

from arclet.alconna import Alconna, AlconnaFormat
from arclet.alconna.graia import AlconnaProperty, AlconnaSchema, AlconnaDispatcher

from avilla.core.elements import Notice
from avilla.core.cell.cells import Summary
from avilla.core.relationship import Relationship
from avilla.core.event.message import MessageReceived
from avilla.core.tools.filter import Filter


NoticeID = BasePattern(
    model=PatternModel.TYPE_CONVERT,
    origin=int,
    alias="notice_id",
    accepts=[str, Notice, int],
    converter=lambda x: int(x.target.pattern['contact']) if isinstance(x, Notice) else int(str(x).lstrip("@")),
)
"""
内置类型，允许传入提醒元素(Notice)或者'@xxxx'式样的字符串或者数字, 返回数字
"""


def fetch_name(path: str = "name"):
    """
    在可能的命令输入中获取目标的名字

    要求 Alconna 命令中含有 Args[path;O:[str, At]] 参数
    """

    async def __wrapper__(rs: Relationship, result: AlconnaProperty[MessageReceived]):
        arp = result.result
        if t := arp.all_matched_args.get(path, None):
            return (
                t.target.pattern.get('display') or (await rs.pull(Summary, target=result.source.ctx)).name
                if isinstance(t, Notice)
                else t
            )
        else:
            return (await rs.pull(Summary, target=result.source.ctx)).name

    return Depend(__wrapper__)


def alcommand(
    alconna: Alconna,
    guild: bool = True,
    private: bool = True,
    send_error: bool = False,
    post: bool = False,
) -> Wrapper:
    """
    saya-util 形式的注册一个消息事件监听器并携带 AlconnaDispatcher

    Args:
        alconna: 使用的 Alconna 命令
        guild: 命令是否群聊可用
        private: 命令是否私聊可用
        send_error: 是否发送错误信息
        post: 是否以事件发送输出信息
    """
    if alconna.meta.example and "$" in alconna.meta.example:
        alconna.meta.example = alconna.meta.example.replace("$", alconna.headers[0])

    def wrapper(func: T_Callable) -> T_Callable:
        cube: Cube[ListenerSchema] = ensure_cube_as_listener(func)
        cube.metaclass.listening_events.append(MessageReceived)
        if not guild and not private:
            raise ValueError
        if not guild:
            cube.metaclass.inline_dispatchers.append(Filter().ctx.follows("friend"))
        elif not private:
            cube.metaclass.inline_dispatchers.append(Filter().ctx.follows("group"))
        cube.metaclass.inline_dispatchers.append(
            AlconnaDispatcher(
                alconna, send_flag="post" if post else "reply", skip_for_unmatch=not send_error  # type: ignore
            )
        )
        channel = Channel.current()
        channel.use(AlconnaSchema(alconna))(func)
        return func

    return wrapper


def from_command(
    format_command: str,
    args: Optional[Dict[str, Union[type, BasePattern]]] = None,
    post: bool = False,
) -> Wrapper:
    """
    saya-util 形式的仅注入一个 AvillaAlconnaDispatcher, 事件监听部分自行处理

    Args:
        format_command: 格式化命令字符串
        args: 格式化填入内容
        post: 是否以事件发送输出信息
    """

    def wrapper(func: T_Callable) -> T_Callable:
        custom_args = {
            v.name: v.annotation for v in inspect.signature(func).parameters.values()
        }
        custom_args.update(args or {})
        cube: Cube[ListenerSchema] = ensure_cube_as_listener(func)
        cmd = AlconnaFormat(format_command, custom_args)
        cube.metaclass.inline_dispatchers.append(
            AvillaAlconnaDispatcher(cmd, send_flag="post" if post else "reply")  # type: ignore
        )
        channel = Channel.current()
        channel.use(AlconnaSchema(cmd))(func)
        return func

    return wrapper


__all__ = [
    "NoticeID",
    "fetch_name",
    "alcommand",
    "from_command",
]
