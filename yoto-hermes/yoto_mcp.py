"""Yoto bedtime / morning switch, as an MCP server for Hermes Agent.

Run with no arguments to serve MCP over stdio (that is what Hermes does).
For setup and testing from a shell:

    python yoto_mcp.py login              # one-time Yoto sign-in
    python yoto_mcp.py status             # show players and their schedule
    python yoto_mcp.py bedtime [--player NAME|all]
    python yoto_mcp.py morning [--player NAME|all]

How the switch works: a Yoto player changes mode at its configured `dayTime`
and `nightTime`. "Bedtime now" moves `nightTime` to the next minute and puts
`dayTime` back to your usual morning time; "morning now" does the reverse.
So a manual switch only lasts until the next usual change-over, and the
regular schedule keeps working afterwards.

Environment:
    YOTO_CLIENT_ID     Client ID of your app from the Yoto developer portal (required)
    YOTO_DAY_TIME      Usual morning time, HH:MM (default 07:00)
    YOTO_NIGHT_TIME    Usual bedtime, HH:MM (default 19:00)
    YOTO_PLAYER        Default player name when you have several (optional)
    YOTO_TIMEZONE      IANA time zone, e.g. Europe/London (default: the player's)
    YOTO_TOKEN_FILE    Where the sign-in is stored (default ~/.config/yoto-hermes/token.json)
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

API_URL = "https://api.yotoplay.com"
DEVICE_CODE_URL = "https://login.yotoplay.com/oauth/device/code"
TOKEN_URL = "https://login.yotoplay.com/oauth/token"

CLIENT_ID = os.environ.get("YOTO_CLIENT_ID", "")
DAY_TIME = os.environ.get("YOTO_DAY_TIME", "07:00")
NIGHT_TIME = os.environ.get("YOTO_NIGHT_TIME", "19:00")
DEFAULT_PLAYER = os.environ.get("YOTO_PLAYER", "")
TIMEZONE = os.environ.get("YOTO_TIMEZONE", "")
TOKEN_FILE = Path(
    os.environ.get("YOTO_TOKEN_FILE", "~/.config/yoto-hermes/token.json")
).expanduser()

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class YotoError(Exception):
    pass


# ─── Auth ─────────────────────────────────────────────────────────────


def _require_client_id() -> None:
    if not CLIENT_ID:
        raise YotoError("YOTO_CLIENT_ID is not set.")


def _save_token(body: dict, previous: dict | None = None) -> dict:
    token = {
        "access_token": body["access_token"],
        # Refresh responses may omit the refresh token when rotation is off.
        "refresh_token": body.get("refresh_token")
        or (previous or {}).get("refresh_token"),
        "expires_at": time.time() + int(body.get("expires_in", 3600)),
    }
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.touch(mode=0o600, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(token))
    return token


def login() -> None:
    """Device-code sign-in: prints a link, waits until you approve it."""
    _require_client_id()
    start = httpx.post(
        DEVICE_CODE_URL,
        data={
            "client_id": CLIENT_ID,
            "scope": "offline_access",
            "audience": API_URL,
        },
    )
    if start.is_error:
        raise YotoError(f"Sign-in failed to start: {start.status_code} {start.text}")
    flow = start.json()
    link = flow.get("verification_uri_complete") or flow["verification_uri"]
    print(f"Open this link and approve access:\n\n  {link}\n")
    print(f"Code (if asked): {flow['user_code']}\n\nWaiting...")

    interval = int(flow.get("interval", 5))
    deadline = time.time() + int(flow.get("expires_in", 300))
    while time.time() < deadline:
        time.sleep(interval)
        resp = httpx.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": flow["device_code"],
                "client_id": CLIENT_ID,
                "audience": API_URL,
            },
        )
        body = resp.json()
        if resp.is_success:
            _save_token(body)
            print(f"Signed in. Token saved to {TOKEN_FILE}")
            return
        error = body.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise YotoError(f"Sign-in failed: {body.get('error_description', error)}")
    raise YotoError("Sign-in timed out. Run login again.")


def _access_token() -> str:
    if not TOKEN_FILE.exists():
        raise YotoError("Not signed in to Yoto. Run: python yoto_mcp.py login")
    token = json.loads(TOKEN_FILE.read_text())
    if time.time() < token["expires_at"] - 60:
        return token["access_token"]
    _require_client_id()
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": token["refresh_token"],
            "audience": API_URL,
        },
    )
    if resp.is_error:
        raise YotoError(
            "Yoto sign-in expired. Run: python yoto_mcp.py login "
            f"({resp.status_code} {resp.text})"
        )
    return _save_token(resp.json(), previous=token)["access_token"]


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API_URL,
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=20,
    )


# ─── Yoto API ─────────────────────────────────────────────────────────


def _check(resp: httpx.Response, what: str) -> dict:
    if resp.is_error:
        raise YotoError(f"{what} failed: HTTP {resp.status_code} {resp.text}")
    return resp.json() if resp.content else {}


def _players(client: httpx.Client, wanted: str) -> list[dict]:
    """Resolve a player name (or "all") to device entries."""
    devices = _check(client.get("/device-v2/devices/mine"), "Listing players")[
        "devices"
    ]
    if not devices:
        raise YotoError("No Yoto players found on this account.")
    wanted = (wanted or DEFAULT_PLAYER).strip().lower()
    if wanted == "all":
        return devices
    if not wanted:
        if len(devices) == 1:
            return devices
        names = ", ".join(d.get("name") or d["deviceId"] for d in devices)
        raise YotoError(f"Several players found, say which one (or 'all'): {names}")
    matches = [d for d in devices if wanted in (d.get("name") or "").lower()]
    if not matches:
        names = ", ".join(d.get("name") or d["deviceId"] for d in devices)
        raise YotoError(f"No player called '{wanted}'. Players: {names}")
    return matches


def _device(client: httpx.Client, device_id: str) -> dict:
    return _check(client.get(f"/device-v2/{device_id}/config"), "Reading settings")[
        "device"
    ]


def _now(device: dict) -> dt.datetime:
    zone = TIMEZONE or device.get("geoTimezone") or device["config"].get("timezone")
    return dt.datetime.now(ZoneInfo(zone)) if zone else dt.datetime.now()


def _current_mode(now: dt.datetime, day: str, night: str) -> str:
    t = now.strftime("%H:%M")
    if day < night:
        return "day" if day <= t < night else "night"
    return "night" if night <= t < day else "day"


def switch(mode: str, player: str = "") -> str:
    """Switch players to night ("bedtime") or day ("morning") mode now."""
    for name, value in (("YOTO_DAY_TIME", DAY_TIME), ("YOTO_NIGHT_TIME", NIGHT_TIME)):
        if not HHMM.match(value):
            raise YotoError(f"{name} must be HH:MM, got {value!r}")
    lines = []
    with _client() as client:
        for entry in _players(client, player):
            device = _device(client, entry["deviceId"])
            # Next minute, so the player crosses the change-over and applies it.
            at = (_now(device) + dt.timedelta(minutes=1)).strftime("%H:%M")
            if mode == "night":
                changes = {"nightTime": at, "dayTime": DAY_TIME}
                summary = f"night mode from {at}, morning as usual at {DAY_TIME}"
            else:
                changes = {"dayTime": at, "nightTime": NIGHT_TIME}
                summary = f"day mode from {at}, bedtime as usual at {NIGHT_TIME}"
            # PUT replaces the whole config block, so send it all back.
            body = {
                "deviceId": entry["deviceId"],
                "config": {**device["config"], **changes},
            }
            _check(
                client.put(f"/device-v2/{entry['deviceId']}/config", json=body),
                "Saving settings",
            )
            offline = "" if entry.get("online") else " (player is offline; applies when it reconnects)"
            lines.append(f"{entry.get('name') or entry['deviceId']}: {summary}{offline}")
    return "\n".join(lines)


def status(player: str = "") -> str:
    """Describe each player's schedule and current mode."""
    lines = []
    with _client() as client:
        for entry in _players(client, player or "all"):
            device = _device(client, entry["deviceId"])
            cfg = device["config"]
            day, night = cfg.get("dayTime", "?"), cfg.get("nightTime", "?")
            mode = (
                _current_mode(_now(device), day, night)
                if HHMM.match(day) and HHMM.match(night)
                else "unknown"
            )
            lines.append(
                f"{entry.get('name') or entry['deviceId']}: "
                f"{'online' if entry.get('online') else 'offline'}, {mode} mode now; "
                f"day starts {day}, night starts {night}; "
                f"volume limit day {cfg.get('maxVolumeLimit', '?')} / "
                f"night {cfg.get('nightMaxVolumeLimit', '?')}"
            )
    return "\n".join(lines)


