from __future__ import annotations

import time
from typing import Any


class _Timer:
    start: float
    end: float

    def __enter__(self) -> _Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.end = time.perf_counter()

    def __str__(self) -> str:
        if not self.start:
            raise RuntimeError("Timer not started.")
        if not self.end:
            raise RuntimeError("Timer not done.")

        interval = self.end - self.start
        return f"{interval:.0f}s"


timer = _Timer()
