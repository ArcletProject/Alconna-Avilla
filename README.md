# Alconna-Avilla

Support Alconna for Avilla

## 示例

```python
from creart import it
from arclet.alconna import Alconna
from arclet.alconna.avilla import Alc
from graia.broadcast import Broadcast
from avilla.core import MessageReceived, Relationship, Avilla

bcc = it(Broadcast)
avilla = Avilla(...)


@bcc.receiver(MessageReceived, dispatchers=[Alc(Alconna(...))])
async def _(rs: Relationship, event: MessageReceived):
    ...
```