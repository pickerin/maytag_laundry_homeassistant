"""Shared test fixtures for maytag_laundry tests."""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

# Add custom_components to path so imports work without HA installed
sys.path.insert(0, str(Path(__file__).parent.parent))

# Stub out the entire homeassistant namespace so integration modules can be
# imported without a full HA install.  Names used as base classes must be real
# classes (not MagicMock) because Python can't subclass a mock instance.
_HA_MODULES = [
    "homeassistant",
    "homeassistant.core",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.config_entries",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.entity_platform",
    "homeassistant.exceptions",
]
for _mod_name in _HA_MODULES:
    sys.modules[_mod_name] = MagicMock()

# `from homeassistant import config_entries` resolves via the parent mock's
# attribute, not sys.modules — point it at the stub submodule explicitly.
sys.modules["homeassistant"].config_entries = sys.modules["homeassistant.config_entries"]


# config_entries.ConfigFlow must be a real inheritable class that accepts the
# `domain=` class keyword HA uses.
class _ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        pass


sys.modules["homeassistant.config_entries"].ConfigFlow = _ConfigFlow


class _Subscriptable:
    """Base for stub classes used as generic bases (Class[T])."""

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, *args, **kwargs):
        pass


class _SensorEntity:
    pass


@dataclass(frozen=True, kw_only=True)
class _SensorEntityDescription:
    key: str
    name: Any = None
    icon: Optional[str] = None
    device_class: Any = None
    native_unit_of_measurement: Optional[str] = None
    options: Any = None


class _SensorDeviceClass:
    ENUM = "enum"
    DURATION = "duration"


_sensor_mod = sys.modules["homeassistant.components.sensor"]
_sensor_mod.SensorEntity = _SensorEntity
_sensor_mod.SensorEntityDescription = _SensorEntityDescription
_sensor_mod.SensorDeviceClass = _SensorDeviceClass

_uc_mod = sys.modules["homeassistant.helpers.update_coordinator"]
_uc_mod.DataUpdateCoordinator = type("DataUpdateCoordinator", (_Subscriptable,), {})
_uc_mod.CoordinatorEntity = type("CoordinatorEntity", (_Subscriptable,), {})
_uc_mod.UpdateFailed = type("UpdateFailed", (Exception,), {})

sys.modules["homeassistant.exceptions"].ConfigEntryAuthFailed = type(
    "ConfigEntryAuthFailed", (Exception,), {}
)
