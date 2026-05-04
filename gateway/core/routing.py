"""Provider health checking + dual/multi-provider routing.

Used by api/llm_proxy.py and api/asr_proxy.py to pick the freshest healthy
upstream. Health is judged from a sliding-window success rate over the past
N requests + recent latency.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class ProviderStats:
    name: str
    window: deque[bool] = field(default_factory=lambda: deque(maxlen=50))
    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    last_call_at: float = 0.0
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        if not self.window:
            return 1.0  # assume healthy until proven otherwise
        return sum(self.window) / len(self.window)

    @property
    def p50_latency_ms(self) -> float | None:
        if not self.latencies:
            return None
        sorted_lat = sorted(self.latencies)
        return sorted_lat[len(sorted_lat) // 2] * 1000

    def record(self, success: bool, latency_s: float) -> None:
        self.window.append(success)
        self.latencies.append(latency_s)
        self.last_call_at = time.time()
        self.consecutive_failures = 0 if success else self.consecutive_failures + 1


class HealthChecker:
    """Tracks per-provider health for dual/multi routing decisions.

    Not a literal health *probe* — we observe real traffic. This avoids
    extra cost from periodic pings and makes the data trustworthy.
    """

    def __init__(self) -> None:
        self._stats: dict[str, ProviderStats] = defaultdict(
            lambda: ProviderStats(name="?")
        )
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Hook for any background bookkeeping (none needed yet)."""
        return None

    async def stop(self) -> None:
        return None

    async def record(self, provider: str, success: bool, latency_s: float) -> None:
        async with self._lock:
            stat = self._stats.setdefault(provider, ProviderStats(name=provider))
            stat.record(success, latency_s)

    def pick_primary(self, candidates: list[str]) -> str:
        """Pick the freshest healthy candidate, in caller-given preference order."""
        for name in candidates:
            stat = self._stats.get(name)
            if stat is None:
                return name  # untouched provider — try it
            if stat.success_rate >= 0.9 and stat.consecutive_failures < 3:
                return name
        # all unhealthy — return the first (we'll still try, with fallback inside)
        return candidates[0]

    def snapshot(self) -> dict[str, dict]:
        return {
            name: {
                "success_rate": round(stat.success_rate, 3),
                "p50_latency_ms": stat.p50_latency_ms,
                "consecutive_failures": stat.consecutive_failures,
                "samples": len(stat.window),
            }
            for name, stat in self._stats.items()
        }
