#!/usr/bin/env python3
"""configure-amt-credentials.py

Configure Intel AMT credentials for MeshCentral nodes.

For each node in the supplied list, find the matching MeshCentral node (by
hostname) across all device groups and set its AMT credentials via the
WebSocket 'changedevice' API action.

MeshCentral only updates the credentials when they differ from the stored
values, making repeated runs safe.

Usage:
  python3 configure-amt-credentials.py <url> <username> <password> <nodes_json>

  nodes_json: JSON array of objects with fields:
    hostname  (str) - MeshCentral node name to match (e.g. "ms01-02")
    amt_user  (str) - AMT username (e.g. "admin3")
    amt_pass  (str) - AMT password

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


async def ws_configure_amt(ws_url: str, cookies: dict, nodes: list) -> None:
    """Set AMT credentials for each named node in MeshCentral.

    nodes: list of {"hostname": str, "amt_user": str, "amt_pass": str}
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
        # Consume greeting if sent
        try:
            g = await asyncio.wait_for(ws.recv(), timeout=5)
            d = json.loads(g)
            if isinstance(d, dict) and d.get("action") == "close":
                sys.exit(f"ERROR: Server closed connection: {d}")
        except asyncio.TimeoutError:
            pass

        # Get all nodes across all meshes
        await ws.send(json.dumps({"action": "nodes"}))
        nodes_by_mesh = {}
        deadline = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                d = json.loads(msg)
            except (asyncio.TimeoutError, json.JSONDecodeError):
                break
            if isinstance(d, dict) and d.get("action") == "nodes":
                nodes_by_mesh = d.get("nodes", {})
                break

        # Build hostname → node_id index
        node_id_by_name = {}
        for mesh_nodes in nodes_by_mesh.values():
            if isinstance(mesh_nodes, list):
                for node in mesh_nodes:
                    name = node.get("name", "")
                    if name:
                        node_id_by_name[name] = node.get("_id", "")

        # Build a map of node_id -> full node info for warn/user checking
        node_info_by_name = {}
        for mesh_nodes in nodes_by_mesh.values():
            if isinstance(mesh_nodes, list):
                for node in mesh_nodes:
                    name = node.get("name", "")
                    if name:
                        node_info_by_name[name] = node

        # Configure AMT credentials for each requested node
        errors = []
        for entry in nodes:
            hostname = entry.get("hostname", "")
            power_address = entry.get("power_address", "")
            amt_user = entry.get("amt_user", "")
            amt_pass = entry.get("amt_pass", "")

            if not hostname or not amt_user or not amt_pass:
                print(f"  SKIP '{hostname}': missing hostname/amt_user/amt_pass")
                continue

            node_id = node_id_by_name.get(hostname)
            if not node_id:
                print(f"  SKIP '{hostname}': node not found in MeshCentral")
                continue

            # Check current state: MeshCentral only allows credential updates when
            # the AMT manager has not successfully connected (warn bits 1=unknown or
            # 8=trying must be set). If warn is 0/null and manager is healthy, the
            # changedevice API silently ignores the credential update while returning "ok".
            node_info = node_info_by_name.get(hostname, {})
            current_intelamt = node_info.get("intelamt") or {}
            current_user = current_intelamt.get("user", "")
            warn = current_intelamt.get("warn") or 0
            update_allowed = bool(warn & 9)  # bits 1 (unknown) or 8 (trying)

            if current_user == amt_user:
                # Username matches; can't verify password (redacted), assume correct
                print(f"  OK '{hostname}': AMT user already set to '{amt_user}' (password not verifiable)")
                continue

            if not update_allowed:
                print(f"  ERROR '{hostname}': AMT manager is connected with working credentials "
                      f"(warn={warn:#x}); MeshCentral will silently block the credential update. "
                      f"Stop MeshCentral and update the DB directly, or trigger an AMT auth failure first.")
                errors.append(hostname)
                continue

            rid = f"amt-{hostname}"
            payload = {
                "action": "changedevice",
                "nodeid": node_id,
                "intelamt": {
                    "user": amt_user,
                    "pass": amt_pass,
                },
                "responseid": rid,
            }
            if power_address:
                payload["host"] = power_address
            await ws.send(json.dumps(payload))

            result = None
            try:
                deadline2 = asyncio.get_event_loop().time() + 10
                while asyncio.get_event_loop().time() < deadline2:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    resp = json.loads(msg)
                    if isinstance(resp, dict) and resp.get("responseid") == rid:
                        result = resp.get("result", "")
                        break
            except asyncio.TimeoutError:
                result = "timeout"

            if result == "ok":
                print(f"  OK '{hostname}': AMT credentials configured")
            elif result == "timeout":
                print(f"  WARN '{hostname}': no response (changedevice sent but timed out)")
            else:
                print(f"  ERROR '{hostname}': result={result!r}")
                errors.append(hostname)

        if errors:
            sys.exit(f"ERROR: Failed to configure AMT for: {', '.join(errors)}")


def main():
    if len(sys.argv) != 5:
        sys.exit(
            f"Usage: {sys.argv[0]} <https_url> <username> <password> <nodes_json>"
        )

    base_url, username, password, nodes_json_str = sys.argv[1:5]
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        nodes = json.loads(nodes_json_str)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: Invalid nodes_json: {exc}")

    if not nodes:
        print("No AMT nodes to configure.")
        return

    cookies = http_login(base_url, username, password)
    asyncio.run(ws_configure_amt(ws_url, cookies, nodes))


if __name__ == "__main__":
    main()
