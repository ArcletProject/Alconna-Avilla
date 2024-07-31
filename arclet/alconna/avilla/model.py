from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Generic, Literal, Set, TypedDict, TypeVar, Union
from typing_extensions import NotRequired, TypeAlias

from graia.amnesia.message import MessageChain
from graia.broadcast.entities.event import Dispatchable

from arclet.alconna import Arparma, Empty

TSource = TypeVar("TSource", bound=Dispatchable)
T = TypeVar("T")
OutType = Literal["help", "shortcut", "completion", "error"]
TConvert: TypeAlias = Callable[[OutType, str], Union[MessageChain, Awaitable[MessageChain]]]


class Query(Generic[T]):
    """
    查询项，表示参数是否可由 `Arparma.query` 查询并获得结果

    result (T): 查询结果

    available (bool): 查询状态

    path (str): 查询路径
    """

    result: T
    available: bool
    path: str

    def __init__(self, path: str, default: T = Empty):
        self.path = path
        self.result = default
        self.available = False

    def __repr__(self):
        return f"Query({self.path}, {self.result})"


@dataclass
class Match(Generic[T]):
    """
    匹配项，表示参数是否存在于 `all_matched_args` 内

    result (T): 匹配结果

    available (bool): 匹配状态
    """

    result: T
    available: bool


@dataclass
class CommandResult(Generic[TSource]):
    """对解析结果的封装"""

    result: Arparma
    output_type: str
    output: str | None = field(default=None)
    source: TSource | None = field(default=None)


@dataclass
class Header:
    """
    头部项，表示命令头部为特殊形式时的头部匹配

    result (T): 匹配结果

    available (bool): 匹配状态
    """

    result: dict
    available: bool


class CompConfig(TypedDict):
    tab: NotRequired[str]
    enter: NotRequired[str]
    exit: NotRequired[str]
    timeout: NotRequired[int]
    priority: NotRequired[int]
    hide_tabs: NotRequired[bool]
    hides: NotRequired[Set[Literal["tab", "enter", "exit"]]]
    disables: NotRequired[Set[Literal["tab", "enter", "exit"]]]
    lite: NotRequired[bool]
