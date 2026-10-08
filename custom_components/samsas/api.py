"""The handful of calls to app/homeassistant.py in the Samsas repo."""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp


class SamsasError(Exception):
    """Samsas could not be reached, or answered with an error."""


class SamsasAuthError(SamsasError):
    """The token is wrong, or has been rotated in the app."""


class SamsasApi:
    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self.base = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        try:
            async with self._session.request(
                method, f"{self.base}/hass/v1{path}", headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15), **kwargs,
            ) as resp:
                if resp.status == 401:
                    raise SamsasAuthError("Samsas did not accept the token")
                if resp.status >= 400:
                    raise SamsasError(f"Samsas answered {resp.status} on {path}")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SamsasError(f"Could not reach Samsas: {err}") from err

    async def state(self, day: date) -> dict:
        return await self._request("GET", "/state", params={"day": day.isoformat()})

    async def events(self, start: date, end: date) -> dict:
        return await self._request("GET", "/events", params={"start": start.isoformat(), "end": end.isoformat()})

    async def add_item(self, list_name: str, text: str, due: str | None = None) -> dict:
        return await self._request("POST", f"/lists/{list_name}", json={"text": text, "due": due})

    async def update_item(self, item_id: int, **fields: Any) -> dict:
        return await self._request("PATCH", f"/items/{item_id}", json=fields)

    async def delete_item(self, item_id: int) -> dict:
        return await self._request("DELETE", f"/items/{item_id}")
