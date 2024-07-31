# This file is @generated by tarina.lang CLI tool
# It is not intended for manual editing.

from tarina.lang.model import LangModel, LangItem


class CompletionAvilla:
    tab: LangItem = LangItem("completion", "avilla.tab")
    enter: LangItem = LangItem("completion", "avilla.enter")
    exit: LangItem = LangItem("completion", "avilla.exit")
    other: LangItem = LangItem("completion", "avilla.other")
    timeout: LangItem = LangItem("completion", "avilla.timeout")
    exited: LangItem = LangItem("completion", "avilla.exited")


class Completion:
    avilla = CompletionAvilla


class Lang(LangModel):
    completion = Completion