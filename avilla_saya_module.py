from avilla.console.element import Emoji, Markdown
from avilla.core import Context, MessageChain, MessageReceived, Text
from graia.saya.builtins.broadcast.shortcut import listen
from tarina import lang

from arclet.alconna import Alconna, Args, Arparma, CommandMeta, Field, MultiVar, Option, Subcommand
from arclet.alconna.avilla import Match, alcommand, assign, funcommand, startswith


@alcommand(Alconna("/lang", Args["lang", ["zh_CN", "en_US"]]))
async def on_message_received(ctx: Context, arp: Arparma):
    try:
        lang.select(arp["lang"])
    except ValueError as e:
        return await ctx.scene.send_message(str(e))
    await ctx.scene.send_message("ok")


@alcommand(Alconna("/help"))
async def on_message_received1(ctx: Context):
    await ctx.scene.send_message(
        [
            Markdown(
                """\
## 菜单
- /help
- /lang
- /echo
- /md
- /pip
- /emoji
"""
            )
        ]
    )


@listen(MessageReceived)
@startswith("/echo", bind="content")
async def on_message_received2(ctx: Context, content: MessageChain):
    await ctx.scene.send_message(content)


@alcommand(Alconna("/md"))
async def on_message_received3(ctx: Context):
    await ctx.scene.send_message(
        [
            Markdown(
                """\
# Avilla-Console

`avilla` 的 `Console` 适配，使用 `Textual`

参考: [`nonebot-adapter-console`](https://github.com/nonebot/adapter-console)

## 样例

```python
from creart import create
from launart import Launart
from graia.broadcast import Broadcast

from avilla.core import Avilla, Context, MessageReceived
from avilla.console.protocol import ConsoleProtocol

broadcast = create(Broadcast)
launart = Launart()
avilla = Avilla(broadcast, launart, [ConsoleProtocol()])


@broadcast.receiver(MessageReceived)
async def on_message_received(ctx: Context):
    await ctx.scene.send_message("Hello, Avilla!")


launart.launch_blocking(loop=broadcast.loop)

```
"""
            )
        ]
    )


@alcommand(Alconna("/emoji", Args["emoji", str, "art"]))
async def on_message_received4(ctx: Context, emoji: Match[str]):
    await ctx.scene.send_message([Emoji(emoji.result), " | this is apple -> ", Emoji("apple")])


tt = Alconna(
    "/pip",
    Subcommand(
        "install",
        Option("--upgrade", help_text="升级包"),
        Option("-i|--index-url", Args["url", "url"]),
        Args["pak", str],
        help_text="安装一个包",
    ),
    Option("--retries", Args["retries", int], help_text="设置尝试次数"),
    Option("-t|--timeout", Args["sec", int], help_text="设置超时时间"),
    Option("--exists-action", Args["action", str], help_text="添加行为"),
    Option("--trusted-host", Args["host", str], help_text="选择可信赖地址"),
)


@alcommand(tt, comp_session={"tab": "next"})
@assign("$main")
async def on_message_received5(ctx: Context, arp: Arparma):
    await ctx.scene.send_message("Hello, Completion Main!")
    await ctx.scene.send_message(str(arp.all_matched_args))


@alcommand(tt, comp_session={"tab": "next"})
@assign("install")
async def on_message_received6(ctx: Context, arp: Arparma):
    await ctx.scene.send_message("Hello, Completion Install!")
    await ctx.scene.send_message(str(arp.all_matched_args))


code = Alconna(
    "执行",
    Args["code", MultiVar(str), Field(completion=lambda: "试试 print(1+1)")] / "\n",
    Option("--pure-text"),
    Option("--out", Args["name", str, "res"]),
    meta=CommandMeta(description="执行简易代码", example="$执行 print(1+1)", hide=True),
)
code.shortcut(
    "命令概览",
    {"command": "执行\nfrom arclet.alconna import command_manager\nprint(command_manager)"},
)
code.shortcut("echo", {"command": "执行 --pure-text\nprint(\\'{*}\\')"})


@alcommand(code)
async def on_message_received7(ctx: Context, arp: Arparma):
    await ctx.scene.send_message("Hello, Shortcut!")
    await ctx.scene.send_message(str(arp.all_matched_args))
    await ctx.scene.send_message(str(list(arp.code)))


@funcommand()
def add(a: float, b: float):
    return f"{a} + {b} = {a + b}"
