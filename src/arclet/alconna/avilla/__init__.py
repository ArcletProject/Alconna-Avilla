"""
Alconna 对于 Graia 系列的支持

"""

from . import alc as alc
from .adapter import AlconnaGraiaAdapter
from .argv import BaseMessageChainArgv
from .dispatcher import AlconnaOutputMessage, AlconnaDispatcher
from .model import CommandResult, Match, Query, Header
from .saya import AlconnaBehaviour, AlconnaSchema
from .service import AlconnaGraiaService
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
    check_account,
    mention,
    funcommand,
)

Alc = AlconnaDispatcher
AlconnaProperty = CommandResult
