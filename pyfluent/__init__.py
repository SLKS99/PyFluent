"""PyFluent - Python library for controlling Tecan Fluent liquid handling robots."""

__version__ = "0.1.0"

from .backends.fluent_visionx import FluentVisionX
from .backends.errors import TecanError
from .deck import FluentDeck, Labware, LabwareType, Well
from .protocol import Protocol, Transfer, CommandType
from .worklist import Worklist, WorklistFormat, WorklistOperation
from .method_manager import MethodManager, MethodInfo
from .worklist_converter import (
    OperationRecord,
    convert_operations_to_worklist,
    convert_pylabrobot_operations,
    WorklistRecorder,
    well_to_position,
    resource_to_labware_name,
)

__all__ = [
    # Backend
    "FluentVisionX",
    "TecanError",
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
    # Worklist Converter
    "OperationRecord",
    "convert_operations_to_worklist",
    "convert_pylabrobot_operations",
    "WorklistRecorder",
    "well_to_position",
    "resource_to_labware_name",
    # Method Management
    "MethodManager",
    "MethodInfo",
    # Version
    "__version__",
]
