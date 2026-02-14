"""Option metadata for ryzenadj-control."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionSpec:
    key: str
    cli: str
    label: str
    category: str
    minimum: int
    maximum: int
    default: int
    tooltip: str
    ui_scale: int = 1
    ui_suffix: str = ""


NUMERIC_OPTIONS = [
    OptionSpec(
        "stapm_limit",
        "--stapm-limit",
        "STAPM Limit",
        "Power",
        0,
        200000,
        25000,
        "Sustained platform power limit in W.",
        ui_scale=1000,
        ui_suffix=" W",
    ),
    OptionSpec(
        "fast_limit",
        "--fast-limit",
        "PPT Fast Limit",
        "Power",
        0,
        200000,
        35000,
        "Short boost power limit in W.",
        ui_scale=1000,
        ui_suffix=" W",
    ),
    OptionSpec(
        "slow_limit",
        "--slow-limit",
        "PPT Slow Limit",
        "Power",
        0,
        200000,
        30000,
        "Long-duration package power limit in W.",
        ui_scale=1000,
        ui_suffix=" W",
    ),
    OptionSpec(
        "slow_time",
        "--slow-time",
        "Slow Time",
        "Power",
        0,
        512,
        64,
        "Time window for slow limit.",
    ),
    OptionSpec(
        "stapm_time",
        "--stapm-time",
        "STAPM Time",
        "Power",
        0,
        512,
        64,
        "Time window for STAPM behavior.",
    ),
    OptionSpec(
        "tctl_temp",
        "--tctl-temp",
        "Tctl Temp",
        "Power",
        0,
        105,
        90,
        "Thermal control target temperature in C.",
    ),
    OptionSpec(
        "apu_slow_limit",
        "--apu-slow-limit",
        "APU Slow Limit",
        "Power",
        0,
        200000,
        30000,
        "APU-specific slow power limit in W.",
        ui_scale=1000,
        ui_suffix=" W",
    ),
    OptionSpec(
        "skin_temp_limit",
        "--skin-temp-limit",
        "Skin Temp Limit",
        "Power",
        0,
        100,
        60,
        "Skin temperature control threshold.",
    ),
    OptionSpec(
        "apu_skin_temp",
        "--apu-skin-temp",
        "APU Skin Temp",
        "Power",
        0,
        100,
        55,
        "APU skin temperature target.",
    ),
    OptionSpec(
        "dgpu_skin_temp",
        "--dgpu-skin-temp",
        "dGPU Skin Temp",
        "Power",
        0,
        100,
        60,
        "dGPU skin temperature target.",
    ),
    OptionSpec(
        "vrm_current",
        "--vrm-current",
        "VRM Current",
        "Current",
        0,
        400,
        100,
        "CPU VRM current limit in A.",
    ),
    OptionSpec(
        "vrmsoc_current",
        "--vrmsoc-current",
        "VRMSoC Current",
        "Current",
        0,
        400,
        80,
        "SoC VRM current limit in A.",
    ),
    OptionSpec(
        "vrmmax_current",
        "--vrmmax-current",
        "VRM Max Current",
        "Current",
        0,
        500,
        130,
        "Maximum CPU VRM peak current in A.",
    ),
    OptionSpec(
        "vrmsocmax_current",
        "--vrmsocmax-current",
        "VRMSoC Max Current",
        "Current",
        0,
        500,
        110,
        "Maximum SoC VRM peak current in A.",
    ),
    OptionSpec(
        "psi0_current",
        "--psi0-current",
        "PSI0 Current",
        "Current",
        0,
        500,
        80,
        "PSI0 current threshold for CPU rails.",
    ),
    OptionSpec(
        "psi0soc_current",
        "--psi0soc-current",
        "PSI0SoC Current",
        "Current",
        0,
        500,
        60,
        "PSI0 current threshold for SoC rails.",
    ),
    OptionSpec(
        "max_socclk_frequency",
        "--max-socclk-frequency",
        "Max SoC Clock",
        "Clocks",
        0,
        4000,
        1800,
        "Maximum SoC clock frequency in MHz.",
    ),
    OptionSpec(
        "min_socclk_frequency",
        "--min-socclk-frequency",
        "Min SoC Clock",
        "Clocks",
        0,
        4000,
        400,
        "Minimum SoC clock frequency in MHz.",
    ),
    OptionSpec(
        "max_fclk_frequency",
        "--max-fclk-frequency",
        "Max FCLK",
        "Clocks",
        0,
        4000,
        1800,
        "Maximum fabric clock in MHz.",
    ),
    OptionSpec(
        "min_fclk_frequency",
        "--min-fclk-frequency",
        "Min FCLK",
        "Clocks",
        0,
        4000,
        400,
        "Minimum fabric clock in MHz.",
    ),
    OptionSpec(
        "max_vcn",
        "--max-vcn",
        "Max VCN",
        "Clocks",
        0,
        4000,
        1200,
        "Maximum VCN clock in MHz.",
    ),
    OptionSpec(
        "min_vcn",
        "--min-vcn",
        "Min VCN",
        "Clocks",
        0,
        4000,
        300,
        "Minimum VCN clock in MHz.",
    ),
    OptionSpec(
        "max_lclk",
        "--max-lclk",
        "Max LCLK",
        "Clocks",
        0,
        4000,
        1200,
        "Maximum LCLK in MHz.",
    ),
    OptionSpec(
        "min_lclk",
        "--min-lclk",
        "Min LCLK",
        "Clocks",
        0,
        4000,
        300,
        "Minimum LCLK in MHz.",
    ),
    OptionSpec(
        "max_gfxclk",
        "--max-gfxclk",
        "Max GFX Clock",
        "Clocks",
        0,
        4000,
        2200,
        "Maximum graphics clock in MHz.",
    ),
    OptionSpec(
        "min_gfxclk",
        "--min-gfxclk",
        "Min GFX Clock",
        "Clocks",
        0,
        4000,
        400,
        "Minimum graphics clock in MHz.",
    ),
    OptionSpec(
        "prochot_deassertion_ramp",
        "--prochot-deassertion-ramp",
        "Prochot Deassertion Ramp",
        "Advanced",
        0,
        255,
        50,
        "Ramp behavior after PROCHOT release.",
    ),
]

BOOLEAN_OPTIONS = [
    {
        "key": "power_saving",
        "cli": "--power-saving",
        "label": "Power Saving",
        "category": "Advanced",
        "tooltip": "Enable ryzenadj power-saving mode.",
    },
    {
        "key": "max_performance",
        "cli": "--max-performance",
        "label": "Max Performance",
        "category": "Advanced",
        "tooltip": "Enable ryzenadj max-performance mode.",
    },
]


def default_profile_values() -> dict:
    """Return defaults for every known option."""
    values = {spec.key: spec.default for spec in NUMERIC_OPTIONS}
    for spec in NUMERIC_OPTIONS:
        values[f"{spec.key}_enabled"] = False
    for option in BOOLEAN_OPTIONS:
        values[option["key"]] = False
    return values


def options_by_category() -> dict:
    """Group numeric options by category."""
    categories = {"Power": [], "Current": [], "Clocks": [], "Advanced": []}
    for spec in NUMERIC_OPTIONS:
        categories.setdefault(spec.category, []).append(spec)
    return categories
