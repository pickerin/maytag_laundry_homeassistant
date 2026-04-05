"""Shared test fixtures for maytag_laundry tests."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add custom_components to path so imports work without HA installed
sys.path.insert(0, str(Path(__file__).parent.parent))

# Stub out the entire homeassistant namespace so integration modules can be
# imported without a full HA install.  ConfigFlow must be a real class (not a
# MagicMock) because config_flow.py uses it as a base class.
_HA_MODULES = [
    "homeassistant",
    "homeassistant.core",
    "homeassistant.config_entries",
    "homeassistant.data_entry_flow",
    "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.exceptions",
]
for _mod_name in _HA_MODULES:
    sys.modules[_mod_name] = MagicMock()

# config_entries.ConfigFlow must be a real inheritable class
sys.modules["homeassistant.config_entries"].ConfigFlow = type("ConfigFlow", (), {})
