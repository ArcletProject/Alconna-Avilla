from __future__ import annotations

from typing import TYPE_CHECKING

from creart import AbstractCreator, CreateTargetInfo, exists_module, it, mixin

if TYPE_CHECKING:
    from arclet.alconna.avilla.saya import AlconnaBehaviour


class AlconnaBehaviorCreator(AbstractCreator):
    targets = (
        CreateTargetInfo(
            module="arclet.alconna.avilla.saya",
            identify="AlconnaBehaviour",
            humanized_name="Saya Behavior of Alconna",
            description=(
                "<common, arclet, alconna> A High-performance, Generality, "
                "Humane Command Line Arguments Parser Library."
            ),
            author=["ArcletProject@github"],
        ),
    )
    from graia.broadcast.creator import BroadcastCreator
    from graia.saya.creator import SayaCreator

    @staticmethod
    @mixin(BroadcastCreator, SayaCreator)
    def available() -> bool:
        return exists_module("arclet.alconna.avilla.saya")

    @staticmethod
    def create(create_type: type[AlconnaBehaviour]) -> AlconnaBehaviour:
        from graia.broadcast import Broadcast
        from graia.saya import Saya

        broadcast = it(Broadcast)
        saya = it(Saya)
        behavior = create_type(broadcast)
        saya.install_behaviours(behavior)
        return behavior
