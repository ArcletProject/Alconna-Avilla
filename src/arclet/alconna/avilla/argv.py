from __future__ import annotations

from typing import Any
from arclet.alconna.argv import set_default_argv_type, argv_config
from arclet.alconna._internal._argv import Argv
from graia.amnesia.message import MessageChain
from graia.amnesia.message.element import Text


class BaseMessageChainArgv(Argv[MessageChain]):

    @staticmethod
    def generate_token(data: list[Any | list[str]]) -> int:
        return hash(''.join(i.__repr__() for i in data))


set_default_argv_type(BaseMessageChainArgv)

argv_config(
    BaseMessageChainArgv,
    filter_out=[],
    checker=lambda x: isinstance(x, MessageChain),
    to_text=lambda x: x.text if isinstance(x, Text) else None,
    converter=lambda x: MessageChain(x if isinstance(x, list) else [Text(x)])
)
