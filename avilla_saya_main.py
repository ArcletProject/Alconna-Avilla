from avilla.console.protocol import ConsoleProtocol
from avilla.core import Avilla
from creart import create
from graia.broadcast import Broadcast
from graia.saya import Saya
from launart import Launart

from arclet.alconna.avilla import AlconnaBehaviour

broadcast = create(Broadcast)
saya = create(Saya)
saya.install_behaviours(AlconnaBehaviour(broadcast))
launart = Launart()
avilla = Avilla(broadcast, launart, [ConsoleProtocol()])

with saya.module_context():
    saya.require("avilla_saya_module")

launart.launch_blocking(loop=broadcast.loop)
