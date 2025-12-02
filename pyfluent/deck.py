"""
Deck management for Tecan Fluent.

This module provides classes for managing the Fluent deck layout,
including adding/removing labware and tracking positions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class LabwareType(Enum):
    """Common labware types for Tecan Fluent."""
    PLATE_96_WELL_FLAT = "96 Well Flat"
    PLATE_96_WELL_DEEP = "96 Well Deep"
    PLATE_96_WELL_PCR = "96 Well PCR"
    PLATE_384_WELL = "384 Well"
    TROUGH_SINGLE = "Trough Single"
    TROUGH_8 = "Trough 8-Row"
    TIPS_50UL = "DiTi 50ul"
    TIPS_200UL = "DiTi 200ul"
    TIPS_1000UL = "DiTi 1000ul"
    TIPS_200UL_FILTERED = "DiTi 200ul Filtered SBS"
    RESERVOIR = "Reservoir"
    TUBE_RACK_15ML = "Tube Rack 15mL"
    TUBE_RACK_50ML = "Tube Rack 50mL"
    CUSTOM = "Custom"


@dataclass
class Well:
    """Represents a single well in a plate."""
    row: int  # 0-based row index (0=A, 1=B, ...)
    col: int  # 0-based column index (0=1, 1=2, ...)
    volume: float = 0.0  # Current volume in µL
    max_volume: float = 200.0  # Maximum volume in µL
    
    @property
    def name(self) -> str:
        """Get well name like 'A1', 'B2', etc."""
        row_letter = chr(ord('A') + self.row)
        return f"{row_letter}{self.col + 1}"
    
    @property
    def index(self) -> int:
        """Get 0-based linear index (column-major like Tecan)."""
        # Tecan uses column-major ordering: A1, B1, C1, ... A2, B2, C2, ...
        return self.col * 8 + self.row  # Assuming 8 rows (96-well)


@dataclass
class Labware:
    """Represents a piece of labware on the deck."""
    name: str
    labware_type: str
    location: str
    position: int = 0
    rotation: int = 0
    has_lid: bool = False
    barcode: str = ""
    rows: int = 8  # Default for 96-well
    cols: int = 12  # Default for 96-well
    wells: Dict[str, Well] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize wells after creation."""
        if not self.wells and self.rows > 0 and self.cols > 0:
            for row in range(self.rows):
                for col in range(self.cols):
                    well = Well(row=row, col=col)
                    self.wells[well.name] = well
    
    def get_well(self, well_name: str) -> Optional[Well]:
        """Get a well by name (e.g., 'A1')."""
        return self.wells.get(well_name)
    
    def get_well_by_index(self, index: int) -> Optional[Well]:
        """Get a well by 0-based index."""
        for well in self.wells.values():
            if well.index == index:
                return well
        return None
    
    @property
    def num_wells(self) -> int:
        """Get total number of wells."""
        return len(self.wells)


@dataclass
class DeckPosition:
    """Represents a position on the deck."""
    name: str
    grid: int
    site: int
    labware: Optional[Labware] = None
    
    @property
    def location_string(self) -> str:
        """Get Tecan location string format."""
        return f"Grid:{self.grid}/Site:{self.site}"
    
    @property
    def is_occupied(self) -> bool:
        """Check if position has labware."""
        return self.labware is not None


