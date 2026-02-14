"""Profile persistence for ryzenadj-control."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.options import default_profile_values


class ProfileError(Exception):
    """Raised for profile persistence failures."""


class ProfileManager:
    """Load, save, import, and export tuning profiles."""

    def __init__(self, config_dir: Path | None = None) -> None:
        base_dir = config_dir or Path.home() / ".config" / "ryzenadj-control"
        self.config_dir = base_dir
        self.path = self.config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _default_data(self) -> dict[str, Any]:
        return {
            "selected": "",
            "profiles": {},
        }

    def _normalize_profile(self, raw_profile: dict[str, Any]) -> dict[str, Any]:
        normalized = default_profile_values()
        for key, value in raw_profile.items():
            if key not in normalized:
                continue
            if isinstance(normalized[key], bool):
                normalized[key] = bool(value)
            else:
                try:
                    normalized[key] = max(0, int(value))
                except (TypeError, ValueError):
                    continue
        return normalized

    def load_all(self) -> dict[str, Any]:
        if not self.path.exists():
            data = self._default_data()
            self.save_all(data)
            return data

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ProfileError(f"Failed to read {self.path}: {exc}") from exc

        profiles = raw.get("profiles", {}) if isinstance(raw, dict) else {}
        selected = raw.get("selected", "") if isinstance(raw, dict) else ""

        if not isinstance(profiles, dict):
            profiles = {}

        cleaned = {}
        for name, profile in profiles.items():
            if isinstance(name, str) and isinstance(profile, dict):
                cleaned[name] = self._normalize_profile(profile)

        if selected not in cleaned:
            selected = ""

        normalized_data = {
            "selected": selected,
            "profiles": cleaned,
        }
        self.save_all(normalized_data)
        return normalized_data

    def save_all(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, indent=2, sort_keys=True)
        try:
            self.path.write_text(payload, encoding="utf-8")
        except OSError as exc:
            raise ProfileError(f"Failed to write {self.path}: {exc}") from exc

    def upsert_profile(self, name: str, profile_values: dict[str, Any]) -> dict[str, Any]:
        data = self.load_all()
        if not name.strip():
            raise ProfileError("Profile name must not be empty.")
        data["profiles"][name] = self._normalize_profile(profile_values)
        data["selected"] = name
        self.save_all(data)
        return data

    def delete_profile(self, name: str) -> dict[str, Any]:
        data = self.load_all()
        if name not in data["profiles"]:
            raise ProfileError(f"Profile '{name}' does not exist.")
        data["profiles"].pop(name)
        if data["selected"] == name and data["profiles"]:
            data["selected"] = next(iter(data["profiles"].keys()))
        elif not data["profiles"]:
            data["selected"] = ""
        self.save_all(data)
        return data

    def export_profiles(self, destination: Path) -> None:
        data = self.load_all()
        try:
            destination.write_text(
                json.dumps(data, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError as exc:
            raise ProfileError(f"Failed to export profiles: {exc}") from exc

    def import_profiles(self, source: Path) -> dict[str, Any]:
        try:
            imported = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"Failed to import profiles: {exc}") from exc

        if not isinstance(imported, dict):
            raise ProfileError("Invalid profile file format.")

        profiles = imported.get("profiles")
        if not isinstance(profiles, dict):
            raise ProfileError("Imported file is missing 'profiles'.")

        cleaned = {}
        for name, profile in profiles.items():
            if isinstance(name, str) and isinstance(profile, dict):
                cleaned[name] = self._normalize_profile(profile)

        if not cleaned:
            raise ProfileError("No valid profiles were found in imported file.")

        selected = imported.get("selected")
        if not isinstance(selected, str) or selected not in cleaned:
            selected = next(iter(cleaned.keys()))

        merged = {
            "selected": selected,
            "profiles": cleaned,
        }
        self.save_all(merged)
        return merged