# ─── MCP server ───────────────────────────────────────────────────────


def serve() -> None:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("yoto")

    def run(fn, *args) -> str:
        try:
            return fn(*args)
        except YotoError as err:
            return f"Error: {err}"

    @mcp.tool()
    def yoto_bedtime(player: str = "") -> str:
        """Put the Yoto player into night (bedtime) mode right now.

        Night mode applies the player's night settings (lower volume limit,
        dimmer display, night-light colour). It switches back to day mode at
        the usual morning time. `player` is a player name, or "all"; leave it
        empty when there is only one player.
        """
        return run(switch, "night", player)

    @mcp.tool()
    def yoto_morning(player: str = "") -> str:
        """Put the Yoto player into day (morning) mode right now.

        It switches back to night mode at the usual bedtime. `player` is a
        player name, or "all"; leave it empty when there is only one player.
        """
        return run(switch, "day", player)

    @mcp.tool()
    def yoto_status(player: str = "") -> str:
        """Show each Yoto player's current mode, day/night times and volume limits."""
        return run(status, player)

    mcp.run()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "command", nargs="?", default="serve",
        choices=["serve", "login", "status", "bedtime", "morning"],
    )
    parser.add_argument("--player", default="", help='player name, or "all"')
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve()
        elif args.command == "login":
            login()
        elif args.command == "status":
            print(status(args.player))
        else:
            print(switch("night" if args.command == "bedtime" else "day", args.player))
    except YotoError as err:
        sys.exit(f"Error: {err}")


if __name__ == "__main__":
    main()
