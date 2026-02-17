"""
Worklist generation for Tecan Fluent.

This module creates Tecan-compatible worklist files (GWL format)
that can be executed by FluentControl methods.

The worklist approach is the most reliable way to run liquid handling
operations - you generate the worklist in Python, then run a method
in FluentControl that reads and executes it.
"""

import os
import csv
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from .constants import DEFAULT_LIQUID_CLASS


class WorklistFormat(Enum):
    """Supported worklist formats."""
    GWL = "gwl"  # Tecan GWL format
    CSV = "csv"  # Simple CSV format
    

@dataclass
class WorklistOperation:
    """A single worklist operation."""
    command: str  # A=Aspirate, D=Dispense, W=Wash, etc.
    rack_label: str = ""
    rack_id: str = ""
    rack_type: str = ""
    position: int = 1
    tube_id: str = ""
    volume: float = 0.0
    liquid_class: str = ""
    tip_type: str = ""
    tip_mask: int = 0
    forced_rack_type: str = ""
    comment: str = ""
    
    def to_gwl_line(self) -> str:
        """Convert to GWL format line."""
        if self.command == "C":
            # Comment line
            return f"C;{self.comment}"
        elif self.command == "A":
            # Aspirate: A;RackLabel;RackID;RackType;Position;TubeID;Volume;LiquidClass;TipType;TipMask;ForcedRackType
            return f"A;{self.rack_label};{self.rack_id};{self.rack_type};{self.position};{self.tube_id};{self.volume:.1f};{self.liquid_class};{self.tip_type};{self.tip_mask};"
        elif self.command == "D":
            # Dispense: D;RackLabel;RackID;RackType;Position;TubeID;Volume;LiquidClass;TipType;TipMask;ForcedRackType
            return f"D;{self.rack_label};{self.rack_id};{self.rack_type};{self.position};{self.tube_id};{self.volume:.1f};{self.liquid_class};{self.tip_type};{self.tip_mask};"
        elif self.command == "W":
            # Wash tips
            return f"W;"
        elif self.command == "B":
            # Break (new tip)
            return f"B;"
        else:
            return f"{self.command};"
    
    def to_csv_row(self) -> List[str]:
        """Convert to CSV row."""
        return [
            self.command,
            self.rack_label,
            str(self.position),
            f"{self.volume:.1f}",
            self.liquid_class,
            self.comment
        ]


