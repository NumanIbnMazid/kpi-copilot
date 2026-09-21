#!/usr/bin/env python3
"""
Google Drive and Sheets, with nothing to install.

Two things need Google: reading a source that lives in Drive (the plan, the estimates, a
project tracker), and keeping the KPI sheet as a live Google Sheet that every run updates in
place. Both used to go through an assistant's connector, which means the file's contents
travelling through a chat window - the slow way to move a spreadsheet, and one that cannot
update an existing file at all.

So this talks to the APIs directly, using only the standard library. Two ways to sign in:

  * You, once, in a browser.   `kpi.py auth google` opens a consent page and keeps a refresh
    token in ~/.config/kpi-copilot/google_token.json (readable only by you). It needs an
    OAuth client of type "Desktop app" - one per company is enough - saved as
    ~/.config/kpi-copilot/google_client.json. Files are read and written as you.

  * A service account.   Put its key at ~/.config/kpi-copilot/google_service_account.json
    (or point GOOGLE_APPLICATION_CREDENTIALS at it) and share the Drive folder with the
    account's address. Nothing to click, which suits a scheduled run.

Without either, nothing breaks: the run writes the workbook locally and says, in one line,
what to do to get the Google copy.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
]
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE = "https://www.googleapis.com/drive/v3/files"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GSHEET = "application/vnd.google-apps.spreadsheet"


class GoogleError(RuntimeError):
    pass


def config_dir() -> Path:
    return Path(os.environ.get("KPI_COPILOT_HOME") or Path.home() / ".config" / "kpi-copilot")


def file_id(ref: str | None) -> str | None:
    """A Drive id out of whatever was pasted: a bare id, a /d/<id>/ link, a folders/<id> link
    or an ?id= link."""
    if not ref:
        return None
    ref = str(ref).strip()
    for pat in (r"/d/([A-Za-z0-9_-]{20,})", r"/folders/([A-Za-z0-9_-]{15,})", r"[?&]id=([A-Za-z0-9_-]{20,})"):
        m = re.search(pat, ref)
        if m:
            return m.group(1)
    return ref if re.fullmatch(r"[A-Za-z0-9_-]{20,}", ref) else None


def looks_like_drive(ref: str | None) -> bool:
    ref = str(ref or "")
    return "docs.google.com" in ref or "drive.google.com" in ref or bool(re.fullmatch(r"[A-Za-z0-9_-]{25,}", ref))


# --------------------------------------------------------------------------------------
# RS256 without a crypto library, for the service-account route
# --------------------------------------------------------------------------------------

def _der(buf: bytes, pos: int) -> tuple[int, bytes, int]:
    tag, length, pos = buf[pos], buf[pos + 1], pos + 2
    if length & 0x80:
        n = length & 0x7F
        length, pos = int.from_bytes(buf[pos:pos + n], "big"), pos + n
    return tag, buf[pos:pos + length], pos + length


def _seq(buf: bytes) -> list[tuple[int, bytes]]:
    out, pos = [], 0
    while pos < len(buf):
        tag, val, pos = _der(buf, pos)
        out.append((tag, val))
    return out


def _rsa_key(pem: str) -> tuple[int, int]:
    body = "".join(l for l in pem.strip().splitlines() if "-----" not in l)
    top = _seq(_der(base64.b64decode(body), 0)[1])
    if len(top) == 3 and top[2][0] == 0x04:          # PKCS#8 wraps the RSA key in an octet string
        top = _seq(_der(top[2][1], 0)[1])
    n, d = int.from_bytes(top[1][1], "big"), int.from_bytes(top[3][1], "big")
    return n, d


_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def rs256(message: bytes, pem: str) -> bytes:
    n, d = _rsa_key(pem)
    k = (n.bit_length() + 7) // 8
    digest = _SHA256_PREFIX + hashlib.sha256(message).digest()
    block = b"\x00\x01" + b"\xff" * (k - len(digest) - 3) + b"\x00" + digest
    return pow(int.from_bytes(block, "big"), d, n).to_bytes(k, "big")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# --------------------------------------------------------------------------------------
# tokens
# --------------------------------------------------------------------------------------

def _post_form(url: str, fields: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode("ascii"),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise GoogleError(f"Google refused the sign-in ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise GoogleError(f"Could not reach Google: {e.reason}") from e


def _service_account_path() -> Path | None:
    for p in (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"), config_dir() / "google_service_account.json"):
        if p and Path(p).exists():
            return Path(p)
    return None


def how_signed_in() -> str:
    """'service-account', 'user' or '' - without touching the network."""
    import host_transport
    if host_transport.enabled("google"):
        return "host-connector"
    if _service_account_path():
        return "service-account"
    if (config_dir() / "google_token.json").exists():
        return "user"
    return ""


NOT_SIGNED_IN = (
    "Google is not connected. Either run  python3 scripts/kpi.py auth google  (once, opens a "
    "browser; needs ~/.config/kpi-copilot/google_client.json, an OAuth client of type 'Desktop "
    "app'), or put a service-account key at ~/.config/kpi-copilot/google_service_account.json "
    "and share the Drive folder with its address.")


class Session:
    def __init__(self) -> None:
        self._token: str | None = None
        self._expires = 0.0
        self.identity = ""

    def token(self) -> str:
        if self._token and time.time() < self._expires - 60:
            return self._token
        sa = _service_account_path()
        if sa:
            key = json.loads(sa.read_text(encoding="utf-8"))
            now = int(time.time())
            head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
            claim = _b64(json.dumps({"iss": key["client_email"], "scope": " ".join(SCOPES),
                                     "aud": key["token_uri"], "iat": now, "exp": now + 3600}).encode())
            signed = f"{head}.{claim}".encode("ascii")
            jwt = f"{head}.{claim}.{_b64(rs256(signed, key['private_key']))}"
            doc = _post_form(key["token_uri"], {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt})
            self.identity = key["client_email"]
        else:
            tok_path = config_dir() / "google_token.json"
            if not tok_path.exists():
                raise GoogleError(NOT_SIGNED_IN)
            tok = json.loads(tok_path.read_text(encoding="utf-8"))
            doc = _post_form(tok["token_uri"], {
                "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                "client_id": tok["client_id"], "client_secret": tok.get("client_secret") or ""})
            self.identity = tok.get("email") or "you"
        self._token, self._expires = doc["access_token"], time.time() + int(doc.get("expires_in") or 3600)
        return self._token

    def call(self, method: str, url: str, body: Any = None, params: dict | None = None,
             raw: bool = False) -> Any:
        import host_transport
        if host_transport.enabled("google"):
            self.identity = "connected Google account"
            try:
                return host_transport.call("google", method, url, body, params, raw)
            except host_transport.TransportError as e:
                raise GoogleError(str(e)) from e
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(6):
            req = urllib.request.Request(url, data=data, method=method, headers={
                "Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    payload = r.read()
                    return payload if raw else (json.loads(payload.decode("utf-8")) if payload else {})
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", "replace")
                if e.code in (429, 500, 502, 503) and attempt < 5:
                    time.sleep(min(2 ** attempt, 30))
                    continue
                raise GoogleError(_explain(e.code, text, url)) from e
            except urllib.error.URLError as e:
                if attempt == 5:
                    raise GoogleError(f"Could not reach Google: {e.reason}") from e
                time.sleep(2 ** attempt)
        raise GoogleError("Google kept asking to slow down; try again in a minute.")


def _explain(code: int, text: str, url: str) -> str:
    try:
        msg = json.loads(text)["error"]["message"]
    except Exception:  # noqa: BLE001
        msg = text[:300]
    if code == 404:
        return (f"Google cannot find that file, or this account cannot open it (404). If you signed in with a "
                f"service account, share the file or folder with its address. {msg}")
    if code == 403:
        return f"Google says this account may not do that (403): {msg}"
    return f"Google {code}: {msg}"


def sign_in(scopes: list[str] | None = None, open_browser: bool = True) -> str:
    """The one-time browser consent. The flow itself lives in connect.py, shared with every
    other service that can be signed in to from a browser."""
    import connect
    try:
        return str(connect.sign_in_browser("google", open_browser, scopes))
    except connect.ConnectError as e:
        raise GoogleError(str(e)) from e


# --------------------------------------------------------------------------------------
# Drive
# --------------------------------------------------------------------------------------

def drive_meta(s: Session, fid: str) -> dict:
    return s.call("GET", f"{DRIVE}/{fid}", params={
        "fields": "id,name,mimeType,modifiedTime,md5Checksum,parents,webViewLink", "supportsAllDrives": "true"})


def drive_fetch(s: Session, fid: str, mime: str, dest: Path) -> Path:
    """A Google-native file is exported (Sheets -> xlsx, Docs -> text); anything else is
    downloaded as it is. Straight to disk: nothing passes through anybody's context."""
    if mime == GSHEET:
        data, ext = s.call("GET", f"{DRIVE}/{fid}/export", params={"mimeType": XLSX}, raw=True), ".xlsx"
    elif mime == "application/vnd.google-apps.document":
        data, ext = s.call("GET", f"{DRIVE}/{fid}/export", params={"mimeType": "text/plain"}, raw=True), ".txt"
    else:
        data = s.call("GET", f"{DRIVE}/{fid}", params={"alt": "media", "supportsAllDrives": "true"}, raw=True)
        ext = {"application/pdf": ".pdf", XLSX: ".xlsx", "text/csv": ".csv"}.get(mime, "")
    dest = dest.with_suffix(ext or dest.suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def drive_find(s: Session, folder: str, name: str) -> dict | None:
    safe = name.replace("\\", "\\\\").replace("'", "\\'")
    doc = s.call("GET", DRIVE, params={
        "q": f"'{folder}' in parents and name = '{safe}' and mimeType = '{GSHEET}' and trashed = false",
        "fields": "files(id,name,webViewLink)", "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true", "pageSize": 5})
    files = doc.get("files") or []
    return files[0] if files else None


def drive_create_sheet(s: Session, folder: str | None, name: str) -> dict:
    body = {"name": name, "mimeType": GSHEET, **({"parents": [folder]} if folder else {})}
    return s.call("POST", DRIVE, body, params={"fields": "id,name,webViewLink", "supportsAllDrives": "true"})
