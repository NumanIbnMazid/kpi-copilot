#!/usr/bin/env python3
"""
Signing in - every way a person might want to, and which one to suggest.

People differ. Some will paste a token into a terminal without a second thought; most would
rather click "Allow" in the browser they are already signed in to - their own, or the one
built into their assistant. Some are not allowed to create tokens at all. A tool that offers
one route loses the rest, so each service has several, and this file knows them all:

    browser   Sign in in a browser (OAuth). Click Allow, done. Works in the person's own
              browser or an assistant's built-in one. Needs a small app-registration file
              that one person sets up for the whole company.
    cli       A login the machine already has (GitHub's `gh`). Nothing to set up.
    token     A personal access token, saved by the person. A minute to set up, the fastest
              and sturdiest at run time, and the only one that suits an unattended schedule.
    session   No credential at all: a snippet run in an already signed-in tab downloads the
              board as a file. Slower, and a person (or an assistant's browser) has to be
              there - but it works where tokens are forbidden.

`status()` finds what is already connected without touching the network. `advise()` says, in
plain words, what is connected, what is not, and which route to take first - so an assistant
can put the choice to the person in one message instead of guessing. `credential()` is what
the readers call: it returns whatever works, in a fixed order, and never prints it.

Secrets live in ~/.config/kpi-copilot/ (or $KPI_COPILOT_HOME), readable only by the person.
Nothing here ever asks for a secret in a chat, echoes one, or writes one into a profile.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import http.server
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any


class ConnectError(RuntimeError):
    pass


def home() -> Path:
    return Path(os.environ.get("KPI_COPILOT_HOME") or Path.home() / ".config" / "kpi-copilot")


def _read(name: str) -> dict:
    p = home() / name
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(name: str, doc: dict) -> Path:
    p = home() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.chmod(p, 0o600)
    return p


def saved(key: str) -> str:
    return str(_read("credentials.json").get(key) or "").strip()


def save(**values: str) -> Path:
    doc = _read("credentials.json")
    doc.update({k: v for k, v in values.items() if v})
    return _write("credentials.json", doc)


# --------------------------------------------------------------------------------------
# what each service offers
# --------------------------------------------------------------------------------------

OAUTH = {
    "google": {"client": "google_client.json", "token": "google_token.json",
               "auth_uri": "https://accounts.google.com/o/oauth2/auth",
               "token_uri": "https://oauth2.googleapis.com/token",
               "scopes": ["https://www.googleapis.com/auth/spreadsheets",
                          "https://www.googleapis.com/auth/drive.readonly",
                          "https://www.googleapis.com/auth/drive.file"],
               "extra": {"access_type": "offline", "prompt": "consent"}, "any_port": True,
               "register": "Google Cloud console > APIs & Services > Credentials > OAuth client ID > Desktop app "
                           "(consent screen: Internal; enable the Sheets and Drive APIs). Download the JSON."},
    "asana": {"client": "asana_client.json", "token": "asana_oauth.json",
              "auth_uri": "https://app.asana.com/-/oauth_authorize", "token_uri": "https://app.asana.com/-/oauth_token",
              "scopes": [], "extra": {},
              "register": "Asana > My apps (app.asana.com/0/my-apps) > Create new app; add the redirect URL "
                          "http://localhost:8765/callback. Save {\"client_id\": ..., \"client_secret\": ...}."},
    "jira": {"client": "atlassian_client.json", "token": "atlassian_oauth.json",
             "auth_uri": "https://auth.atlassian.com/authorize", "token_uri": "https://auth.atlassian.com/oauth/token",
             "scopes": ["read:jira-work", "read:jira-user", "offline_access"],
             "extra": {"audience": "api.atlassian.com", "prompt": "consent"}, "json_token": True,
             "register": "developer.atlassian.com > Console > Create > OAuth 2.0 integration; add the Jira API with "
                         "read:jira-work and read:jira-user; callback URL http://localhost:8765/callback. "
                         "Save {\"client_id\": ..., \"client_secret\": ...}."},
}
REDIRECT_PORT = 8765

ROUTES: dict[str, list[dict]] = {
    "asana": [
        {"id": "token", "label": "Personal access token", "setup": "1 minute, by you",
         "run": "fastest; also works unattended",
         "how": "Asana > Settings > Apps > Developer apps > Personal access tokens, then run "
                "`python3 scripts/kpi.py auth asana --route token` in a terminal (or export ASANA_TOKEN)."},
        {"id": "browser", "label": "Sign in in your browser", "setup": "one click, once your company has "
         "registered an Asana app (10 minutes, once for everybody)", "run": "as fast as a token",
         "how": "`python3 scripts/kpi.py auth asana --route browser` opens the consent page; click Allow."},
        {"id": "session", "label": "No credential: use a tab where you are already signed in",
         "setup": "none", "run": "about a minute per run, and somebody has to be there",
         "how": "In a signed-in app.asana.com tab (yours, or your assistant's built-in browser) run "
                "adapters/asana/browser_snapshot.js, then `kpi.py run ... --from-raw <the downloaded file>`."},
    ],
    "jira": [
        {"id": "token", "label": "API token", "setup": "1 minute, by you", "run": "fastest; also works unattended",
         "how": "id.atlassian.com > Security > API tokens (Server/Data Center: a personal access token), then "
                "`python3 scripts/kpi.py auth jira --route token` in a terminal (or export JIRA_EMAIL and JIRA_TOKEN)."},
        {"id": "browser", "label": "Sign in in your browser", "setup": "one click, once your company has "
         "registered an Atlassian OAuth app (Jira Cloud only)", "run": "as fast as a token",
         "how": "`python3 scripts/kpi.py auth jira --route browser` opens the consent page; click Accept."},
        {"id": "session", "label": "No credential: use a tab where you are already signed in",
         "setup": "none", "run": "about a minute per run, and somebody has to be there",
         "how": "In a signed-in Jira tab run adapters/jira/browser_snapshot.js, then "
                "`kpi.py run ... --from-raw <the downloaded file>`."},
    ],
    "github": [
        {"id": "cli", "label": "GitHub's own sign-in (the gh command)", "setup": "none if gh is already signed in; "
         "otherwise `gh auth login --web` opens your browser", "run": "fastest",
         "how": "Install GitHub CLI (cli.github.com) and run `gh auth login --web`. Nothing is copied or pasted."},
        {"id": "token", "label": "Personal access token", "setup": "1 minute, by you",
         "run": "fastest; the one to use unattended",
         "how": "github.com > Settings > Developer settings > Fine-grained tokens (Issues: read; Projects: read), "
                "then `python3 scripts/kpi.py auth github --route token` (or export GITHUB_TOKEN)."},
    ],
    "google": [
        {"id": "browser", "label": "Sign in in your browser", "setup": "one click, once your company has created "
         "one OAuth client file (10 minutes, once for everybody)", "run": "reads and writes as you",
         "how": "`python3 scripts/kpi.py auth google` opens the consent page; click Allow."},
        {"id": "service-account", "label": "Service account key", "setup": "10 minutes, by whoever runs Google Cloud",
         "run": "the one to use unattended", "how": "Save the key as ~/.config/kpi-copilot/"
         "google_service_account.json and share the Drive folder with the account's address."},
        {"id": "none", "label": "Do without", "setup": "none", "run": "the sheet stays a local file",
         "how": "Drop exports of your sources into <project>/inbox/, and put the local workbook over the Google "
                "Sheet with File > Import > Replace spreadsheet."},
    ],
}


def _gh_token() -> str:
    if not shutil.which("gh"):
        return ""
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def status(service: str) -> dict:
    """What is connected for this service, and by which route. No network."""
    via = ""
    if service == "asana":
        via = ("token" if (os.environ.get("ASANA_TOKEN") or os.environ.get("ASANA_PAT") or saved("asana_token"))
               else "browser" if _read(OAUTH["asana"]["token"]).get("refresh_token") else "")
    elif service == "jira":
        via = ("token" if ((os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_TOKEN")) or os.environ.get("JIRA_PAT")
                           or saved("jira_token")) else
               "browser" if _read(OAUTH["jira"]["token"]).get("refresh_token") else "")
    elif service == "github":
        via = ("token" if (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or saved("github_token"))
               else "cli" if _gh_token() else "")
    elif service == "google":
        sa = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        via = ("service-account" if ((sa and Path(sa).exists()) or (home() / "google_service_account.json").exists())
               else "browser" if _read(OAUTH["google"]["token"]).get("refresh_token") else "")
    ready = {"browser": (home() / OAUTH[service]["client"]).exists() if service in OAUTH else False,
             "cli": bool(shutil.which("gh")) if service == "github" else False}
    return {"service": service, "connected": bool(via), "via": via, "ready": ready}


def recommend(service: str, unattended: bool = False) -> list[dict]:
    """The routes for a service, best first for THIS machine: whatever needs no more setup
    comes first; for a schedule, only what works with nobody there."""
    st = status(service)
    routes = [dict(r) for r in ROUTES.get(service, [])]
    if unattended:
        routes = [r for r in routes if r["id"] in ("token", "service-account", "cli")]

    def rank(r: dict) -> int:
        if r["id"] == "cli" and st["ready"]["cli"]:
            return 0
        if r["id"] == "browser" and st["ready"]["browser"]:
            return 1
        return {"token": 2, "service-account": 3, "browser": 4, "cli": 5, "session": 6, "none": 7}.get(r["id"], 9)

    routes.sort(key=rank)
    for r in routes:
        r["ready_now"] = (r["id"] == "cli" and st["ready"]["cli"]) or (r["id"] == "browser" and st["ready"]["browser"]) \
            or r["id"] in ("token", "session", "none")
    return routes


def advise(services: list[str], unattended: bool = False) -> str:
    """One readable block: what is connected, and for what is not, the choice to put to the
    person - the recommended route first, and why."""
    out = []
    for s in services:
        st = status(s)
        if st["connected"]:
            out.append(f"{s}: connected ({st['via']}).")
            continue
        routes = recommend(s, unattended)
        out.append(f"{s}: not connected. Ways to connect, best first for this machine:")
        for i, r in enumerate(routes, start=1):
            star = "  <- suggested" if i == 1 else ""
            blocked = "" if r["ready_now"] else "  (needs the one-time company setup first)"
            out.append(f"  {i}. {r['label']}{star}{blocked}\n       setup: {r['setup']} · at run time: {r['run']}\n"
                       f"       {r['how']}")
        if s in OAUTH and not st["ready"]["browser"]:
            out.append(f"     To make browser sign-in available to everyone: {OAUTH[s]['register']} "
                       f"Save it as {home() / OAUTH[s]['client']}.")
    return "\n".join(out)


# --------------------------------------------------------------------------------------
# credentials for the readers
# --------------------------------------------------------------------------------------

def credential(service: str, env_name: str | None = None) -> dict | None:
    """Whatever works for this service, or None. Shapes:
       asana/github {"bearer": ...}   jira {"basic": ...} | {"bearer": ...[, "base": api root]}"""
    if service == "asana":
        tok = next((os.environ[n].strip() for n in (env_name, "ASANA_TOKEN", "ASANA_PAT", "ASANA_ACCESS_TOKEN")
                    if n and os.environ.get(n)), "") or saved("asana_token")
        if tok:
            return {"bearer": tok}
        tok = _oauth_access("asana")
        return {"bearer": tok} if tok else None
    if service == "github":
        tok = next((os.environ[n].strip() for n in (env_name, "GITHUB_TOKEN", "GH_TOKEN") if n and os.environ.get(n)), "") \
            or saved("github_token") or _gh_token()
        return {"bearer": tok} if tok else None
    if service == "jira":
        email, tok = os.environ.get("JIRA_EMAIL") or saved("jira_email"), os.environ.get("JIRA_TOKEN") or saved("jira_token")
        if os.environ.get("JIRA_PAT"):
            return {"bearer": os.environ["JIRA_PAT"].strip()}
        if email and tok:
            return {"basic": base64.b64encode(f"{email}:{tok}".encode()).decode()}
        if tok:
            return {"bearer": tok}                              # Server / Data Center personal access token
        tok = _oauth_access("jira")
        if tok:
            return {"bearer": tok, "cloud": True}
    return None


def _post(url: str, fields: dict, as_json: bool = False) -> dict:
    data = json.dumps(fields).encode() if as_json else urllib.parse.urlencode(fields).encode("ascii")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json" if as_json else "application/x-www-form-urlencoded",
        "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ConnectError(f"The sign-in was refused ({e.code}): {e.read().decode('utf-8', 'replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise ConnectError(f"Could not reach the sign-in server: {e.reason}") from e


def _oauth_access(service: str) -> str:
    """A fresh access token from a stored browser sign-in, or ''."""
    cfg = OAUTH[service]
    tok = _read(cfg["token"])
    if not tok.get("refresh_token"):
        return ""
    if tok.get("access_token") and tok.get("expires_at", 0) > time.time() + 60:
        return tok["access_token"]
    doc = _post(tok.get("token_uri") or cfg["token_uri"], {
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
        "client_id": tok["client_id"], "client_secret": tok.get("client_secret") or ""}, cfg.get("json_token", False))
    tok.update(access_token=doc["access_token"], expires_at=time.time() + int(doc.get("expires_in") or 3600))
    if doc.get("refresh_token"):                                # Atlassian rotates them
        tok["refresh_token"] = doc["refresh_token"]
    _write(cfg["token"], tok)
    return tok["access_token"]


# --------------------------------------------------------------------------------------
# signing in
# --------------------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_in_browser(service: str, open_browser: bool = True, scopes: list[str] | None = None) -> Path:
    """The browser sign-in: authorization code with PKCE, redirected to this machine. The
    page can be opened in the person's own browser or in an assistant's built-in one - the
    redirect comes back to localhost either way. `open_browser=False` prints the link only."""
    cfg = OAUTH[service]
    doc = _read(cfg["client"])
    client = doc.get("installed") or doc.get("web") or doc
    if not client.get("client_id"):
        raise ConnectError(f"Browser sign-in for {service} needs a one-time app registration.\n{cfg['register']}\n"
                           f"Save it as {home() / cfg['client']}. Until then, the other routes work:\n"
                           + advise([service]))
    verifier = _b64(secrets.token_bytes(48))
    state = secrets.token_urlsafe(16)
    if cfg.get("any_port"):
        import socket
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        redirect = f"http://127.0.0.1:{port}"
    else:
        port = REDIRECT_PORT
        redirect = client.get("redirect_uri") or f"http://localhost:{port}/callback"
    got: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<p style='font:16px sans-serif'>KPI Copilot is connected. You can close this tab.</p>")

        def log_message(self, *_):
            pass

    params = {"client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code",
              "state": state, "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
              "code_challenge_method": "S256", **cfg.get("extra", {})}
    if scopes or cfg["scopes"]:
        params["scope"] = " ".join(scopes or cfg["scopes"])
    url = (client.get("auth_uri") or cfg["auth_uri"]) + "?" + urllib.parse.urlencode(params)
    try:
        server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        raise ConnectError(f"Port {port} is busy, so the sign-in page has nowhere to come back to ({e}).") from e
    server.timeout = 300
    print(f"Sign in to {service} and click Allow. Opening your browser; if nothing opens - or you would rather use "
          f"your assistant's built-in browser - open this link there:\n\n  {url}\n\nWaiting (5 minutes)...", flush=True)
    if open_browser:
        webbrowser.open(url)
    deadline = time.time() + 300
    while "code" not in got and "error" not in got and time.time() < deadline:
        server.handle_request()
    server.server_close()
    if "code" not in got or got.get("state") != state:
        raise ConnectError(f"Sign-in did not complete: {got.get('error') or 'nobody clicked Allow in time'}")
    token_uri = client.get("token_uri") or cfg["token_uri"]
    tok = _post(token_uri, {"grant_type": "authorization_code", "code": got["code"], "redirect_uri": redirect,
                            "client_id": client["client_id"], "client_secret": client.get("client_secret") or "",
                            "code_verifier": verifier}, cfg.get("json_token", False))
    if not tok.get("refresh_token"):
        raise ConnectError("The service returned no refresh token, so the sign-in would not last. Remove KPI "
                           "Copilot's access in your account's connected apps and sign in again.")
    return _write(cfg["token"], {
        "refresh_token": tok["refresh_token"], "access_token": tok.get("access_token"),
        "expires_at": time.time() + int(tok.get("expires_in") or 0), "client_id": client["client_id"],
        "client_secret": client.get("client_secret") or "", "token_uri": token_uri, "scopes": scopes or cfg["scopes"]})


def sign_in_token(service: str) -> Path:
    """Typed by the person, in a terminal, never shown. Refuses anywhere it could be seen."""
    if not sys.stdin.isatty():
        raise ConnectError(
            f"A token must not pass through a chat. Run this yourself, in a terminal:\n"
            f"  python3 scripts/kpi.py auth {service} --route token\n"
            f"Or pick a route with nothing to paste:\n{advise([service])}")
    if service == "jira":
        email = input("Your Atlassian email (leave empty for a Server / Data Center personal access token): ").strip()
        tok = getpass.getpass("API token (it will not be shown): ").strip()
        if not tok:
            raise ConnectError("Nothing entered.")
        return save(jira_email=email, jira_token=tok)
    tok = getpass.getpass(f"Paste your {service} token (it will not be shown): ").strip()
    if not tok:
        raise ConnectError("Nothing entered.")
    return save(**{f"{service}_token": tok})


def needed(profile: dict, project: dict | None = None) -> list[str]:
    """Which services this profile actually uses."""
    out = []
    adapter = (profile.get("tracker") or {}).get("adapter")
    if adapter in ROUTES:
        out.append(adapter)
    o, src = profile.get("output") or {}, profile.get("sources") or {}
    refs = [str((src.get(k) or {}).get("ref") or "") for k in ("plan", "estimates", "timeline")]
    refs += [str((project or {}).get(f"{k}_ref") or "") for k in ("plan", "estimates")]
    drive = any("google.com" in r or (len(r) >= 25 and "/" not in r and "." not in r and " " not in r) for r in refs)
    if drive or o.get("workbook") == "google-sheets" or o.get("workbook_file") or o.get("workbook_location"):
        out.append("google")
    return out
