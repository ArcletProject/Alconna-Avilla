# Alconna Graia

该项目为 [`Alconna`](https://github.com/ArcletProject/Alconna) 为 [`GraiaProject`](https://github.com/GraiaProject) 下项目的内建支持

包括解析器、Dispatcher、SayaSchema 和 附加组件

## 快速使用

### 单文件

```python
from arclet.alconna.graia import Alconna, Match, AlconnaProperty
from arclet.alconna.avilla import AlconnaDispatcher
from arclet.alconna import Args
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
    result: AlconnaProperty[MessageReceived],
    sth: Match[str]
):
    print("sign:", result.result)
    print("sender:", context.scene)
    print("match", sth.available, sth.result)
```

### 使用 Saya

in module.py:
```python
from arclet.alconna.graia import Alconna, Match, AlconnaProperty, AlconnaSchema
from arclet.alconna.avilla import AlconnaDispatcher
from arclet.alconna import Args
...
channel = Channel.current()

alc = Alconna("!jrrp", Args["sth", str, 1123])

@channel.use(AlconnaSchema(AlconnaDispatcher(alc)))
@channel.use(ListenerSchema([MessageReceived]))
async def test2(context: Context, result: AlconnaProperty[MessageReceived], sth: Match[str]):
    print("sign:", result.result)
    print("sender:", context.scene)
    print("match", sth.available, sth.result)


```

in main.py:
```python
from arclet.alconna.graia import AlconnaBehaviour
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
from graiax.shortcut.saya import listen
from arclet.alconna.graia import Alconna, Match, from_command, startswith, endswith
from arclet.alconnaavilla import alcommand
from arclet.alconna import  Args, Arpamar

...


@alcommand(Alconna("!jrrp", Args["sth", str, 1123]), private=False)
async def test1(context: Context, result: Arpamar, sth: Match[str]):
    print("sign:", result)
    print("sender:", context.scene)
    print("match", sth.available, sth.result)


@alcommand("[!|.]hello <name:str>;say <word>", send_error=True)
async def test1(context: Context, result: Arpamar, name: Match[str]):
    print("sign:", result)
    print("sender:", context.scene)
    print("match", name.available, name.result)

    
@listen(MessageReceived) 
@from_command("foo bar {baz}")
async def test2(context: Context, baz: int):
    print("sender:", context.scene)
    print("baz", baz)
    
    
@listen(MessageReceived)
@startswith("foo bar")
async def test3(event: MessageReceived):
    ...


@listen(MessageReceived)
@endswith(int)
async def test4(event: MessageReceived):
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
        output_handler: type[TOHandler] | None = None,
        message_converter: Callable[[str], MessageChain | Coroutine[Any, Any, MessageChain]] | None = None,
    ): ...
```

`command`: 使用的 Alconna 指令

`send_flag`: 解析期间输出信息的发送方式
- reply: 直接发送给指令发送者
- post: 以事件通过 Broadcast 广播
- stay: 存入 AlconnaProperty 传递给事件处理器

`skip_for_unmatch`: 解析失败时是否跳过, 否则错误信息按 send_flag 处理

`output_handler`: 处理命令输出信息的发送的类

`message_converter`: send_flag 为 reply 时 输出信息的预处理器

## 附加组件

- `Match`: 查询某个参数是否匹配，如`foo: Match[int]`。使用时以 `Match.available` 判断是否匹配成功，以
`Match.result` 获取匹配结果

- `Query`: 查询某个参数路径是否存在，如`sth: Query[int] = Query("foo.bar")`；可以指定默认值如
`Query("foo.bar", 1234)`。使用时以 `Query.available` 判断是否匹配成功，以 `Query.result` 获取匹配结果

- `Header`: 表示命令头部为特殊形式时的头部匹配

- `assign`: 依托路径是否匹配成功为命令分发处理器。

```python
from arclet.alconna.graia import assign
from arclet.alconna.avilla import alcommand
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
from arclet.alconna.graia import Match
from arclet.alconna/avilla import Alc
...

@app.broadcast.receiver(
    MessageReceived, dispatchers=[Alc.from_format("foo bar {baz:int}")]
)
async def test2(baz: Match[int]):
    print("match", baz.available, baz.result)
```

or

```python
from arclet.alconna.graia import Match, AlconnaSchema
...
channel = Channel.current()

@channel.use(AlconnaSchema.from_("foo <arg:str>", "bar"))
@channel.use(ListenerSchema([MessageReceived]))
async def test2(sth: Match[str]):
    print("match", sth.available, sth.result)
```

## 文档

[链接](https://graiax.cn/guide/alconna.html#kirakira%E2%98%86dokidoki%E7%9A%84dispatcher)