"""PyFluent - Python library for controlling Tecan Fluent liquid handling robots."""

__version__ = "0.1.0"

from .backends.fluent_visionx import FluentVisionX, PYLABROBOT_AVAILABLE
from .backends.errors import TecanError
from .deck import FluentDeck, Labware, LabwareType, Well
from .protocol import Protocol, Transfer, CommandType
from .worklist import Worklist, WorklistFormat, WorklistOperation
from .method_manager import MethodManager, MethodInfo

# Conditionally import worklist converter items if pylabrobot is available
if PYLABROBOT_AVAILABLE:
    from .worklist_converter import (
        OperationRecord,
        convert_operations_to_worklist,
        convert_pylabrobot_operations,
        WorklistRecorder,
        well_to_position,
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
    # Worklist
    "Worklist",
    "WorklistFormat",
    "WorklistOperation",
    # Method Management
    "MethodManager",
    "MethodInfo",
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
        "resource_to_labware_name",
    ])