class FluentDeck:
    """
    Represents the Tecan Fluent deck layout.
    
    The deck is organized as a grid with multiple sites per grid position.
    This class tracks what labware is placed where and provides methods
    to manipulate the deck layout.
    """
    
    # Common deck location names
    COMMON_LOCATIONS = {
        "Nest61mm_Pos": {"grid": 1, "sites": 6},
        "Nest100mm_Pos": {"grid": 2, "sites": 4},
        "DiTi_Nest": {"grid": 3, "sites": 8},
        "Waste": {"grid": 4, "sites": 1},
        "Hotel": {"grid": 5, "sites": 10},
    }
    
    def __init__(self, backend=None):
        """
        Initialize the deck.
        
        Args:
            backend: Optional FluentVisionX backend for direct control
        """
        self.backend = backend
        self.positions: Dict[str, DeckPosition] = {}
        self.labware: Dict[str, Labware] = {}
        self._initialize_default_positions()
    
    def _initialize_default_positions(self):
        """Initialize common deck positions."""
        for loc_name, config in self.COMMON_LOCATIONS.items():
            for site in range(config["sites"]):
                pos_name = f"{loc_name}_{site}"
                self.positions[pos_name] = DeckPosition(
                    name=pos_name,
                    grid=config["grid"],
                    site=site
                )
    
    def add_labware(
        self,
        name: str,
        labware_type: str,
        location: str,
        position: int = 0,
        rotation: int = 0,
        has_lid: bool = False,
        barcode: str = "",
        sync_to_fluent: bool = True
    ) -> Labware:
        """
        Add labware to the deck.
        
        Args:
            name: Unique name for the labware (e.g., "Source[001]")
            labware_type: Type of labware (e.g., "96 Well Flat")
            location: Deck location (e.g., "Nest61mm_Pos")
            position: Position at location (0-based)
            rotation: Rotation in degrees (0, 90, 180, 270)
            has_lid: Whether labware has a lid
            barcode: Barcode if any
            sync_to_fluent: Whether to sync to FluentControl
            
        Returns:
            The created Labware object
        """
        # Determine plate dimensions based on type
        rows, cols = self._get_plate_dimensions(labware_type)
        
        labware = Labware(
            name=name,
            labware_type=labware_type,
            location=location,
            position=position,
            rotation=rotation,
            has_lid=has_lid,
            barcode=barcode,
            rows=rows,
            cols=cols
        )
        
        self.labware[name] = labware
        
        # Update deck position
        pos_key = f"{location}_{position}"
        if pos_key in self.positions:
            self.positions[pos_key].labware = labware
        
        # Sync to FluentControl if backend is available
        if sync_to_fluent and self.backend:
            try:
                self.backend.add_labware(
                    labware_name=name,
                    labware_type=labware_type,
                    target_location=location,
                    position=position,
                    rotation=rotation,
                    has_lid=has_lid,
                    barcode=barcode
                )
            except Exception as e:
                print(f"Warning: Could not sync labware to FluentControl: {e}")
        
        return labware
    
    def remove_labware(self, name: str, sync_to_fluent: bool = True) -> bool:
        """
        Remove labware from the deck.
        
        Args:
            name: Name of the labware to remove
            sync_to_fluent: Whether to sync to FluentControl
            
        Returns:
            True if removed, False if not found
        """
        if name not in self.labware:
            return False
        
        labware = self.labware[name]
        
        # Clear deck position
        pos_key = f"{labware.location}_{labware.position}"
        if pos_key in self.positions:
            self.positions[pos_key].labware = None
        
        del self.labware[name]
        
        # Sync to FluentControl
        if sync_to_fluent and self.backend:
            try:
                self.backend.remove_labware(name)
            except Exception as e:
                print(f"Warning: Could not remove labware from FluentControl: {e}")
        
        return True
    
    def transfer_labware(
        self,
        name: str,
        target_location: str,
        target_position: int = 0,
        sync_to_fluent: bool = True
    ) -> bool:
        """
        Transfer labware to a new location using the robot gripper.
        
        Args:
            name: Name of the labware to transfer
            target_location: Target deck location
            target_position: Position at target location
            sync_to_fluent: Whether to sync to FluentControl
            
        Returns:
            True if transferred
        """
        if name not in self.labware:
            raise ValueError(f"Labware '{name}' not found on deck")
        
        labware = self.labware[name]
        
        # Update old position
        old_pos_key = f"{labware.location}_{labware.position}"
        if old_pos_key in self.positions:
            self.positions[old_pos_key].labware = None
        
        # Update labware
        labware.location = target_location
        labware.position = target_position
        
        # Update new position
        new_pos_key = f"{target_location}_{target_position}"
        if new_pos_key in self.positions:
            self.positions[new_pos_key].labware = labware
        
        # Sync to FluentControl (robot movement)
        if sync_to_fluent and self.backend:
            try:
                self.backend.transfer_labware(
                    labware_name=name,
                    target_location=target_location,
                    target_position=target_position
                )
            except Exception as e:
                print(f"Warning: Could not transfer labware in FluentControl: {e}")
        
        return True
    
    def get_labware(self, name: str) -> Optional[Labware]:
        """Get labware by name."""
        return self.labware.get(name)
    
    def get_labware_at(self, location: str, position: int = 0) -> Optional[Labware]:
        """Get labware at a specific deck position."""
        pos_key = f"{location}_{position}"
        if pos_key in self.positions:
            return self.positions[pos_key].labware
        return None
    
    def _get_plate_dimensions(self, labware_type: str) -> Tuple[int, int]:
        """Get rows and columns for a labware type."""
        labware_type_lower = labware_type.lower()
        
        if "384" in labware_type_lower:
            return (16, 24)
        elif "96" in labware_type_lower or "well" in labware_type_lower:
            return (8, 12)
        elif "trough" in labware_type_lower:
            if "8" in labware_type_lower:
                return (8, 1)
            return (1, 1)
        elif "reservoir" in labware_type_lower:
            return (1, 1)
        elif "diti" in labware_type_lower or "tip" in labware_type_lower:
            return (8, 12)
        else:
            return (8, 12)  # Default to 96-well format
    
    def get_deck_layout(self) -> str:
        """
        Get a string representation of the deck layout.
        
        Returns:
            Formatted string showing deck layout
        """
        lines = []
        lines.append("=" * 60)
        lines.append("  TECAN FLUENT DECK LAYOUT")
        lines.append("=" * 60)
        
        # Group by location
        locations = {}
        for labware in self.labware.values():
            if labware.location not in locations:
                locations[labware.location] = []
            locations[labware.location].append(labware)
        
        if not locations:
            lines.append("\n  [Deck is empty]")
        else:
            for loc_name, labwares in sorted(locations.items()):
                lines.append(f"\n  Location: {loc_name}")
                lines.append("  " + "-" * 40)
                for lw in sorted(labwares, key=lambda x: x.position):
                    lines.append(f"    Position {lw.position}: {lw.name}")
                    lines.append(f"      Type: {lw.labware_type}")
                    lines.append(f"      Wells: {lw.num_wells}")
                    if lw.barcode:
                        lines.append(f"      Barcode: {lw.barcode}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    def print_deck_layout(self):
        """Print the deck layout to console."""
        print(self.get_deck_layout())
    
    def get_available_positions(self, location: str) -> List[int]:
        """
        Get list of available (empty) positions at a location.
        
        Args:
            location: Deck location name
            
        Returns:
            List of available position numbers
        """
        available = []
        for pos_name, pos in self.positions.items():
            if pos_name.startswith(location) and not pos.is_occupied:
                available.append(pos.site)
        return sorted(available)


# Pre-defined labware factory functions
def create_96_well_plate(name: str, location: str, position: int = 0) -> dict:
    """Create parameters for a 96-well plate."""
    return {
        "name": name,
        "labware_type": LabwareType.PLATE_96_WELL_FLAT.value,
        "location": location,
        "position": position
    }


def create_384_well_plate(name: str, location: str, position: int = 0) -> dict:
    """Create parameters for a 384-well plate."""
    return {
        "name": name,
        "labware_type": LabwareType.PLATE_384_WELL.value,
        "location": location,
        "position": position
    }


def create_tip_rack(name: str, location: str, position: int = 0, tip_type: str = "200ul") -> dict:
    """Create parameters for a tip rack."""
    tip_types = {
        "50ul": LabwareType.TIPS_50UL.value,
        "200ul": LabwareType.TIPS_200UL.value,
        "1000ul": LabwareType.TIPS_1000UL.value,
        "200ul_filtered": LabwareType.TIPS_200UL_FILTERED.value,
    }
    return {
        "name": name,
        "labware_type": tip_types.get(tip_type, LabwareType.TIPS_200UL.value),
        "location": location,
        "position": position
    }


def create_reservoir(name: str, location: str, position: int = 0) -> dict:
    """Create parameters for a reservoir."""
    return {
        "name": name,
        "labware_type": LabwareType.RESERVOIR.value,
        "location": location,
        "position": position
    }

