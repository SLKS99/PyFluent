"""
Converter from PyLabRobot operations to Tecan worklist format.

This module provides functions to convert PyLabRobot-style operations
to Tecan worklist files (GWL/CSV format).
"""

from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass
from .worklist import Worklist, WorklistFormat, WorklistOperation
from pylabrobot.liquid_handling.standard import (
    Aspiration,
    Dispense,
    Pickup,
    Drop,
    PickupTipRack,
    DropTipRack,
)
from pylabrobot.resources import Resource, Well


@dataclass
class OperationRecord:
    """Record of a PyLabRobot operation for worklist conversion."""
    operation_type: str  # "pickup", "aspirate", "dispense", "drop"
    resource: Optional[Resource] = None
    well: Optional[Union[str, Well]] = None
    volume: float = 0.0
    liquid_class: str = "Water Test No Detect"
    tip_type: str = ""
    comment: str = ""


def well_to_position(well: Union[str, Well, int]) -> int:
    """
    Convert well to Tecan position number.
    
    Tecan uses column-major ordering:
    - A1 = 1, B1 = 2, ..., H1 = 8
    - A2 = 9, B2 = 10, ..., H2 = 16
    - etc.
    
    Args:
        well: Well name (e.g., "A1"), Well object, or position number
    
    Returns:
        Position number (1-based)
    """
    if isinstance(well, int):
        return well
    
    if isinstance(well, Well):
        # Well object - get name
        well_name = well.name if hasattr(well, 'name') else str(well)
    else:
        well_name = str(well).upper().strip()
    
    # If already a number string
    if well_name.isdigit():
        return int(well_name)
    
    # Parse A1, B2, etc.
    if len(well_name) < 2:
        return 1  # Default to A1
    
    row_letter = well_name[0]
    col_str = well_name[1:]
    
    if not col_str.isdigit():
        return 1  # Default
    
    row = ord(row_letter) - ord('A')  # 0-based
    col = int(col_str) - 1  # 0-based
    
    # Column-major: position = col * 8 + row + 1
    return col * 8 + row + 1


def resource_to_labware_name(resource: Resource) -> str:
    """
    Convert PyLabRobot resource to Tecan labware name.
    
    Args:
        resource: PyLabRobot Resource object
    
    Returns:
        Labware name string
    """
    if hasattr(resource, 'name'):
        return resource.name
    elif hasattr(resource, 'get_name'):
        return resource.get_name()
    else:
        return str(resource)


def convert_operations_to_worklist(
    operations: List[OperationRecord],
    name: str = "ConvertedProtocol",
    liquid_class: str = "Water Test No Detect",
    tip_type: str = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul"
) -> Worklist:
    """
    Convert a list of PyLabRobot operations to a Tecan worklist.
    
    Args:
        operations: List of OperationRecord objects
        name: Name for the worklist
        liquid_class: Default liquid class
        tip_type: Default tip type
    
    Returns:
        Worklist object
    
    Example:
        from pyfluent.worklist_converter import OperationRecord, convert_operations_to_worklist
        
        operations = [
            OperationRecord("pickup", resource=tip_rack, well="A1"),
            OperationRecord("aspirate", resource=source_plate, well="A1", volume=100),
            OperationRecord("dispense", resource=dest_plate, well="A1", volume=100),
            OperationRecord("drop", resource=waste)
        ]
        
        wl = convert_operations_to_worklist(operations)
        wl.save("my_worklist.gwl")
    """
    wl = Worklist(name, liquid_class=liquid_class, tip_type=tip_type)
    
    current_tips_loaded = False
    
    for op in operations:
        if op.operation_type == "pickup" or op.operation_type == "pick_up_tips":
            # Get new tips
            if not current_tips_loaded:
                wl.break_tips()  # Get new tips
                current_tips_loaded = True
                if op.comment:
                    wl.comment(f"Pick up tips: {op.comment}")
        
        elif op.operation_type == "aspirate":
            if not op.resource:
                continue
            
            labware_name = resource_to_labware_name(op.resource)
            well_pos = well_to_position(op.well) if op.well else 1
            vol = op.volume if op.volume > 0 else 100.0
            lc = op.liquid_class if op.liquid_class else liquid_class
            
            wl.aspirate(
                rack_label=labware_name,
                well=well_pos,
                volume=vol,
                liquid_class=lc
            )
        
        elif op.operation_type == "dispense":
            if not op.resource:
                continue
            
            labware_name = resource_to_labware_name(op.resource)
            well_pos = well_to_position(op.well) if op.well else 1
            vol = op.volume if op.volume > 0 else 100.0
            lc = op.liquid_class if op.liquid_class else liquid_class
            
            wl.dispense(
                rack_label=labware_name,
                well=well_pos,
                volume=vol,
                liquid_class=lc
            )
        
        elif op.operation_type == "drop" or op.operation_type == "drop_tips":
            # Drop tips
            if current_tips_loaded:
                if op.resource:
                    labware_name = resource_to_labware_name(op.resource)
                    # For drop tips, we typically use waste location
                    # The worklist format doesn't have explicit drop tips command
                    # So we'll add a comment
                    wl.comment(f"Drop tips to {labware_name}")
                current_tips_loaded = False
        
        if op.comment and op.operation_type not in ["pickup", "pick_up_tips"]:
            wl.comment(op.comment)
    
    return wl


