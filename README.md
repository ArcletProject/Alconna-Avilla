# Alconna Avilla

该项目为 [`Alconna`](https://github.com/ArcletProject/Alconna) 为 [`Avilla`](https://github.com/GraiaProject/Avilla) 框架的内建支持

包括解析器、Dispatcher、SayaSchema 和 附加组件

> [!WARNING]
> 本项目与 `avilla.core.builtins.command` 不兼容

## 安装

```shell
pip install arclet-alconna-avilla
pdm add arclet-alconna-avilla
```

## 快速使用

### 单文件

```python
from arclet.alconna import Args, Alconna
from arclet.alconna.avilla import AlconnaDispatcher, Match, CommandResult
...
broadcast = create(Broadcast)
avilla = Avilla(...)


alc = Alconna("!jrrp", Args["sth", str, 1123])

@broadcast.receiver(
    MessageReceived,
    dispatchers=[AlconnaDispatcher(alc, send_flag='stay')]
)
async def test2(
    context: Context,
    result: CommandResult[MessageReceived],
    sth: Match[str]
):
    print("sign:", result.result)
    print("sender:", context.scene)
    print("match", sth.available, sth.result)
```

### 使用 Saya

in module.py:
```python
from arclet.alconna.avilla import AlconnaDispatcher, Match, CommandResult, AlconnaSchema
from arclet.alconna import Alconna, Args
...
channel = Channel.current()

alc = Alconna("!jrrp", Args["sth", str, 1123])

@channel.use(AlconnaSchema(AlconnaDispatcher(alc)))
@channel.use(ListenerSchema([...]))
async def test2(result: CommandResult[...], sth: Match[str]):
    print("sign:", result.result)
    print("match", sth.available, sth.result)


```

in main.py:
```python
from arclet.alconna.avilla import AlconnaBehaviour
from creart import create
...

saya = create(Saya)
create(AlconnaBehaviour)

with saya.module_context():
    saya.require("module")

```
### 使用 Saya Util

in module.py:

```python
from graia.saya.builtins.broadcast.shortcut import listen
from arclet.alconna.avilla import alcommand, Match, from_command, startswith, endswith
from arclet.alconna import  Args, Arparma, Alconna

...


@alcommand(Alconna("!jrrp", Args["sth", str, 1123]), private=False)
async def test1(result: Arparma, sth: Match[str]):
    print("sign:", result)
    print("match", sth.available, sth.result)


@alcommand("[!|.]hello <name:str>", send_error=True)
async def test1(result: Arparma, name: Match[str]):
    print("sign:", result)
    print("match", name.available, name.result)

    
@listen(...) 
@from_command("foo bar {baz}")
async def test2(baz: int):
    print("baz", baz)
    
    
@listen(...)
@startswith("foo bar")
async def test3(event: ...):
    ...


@listen(...)
@endswith(int)
async def test4(event: ...):
    ...
```

in main.py:
```python
from creart import create
...

saya = create(Saya)

with saya.module_context():
    saya.require("module")

```

## AlconnaDispatcher 参数说明

```python
class AlconnaDispatcher(BaseDispatcher, Generic[TOHandler]):
    def __init__(
        self,
        command: Alconna | AlconnaGroup,
        *,
        send_flag: Literal["reply", "post", "stay"] = "stay",
        skip_for_unmatch: bool = True,
        comp_session: Optional[CompConfig] = None,
        message_converter: Callable[[OutType, str], MessageChain | Coroutine[Any, Any, MessageChain]] | None = None,
    ): ...
```

`command`: 使用的 Alconna 指令

`send_flag`: 解析期间输出信息的发送方式
- reply: 直接发送给指令发送者
- post: 以事件通过 Broadcast 广播
- stay: 存入 CommandResult 传递给事件处理器

`skip_for_unmatch`: 解析失败时是否跳过, 否则错误信息按 send_flag 处理

`comp_session`: 补全会话配置, 不传入则不启用补全会话

`message_converter`: send_flag 为 reply 时 输出信息的预处理器

## 附加组件

- `Match`: 查询某个参数是否匹配，如`foo: Match[int]`。使用时以 `Match.available` 判断是否匹配成功，以
`Match.result` 获取匹配结果

- `Query`: 查询某个参数路径是否存在，如`sth: Query[int] = Query("foo.bar")`；可以指定默认值如
`Query("foo.bar", 1234)`。使用时以 `Query.available` 判断是否匹配成功，以 `Query.result` 获取匹配结果

- `Header`: 表示命令头部为特殊形式时的头部匹配

- `assign`: 依托路径是否匹配成功为命令分发处理器。

```python
from arclet.alconna.avilla import assign, alcommand
from arclet.alconna import Alconna, Arpamar
...

alc = Alconna(...)

@alcommand(alc, private=False)
@assign("foo")
async def foo(result: Arpamar):
    ...

@alcommand(alc, private=False)
@assign("bar.baz", 1)
async def bar_baz_1(result: Arpamar):
    ...
```

## 便捷方法

```python
from arclet.alconna.avilla import Match, Alc
...

@app.broadcast.receiver(
    ..., dispatchers=[Alc.from_format("foo bar {baz:int}")]
)
async def test2(baz: Match[int]):
    print("match", baz.available, baz.result)
```

or

```python
from arclet.alconna.avilla import Match, AlconnaSchema
...
channel = Channel.current()

@channel.use(AlconnaSchema.from_("foo {sth:str} bar {baz:int}"))
@channel.use(ListenerSchema([...]))
async def test2(sth: Match[str]):
    print("match", sth.available, sth.result)
```

## 文档

[链接](https://graiax.cn/guide/alconna.html#kirakira%E2%98%86dokidoki%E7%9A%84dispatcher)