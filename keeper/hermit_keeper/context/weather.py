"""Current weather from Open-Meteo. Owner: Abhishek (4.3). Free, no key.

Cached for ten minutes and given three seconds to answer. Weather is flavour:
if it is slow or down, Hermit says nothing about the sky and carries on. It is
never a reason for a handoff to stall.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from ..clock import Clock

log = structlog.get_logger(__name__)

ENDPOINT = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL_S = 600.0
TIMEOUT_S = 3.0


class Weather:
    def __init__(self, lat: float, lon: float, clock: Clock, client: Any = None) -> None:
        self._lat = lat
        self._lon = lon
        self._clock = clock
        self._client = client
        self._cached: dict[str, Any] | None = None
        self._cached_at: float = -CACHE_TTL_S * 2

    async def current(self) -> dict[str, Any] | None:
        """``{"temp_c": float, "code": int}``, or None if we could not tell."""
        now = self._clock.now().timestamp()
        if self._cached is not None and now - self._cached_at < CACHE_TTL_S:
            return self._cached

        params: dict[str, str] = {
            "latitude": str(self._lat),
            "longitude": str(self._lon),
            "current": "temperature_2m,weather_code",
        }
        try:
            if self._client is not None:
                response = await self._client.get(ENDPOINT, params=params, timeout=TIMEOUT_S)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(ENDPOINT, params=params, timeout=TIMEOUT_S)
            response.raise_for_status()
            current = response.json()["current"]
            self._cached = {
                "temp_c": float(current["temperature_2m"]),
                "code": int(current["weather_code"]),
            }
            self._cached_at = now
            return self._cached
        except Exception:  # network, timeout, shape change - all the same to us
            log.info("weather unavailable", lat=self._lat, lon=self._lon)
            return None
