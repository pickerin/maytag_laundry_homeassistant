"""Appliance capability profiles for Whirlpool/Maytag/KitchenAid AWS IoT appliances.

Capability documents are fetched from the Whirlpool cloud during device
discovery and define the full set of cycles, options, and valid values for
each appliance model. The bundled profiles in profiles/ were captured from
live devices using the fixture tooling developed by Paul T. (pts211).

Concept, capability document research, and fixture capture tooling:
  Paul T. (pts211) — https://github.com/pts211/ha-whirlpool-aws

Key insight: the AWS IoT thing attributes already include CapabilityPartNumber,
so the profile can be resolved at discovery time without an additional API call.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

_PROFILES_DIR = Path(__file__).parent / "profiles"


@dataclass
class ApplianceProfile:
    """Parsed capability profile for a specific appliance model.

    Derived from the raw capability document fetched from the Whirlpool
    AWS IoT cloud and bundled here by capability part number.
    """

    part_number: str
    appliance_type: str            # "washer" or "dryer" — authoritative from cavities key
    cycles: List[str]              # all valid cycle names for this model
    options: Dict[str, List[str]]  # option name -> union of valid values across all cycles


def load_profile(part_number: str) -> Optional[ApplianceProfile]:
    """Load and parse a bundled capability profile by part number.

    Returns None if no profile is bundled for this part number.
    Devices without a profile continue to work with the base sensor set.
    """
    if not part_number:
        return None

    path = _PROFILES_DIR / f"{part_number}.json"
    if not path.exists():
        _LOGGER.debug("No bundled capability profile for part number %s", part_number)
        return None

    try:
        raw = json.loads(path.read_text())
        return _parse_profile(part_number, raw)
    except Exception:
        _LOGGER.exception("Failed to parse capability profile %s", part_number)
        return None


def _parse_profile(part_number: str, raw: dict) -> ApplianceProfile:
    """Parse a raw capability JSON document into an ApplianceProfile.

    The cavities key defines the appliance type ("washer" or "dryer") and
    is authoritative — more reliable than inferring type from model number
    prefix or live state payload.

    Option values are unioned across all cycles so the resulting list covers
    every value the appliance can report or accept regardless of active cycle.
    """
    cavities = raw.get("cavities", {})
    appliance_type = next(iter(cavities), "washer")
    cavity = cavities[appliance_type]
    cycles_data = cavity.get("cycles", {})
    cycles = list(cycles_data.keys())

    options: Dict[str, List[str]] = {}
    for cycle_data in cycles_data.values():
        whr = cycle_data.get("whrOptions", {})
        for group in ("requiredOptions", "optionalOptions"):
            for opt_name, opt_cfg in whr.get(group, {}).items():
                for val in opt_cfg.get("enumeration", []):
                    if opt_name not in options:
                        options[opt_name] = [val]
                    elif val not in options[opt_name]:
                        options[opt_name].append(val)

    return ApplianceProfile(
        part_number=part_number,
        appliance_type=appliance_type,
        cycles=cycles,
        options=options,
    )
