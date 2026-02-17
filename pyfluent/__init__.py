"""PyFluent - Python library for controlling Tecan Fluent liquid handling robots."""

__version__ = "0.1.0"

from .backends.fluent_visionx import FluentVisionX, PYLABROBOT_AVAILABLE
from .backends.errors import TecanError
from .deck import FluentDeck, Labware, LabwareType, Well
from .protocol import Protocol, Transfer, CommandType, well_name_to_offset, offset_to_well_name
from .worklist import Worklist, WorklistFormat, WorklistOperation
from .method_manager import MethodManager, MethodInfo
from .constants import (
    # Liquid classes
    DEFAULT_LIQUID_CLASS,
    WATER_TEST_NO_DETECT,
    # Waste locations
    DEFAULT_FCA_WASTE,
    DEFAULT_MCA_WASTE,
    DEFAULT_WASTE_LOCATION,
    # Tip types
    DEFAULT_DITI_TYPE,
    DITI_200UL_FILTERED_SBS,
    # Airgap
    DEFAULT_AIRGAP_VOLUME,
    DEFAULT_AIRGAP_SPEED,
    # Plate dimensions
    ROWS_96_WELL,
    COLS_96_WELL,
    # Device aliases
    FCA_DEVICE_ALIAS,
    MCA_DEVICE_ALIAS,
    RGA_DEVICE_ALIAS,
    LIHA_DEVICE_ALIAS,
    # Gripper constants
    DEFAULT_GRIPPER_FINGERS,
    DEFAULT_GRIP_FORCE,
    # Speed constants
    SPEED_SLOW,
    SPEED_MEDIUM,
    SPEED_FAST,
)

# Conditionally import worklist converter items if pylabrobot is available
if PYLABROBOT_AVAILABLE:
    from .worklist_converter import (
        OperationRecord,
        convert_operations_to_worklist,
        convert_pylabrobot_operations,
        WorklistRecorder,
        well_to_position,
        well_to_offset,
        resource_to_labware_name,
    )
    _worklist_converter_available = True
else:
    _worklist_converter_available = False
    # Define dummy classes/functions for compatibility
    class OperationRecord:
        pass

    class WorklistRecorder:
        pass

    def convert_operations_to_worklist(*args, **kwargs):
        raise NotImplementedError("Worklist converter requires pylabrobot")

    def convert_pylabrobot_operations(*args, **kwargs):
        raise NotImplementedError("Worklist converter requires pylabrobot")

    def well_to_position(*args, **kwargs):
        raise NotImplementedError("Worklist converter requires pylabrobot")

    def well_to_offset(*args, **kwargs):
        raise NotImplementedError("Worklist converter requires pylabrobot")

    def resource_to_labware_name(*args, **kwargs):
        raise NotImplementedError("Worklist converter requires pylabrobot")

# Build __all__ conditionally based on available modules
__all__ = [
    # Backend
    "FluentVisionX",
    "TecanError",
    "PYLABROBOT_AVAILABLE",
    # Deck management
    "FluentDeck",
    "Labware",
    "LabwareType",
    "Well",
    # Protocol
    "Protocol",
    "Transfer",
    "CommandType",
    "well_name_to_offset",
    "offset_to_well_name",
    # Worklist
    "Worklist",
    "WorklistFormat",
    "WorklistOperation",
    # Method Management
    "MethodManager",
    "MethodInfo",
    # Constants - Liquid classes
    "DEFAULT_LIQUID_CLASS",
    "WATER_TEST_NO_DETECT",
    # Constants - Waste locations
    "DEFAULT_FCA_WASTE",
    "DEFAULT_MCA_WASTE",
    "DEFAULT_WASTE_LOCATION",
    # Constants - Tips
    "DEFAULT_DITI_TYPE",
    "DITI_200UL_FILTERED_SBS",
    # Constants - Airgap
    "DEFAULT_AIRGAP_VOLUME",
    "DEFAULT_AIRGAP_SPEED",
    # Constants - Plate dimensions
    "ROWS_96_WELL",
    "COLS_96_WELL",
    # Constants - Device aliases
    "FCA_DEVICE_ALIAS",
    "MCA_DEVICE_ALIAS",
    "RGA_DEVICE_ALIAS",
    "LIHA_DEVICE_ALIAS",
    # Constants - Gripper
    "DEFAULT_GRIPPER_FINGERS",
    "DEFAULT_GRIP_FORCE",
    # Constants - Speed
    "SPEED_SLOW",
    "SPEED_MEDIUM",
    "SPEED_FAST",
    # Version
    "__version__",
]

# Add worklist converter items if available
if _worklist_converter_available:
    __all__.extend([
        "OperationRecord",
        "convert_operations_to_worklist",
        "convert_pylabrobot_operations",
        "WorklistRecorder",
        "well_to_position",
        "well_to_offset",
        "resource_to_labware_name",
    ])
