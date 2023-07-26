from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar, Union
from tarina import gen_subclass

from graia.broadcast import Decorator
from graia.broadcast.entities.event import Dispatchable
from graia.saya.builtins.broadcast import ListenerSchema
from graia.saya.factory import SchemaWrapper, factory
from typing_extensions import ParamSpec


@factory
def listen(*event: type[Dispatchable] | str) -> SchemaWrapper:
    """在当前 Saya Channel 中监听指定事件

    Args:
        *event (Union[Type[Dispatchable], str]): 事件类型或事件名称

    Returns:
        Callable[[T_Callable], T_Callable]: 装饰器
    """
    EVENTS: dict[str, type[Dispatchable]] = {e.__name__: e for e in gen_subclass(Dispatchable)}
    events: list[type[Dispatchable]] = [e if isinstance(e, type) else EVENTS[e] for e in event]

    def wrapper(func: Callable, buffer: dict[str, Any]) -> ListenerSchema:
        decorator_map: dict[str, Decorator] = buffer.pop("decorator_map", {})
        buffer["inline_dispatchers"] = buffer.pop("dispatchers", [])
        if decorator_map:
            sig = inspect.signature(func)
            for param in sig.parameters.values():
                if decorator := decorator_map.get(param.name):
                    setattr(param, "_default", decorator)
            func.__signature__ = sig
        return ListenerSchema(listening_events=events, **buffer)

    return wrapper


T_Callable = TypeVar("T_Callable", bound=Callable)

R = TypeVar("R")
P = ParamSpec("P")
