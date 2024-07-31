from nepattern import (
    BasePattern,
    MatchMode,
    UnionPattern,
)
from typing import Union
from avilla.core.elements import Notice

_NoticeID = BasePattern(mode=MatchMode.TYPE_CONVERT, origin=str, alias="Notice", accepts=Notice, converter=lambda _, x: x.target.pattern["member"])
_NoticeText = BasePattern(
    r"@(.+)",
    mode=MatchMode.REGEX_CONVERT,
    origin=str,
    alias="@xxx",
    converter=lambda _, x: x[1],
)

NoticeID = UnionPattern[Union[str, Notice]]([_NoticeID, _NoticeText]) @ "notice_id"  # type: ignore
"""
内置类型，允许传入提醒元素(Notice)或者'@xxxx'式样的字符串, 返回字符串
"""
