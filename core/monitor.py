"""Monitoring helpers for ryzenadj --info."""

from __future__ import annotations

import re

from core.options import NUMERIC_OPTIONS, default_profile_values


INFO_PATTERNS = {
    "stapm": [r"stapm[^\n]*?(-?\d+(?:\.\d+)?)"],
    "ppt_fast": [r"ppt\s*fast[^\n]*?(-?\d+(?:\.\d+)?)", r"fast[^\n]*?(-?\d+(?:\.\d+)?)"],
    "ppt_slow": [r"ppt\s*slow[^\n]*?(-?\d+(?:\.\d+)?)", r"slow[^\n]*?(-?\d+(?:\.\d+)?)"],
    "cpu_temp": [r"(?:cpu\s*temp|tctl|temperature)[^\n]*?(-?\d+(?:\.\d+)?)"],
    "power_draw": [
        r"(?:current\s*power\s*draw|package\s*power|cpu\s*power)[^\n]*?(-?\d+(?:\.\d+)?)"
    ],
}


def parse_info_output(output: str) -> dict[str, str]:
    """Extract common telemetry values from ryzenadj --info output."""
    text = output.lower()
    parsed: dict[str, str] = {}
    for key, patterns in INFO_PATTERNS.items():
        parsed[key] = "N/A"
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                parsed[key] = match.group(1)
                break
    return parsed


def parse_profile_values_from_info(output: str) -> dict:
    """Build a profile-value dictionary from ryzenadj --info text.

    Parsed numeric options are marked enabled. Unparsed options remain disabled.
    """
    values = default_profile_values()
    lines = output.splitlines()

    for spec in NUMERIC_OPTIONS:
        token = spec.cli.lstrip("-").lower()
        token_alt = token.replace("-", " ")

        for line in lines:
            lowered = line.lower()
            if token not in lowered and token_alt not in lowered:
                continue

            match = re.search(r"(-?\d+(?:\.\d+)?)", line)
            if not match:
                continue

            try:
                parsed_value = int(float(match.group(1)))
            except ValueError:
                continue

            if spec.ui_scale > 1 and parsed_value <= (spec.maximum // spec.ui_scale):
                parsed_value *= spec.ui_scale

            values[spec.key] = max(0, parsed_value)
            values[f"{spec.key}_enabled"] = True
            break

    return values
