from __future__ import annotations

from typing import Any, Callable, Union

from avilla.core.context import Context
from avilla.core.elements import Notice
from avilla.core.tools.filter import Filter
from avilla.standard.core.message import MessageEdited, MessageReceived
from avilla.standard.core.profile import Summary
from graia.amnesia.message import MessageChain
from graia.amnesia.message.element import Text
from graia.broadcast import BaseDispatcher
from graia.broadcast.builtin.decorators import Depend
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.interrupt import Waiter
from graia.broadcast.utilles import run_always_await

from arclet.alconna import Arparma
from arclet.alconna.exceptions import SpecialOptionTriggered
from arclet.alconna.tools.construct import FuncMounter
from tarina import is_awaitable

from ..graia.model import CommandResult, TConvert
from ..graia.adapter import AlconnaGraiaAdapter
from ..graia.dispatcher import AlconnaDispatcher
from ..graia.utils import listen

AlconnaDispatcher.default_send_handler = lambda _, x: MessageChain([Text(x)])

AvillaMessageEvent = Union[MessageEdited, MessageReceived]


class AlconnaAvillaAdapter(AlconnaGraiaAdapter[AvillaMessageEvent]):

    def handle_listen(
        self,
        func: Callable,
        buffer: dict[str, Any],
        dispatcher: BaseDispatcher | None,
        guild: bool,
        private: bool,
        patterns: list[str] | None = None,
    ) -> None:
        _filter = Filter().cx.client
        _dispatchers = buffer.setdefault("dispatchers", [])
        if patterns:
            _dispatchers.append(_filter.follows(*patterns))
        if dispatcher:
            _dispatchers.append(dispatcher)
        listen(MessageReceived, MessageEdited)(func)


    def handle_command(self, alc: FuncMounter[Any, MessageChain]) -> Callable:
        async def wrapper(ctx: Context, message: MessageChain):
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
        return wrapper