class Worklist:
    """
    Tecan-compatible worklist generator.
    
    Use this to create worklists that can be executed by FluentControl.
    
    Example:
        wl = Worklist("MyWorklist")
        
        # Add operations
        wl.aspirate("SourcePlate", "A1", 100)
        wl.dispense("DestPlate", "A1", 100)
        wl.aspirate("SourcePlate", "B1", 100)
        wl.dispense("DestPlate", "B1", 100)
        
        # Save worklist
        wl.save("C:/Worklists/my_worklist.gwl")
        
        # Then run your FluentControl method that reads this worklist
    """
    
    def __init__(
        self,
        name: str = "Worklist",
        liquid_class: str = DEFAULT_LIQUID_CLASS,
        tip_type: str = "",
        default_tip_mask: int = 255  # All 8 tips
    ):
        """
        Create a new worklist.
        
        Args:
            name: Name of the worklist
            liquid_class: Default liquid class for operations (from constants)
            tip_type: Default tip type
            default_tip_mask: Default tip mask (255 = all 8 tips)
        """
        self.name = name
        self.liquid_class = liquid_class
        self.tip_type = tip_type
        self.default_tip_mask = default_tip_mask
        self.operations: List[WorklistOperation] = []
        self.created = datetime.now()
    
    def _well_to_position(self, well: str) -> int:
        """
        Convert well name (A1, B2, etc.) to position number.
        Tecan uses column-major ordering: A1=1, B1=2, ..., A2=9, B2=10, ...
        """
        if isinstance(well, int):
            return well
        
        well = well.upper().strip()
        if well.isdigit():
            return int(well)
        
        # Parse A1, B2, etc.
        row = ord(well[0]) - ord('A')  # 0-based row
        col = int(well[1:]) - 1  # 0-based column
        
        # Column-major: position = col * 8 + row + 1
        return col * 8 + row + 1
    
    def comment(self, text: str):
        """Add a comment line to the worklist."""
        self.operations.append(WorklistOperation(
            command="C",
            comment=text
        ))
        return self
    
    def aspirate(
        self,
        rack_label: str,
        well: str,
        volume: float,
        liquid_class: Optional[str] = None,
        tip_mask: Optional[int] = None
    ):
        """
        Add an aspirate operation.
        
        Args:
            rack_label: Label of the source labware (e.g., "SourcePlate")
            well: Well position (e.g., "A1", "B2", or position number)
            volume: Volume to aspirate in µL
            liquid_class: Liquid class (uses default if not specified)
            tip_mask: Tip mask (uses default if not specified)
        """
        self.operations.append(WorklistOperation(
            command="A",
            rack_label=rack_label,
            position=self._well_to_position(well),
            volume=volume,
            liquid_class=liquid_class or self.liquid_class,
            tip_type=self.tip_type,
            tip_mask=tip_mask if tip_mask is not None else self.default_tip_mask
        ))
        return self
    
    def dispense(
        self,
        rack_label: str,
        well: str,
        volume: float,
        liquid_class: Optional[str] = None,
        tip_mask: Optional[int] = None
    ):
        """
        Add a dispense operation.
        
        Args:
            rack_label: Label of the destination labware
            well: Well position (e.g., "A1", "B2", or position number)
            volume: Volume to dispense in µL
            liquid_class: Liquid class (uses default if not specified)
            tip_mask: Tip mask (uses default if not specified)
        """
        self.operations.append(WorklistOperation(
            command="D",
            rack_label=rack_label,
            position=self._well_to_position(well),
            volume=volume,
            liquid_class=liquid_class or self.liquid_class,
            tip_type=self.tip_type,
            tip_mask=tip_mask if tip_mask is not None else self.default_tip_mask
        ))
        return self
    
    def transfer(
        self,
        source_rack: str,
        source_well: str,
        dest_rack: str,
        dest_well: str,
        volume: float,
        liquid_class: Optional[str] = None,
        new_tip: bool = False
    ):
        """
        Add a complete transfer (aspirate + dispense).
        
        Args:
            source_rack: Source labware label
            source_well: Source well
            dest_rack: Destination labware label
            dest_well: Destination well
            volume: Volume to transfer
            liquid_class: Liquid class
            new_tip: Whether to get new tip before transfer
        """
        if new_tip:
            self.break_tips()
        
        self.aspirate(source_rack, source_well, volume, liquid_class)
        self.dispense(dest_rack, dest_well, volume, liquid_class)
        return self
    
    def multi_dispense(
        self,
        source_rack: str,
        source_well: str,
        dest_rack: str,
        dest_wells: List[str],
        volume_per_well: float,
        liquid_class: Optional[str] = None
    ):
        """
        Aspirate once and dispense to multiple wells.
        
        Args:
            source_rack: Source labware
            source_well: Source well
            dest_rack: Destination labware
            dest_wells: List of destination wells
            volume_per_well: Volume per dispense
            liquid_class: Liquid class
        """
        total_volume = volume_per_well * len(dest_wells)
        self.aspirate(source_rack, source_well, total_volume, liquid_class)
        
        for well in dest_wells:
            self.dispense(dest_rack, well, volume_per_well, liquid_class)
        
        return self
    
    def serial_dilution(
        self,
        rack_label: str,
        wells: List[str],
        initial_volume: float,
        transfer_volume: float,
        liquid_class: Optional[str] = None
    ):
        """
        Create a serial dilution series.
        
        Args:
            rack_label: Labware label
            wells: List of wells in order (e.g., ["A1", "A2", "A3", ...])
            initial_volume: Volume already in wells
            transfer_volume: Volume to transfer between wells
            liquid_class: Liquid class
        """
        for i in range(len(wells) - 1):
            self.transfer(
                rack_label, wells[i],
                rack_label, wells[i + 1],
                transfer_volume,
                liquid_class,
                new_tip=True
            )
        return self
    
    def wash_tips(self):
        """Add a wash tips operation."""
        self.operations.append(WorklistOperation(command="W"))
        return self
    
    def break_tips(self):
        """Add a break (get new tips) operation."""
        self.operations.append(WorklistOperation(command="B"))
        return self
    
    def to_gwl(self) -> str:
        """
        Generate worklist in GWL format.
        
        Returns:
            GWL file content as string
        """
        lines = []
        lines.append(f"C;Worklist: {self.name}")
        lines.append(f"C;Created: {self.created.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"C;Operations: {len(self.operations)}")
        lines.append("C;")
        
        for op in self.operations:
            lines.append(op.to_gwl_line())
        
        return "\n".join(lines)
    
    def to_csv(self) -> str:
        """
        Generate worklist in CSV format.
        
        Returns:
            CSV file content as string
        """
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Command", "RackLabel", "Position", "Volume", "LiquidClass", "Comment"])
        
        for op in self.operations:
            writer.writerow(op.to_csv_row())
        
        return output.getvalue()
    
    def save(self, filepath: str, format: WorklistFormat = WorklistFormat.GWL):
        """
        Save worklist to file.
        
        Args:
            filepath: Path to save the worklist
            format: Worklist format (GWL or CSV)
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        
        if format == WorklistFormat.GWL:
            content = self.to_gwl()
        else:
            content = self.to_csv()
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        print(f"Saved worklist to: {filepath}")
        return filepath
    
    def get_summary(self) -> str:
        """Get a summary of the worklist."""
        aspirates = sum(1 for op in self.operations if op.command == "A")
        dispenses = sum(1 for op in self.operations if op.command == "D")
        total_asp_vol = sum(op.volume for op in self.operations if op.command == "A")
        total_disp_vol = sum(op.volume for op in self.operations if op.command == "D")
        
        return f"""
Worklist: {self.name}
Created: {self.created}
------------------------
Operations: {len(self.operations)}
  Aspirates: {aspirates} ({total_asp_vol:.1f} µL total)
  Dispenses: {dispenses} ({total_disp_vol:.1f} µL total)
"""
    
    def print_summary(self):
        """Print worklist summary."""
        print(self.get_summary())
    
    def print_operations(self):
        """Print all operations."""
        print(f"\nWorklist: {self.name}")
        print("=" * 60)
        for i, op in enumerate(self.operations):
            if op.command == "C":
                print(f"  # {op.comment}")
            elif op.command == "A":
                print(f"  {i+1}. ASPIRATE {op.volume:.1f}µL from {op.rack_label} pos {op.position}")
            elif op.command == "D":
                print(f"  {i+1}. DISPENSE {op.volume:.1f}µL to {op.rack_label} pos {op.position}")
            elif op.command == "W":
                print(f"  {i+1}. WASH TIPS")
            elif op.command == "B":
                print(f"  {i+1}. NEW TIPS")
        print("=" * 60)


def create_plate_transfer_worklist(
    source_plate: str,
    dest_plate: str,
    volume: float,
    wells: Optional[List[str]] = None,
    num_wells: int = 96,
    liquid_class: str = DEFAULT_LIQUID_CLASS
) -> Worklist:
    """
    Create a worklist for plate-to-plate transfer.
    
    Args:
        source_plate: Source plate label
        dest_plate: Destination plate label
        volume: Volume per well
        wells: Specific wells to transfer (default: all)
        num_wells: Number of wells if not specifying wells
        liquid_class: Liquid class
    
    Returns:
        Worklist object
    """
    wl = Worklist(f"Transfer_{source_plate}_to_{dest_plate}", liquid_class)
    wl.comment(f"Transfer from {source_plate} to {dest_plate}")
    
    if wells is None:
        # Generate all well names for 96-well plate
        wells = []
        for col in range(1, 13):
            for row in "ABCDEFGH":
                wells.append(f"{row}{col}")
                if len(wells) >= num_wells:
                    break
            if len(wells) >= num_wells:
                break
    
    for well in wells:
        wl.transfer(source_plate, well, dest_plate, well, volume)
    
    return wl


def create_reagent_addition_worklist(
    reagent_source: str,
    reagent_well: str,
    dest_plate: str,
    dest_wells: List[str],
    volume: float,
    liquid_class: str = DEFAULT_LIQUID_CLASS
) -> Worklist:
    """
    Create a worklist for adding reagent to multiple wells.
    
    Args:
        reagent_source: Reagent source labware
        reagent_well: Reagent well
        dest_plate: Destination plate
        dest_wells: Destination wells
        volume: Volume per well
        liquid_class: Liquid class
    
    Returns:
        Worklist object
    """
    wl = Worklist(f"ReagentAddition_{dest_plate}", liquid_class)
    wl.comment(f"Add reagent from {reagent_source} to {dest_plate}")
    
    wl.multi_dispense(reagent_source, reagent_well, dest_plate, dest_wells, volume)
    
    return wl

