#!/usr/bin/env python3
"""get-or-create-mesh-group.py

Get or create a MeshCentral device group by name.

Uses HTTP login to get an authenticated session cookie, then uses the
WebSocket control API (/control.ashx) with the cookie to list and create
device groups.

Usage:
  python3 get-or-create-mesh-group.py <url> <username> <password> <group_name>

Outputs the mesh ID on stdout (for use in Ansible set_fact / shell tasks).
Exits non-zero on failure.
"""

import asyncio
import json
import ssl
import sys
import urllib.parse

import requests
import websockets


def http_login(base_url: str, username: str, password: str) -> dict:
    """Login via HTTP POST and return the session cookies dict."""
    session = requests.Session()
    session.verify = False
    r = session.post(
        base_url + "/",
        data={
            "action": "login",
            "username": username,
            "password": password,
        },
        timeout=15,
        allow_redirects=True,
    )
    r.raise_for_status()
    cookies = dict(r.cookies)
    if "xid" not in cookies:
        sys.exit("ERROR: Login failed — no xid cookie in response")
    return cookies


async def ws_get_or_create_group(
    ws_url: str,
    cookies: dict,
    group_name: str,
) -> str:
    """Connect to MeshCentral WebSocket API and get or create a device group.

    Returns the meshid of the named group.
    """
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

    async with websockets.connect(
        ws_url + "/control.ashx",
        ssl=ssl_ctx,
        additional_headers={"Cookie": cookie_header},
        ping_interval=None,
    ) as ws:
        # Wait for the server's greeting / ready signal
        try:
            greeting = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(greeting)
            if data.get("action") == "close":
                sys.exit(f"ERROR: Server closed connection: {data}")
        except asyncio.TimeoutError:
            pass  # Some versions don't send a greeting

        # Drain any initial server messages, then list existing device groups.
        # MeshCentral responds to "meshes" with {"action":"meshes","meshes":[...]}.
        # We match on action, not responseid, because the server does not always
        # echo back the responseid field.
        await ws.send(json.dumps({"action": "meshes"}))

        meshes = []
        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                break
            try:
                data = json.loads(msg)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("action") == "meshes":
                meshes = data.get("meshes", [])
                break

        # Check if the group already exists
        for mesh in meshes:
            if mesh.get("meshname") == group_name or mesh.get("name") == group_name:
                return mesh["_id"].split("/")[-1]  # strip 'mesh//' prefix

        # Create the group
        await ws.send(json.dumps({
            "action": "createmesh",
            "meshname": group_name,
            "meshtype": 2,  # 2 = Manage Multiple Computers
        }))

        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                break
            try:
                data = json.loads(msg)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            if data.get("action") == "createmesh":
                mesh_id = data.get("meshid") or data.get("_id", "")
                if mesh_id:
                    return mesh_id.split("/")[-1]
                sys.exit(f"ERROR: Create group response missing meshid: {data}")

        sys.exit("ERROR: Timed out waiting for device group creation response")


def main():
    if len(sys.argv) != 5:
        sys.exit(f"Usage: {sys.argv[0]} <https_url> <username> <password> <group_name>")

    base_url, username, password, group_name = sys.argv[1:5]
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    # Suppress InsecureRequestWarning for self-signed certs
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    cookies = http_login(base_url, username, password)
    mesh_id = asyncio.run(ws_get_or_create_group(ws_url, cookies, group_name))
    print(mesh_id)


if __name__ == "__main__":
    main()
