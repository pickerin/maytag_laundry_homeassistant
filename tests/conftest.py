"""Shared test fixtures for maytag_laundry tests."""
import sys
from pathlib import Path

# Add custom_components to path so imports work without HA installed
sys.path.insert(0, str(Path(__file__).parent.parent))
