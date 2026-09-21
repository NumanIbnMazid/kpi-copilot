"""Optional file-backed transport for an assistant's connected services.

The pipeline owns requests and validation; the host owns authentication. Credentials never
enter request files. A transport is usable only while a host has explicitly enabled its
service in a private session manifest. Ordinary CLI/token operation is unchanged.
"""
from __future__ import annotations

import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


class TransportError(RuntimeError):
    pass


def directory() -> Path | None:
    value = os.environ.get("KPI_HOST_BRIDGE")
    return Path(value).expanduser().resolve() if value else None


def enabled(service: str) -> bool:
    root = directory()
    if not root:
        return False
    try:
        manifest = json.loads((root / "session.json").read_text())
        return service in manifest.get("services", []) and float(manifest.get("expires_at", 0)) > time.time()
    except (OSError, ValueError, TypeError):
        return False


def call(service: str, method: str, url: str, body: Any = None,
         params: dict | None = None, raw: bool = False, timeout: float = 180,
         headers: dict | None = None) -> Any:
    root = directory()
    if not root or not enabled(service):
        raise TransportError(f"The host's {service} connection is not active.")
    job = uuid.uuid4().hex
    request = root / f"{job}.request.json"
    response = root / f"{job}.response.json"
    data = {"id": job, "service": service, "method": method, "url": url,
            "body": body, "params": params, "raw": raw, "headers": headers,
            "expires_at": time.time() + timeout}
    if any(k.lower() in ("authorization", "cookie") for k in (headers or {})):
        raise TransportError("Credentials must stay in the host connection.")
    # Atomic publication lets concurrent history readers share one host connection.
    temporary = request.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    temporary.chmod(0o600)
    temporary.replace(request)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if response.exists():
            result = json.loads(response.read_text())
            if result.get("error"):
                raise TransportError(str(result["error"]))
            if raw:
                if "base64" in result:
                    return base64.b64decode(result["base64"], validate=True)
                if "file" in result:
                    path = Path(result["file"]).resolve()
                    if root not in path.parents:
                        raise TransportError("Host download is outside its private session folder.")
                    return path.read_bytes()
                raise TransportError("Host did not return the requested file bytes.")
            if "data" not in result:
                raise TransportError("Host returned an incomplete response.")
            return result["data"]
        time.sleep(0.1)
    raise TransportError(f"The host did not finish the {service} request. Reconnect it and retry.")
