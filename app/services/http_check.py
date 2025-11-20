import json
import time
from typing import Any, Dict, Optional

import httpx


async def perform_http_request(
    method: str,
    url: str,
    headers_json: Optional[str] = None,
    body_json: Optional[str] = None,
    timeout_s: float = 15.0,
) -> Dict[str, Any]:
    headers = json.loads(headers_json) if headers_json else None
    data = json.loads(body_json) if body_json else None

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            resp = await client.request(method.upper(), url, headers=headers, json=data)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": resp.status_code < 500,
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "error": None,
            "text": resp.text[:1000],
        }
    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "error": str(exc),
            "text": None,
        }

