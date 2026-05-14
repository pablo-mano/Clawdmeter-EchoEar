#!/usr/bin/env python3
"""
Claude Usage Daemon — macOS BLE edition.

Reads Claude Code OAuth token from macOS Keychain, polls the Anthropic API
for 5h/7d utilization, and pushes JSON usage data to the ESP32 "Claude Controller"
over BLE GATT.

Requirements:
    pip3 install bleak

Usage:
    python3 claude-usage-daemon-macos.py
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

from bleak import BleakClient, BleakScanner

# ── BLE UUIDs ──────────────────────────────────────────────────────────────
DEVICE_NAME   = "Claude Controller"
SERVICE_UUID  = "4c41555a-4465-7669-6365-000000000001"
RX_CHAR_UUID  = "4c41555a-4465-7669-6365-000000000002"   # daemon writes here
TX_CHAR_UUID  = "4c41555a-4465-7669-6365-000000000003"
REQ_CHAR_UUID = "4c41555a-4465-7669-6365-000000000004"   # device requests refresh

# ── Timing ─────────────────────────────────────────────────────────────────
POLL_INTERVAL   = 60   # seconds between API polls
SCAN_TIMEOUT    = 15   # BLE discovery timeout
RECONNECT_DELAY = 5    # seconds between reconnect attempts
CACHE_FILE      = os.path.expanduser("~/.config/claude-usage-monitor/ble-address-macos")

refresh_requested = False


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Auth ───────────────────────────────────────────────────────────────────

def _keychain_get(service: str) -> str | None:
    r = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-w"],
        capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 else None


def read_token() -> str:
    """
    Return a valid OAuth access token.
    Priority:
      1. macOS Keychain  (Claude Code-credentials service)
      2. ~/.claude/.credentials.json  (Linux / older Claude Code)
      3. ANTHROPIC_API_KEY env var
    """
    # 1. macOS Keychain
    for svc in [
        "Claude Code-credentials",
        "Claude Code-credentials-0a0f82fe",
        "Claude Code-credentials-e534e317",
        "Claude Code-credentials-134f4f56",
    ]:
        raw = _keychain_get(svc)
        if not raw:
            continue
        try:
            d = json.loads(raw)
            oauth = d.get("claudeAiOauth", {})
            if isinstance(oauth, str):
                oauth = json.loads(oauth)
            token = oauth.get("accessToken", "")
            if token:
                return token
        except Exception:
            pass

    # 2. ~/.claude/.credentials.json
    creds = os.path.expanduser("~/.claude/.credentials.json")
    if os.path.exists(creds):
        try:
            with open(creds) as f:
                d = json.load(f)
            token = d.get("accessToken") or d.get("claudeAiOauth", {}).get("accessToken", "")
            if token:
                return token
        except Exception:
            pass

    # 3. Env var (may not have unified headers, but try)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        log("Warning: using ANTHROPIC_API_KEY — unified rate-limit headers may not be available")
        return key

    raise RuntimeError(
        "No API token found.\n"
        "Run 'claude auth login' in terminal, or set ANTHROPIC_API_KEY."
    )


# ── API poll ───────────────────────────────────────────────────────────────

def _mins_until(ts_value: str | int | float) -> int:
    """Return minutes until a reset timestamp (Unix epoch or ISO-8601 string)."""
    try:
        epoch = float(ts_value)           # works for integer or float strings
    except (TypeError, ValueError):
        try:                               # try ISO-8601
            s = str(ts_value).rstrip("Z").replace("+00:00", "")
            epoch = datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            return -1
    delta = epoch - time.time()
    return max(0, int(delta / 60))


def poll(token: str) -> dict | None:
    url  = "https://api.anthropic.com/v1/messages"
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization",    f"Bearer {token}")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta",    "oauth-2025-04-20")
    req.add_header("Content-Type",      "application/json")
    req.add_header("User-Agent",        "claude-code/2.1.5")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in e.headers.items()}
        if e.code == 401:
            log("Token expired or invalid (401). Try re-running 'claude auth login'.")
            return None
    except Exception as ex:
        log(f"API error: {ex}")
        return None

    s_util  = hdrs.get("anthropic-ratelimit-unified-5h-utilization")
    s_reset = hdrs.get("anthropic-ratelimit-unified-5h-reset")
    w_util  = hdrs.get("anthropic-ratelimit-unified-7d-utilization")
    w_reset = hdrs.get("anthropic-ratelimit-unified-7d-reset")
    status  = hdrs.get("anthropic-ratelimit-unified-status", "allowed")

    if s_util is None:
        log("No unified rate-limit headers (OAuth token may not have Claude Code subscription)")
        return None

    try:
        s_pct = round(float(s_util) * 100, 1)
        w_pct = round(float(w_util) * 100, 1)
    except (TypeError, ValueError) as e:
        log(f"Header parse error: {e}")
        return None

    return {
        "session_pct":        s_pct,
        "session_reset_mins": _mins_until(s_reset),
        "weekly_pct":         w_pct,
        "weekly_reset_mins":  _mins_until(w_reset),
        "status":             status,
    }


def build_payload(d: dict) -> bytes:
    return json.dumps({
        "s":  d["session_pct"],
        "sr": d["session_reset_mins"],
        "w":  d["weekly_pct"],
        "wr": d["weekly_reset_mins"],
        "st": d["status"],
        "ok": True,
    }, separators=(",", ":")).encode()


# ── BLE session ────────────────────────────────────────────────────────────

async def run_session(client: BleakClient, token: str) -> None:
    global refresh_requested

    def on_req(_char, data: bytearray) -> None:
        global refresh_requested
        if data and data[0] == 0x01:
            log("Device requested refresh")
            refresh_requested = True

    try:
        await client.start_notify(REQ_CHAR_UUID, on_req)
    except Exception as e:
        log(f"REQ subscribe failed (non-fatal): {e}")

    last_poll = 0.0

    while client.is_connected:
        now = time.monotonic()
        if (now - last_poll >= POLL_INTERVAL) or refresh_requested:
            refresh_requested = False
            # Re-read token from Keychain on every poll — Claude Code refreshes it periodically
            try:
                token = read_token()
            except Exception as e:
                log(f"Token refresh failed: {e}")
            log("Polling Anthropic API...")
            data = poll(token)
            if data:
                payload = build_payload(data)
                log(f"Session {data['session_pct']}% (reset {data['session_reset_mins']}m) | "
                    f"Weekly {data['weekly_pct']}% (reset {data['weekly_reset_mins']}m) | "
                    f"Status: {data['status']}")
                try:
                    await client.write_gatt_char(RX_CHAR_UUID, payload, response=False)
                    log("Sent to device ✓")
                    last_poll = now
                except Exception as e:
                    log(f"Write failed: {e}")
                    break
            else:
                log("Poll failed — will retry")

        await asyncio.sleep(5)

    log("Disconnected")


# ── Main ───────────────────────────────────────────────────────────────────

def load_cached_address() -> str | None:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            addr = f.read().strip()
        if addr:
            return addr
    return None


def save_cached_address(addr: str) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        f.write(addr)


async def find_or_connect(token: str) -> None:
    """Find the ESP32 by name (handles macOS UUID caching) and run a session."""
    # 1. Try cached address first (macOS UUID doesn't change for a bonded device)
    cached = load_cached_address()
    if cached:
        log(f"Trying cached address {cached}...")
        try:
            async with BleakClient(cached, timeout=15) as client:
                log("Connected via cached address!")
                await run_session(client, token)
                return
        except Exception as e:
            log(f"Cached address failed ({e}), scanning...")
            os.remove(CACHE_FILE)

    # 2. Full BLE scan
    log(f"Scanning for '{DEVICE_NAME}' (up to {SCAN_TIMEOUT}s)...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=SCAN_TIMEOUT)

    if not device:
        # 3. macOS sometimes hides already-connected devices from scan results.
        #    Try discovering all devices and look for our service UUID.
        log("Name scan failed — trying service UUID discovery...")
        devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT, return_adv=True)
        for addr, (dev, adv) in devices.items():
            if adv.service_uuids and SERVICE_UUID.lower() in [u.lower() for u in adv.service_uuids]:
                device = dev
                log(f"Found via service UUID: {addr}")
                break

    if not device:
        log(f"'{DEVICE_NAME}' not found. Make sure ESP32 is on and Bluetooth is enabled.")
        return

    save_cached_address(str(device.address))
    log(f"Found {device.address} — connecting...")
    try:
        async with BleakClient(device, timeout=15) as client:
            log("Connected!")
            await run_session(client, token)
    except Exception as e:
        log(f"BLE error: {e}")
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)


async def main() -> None:
    try:
        token = read_token()
    except RuntimeError as e:
        log(f"Auth error: {e}")
        sys.exit(1)

    log(f"Auth: {'OAuth (claude.ai)' if 'oat01' in token else 'API key'}")

    while True:
        await find_or_connect(token)
        log(f"Reconnecting in {RECONNECT_DELAY}s...")
        await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Stopped.")
