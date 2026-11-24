"""Links between worlds: a character crosses from one world to another through a gate, as the same person, and plays
in one world at a time (Nate, 2026-11-23). Every world runs its own server (a hub runs one per world), so a crossing
is always one signed HTTP call from the world it leaves to the world it enters, the way two sites trust each other
under OAuth: the two owners share a secret once (link_world on each side), and each call carries an HMAC of its body
and time under that secret, with a nonce the receiver never accepts twice.

What crosses is the world's call on both ends: the leaving gate names the state keys it sends (`carry`), the
receiving link names the ones it takes (`accept`) and the template the body is made from; a name, a description and
the traveller's id always go. Things held stay with the body left behind. Memory stays with the agent: a body keeps
its own (remember, knows, standing), so the new body starts blank.

This module is the pure part: the card, the signature and its check. ops.Session does the crossing."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any, Callable

SKEW = 300.0  # seconds a signed call may be off the receiver's clock, either way
NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")  # a link's name, as each world calls the other
CARD_MAX = 8000  # bytes of card a world takes
TEXT_MAX = 1000  # characters of a name or a description that cross
HEADERS = ("x-embody-link", "x-embody-time", "x-embody-nonce", "x-embody-sig")


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def body_bytes(card: dict[str, Any]) -> bytes:
    """The one form a card is signed and sent in."""
    return json.dumps(card, sort_keys=True, separators=(",", ":")).encode()


def sign(secret: str, link: str, ts: float, nonce: str, body: bytes) -> str:
    msg = f"{link}\n{ts:.3f}\n{nonce}\n".encode() + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def signed_headers(secret: str, link: str, body: bytes, now: float | None = None) -> dict[str, str]:
    """The headers a crossing call carries. `link` is the name the receiving world gave the sender."""
    ts = time.time() if now is None else now
    nonce = secrets.token_hex(12)
    return {"x-embody-link": link, "x-embody-time": f"{ts:.3f}", "x-embody-nonce": nonce,
            "x-embody-sig": sign(secret, link, ts, nonce, body), "content-type": "application/json"}


def check(secret: str, headers: dict[str, str], body: bytes, now: float | None = None) -> str | None:
    """Why a signed call is refused, or None when it is good (the nonce is the caller's to remember)."""
    try:
        ts = float(headers.get("x-embody-time") or "")
    except ValueError:
        return "no time on the call"
    now = time.time() if now is None else now
    if abs(now - ts) > SKEW:
        return "the call's time is too far from ours"
    want = sign(secret, headers.get("x-embody-link") or "", ts, headers.get("x-embody-nonce") or "", body)
    if not hmac.compare_digest(want, headers.get("x-embody-sig") or ""):
        return "the signature does not match this link's secret"
    if len(body) > CARD_MAX:
        return f"a card is at most {CARD_MAX} bytes"
    return None


def clip(text: Any) -> str:
    return str(text or "").strip()[:TEXT_MAX]


def post(url: str, headers: dict[str, str], body: bytes, timeout: float = 20.0) -> tuple[int, dict[str, Any]]:
    """The real call to another world's server: POST <its base>/link/arrive. (status, json); a failure to reach it is
    (0, {reason})."""
    import httpx2

    try:
        r = httpx2.post(url.rstrip("/") + "/link/arrive", content=body, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001 - any failure to reach the other world is one answer
        return 0, {"ok": False, "reason": f"the other world did not answer: {type(e).__name__}"}
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"ok": False, "reason": "the other world's answer was not JSON"}


Transport = Callable[[str, dict[str, str], bytes], "tuple[int, dict[str, Any]]"]
