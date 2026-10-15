"""The handful of calls to app/homeassistant.py in the Samsas repo."""

from __future__ import annotations

from datetime import date
from typing import Any

import aiohttp


class SamsasError(Exception):
    """Samsas could not be reached, or answered with an error."""

    def __init__(self, message: str = "", status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


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
                **({"timeout": aiohttp.ClientTimeout(total=15)} | kwargs),
            ) as resp:
                if resp.status == 401:
                    raise SamsasAuthError("Samsas did not accept the token")
                if resp.status >= 400:
                    # the server explains itself in Swedish ({"detail": ...}); pass that on
                    try:
                        detail = (await resp.json()).get("detail")
                    except (aiohttp.ContentTypeError, ValueError):
                        detail = None
                    raise SamsasError(detail if isinstance(detail, str) else f"Samsas answered {resp.status} on {path}", resp.status)
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SamsasError(f"Could not reach Samsas: {err}") from err

    async def state(self, day: date) -> dict:
        return await self._request("GET", "/state", params={"day": day.isoformat()})

    async def events(self, start: date, end: date) -> dict:
        return await self._request("GET", "/events", params={"start": start.isoformat(), "end": end.isoformat()})

    async def add_item(self, list_name: str, text: str, due: str | None = None) -> dict:
        return await self._request("POST", f"/lists/{list_name}", json={"text": text, "due": due})

    async def add_custom_item(self, list_id: int, text: str, due: str | None = None) -> dict:
        """A row on one of the household's own lists (Egna listor)."""
        return await self._request("POST", f"/lists/custom/{list_id}", json={"text": text, "due": due})

    async def update_item(self, item_id: int, **fields: Any) -> dict:
        return await self._request("PATCH", f"/items/{item_id}", json=fields)

    async def import_recipe(self, url: str | None, text: str | None, member: int | None) -> dict:
        """A recipe into the cookbook (Samsas Plus), starred by `member`."""
        return await self._request("POST", "/import", json={"url": url, "text": text, "member": member},
                                   timeout=aiohttp.ClientTimeout(total=90))   # reading a page with the model takes a while

    async def delete_item(self, item_id: int) -> dict:
        return await self._request("DELETE", f"/items/{item_id}")

    async def share_entities(self, entities: list[dict], complete: bool = False) -> dict:
        """The house's values for the Huset card; `complete` is the whole set, in order."""
        return await self._request("POST", "/entities", json={"entities": entities, "complete": complete})

    async def notify(self, message: str, title: str | None = None, members: list[int] | None = None) -> dict:
        """A push to the adults (Samsas Plus), in the household's own words."""
        return await self._request("POST", "/notify", json={"message": message, "title": title, "members": members})
