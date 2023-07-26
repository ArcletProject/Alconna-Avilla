"""
Alconna 对于 Avilla 的支持

"""
from pathlib import Path
from tarina import lang

lang.load(Path(__file__).parent / "i18n")

from . import alc as alc
from .argv import BaseMessageChainArgv
from .dispatcher import AlconnaOutputMessage, AlconnaDispatcher
from .model import CommandResult, Match, Query, Header
from .saya import AlconnaBehaviour, AlconnaSchema
from .tools import (
    MatchPrefix,
    MatchSuffix,
    fetch_name,
    assign,
    endswith,
    alcommand,
    from_command,
    match_path,
    match_value,
    shortcuts,
    startswith,
    funcommand,
)

Alc = AlconnaDispatcher
AlconnaProperty = CommandResult
