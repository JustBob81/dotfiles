#!/usr/bin/env python3
"""Set the reviewed user-level GNOME appearance preferences."""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
from pathlib import Path


class AppearanceError(RuntimeError):
    pass


def run_gsettings(*args: str) -> str:
    result = subprocess.run(
        ["gsettings", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise AppearanceError(result.stderr.strip() or "gsettings command failed")
    return result.stdout.strip()


def load_settings(config_path: Path) -> tuple[str, dict[str, str]]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AppearanceError(f"Cannot read appearance policy {config_path}: {exc}") from exc
    schema = config.get("schema")
    settings = config.get("settings")
    if schema != "org.gnome.desktop.interface":
        raise AppearanceError("Only the reviewed GNOME interface schema is supported")
    if not isinstance(settings, dict) or not settings:
        raise AppearanceError("Appearance policy must declare settings")
    if set(settings) != {"color-scheme", "gtk-theme"}:
        raise AppearanceError("Appearance policy must declare color-scheme and gtk-theme only")
    if settings["color-scheme"] != "prefer-dark" or settings["gtk-theme"] != "Yaru-dark":
        raise AppearanceError("Appearance policy values differ from the reviewed dark preference")
    return schema, settings


def current_string(schema: str, key: str) -> str:
    raw = run_gsettings("get", schema, key)
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise AppearanceError(f"Cannot parse current GNOME setting {key}: {raw}") from exc
    if not isinstance(value, str):
        raise AppearanceError(f"GNOME setting {key} is not a string")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report planned settings only")
    mode.add_argument("--apply", action="store_true", help="apply settings for this user")
    args = parser.parse_args()

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "GNOME" not in desktop:
        print(json.dumps({"changed": False, "skipped": "not running inside a GNOME desktop session"}))
        return 0
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS") or not os.environ.get("XDG_RUNTIME_DIR"):
        print(json.dumps({"changed": False, "skipped": "GNOME user D-Bus session is unavailable; run from a GNOME terminal"}))
        return 0
    if os.geteuid() == 0:
        print(json.dumps({"changed": False, "skipped": "run as the desktop user, not root"}))
        return 0
    if not shutil.which("gsettings"):
        print(json.dumps({"changed": False, "error": "gsettings is not installed"}))
        return 1

    try:
        schema, desired = load_settings(args.config)
        changes = []
        for key, value in desired.items():
            current = current_string(schema, key)
            if current != value:
                changes.append({"key": key, "current": current, "desired": value})
        applied = []
        if args.apply:
            for item in changes:
                run_gsettings("set", schema, item["key"], json.dumps(item["desired"]))
                if current_string(schema, item["key"]) != item["desired"]:
                    raise AppearanceError(f"GNOME did not retain the requested {item['key']} setting")
                applied.append(item["key"])
        print(json.dumps({"changed": bool(changes), "planned_changes": changes, "applied": applied}))
        return 0
    except (AppearanceError, OSError) as exc:
        print(json.dumps({"changed": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
