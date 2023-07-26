from __future__ import annotations

from dataclasses import dataclass
from typing import Any 

from arclet.alconna.core import Alconna
from arclet.alconna.manager import command_manager
from arclet.alconna.tools import AlconnaFormat
from graia.broadcast import Broadcast
from graia.saya.behaviour import Behaviour
from graia.saya.cube import Cube
from graia.saya.schema import BaseSchema

from .dispatcher import AlconnaDispatcher


@dataclass
class AlconnaSchema(BaseSchema):
    command: Alconna | AlconnaDispatcher

    @classmethod
    def from_(cls, command: str, flag: str = "reply") -> AlconnaSchema:
        return cls(
            AlconnaDispatcher(AlconnaFormat(command), send_flag=flag)  # type: ignore
        )

    def record(self, func: Any):
        command: Alconna
        if isinstance(self.command, AlconnaDispatcher):
            command = self.command.command
        else:
            command = self.command
        if shortcuts := getattr(func, "__alc_shortcuts__", {}):
            for k, v in shortcuts.items():
                command.shortcut(k, v)


class AlconnaBehaviour(Behaviour):
    """命令行为"""

    def __init__(self, broadcast: Broadcast) -> None:
        self.broadcast = broadcast

    def allocate(self, cube: Cube[AlconnaSchema]):
        if not isinstance(cube.metaclass, AlconnaSchema):
            return
        if listener := self.broadcast.getListener(cube.content):
            for dispatcher in listener.dispatchers:
                if isinstance(dispatcher, AlconnaDispatcher):
                    cube.metaclass.command = dispatcher.command
                    cube.metaclass.record(cube.content)
                    return True
            if isinstance(cube.metaclass.command, AlconnaDispatcher):
                listener.dispatchers.append(cube.metaclass.command)
                cube.metaclass.record(cube.content)
                return True
            return
        cube.metaclass.record(cube.content)
        return True

    def release(self, cube: Cube[AlconnaSchema]):
        if not isinstance(cube.metaclass, AlconnaSchema):
            return
        if isinstance(cube.metaclass.command, AlconnaDispatcher):
            cmd = cube.metaclass.command.command
        else:
            cmd = cube.metaclass.command
        command_manager.delete(cmd)
        return True
