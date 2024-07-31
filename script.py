import shutil
from pathlib import Path

target = Path("./arclet/alconna/avilla")
backport = Path("./arclet/alconna/graia")


def pre_build():
    shutil.rmtree(backport, ignore_errors=True)
    shutil.copytree(target, backport)


def post_build() -> None:
    shutil.rmtree(backport, ignore_errors=True)
