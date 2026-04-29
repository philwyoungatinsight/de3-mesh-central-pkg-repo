#!/usr/bin/env python3
"""cleanup-stale-mesh-nodes.py

Remove stale nodes from MeshCentral mgmt_group_* device groups.

A node is considered stale if its name does not appear in the expected
list for that group (i.e. the host moved to a different group, or was
removed from the inventory entirely).

Uses HTTP login to get an authenticated session cookie, then uses the
WebSocket control API (/control.ashx) to list and remove nodes.

Usage:
  python3 cleanup-stale-mesh-nodes.py <url> <username> <password> <expected_json>

  expected_json: JSON mapping of {group_name: [hostname, ...]}
    e.g. '{"mgmt_group_ms01": ["ms01-02"], "mgmt_group_vms": ["mesh-central"]}'

Exits non-zero on failure.
"""

import asyncio
import json
import ssl
import sys

import requests
import websockets


def http_login(base_url: str, username: str, password: str) -> dict:
    session = requests.Session()
    session.verify = False
    r = session.post(
        base_url + "/",
        data={"action": "login", "username": username, "password": password},
        timeout=15,
        allow_redirects=True,
    )
    r.raise_for_status()
    cookies = dict(r.cookies)
    if "xid" not in cookies:
        sys.exit("ERROR: Login failed — no xid cookie in response")
    return cookies


async def ws_cleanup(ws_url: str, cookies: dict, expected: dict) -> None:
    """Remove stale nodes from mgmt_group_* meshes.

    expected: {group_name: [hostname, ...]} — nodes NOT in this list are removed.
    Only acts on meshes whose names are keys in expected.
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
        # greeting
        try:
            g = await asyncio.wait_for(ws.recv(), timeout=5)
            d = json.loads(g)
            if d.get("action") == "close":
                sys.exit(f"ERROR: Server closed connection: {d}")
        except asyncio.TimeoutError:
            pass

        # List all meshes
        await ws.send(json.dumps({"action": "meshes"}))
        meshes = []
        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                d = json.loads(msg)
            except (asyncio.TimeoutError, json.JSONDecodeError):
                break
            if isinstance(d, dict) and d.get("action") == "meshes":
                meshes = d.get("meshes", [])
                break

        # Build {mesh_id: group_name} for groups we manage
        managed_mesh_ids = {}
        for mesh in meshes:
            name = mesh.get("meshname") or mesh.get("name", "")
            if name in expected:
                managed_mesh_ids[mesh["_id"]] = name

        if not managed_mesh_ids:
            print("No managed mgmt_group_* meshes found — nothing to clean up.")
            return

        # List all nodes
        await ws.send(json.dumps({"action": "nodes"}))
        nodes_by_mesh = {}
        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                d = json.loads(msg)
            except (asyncio.TimeoutError, json.JSONDecodeError):
                break
            if isinstance(d, dict) and d.get("action") == "nodes":
                nodes_by_mesh = d.get("nodes", {})
                break

        # Find stale nodes
        stale_node_ids = []
        for mesh_id, group_name in managed_mesh_ids.items():
            expected_names = set(expected.get(group_name, []))
            nodes = nodes_by_mesh.get(mesh_id, [])
            for node in nodes:
                node_name = node.get("name", "")
                node_id   = node.get("_id", "")
                if node_name not in expected_names:
                    print(f"  Stale: '{node_name}' in '{group_name}' (node_id={node_id})")
                    stale_node_ids.append(node_id)
                else:
                    print(f"  OK:    '{node_name}' in '{group_name}'")

        if not stale_node_ids:
            print("No stale nodes found.")
            return

        # Remove stale nodes
        print(f"Removing {len(stale_node_ids)} stale node(s)...")
        await ws.send(json.dumps({"action": "removedevices", "nodeids": stale_node_ids}))
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            print(f"Remove response: {resp}")
        except asyncio.TimeoutError:
            print("No response to removedevices (timeout) — nodes may still have been removed.")


def main():
    if len(sys.argv) != 5:
        sys.exit(
            f"Usage: {sys.argv[0]} <https_url> <username> <password> <expected_json>"
        )

    base_url, username, password, expected_json = sys.argv[1:5]
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        expected = json.loads(expected_json)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: Invalid expected_json: {exc}")

    cookies = http_login(base_url, username, password)
    asyncio.run(ws_cleanup(ws_url, cookies, expected))


if __name__ == "__main__":
    main()
