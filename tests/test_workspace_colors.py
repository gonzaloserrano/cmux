#!/usr/bin/env python3
"""
Tests for set_workspace_color and list_workspace_colors socket commands.

Usage:
    python3 test_workspace_colors.py

Requirements:
    - cmux must be running with the socket controller enabled
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cmux import cmux


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""

    def success(self, msg: str = ""):
        self.passed = True
        self.message = msg

    def failure(self, msg: str):
        self.passed = False
        self.message = msg


def test_list_workspace_colors_empty(client: cmux) -> TestResult:
    """Workspaces without custom colors should return 'No colors'."""
    result = TestResult("list_workspace_colors (no colors set)")
    try:
        # Clear colors on all workspaces first
        workspaces = client.list_workspaces()
        for _, wid, _, _ in workspaces:
            client._send_command(f"set_workspace_color {wid} none")

        resp = client._send_command("list_workspace_colors")
        if resp == "No colors":
            result.success("Got 'No colors' as expected")
        else:
            result.failure(f"Expected 'No colors', got: {resp}")
    except Exception as e:
        result.failure(str(e))
    return result


def test_set_workspace_color(client: cmux) -> TestResult:
    """Setting a color should be reflected in list_workspace_colors."""
    result = TestResult("set_workspace_color + list_workspace_colors")
    try:
        workspaces = client.list_workspaces()
        if not workspaces:
            result.failure("No workspaces available")
            return result

        target_id = workspaces[0][1]
        color = "#C0392B"

        resp = client._send_command(f"set_workspace_color {target_id} {color}")
        if resp != "OK":
            result.failure(f"set_workspace_color returned: {resp}")
            return result

        resp = client._send_command("list_workspace_colors")
        found = False
        for line in resp.split("\n"):
            parts = line.strip().split()
            if len(parts) == 2 and parts[0] == target_id and parts[1] == color:
                found = True
                break

        if found:
            result.success(f"Color {color} set and found for {target_id[:8]}...")
        else:
            result.failure(f"Color not found in list_workspace_colors: {resp}")

        # Clean up
        client._send_command(f"set_workspace_color {target_id} none")
    except Exception as e:
        result.failure(str(e))
    return result


def test_clear_workspace_color(client: cmux) -> TestResult:
    """Setting color to 'none' should remove it from list_workspace_colors."""
    result = TestResult("set_workspace_color none (clear)")
    try:
        workspaces = client.list_workspaces()
        if not workspaces:
            result.failure("No workspaces available")
            return result

        target_id = workspaces[0][1]

        client._send_command(f"set_workspace_color {target_id} #196F3D")
        client._send_command(f"set_workspace_color {target_id} none")

        resp = client._send_command("list_workspace_colors")
        if target_id in resp:
            result.failure(f"Color still present after clearing: {resp}")
        else:
            result.success("Color cleared successfully")
    except Exception as e:
        result.failure(str(e))
    return result


def test_set_workspace_color_invalid_uuid(client: cmux) -> TestResult:
    """Setting color on invalid UUID should return error."""
    result = TestResult("set_workspace_color invalid UUID")
    try:
        resp = client._send_command("set_workspace_color not-a-uuid #C0392B")
        if resp.startswith("ERROR"):
            result.success(f"Got expected error: {resp}")
        else:
            result.failure(f"Expected error, got: {resp}")
    except Exception as e:
        result.failure(str(e))
    return result


def test_set_workspace_color_no_args(client: cmux) -> TestResult:
    """set_workspace_color with no args should return usage error."""
    result = TestResult("set_workspace_color no args")
    try:
        resp = client._send_command("set_workspace_color")
        if resp.startswith("ERROR"):
            result.success(f"Got expected error: {resp}")
        else:
            result.failure(f"Expected error, got: {resp}")
    except Exception as e:
        result.failure(str(e))
    return result


def test_list_workspaces_unchanged(client: cmux) -> TestResult:
    """list_workspaces format should not include color data."""
    result = TestResult("list_workspaces format unchanged")
    try:
        workspaces = client.list_workspaces()
        if not workspaces:
            result.failure("No workspaces available")
            return result

        target_id = workspaces[0][1]
        client._send_command(f"set_workspace_color {target_id} #C0392B")

        raw = client._send_command("list_workspaces")
        # Verify no color hex appears after workspace titles
        for line in raw.split("\n"):
            if "#C0392B" in line:
                result.failure(f"Color leaked into list_workspaces: {line}")
                client._send_command(f"set_workspace_color {target_id} none")
                return result

        # Verify parsing still works (4-tuple)
        workspaces_after = client.list_workspaces()
        if len(workspaces_after) == len(workspaces):
            result.success("list_workspaces format unchanged after setting color")
        else:
            result.failure("Workspace count changed unexpectedly")

        client._send_command(f"set_workspace_color {target_id} none")
    except Exception as e:
        result.failure(str(e))
    return result


def run_tests():
    print("=" * 60)
    print("Workspace Color Socket Command Tests")
    print("=" * 60)
    print()

    socket_path = cmux.DEFAULT_SOCKET_PATH
    if not os.path.exists(socket_path):
        print(f"Error: Socket not found at {socket_path}")
        print("Please make sure cmux is running.")
        return 1

    tests = [
        test_set_workspace_color_no_args,
        test_set_workspace_color_invalid_uuid,
        test_list_workspace_colors_empty,
        test_set_workspace_color,
        test_clear_workspace_color,
        test_list_workspaces_unchanged,
    ]

    results = []
    try:
        with cmux() as client:
            if not client.ping():
                print("Error: Could not ping cmux")
                return 1

            for test_fn in tests:
                r = test_fn(client)
                results.append(r)
                status = "✅" if r.passed else "❌"
                print(f"  {status} {r.name}: {r.message}")
    except Exception as e:
        print(f"Error: {e}")
        return 1

    print()
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_tests())
