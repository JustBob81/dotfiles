#!/usr/bin/env python3
"""Safely bind GNOME Alt+Space to a launcher while preserving other shortcuts."""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys


MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = f"{MEDIA_KEYS}.custom-keybinding"
CUSTOM_PATH_TEMPLATE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/{launcher}/"
CUSTOM_PATH = CUSTOM_PATH_TEMPLATE.format(launcher="albert")
ACTIVATE_MENU_SCHEMA = "org.gnome.desktop.wm.keybindings"
ACTIVATE_MENU_KEY = "activate-window-menu"
LAUNCHER_BINDING = "<Alt>space"
LAUNCHER_COMMAND = "sh -c 'albert toggle'"
LAUNCHER_NAME = "Albert launcher"
LAUNCHER_OPTIONS = {
    "albert": ("Albert launcher", "sh -c 'albert toggle'"),
    "ulauncher": ("Ulauncher", "ulauncher show"),
}


class ShortcutError(RuntimeError):
    pass


def gsettings(*args: str) -> str:
    result = subprocess.run(
        ["gsettings", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ShortcutError(result.stderr.strip() or "gsettings command failed")
    return result.stdout.strip()


def value(schema: str, key: str, path: str | None = None) -> str:
    target = f"{schema}:{path}" if path else schema
    return gsettings("get", target, key)


def parse_variant(raw: str):
    # gsettings prints an explicit type for empty arrays, for example
    # ``@as []`` for an empty array of strings. Python's literal parser does
    # not accept that GVariant annotation, so remove this known annotation
    # before parsing the array value.
    raw = raw.strip()
    if raw.startswith("@as "):
        raw = raw[4:].lstrip()
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise ShortcutError(f"Cannot safely parse GNOME setting {raw!r}") from exc


def variant_string(raw: str) -> str:
    # GVariant accepts the JSON double-quoted string form for string values.
    return json.dumps(raw, ensure_ascii=False)


def variant_string_array(values: list[str]) -> str:
    return "[" + ", ".join(variant_string(item) for item in values) + "]"


def shortcut_conflicts_with_system() -> list[str]:
    conflicts: list[str] = []
    schemas = gsettings("list-schemas").splitlines()
    for schema in schemas:
        if "keybindings" not in schema:
            continue
        for key in gsettings("list-keys", schema).splitlines():
            try:
                current = parse_variant(value(schema, key))
            except ShortcutError:
                continue
            bindings = current if isinstance(current, list) else [current]
            if LAUNCHER_BINDING in bindings:
                if (schema, key) != (ACTIVATE_MENU_SCHEMA, ACTIVATE_MENU_KEY):
                    conflicts.append(f"{schema} {key}")
    return conflicts


def plan() -> tuple[list[str], list[str], list[str]]:
    current_paths = parse_variant(value(MEDIA_KEYS, "custom-keybindings"))
    if not isinstance(current_paths, list) or not all(isinstance(path, str) for path in current_paths):
        raise ShortcutError("GNOME custom-keybindings is not a string array; preserving it")

    for path in current_paths:
        if path == CUSTOM_PATH:
            continue
        try:
            binding = parse_variant(value(CUSTOM_SCHEMA, "binding", path))
        except ShortcutError:
            continue
        if binding == LAUNCHER_BINDING:
            raise ShortcutError(f"Alt+Space is already used by GNOME shortcut path {path}")
    conflicts = shortcut_conflicts_with_system()
    if conflicts:
        raise ShortcutError("Alt+Space is already assigned to: " + ", ".join(conflicts))

    if CUSTOM_PATH in current_paths:
        binding = parse_variant(value(CUSTOM_SCHEMA, "binding", CUSTOM_PATH))
        command = parse_variant(value(CUSTOM_SCHEMA, "command", CUSTOM_PATH))
        name = parse_variant(value(CUSTOM_SCHEMA, "name", CUSTOM_PATH))
        if (binding, command, name) != (LAUNCHER_BINDING, LAUNCHER_COMMAND, LAUNCHER_NAME):
            raise ShortcutError(f"The reserved GNOME shortcut path is already customized: {CUSTOM_PATH}")
        next_paths = list(current_paths)
        set_custom_values: list[str] = []
    else:
        existing = {
            key: parse_variant(value(CUSTOM_SCHEMA, key, CUSTOM_PATH))
            for key in ("name", "command", "binding")
        }
        desired = {"name": LAUNCHER_NAME, "command": LAUNCHER_COMMAND, "binding": LAUNCHER_BINDING}
        if any(existing[key] not in ("", desired[key]) for key in desired):
            raise ShortcutError(f"The reserved GNOME shortcut path contains user data: {CUSTOM_PATH}")

        next_paths = [*current_paths, CUSTOM_PATH]
        set_custom_values = ["name", "command", "binding"]

    menu_bindings = parse_variant(value(ACTIVATE_MENU_SCHEMA, ACTIVATE_MENU_KEY))
    if not isinstance(menu_bindings, list) or not all(isinstance(item, str) for item in menu_bindings):
        raise ShortcutError("GNOME's window-menu shortcut is not a string array; preserving it")
    next_menu_bindings = [item for item in menu_bindings if item != LAUNCHER_BINDING]

    actions = [f"set GNOME shortcut {CUSTOM_PATH} to Alt+Space for {LAUNCHER_NAME}"] if set_custom_values else []
    if next_paths != current_paths:
        actions.append("add launcher shortcut path while preserving existing GNOME shortcuts")
    if next_menu_bindings != menu_bindings:
        actions.append("free Alt+Space by removing it from the GNOME window-menu binding")
    return actions, next_paths, next_menu_bindings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", choices=sorted(LAUNCHER_OPTIONS), default="albert")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report planned changes only")
    mode.add_argument("--apply", action="store_true", help="apply the GNOME shortcut")
    args = parser.parse_args()
    global CUSTOM_PATH, LAUNCHER_COMMAND, LAUNCHER_NAME
    LAUNCHER_NAME, LAUNCHER_COMMAND = LAUNCHER_OPTIONS[args.launcher]
    CUSTOM_PATH = CUSTOM_PATH_TEMPLATE.format(launcher=args.launcher)

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    if "GNOME" not in desktop:
        print(json.dumps({"changed": False, "skipped": "not running inside a GNOME desktop session"}))
        return 0
    if not bus or not os.environ.get("XDG_RUNTIME_DIR"):
        print(json.dumps({"changed": False, "skipped": "GNOME user D-Bus session is unavailable; run from a GNOME terminal"}))
        return 0
    if os.geteuid() == 0:
        print(json.dumps({"changed": False, "skipped": "run as the desktop user, not root"}))
        return 0
    if not shutil.which("gsettings"):
        print(json.dumps({"changed": False, "error": "gsettings is not installed"}))
        return 1

    try:
        actions, next_paths, next_menu_bindings = plan()
        if args.apply and actions:
            if "set GNOME shortcut" in actions[0]:
                for key, setting in (
                    ("name", LAUNCHER_NAME),
                    ("command", LAUNCHER_COMMAND),
                    ("binding", LAUNCHER_BINDING),
                ):
                    gsettings("set", f"{CUSTOM_SCHEMA}:{CUSTOM_PATH}", key, variant_string(setting))
            if "add launcher shortcut path while preserving existing GNOME shortcuts" in actions:
                gsettings("set", MEDIA_KEYS, "custom-keybindings", variant_string_array(next_paths))
            current_menu = parse_variant(value(ACTIVATE_MENU_SCHEMA, ACTIVATE_MENU_KEY))
            if current_menu != next_menu_bindings:
                gsettings("set", ACTIVATE_MENU_SCHEMA, ACTIVATE_MENU_KEY, variant_string_array(next_menu_bindings))

        print(json.dumps({"changed": bool(actions), "planned_changes": actions, "applied": bool(args.apply and actions)}))
        return 0
    except (ShortcutError, OSError) as exc:
        print(json.dumps({"changed": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