def convert_pylabrobot_operations(
    aspirations: Optional[List[Aspiration]] = None,
    dispenses: Optional[List[Dispense]] = None,
    pickups: Optional[List[Pickup]] = None,
    drops: Optional[List[Drop]] = None,
    name: str = "ConvertedProtocol",
    liquid_class: str = "Water Test No Detect"
) -> Worklist:
    """
    Convert PyLabRobot operation objects to a Tecan worklist.
    
    This is a convenience function that takes PyLabRobot operation objects
    and converts them to a worklist.
    
    Args:
        aspirations: List of Aspiration operations
        dispenses: List of Dispense operations
        pickups: List of Pickup operations
        drops: List of Drop operations
        name: Name for the worklist
        liquid_class: Default liquid class
    
    Returns:
        Worklist object
    
    Example:
        from pylabrobot.liquid_handling.standard import Aspiration, Dispense
        from pyfluent.worklist_converter import convert_pylabrobot_operations
        
        # Create operations (PyLabRobot style)
        asp = Aspiration(resource=source_plate["A1"], volume=100)
        disp = Dispense(resource=dest_plate["A1"], volume=100)
        
        # Convert to worklist
        wl = convert_pylabrobot_operations(
            aspirations=[asp],
            dispenses=[disp]
        )
        wl.save("my_worklist.gwl")
    """
    operations = []
    
    # Convert pickups
    if pickups:
        for pickup in pickups:
            resource = pickup.resource if hasattr(pickup, 'resource') else None
            well = None
            if resource and hasattr(resource, 'name'):
                # Try to get well from resource
                pass
            operations.append(OperationRecord(
                operation_type="pickup",
                resource=resource,
                comment="Pick up tips"
            ))
    
    # Convert aspirations
    if aspirations:
        for asp in aspirations:
            resource = asp.resource if hasattr(asp, 'resource') else None
            volume = float(asp.volume) if hasattr(asp, 'volume') else 0.0
            liquid_class = getattr(asp, 'liquid_class', liquid_class)
            
            # Try to get well name
            well = None
            if resource:
                if hasattr(resource, 'name'):
                    well = resource.name
                elif isinstance(resource, Well):
                    well = resource
            
            operations.append(OperationRecord(
                operation_type="aspirate",
                resource=resource,
                well=well,
                volume=volume,
                liquid_class=liquid_class
            ))
    
    # Convert dispenses
    if dispenses:
        for disp in dispenses:
            resource = disp.resource if hasattr(disp, 'resource') else None
            volume = float(disp.volume) if hasattr(disp, 'volume') else 0.0
            liquid_class = getattr(disp, 'liquid_class', liquid_class)
            
            # Try to get well name
            well = None
            if resource:
                if hasattr(resource, 'name'):
                    well = resource.name
                elif isinstance(resource, Well):
                    well = resource
            
            operations.append(OperationRecord(
                operation_type="dispense",
                resource=resource,
                well=well,
                volume=volume,
                liquid_class=liquid_class
            ))
    
    # Convert drops
    if drops:
        for drop in drops:
            resource = drop.resource if hasattr(drop, 'resource') else None
            operations.append(OperationRecord(
                operation_type="drop",
                resource=resource,
                comment="Drop tips"
            ))
    
    return convert_operations_to_worklist(operations, name, liquid_class)


class WorklistRecorder:
    """
    Context manager that records PyLabRobot operations and converts them to a worklist.
    
    Usage:
        from pyfluent.worklist_converter import WorklistRecorder
        from pylabrobot.liquid_handling import LiquidHandler
        
        lh = LiquidHandler(backend=backend)
        
        with WorklistRecorder("MyProtocol") as recorder:
            # Perform operations (these are recorded, not executed)
            await lh.pick_up_tips(tip_rack["A1"])
            await lh.aspirate(source_plate["A1"], vols=100)
            await lh.dispense(dest_plate["A1"], vols=100)
            await lh.drop_tips(tip_rack["A1"])
        
        # Get the worklist
        wl = recorder.get_worklist()
        wl.save("my_worklist.gwl")
    
    Note: This is a simplified version. For full implementation, you would need
    to intercept the backend calls, which requires more complex setup.
    """
    
    def __init__(
        self,
        name: str = "RecordedProtocol",
        liquid_class: str = "Water Test No Detect"
    ):
        self.name = name
        self.liquid_class = liquid_class
        self.operations: List[OperationRecord] = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    
    def record_pickup(self, resource: Resource, well: Optional[Union[str, Well]] = None):
        """Record a pickup operation."""
        self.operations.append(OperationRecord(
            operation_type="pickup",
            resource=resource,
            well=well
        ))
    
    def record_aspirate(
        self,
        resource: Resource,
        well: Optional[Union[str, Well]] = None,
        volume: float = 0.0,
        liquid_class: Optional[str] = None
    ):
        """Record an aspirate operation."""
        self.operations.append(OperationRecord(
            operation_type="aspirate",
            resource=resource,
            well=well,
            volume=volume,
            liquid_class=liquid_class or self.liquid_class
        ))
    
    def record_dispense(
        self,
        resource: Resource,
        well: Optional[Union[str, Well]] = None,
        volume: float = 0.0,
        liquid_class: Optional[str] = None
    ):
        """Record a dispense operation."""
        self.operations.append(OperationRecord(
            operation_type="dispense",
            resource=resource,
            well=well,
            volume=volume,
            liquid_class=liquid_class or self.liquid_class
        ))
    
    def record_drop(self, resource: Resource):
        """Record a drop operation."""
        self.operations.append(OperationRecord(
            operation_type="drop",
            resource=resource
        ))
    
    def get_worklist(self) -> Worklist:
        """Get the worklist from recorded operations."""
        return convert_operations_to_worklist(
            self.operations,
            name=self.name,
            liquid_class=self.liquid_class
        )

