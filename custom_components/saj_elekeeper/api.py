"""Safe construction helpers for the Elekeeper API client."""

from __future__ import annotations

from datetime import date
from functools import partial
from time import time
from typing import Any, Mapping
from uuid import uuid4

import httpx
from elekeeper import SajApiError, SajClient
from elekeeper.exceptions import SajAuthError

from homeassistant.core import HomeAssistant

from .const import DEFAULT_REGION, REGION_BASE_URLS


async def async_create_client(
    hass: HomeAssistant, *, region: str = DEFAULT_REGION
) -> SajClient:
    """Create the HTTP client outside Home Assistant's event loop."""
    base_url = REGION_BASE_URLS.get(region, REGION_BASE_URLS[DEFAULT_REGION])
    return await hass.async_add_executor_job(partial(SajClient, base_url=base_url))


async def async_post_v2(
    client: SajClient,
    path: str,
    data: Mapping[str, Any],
    *,
    org_code: str | None = None,
) -> dict[str, Any]:
    """Call a private Elekeeper V2 endpoint with the portal's JSON headers."""
    if not client.token:
        raise SajAuthError("Login is required before calling Elekeeper V2")

    timestamp = int(time() * 1000)
    payload = {
        **data,
        "appProjectName": "elekeeper",
        "clientDate": date.today().isoformat(),
        "lang": client.language,
        "timeStamp": timestamp,
        "clientId": "esolar-monitor-admin",
        "clientCode": "organization",
        "themeColor": "light",
    }
    headers = {
        "Authorization": f"Bearer {client.token}",
        "Content-Type": "application/json;charset=utf-8",
        "Content-Language": "zh_CN",
        "lang": client.language,
        "X-App-Project-Name": "elekeeper",
        "X-Client-Date": payload["clientDate"],
        "X-Lang": client.language,
        "X-Timestamp": str(timestamp),
        "X-Client-Code": "organization",
        "X-Theme-Color": "light",
        "X-Trace-Id": uuid4().hex[:16],
    }
    if org_code:
        headers["X-Org-Code"] = org_code

    http_client: httpx.AsyncClient = client._client
    response = await http_client.post(
        f"{client.api_base}{path}", json=payload, headers=headers
    )
    response.raise_for_status()
    envelope = response.json()
    err_code = envelope.get("errCode", 0)
    if err_code != 0:
        raise SajApiError(err_code, envelope.get("errMsg", "Unknown error"), envelope)
    return envelope.get("data") or {}
