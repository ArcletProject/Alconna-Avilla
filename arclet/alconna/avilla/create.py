from __future__ import annotations

from typing import TYPE_CHECKING 
from creart import AbstractCreator, CreateTargetInfo, it, exists_module, mixin

if TYPE_CHECKING:
    from arclet.alconna.graia.saya import AlconnaBehaviour


class AlconnaBehaviorCreator(AbstractCreator):
    targets = (
        CreateTargetInfo(
            module="arclet.alconna.graia.saya",
            identify="AlconnaBehaviour",
            humanized_name="Saya Behavior of Alconna",
            description=(
                "<common, arclet, alconna> A High-performance, Generality, "
                "Humane Command Line Arguments Parser Library."
            ),
            author=["ArcletProject@github"],
        ),
    )
    from graia.creart.broadcast import BroadcastCreator
    from graia.creart.saya import SayaCreator

    @staticmethod
    @mixin(BroadcastCreator, SayaCreator)
    def available() -> bool:
        return exists_module("arclet.alconna.graia.saya")

    @staticmethod
    def create(create_type: type[AlconnaBehaviour]) -> AlconnaBehaviour:
        from graia.broadcast import Broadcast
        from graia.saya import Saya

        broadcast = it(Broadcast)
        saya = it(Saya)
        behavior = create_type(broadcast)
        saya.install_behaviours(behavior)
        return behavior
