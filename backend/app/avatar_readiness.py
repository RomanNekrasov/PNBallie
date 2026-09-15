"""Bounded private readiness probe, without sending a photograph or loading models."""

from urllib.parse import urljoin

import httpx

from app.avatar_providers import AvatarSettings

CAPACITY_MESSAGE = "De eigen server heeft nu onvoldoende vrije capaciteit. Probeer later opnieuw."
UNAVAILABLE_MESSAGE = "De eigen server is niet bereikbaar. Probeer later opnieuw."


async def local_status(config: AvatarSettings) -> str:
    if not config.local_available:
        return "unconfigured"
    if not config.check_capacity:
        return "unknown"
    try:
        async with httpx.AsyncClient(timeout=2, follow_redirects=False) as client:
            # The endpoint returns a tiny fixed-state object, never model output.
            async with client.stream("GET", urljoin(config.local_url, "/v1/status"),
                                     headers={"Authorization": f"Bearer {config.local_token}"}) as response:
                if response.status_code != 200:
                    return "unavailable"
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1024:
                        return "unavailable"
                payload = httpx.Response(200, content=bytes(raw)).json()
        state = payload.get("state") if isinstance(payload, dict) else None
        return state if isinstance(state, str) and state in {"ready", "busy", "capacity", "unavailable"} else "unavailable"
    except (httpx.HTTPError, ValueError):
        return "unavailable"
