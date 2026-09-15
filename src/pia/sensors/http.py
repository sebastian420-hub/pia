import os

import requests

DEFAULT_TIMEOUT = int(os.getenv("CAMERA_HTTP_TIMEOUT", "40"))
USER_AGENT = "PIA-camera-agent/1.0 (+https://github.com/sebastian420-hub/pia)"


def relay_url() -> str:
    """Base URL of the US relay, or '' when none is configured."""
    return os.getenv("RELAY_URL", "").rstrip("/")


def relay_token() -> str:
    return os.getenv("RELAY_TOKEN", "")


def get(url: str, via_relay: bool = False, **kwargs) -> requests.Response:
    """GET with sane defaults. via_relay routes through RELAY_URL/fetch?url=... when configured."""
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    headers.update(kwargs.pop("headers", {}) or {})
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    if via_relay:
        base = relay_url()
        if not base:
            raise RuntimeError("RELAY_URL is not configured; this provider needs the US relay")
        headers["Authorization"] = f"Bearer {relay_token()}"
        return requests.get(f"{base}/fetch", params={"url": url}, headers=headers, timeout=timeout, **kwargs)
    return requests.get(url, headers=headers, timeout=timeout, **kwargs)
