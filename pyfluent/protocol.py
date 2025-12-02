"""
Protocol management for Tecan Fluent.

This module provides classes for creating and executing liquid handling protocols,
including aspirate, dispense, tip handling, and worklist generation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import csv
import io


class CommandType(Enum):
    """Types of protocol commands."""
    ASPIRATE = "aspirate"
    DISPENSE = "dispense"
    GET_TIPS = "get_tips"
    DROP_TIPS = "drop_tips"
    TRANSFER_LABWARE = "transfer_labware"
    ADD_LABWARE = "add_labware"
    REMOVE_LABWARE = "remove_labware"
    USER_PROMPT = "user_prompt"
    SUBROUTINE = "subroutine"
    PAUSE = "pause"


@dataclass
class ProtocolCommand:
    """A single command in a protocol."""
    command_type: CommandType
    parameters: Dict[str, Any] = field(default_factory=dict)
    comment: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.command_type.value,
            "parameters": self.parameters,
            "comment": self.comment
        }


@dataclass
class Transfer:
    """Represents a liquid transfer operation."""
    source_labware: str
    source_well: str
    dest_labware: str
    dest_well: str
    volume: float  # in µL
    liquid_class: str = "Water Free Single"
    
    @property
    def source_well_offset(self) -> int:
        """Get source well as numeric offset."""
        return well_name_to_offset(self.source_well)
    
    @property
    def dest_well_offset(self) -> int:
        """Get destination well as numeric offset."""
        return well_name_to_offset(self.dest_well)


def well_name_to_offset(well_name: str) -> int:
    """
    Convert well name (e.g., 'A1') to 0-based offset.
    Tecan uses column-major ordering: A1=0, B1=1, C1=2, ... A2=8, B2=9, ...
    """
    if not well_name:
        return 0
    
    well_name = well_name.upper().strip()
    
    # Handle numeric offset directly
    if well_name.isdigit():
        return int(well_name)
    
    # Parse letter + number format (e.g., A1, B12)
    row_letter = well_name[0]
    col_num = int(well_name[1:]) - 1  # Convert to 0-based
    row_num = ord(row_letter) - ord('A')
    
    # Column-major ordering (8 rows per column for 96-well)
    return col_num * 8 + row_num


def offset_to_well_name(offset: int, rows: int = 8) -> str:
    """
    Convert 0-based offset to well name (e.g., 0 -> 'A1').
    Assumes column-major ordering.
    """
    col = offset // rows
    row = offset % rows
    row_letter = chr(ord('A') + row)
    return f"{row_letter}{col + 1}"


class Protocol:
    """
    Represents a liquid handling protocol.
    
    A protocol is a sequence of commands that can be executed on the Fluent.
    """
    
    def __init__(self, name: str = "Untitled Protocol", backend=None, deck=None):
        """
        Initialize a protocol.
        
        Args:
            name: Name of the protocol
            backend: FluentVisionX backend for execution
            deck: FluentDeck instance for tracking labware
        """
        self.name = name
        self.backend = backend
        self.deck = deck
        self.commands: List[ProtocolCommand] = []
        self.transfers: List[Transfer] = []
        self.current_tips_loaded = False
        self.liquid_class = "Water Free Single"  # Default liquid class
    
    def set_liquid_class(self, liquid_class: str):
        """Set the default liquid class for transfers."""
        self.liquid_class = liquid_class
    
    # ========================================================================
    # TIP HANDLING
    # ========================================================================
    
    def get_tips(
        self,
        tip_type: str = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul Filtered SBS",
        airgap_volume: int = 10,
        airgap_speed: int = 70
    ):
        """
        Add a get tips command to the protocol.
        
        Args:
            tip_type: DiTi type string
            airgap_volume: Air gap volume in µL
            airgap_speed: Air gap speed
        """
        cmd = ProtocolCommand(
            command_type=CommandType.GET_TIPS,
            parameters={
                "tip_type": tip_type,
                "airgap_volume": airgap_volume,
                "airgap_speed": airgap_speed
            }
        )
        self.commands.append(cmd)
        self.current_tips_loaded = True
        return self
    
    def drop_tips(self, waste_location: str = "FCA Thru Deck Waste Chute_1"):
        """
        Add a drop tips command to the protocol.
        
        Args:
            waste_location: Where to drop the tips
        """
        cmd = ProtocolCommand(
            command_type=CommandType.DROP_TIPS,
            parameters={"waste_location": waste_location}
        )
        self.commands.append(cmd)
        self.current_tips_loaded = False
        return self
    
    # ========================================================================
    # LIQUID HANDLING
    # ========================================================================
    
    def aspirate(
        self,
        labware: str,
        well: str,
        volume: float,
        liquid_class: Optional[str] = None
    ):
        """
        Add an aspirate command to the protocol.
        
        Args:
            labware: Name of the source labware
            well: Well name (e.g., 'A1') or offset
            volume: Volume to aspirate in µL
            liquid_class: Liquid class (uses default if not specified)
        """
        cmd = ProtocolCommand(
            command_type=CommandType.ASPIRATE,
            parameters={
                "labware": labware,
                "well": well,
                "volume": int(volume),
                "liquid_class": liquid_class or self.liquid_class,
                "well_offset": well_name_to_offset(well) if isinstance(well, str) else well
            }
        )
        self.commands.append(cmd)
        return self
    
    def dispense(
        self,
        labware: str,
        well: str,
        volume: float,
        liquid_class: Optional[str] = None
    ):
        """
        Add a dispense command to the protocol.
        
        Args:
            labware: Name of the destination labware
            well: Well name (e.g., 'A1') or offset
            volume: Volume to dispense in µL
            liquid_class: Liquid class (uses default if not specified)
        """
        cmd = ProtocolCommand(
            command_type=CommandType.DISPENSE,
            parameters={
                "labware": labware,
                "well": well,
                "volume": int(volume),
                "liquid_class": liquid_class or self.liquid_class,
                "well_offset": well_name_to_offset(well) if isinstance(well, str) else well
            }
        )
        self.commands.append(cmd)
        return self
    
    def transfer(
        self,
        source_labware: str,
        source_well: str,
        dest_labware: str,
        dest_well: str,
        volume: float,
        liquid_class: Optional[str] = None,
        new_tip: bool = True
    ):
        """
        Add a complete transfer (aspirate + dispense) to the protocol.
        
        Args:
            source_labware: Name of the source labware
            source_well: Source well name
            dest_labware: Name of the destination labware
            dest_well: Destination well name
            volume: Volume to transfer in µL
            liquid_class: Liquid class
            new_tip: Whether to get new tips before transfer
        """
        lc = liquid_class or self.liquid_class
        
        # Get tips if needed
        if new_tip and not self.current_tips_loaded:
            self.get_tips()
        
        # Aspirate
        self.aspirate(source_labware, source_well, volume, lc)
        
        # Dispense
        self.dispense(dest_labware, dest_well, volume, lc)
        
        # Track transfer
        self.transfers.append(Transfer(
            source_labware=source_labware,
            source_well=source_well,
            dest_labware=dest_labware,
            dest_well=dest_well,
            volume=volume,
            liquid_class=lc
        ))
        
        return self
    
    def multi_dispense(
        self,
        source_labware: str,
        source_well: str,
        dest_labware: str,
        dest_wells: List[str],
        volume: float,
        liquid_class: Optional[str] = None
    ):
        """
        Aspirate once and dispense to multiple wells.
        
        Args:
            source_labware: Source labware name
            source_well: Source well
            dest_labware: Destination labware name
            dest_wells: List of destination wells
            volume: Volume per dispense
            liquid_class: Liquid class
        """
        lc = liquid_class or self.liquid_class
        
        # Get tips
        if not self.current_tips_loaded:
            self.get_tips()
        
        # Aspirate total volume
        total_volume = volume * len(dest_wells)
        self.aspirate(source_labware, source_well, total_volume, lc)
        
        # Dispense to each well
        for well in dest_wells:
            self.dispense(dest_labware, well, volume, lc)
            self.transfers.append(Transfer(
                source_labware=source_labware,
                source_well=source_well,
                dest_labware=dest_labware,
                dest_well=well,
                volume=volume,
                liquid_class=lc
            ))
        
        return self
    
    # ========================================================================
    # LABWARE OPERATIONS
    # ========================================================================
    
    def add_labware(
        self,
        name: str,
        labware_type: str,
        location: str,
        position: int = 0
    ):
        """
        Add labware to the deck.
        
        Args:
            name: Labware name
            labware_type: Type of labware
            location: Deck location
            position: Position at location
        """
        cmd = ProtocolCommand(
            command_type=CommandType.ADD_LABWARE,
            parameters={
                "name": name,
                "labware_type": labware_type,
                "location": location,
                "position": position
            }
        )
        self.commands.append(cmd)
        
        # Also add to deck if available
        if self.deck:
            self.deck.add_labware(name, labware_type, location, position, sync_to_fluent=False)
        
        return self
    
    def transfer_labware(
        self,
        labware_name: str,
        target_location: str,
        target_position: int = 0
    ):
        """
        Transfer labware to a new location (robot gripper).
        
        Args:
            labware_name: Name of labware to move
            target_location: Target location
            target_position: Target position
        """
        cmd = ProtocolCommand(
            command_type=CommandType.TRANSFER_LABWARE,
            parameters={
                "labware_name": labware_name,
                "target_location": target_location,
                "target_position": target_position
            }
        )
        self.commands.append(cmd)
        
        # Update deck if available
        if self.deck:
            self.deck.transfer_labware(labware_name, target_location, target_position, sync_to_fluent=False)
        
        return self
    
    # ========================================================================
    # USER INTERACTION
    # ========================================================================
    
    def user_prompt(self, message: str):
        """
        Add a user prompt (pause and show message).
        
        Args:
            message: Message to display to user
        """
        cmd = ProtocolCommand(
            command_type=CommandType.USER_PROMPT,
            parameters={"message": message}
        )
        self.commands.append(cmd)
        return self
    
    def run_subroutine(self, subroutine_name: str):
        """
        Run a subroutine.
        
        Args:
            subroutine_name: Name of subroutine to run
        """
        cmd = ProtocolCommand(
            command_type=CommandType.SUBROUTINE,
            parameters={"subroutine_name": subroutine_name}
        )
        self.commands.append(cmd)
        return self
    
    # ========================================================================
    # EXECUTION
    # ========================================================================
    
    async def execute(self, backend=None):
        """
        Execute the protocol on the Fluent.
        
        Args:
            backend: FluentVisionX backend (uses self.backend if not provided)
        """
        be = backend or self.backend
        if not be:
            raise RuntimeError("No backend available. Provide a backend or set self.backend")
        
        print(f"Executing protocol: {self.name}")
        print(f"Total commands: {len(self.commands)}")
        print("-" * 40)
        
        for i, cmd in enumerate(self.commands):
            print(f"Step {i+1}/{len(self.commands)}: {cmd.command_type.value}")
            
            try:
                if cmd.command_type == CommandType.GET_TIPS:
                    be.get_tips(
                        airgap_volume=cmd.parameters.get("airgap_volume", 10),
                        airgap_speed=cmd.parameters.get("airgap_speed", 70),
                        diti_type=cmd.parameters.get("tip_type", "")
                    )
                
                elif cmd.command_type == CommandType.DROP_TIPS:
                    be.drop_tips_to_location(cmd.parameters.get("waste_location", ""))
                
                elif cmd.command_type == CommandType.ASPIRATE:
                    be.aspirate_volume(
                        volume=cmd.parameters["volume"],
                        labware=cmd.parameters["labware"],
                        liquid_class=cmd.parameters["liquid_class"],
                        well_offset=cmd.parameters.get("well_offset", 0)
                    )
                
                elif cmd.command_type == CommandType.DISPENSE:
                    be.dispense_volume(
                        volume=cmd.parameters["volume"],
                        labware=cmd.parameters["labware"],
                        liquid_class=cmd.parameters["liquid_class"],
                        well_offset=cmd.parameters.get("well_offset", 0)
                    )
                
                elif cmd.command_type == CommandType.ADD_LABWARE:
                    be.add_labware(
                        labware_name=cmd.parameters["name"],
                        labware_type=cmd.parameters["labware_type"],
                        target_location=cmd.parameters["location"],
                        position=cmd.parameters.get("position", 0),
                        rotation=cmd.parameters.get("rotation", 0),
                        has_lid=cmd.parameters.get("has_lid", False),
                        barcode=cmd.parameters.get("barcode", "")
                    )
                
                elif cmd.command_type == CommandType.TRANSFER_LABWARE:
                    be.transfer_labware(
                        labware_name=cmd.parameters["labware_name"],
                        target_location=cmd.parameters["target_location"],
                        target_position=cmd.parameters.get("target_position", 0)
                    )
                
                elif cmd.command_type == CommandType.USER_PROMPT:
                    be.user_prompt(cmd.parameters["message"])
                
                elif cmd.command_type == CommandType.SUBROUTINE:
                    be.run_subroutine(cmd.parameters["subroutine_name"])
                
                print(f"  [OK]")
                
            except Exception as e:
                print(f"  [ERROR] {e}")
                raise
        
        print("-" * 40)
        print(f"Protocol complete!")
    
    # ========================================================================
    # WORKLIST / CSV EXPORT
    # ========================================================================
    
    def to_worklist_csv(self) -> str:
        """
        Export protocol as a worklist CSV.
        
        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(["Command", "Labware", "Well", "Volume", "LiquidClass", "Extra"])
        
        for cmd in self.commands:
            if cmd.command_type == CommandType.ASPIRATE:
                writer.writerow([
                    "A",  # Aspirate
                    cmd.parameters["labware"],
                    cmd.parameters["well"],
                    cmd.parameters["volume"],
                    cmd.parameters["liquid_class"],
                    ""
                ])
            elif cmd.command_type == CommandType.DISPENSE:
                writer.writerow([
                    "D",  # Dispense
                    cmd.parameters["labware"],
                    cmd.parameters["well"],
                    cmd.parameters["volume"],
                    cmd.parameters["liquid_class"],
                    ""
                ])
            elif cmd.command_type == CommandType.GET_TIPS:
                writer.writerow(["G", "", "", "", "", cmd.parameters.get("tip_type", "")])
            elif cmd.command_type == CommandType.DROP_TIPS:
                writer.writerow(["DROP", cmd.parameters.get("waste_location", ""), "", "", "", ""])
        
        return output.getvalue()
    
    def save_worklist(self, filepath: str):
        """Save protocol as a worklist CSV file."""
        with open(filepath, 'w', newline='') as f:
            f.write(self.to_worklist_csv())
        print(f"Saved worklist to: {filepath}")
    
    def get_summary(self) -> str:
        """
        Get a summary of the protocol.
        
        Returns:
            Summary string
        """
        lines = []
        lines.append(f"Protocol: {self.name}")
        lines.append("=" * 40)
        lines.append(f"Total commands: {len(self.commands)}")
        lines.append(f"Total transfers: {len(self.transfers)}")
        
        # Count by command type
        counts = {}
        for cmd in self.commands:
            counts[cmd.command_type.value] = counts.get(cmd.command_type.value, 0) + 1
        
        lines.append("\nCommands by type:")
        for cmd_type, count in sorted(counts.items()):
            lines.append(f"  {cmd_type}: {count}")
        
        # Calculate total volume
        if self.transfers:
            total_volume = sum(t.volume for t in self.transfers)
            lines.append(f"\nTotal volume transferred: {total_volume:.1f} µL")
        
        return "\n".join(lines)
    
    def print_summary(self):
        """Print protocol summary."""
        print(self.get_summary())
    
    def print_steps(self):
        """Print all protocol steps."""
        print(f"\nProtocol: {self.name}")
        print("=" * 50)
        for i, cmd in enumerate(self.commands):
            params = ", ".join(f"{k}={v}" for k, v in cmd.parameters.items())
            print(f"{i+1:3d}. {cmd.command_type.value}: {params}")
        print("=" * 50)

