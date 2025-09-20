
from __future__ import annotations
import logging

_DEF_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=_DEF_FMT)
