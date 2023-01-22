from __future__ import annotations

from contextlib import suppress
from typing import Any, Callable, Union

from avilla.core.context import Context
from avilla.core.elements import Notice
from avilla.core.tools.filter import Filter
from avilla.spec.core.message import MessageEdited, MessageReceived
from avilla.spec.core.profile import Summary
from graia.amnesia.message import MessageChain
from graia.broadcast.builtin.decorators import Depend
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from graia.broadcast.utilles import run_always_await

from arclet.alconna import Arparma

from arclet.alconna.graia import AlconnaProperty, AlconnaSchema
from arclet.alconna.graia.adapter import AlconnaGraiaAdapter
from arclet.alconna.graia.analyser import MessageChainContainer
from arclet.alconna.graia.dispatcher import AlconnaDispatcher, AlconnaOutputMessage

AvillaMessageEvent = Union[MessageEdited, MessageReceived]


class AlconnaAvillaAdapter(AlconnaGraiaAdapter[AvillaMessageEvent]):
    async def send(
        self,
        dispatcher: AlconnaDispatcher,
        result: Arparma[MessageChain],
        output_text: str | None = None,
        source: AvillaMessageEvent | None = None,
    ) -> AlconnaProperty[AvillaMessageEvent]:
        if not isinstance(source, (MessageEdited, MessageReceived)) or (result.matched or not output_text):
            return AlconnaProperty(result, None, source)
        id_ = id(source) if source else 0
        cache = self.output_cache.setdefault(id_, set())
        if dispatcher.command in cache:
            return AlconnaProperty(result, None, source)
        cache.clear()
        cache.add(dispatcher.command)
        if dispatcher.send_flag == "stay":
            return AlconnaProperty(result, output_text, source)
        if dispatcher.send_flag == "reply":
            ctx: Context = source.context
            help_message: MessageChain = await run_always_await(dispatcher.converter, output_text)
            await ctx.scene.send_message(help_message)
        elif dispatcher.send_flag == "post":
            with suppress(LookupError):
                interface = DispatcherInterface.ctx.get()
                dispatchers = [self.Dispatcher(dispatcher.command, output_text, source), source.Dispatcher]
                for listener in interface.broadcast.default_listener_generator(AlconnaOutputMessage):
                    await interface.broadcast.Executor(listener, dispatchers)
                    listener.oplog.clear()
        return AlconnaProperty(result, None, source)

    def fetch_name(self, path: str) -> Depend:
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

    def check_account(self, path: str) -> Depend:
        async def __wrapper__(ctx: Context, arp: Arparma):
            match: Notice | str | bytes = arp.query(path, b"\0")
            if isinstance(match, bytes):
                return True
            if isinstance(match, str):
                bot_name = (await ctx.pull(Summary, target=ctx.self)).name
                if bot_name == match:
                    return True
            if isinstance(match, Notice) and match.target == ctx.self:
                return True
            raise ExecutionStop

        return Depend(__wrapper__)

    def alcommand(
        self, dispatcher: AlconnaDispatcher, guild: bool, private: bool, private_name: str, guild_name: str
    ) -> Callable[[Callable, dict[str, Any]], AlconnaSchema]:
        private_name = "friend" if private_name == "private" else private_name
        guild_name = "group" if guild_name == "guild" else guild_name

        def wrapper(func: Callable, buffer: dict[str, Any]):
            _filter = Filter().scene
            _dispatchers = buffer.setdefault("dispatchers", [])
            if not guild:
                _dispatchers.append(_filter.follows(private_name))
            if not private:
                _dispatchers.append(_filter.follows(guild_name))
            _dispatchers.append(dispatcher)
            listen(MessageReceived, MessageEdited)(func)  # noqa
            return AlconnaSchema(dispatcher.command)

        return wrapper


MessageChainContainer.config(filter_out=[])
