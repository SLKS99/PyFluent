# PyFluent API Method Guide

Complete guide for using PyFluent with both direct API and PyLabRobot interface.

---

## Table of Contents

1. [Connection & Setup](#connection--setup)
2. [Direct API Methods](#direct-api-methods)
   - [FCA (8-Channel) Operations](#fca-8-channel-operations)
   - [MCA (96-Channel) Operations](#mca-96-channel-operations)
   - [RGA (Gripper) Operations](#rga-gripper-operations)
   - [Deck Management](#deck-management)
3. [PyLabRobot Interface](#pylabrobot-interface)
4. [Protocol Builder](#protocol-builder)
5. [Worklist Generation](#worklist-generation)
6. [Constants Reference](#constants-reference)

---

## Connection & Setup

### Basic Connection

```python
from pyfluent import FluentVisionX

# Connect to FluentControl
backend = FluentVisionX()
backend.connect()

# Check connection
print(f"Connected: {backend.is_connected}")
print(f"Simulation mode: {backend.simulation_mode}")
```

### Simulation Mode

```python
# Connect in simulation mode (no hardware required)
backend = FluentVisionX(simulation_mode=True)
backend.connect()

# Or enable simulation after connection
backend.enable_simulation()
backend.disable_simulation()
```

### Disconnect

```python
backend.disconnect()
```

---

## Direct API Methods

The direct API provides low-level control with exact XML command generation.

### FCA (8-Channel) Operations

#### Get Tips

```python
# Get tips with all 8 channels
backend.get_tips()

# Get tips with specific channels
backend.get_tips(tip_indices=[0, 1, 2, 3])  # First 4 channels

# Custom tip type
backend.get_tips(
    diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul Filtered SBS",
    airgap_volume=10,
    airgap_speed=70
)
```

#### Drop Tips

```python
# Drop tips to default waste
backend.drop_tips_to_location("FCA Thru Deck Waste Chute_1")

# Drop specific channels
backend.drop_tips_to_location(
    "FCA Thru Deck Waste Chute_1",
    tip_indices=[0, 1, 2, 3]
)
```

#### Aspirate

```python
# Single volume, single well
backend.aspirate_volume(
    volumes=100,
    labware="SourcePlate_1",
    liquid_class="Water Free Single",
    well_offsets=0  # A1 (0-based)
)

# Multiple channels, same well
backend.aspirate_volume(
    volumes=[100, 100, 100, 100, 100, 100, 100, 100],
    labware="SourcePlate_1",
    well_offsets=0
)

# Multiple channels, different wells
backend.aspirate_volume(
    volumes=[100, 100, 100, 100],
    labware="SourcePlate_1",
    well_offsets=[0, 1, 2, 3],  # A1, B1, C1, D1
    tip_indices=[0, 1, 2, 3]
)

# Using well name conversion
from pyfluent import well_name_to_offset

well_offset = well_name_to_offset("A1")  # Returns 0
backend.aspirate_volume(100, "SourcePlate_1", well_offsets=well_offset)
```

#### Dispense

```python
# Single volume
backend.dispense_volume(
    volumes=100,
    labware="DestPlate_1",
    liquid_class="Water Free Single",
    well_offsets=0
)

# Multiple channels
backend.dispense_volume(
    volumes=[100, 100, 100, 100],
    labware="DestPlate_1",
    well_offsets=[0, 1, 2, 3],
    tip_indices=[0, 1, 2, 3]
)
```

#### Movement

```python
# Move FCA to specific position
backend.fca_move_to_position(
    labware="SourcePlate_1",
    well_offset=0,
    z_position=150.0  # mm above deck (optional)
)

# Move FCA to safe/home position
backend.fca_move_to_safe_position()
```

---

### MCA (96-Channel) Operations

#### Get Tips

```python
# Get tips with MCA (all 96 channels)
backend.mca_get_tips()

# Custom MCA tip type
backend.mca_get_tips(
    diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 150ul Filtered SBS",
    airgap_volume=10,
    airgap_speed=70
)
```

#### Drop Tips

```python
# Drop MCA tips
backend.mca_drop_tips()

# Drop to specific waste location
backend.mca_drop_tips("MCA Thru Deck Waste Chute with Tip Drop Guide_2")
```

#### Aspirate (96 Channels)

```python
# Aspirate with all 96 channels (same volume for all)
backend.mca_aspirate(
    labware="SourcePlate_1",
    volume=50,  # µL per channel
    liquid_class="Water Free Single",
    well_offset=0  # Starting well (typically 0 for full plate)
)
```

#### Dispense (96 Channels)

```python
# Dispense with all 96 channels
backend.mca_dispense(
    labware="DestPlate_1",
    volume=50,
    liquid_class="Water Free Single",
    well_offset=0
)
```

#### Movement

```python
# Move MCA to safe position
backend.mca_move_to_safe_position()
```

---

### RGA (Gripper) Operations

#### Pick Up Labware

```python
# Pick up labware with default grip force
backend.rga_get_labware("MyPlate_1")

# Custom grip force (1-10 scale)
backend.rga_get_labware(
    labware="MyPlate_1",
    grip_force=7,  # Stronger grip
    grip_width=85.48  # mm (optional, auto-detect if None)
)
```

#### Place Labware

```python
# Place labware at target location
backend.rga_put_labware(
    labware="MyPlate_1",
    target_location="Hotel_Slot_1"
)
```

#### Transfer Labware (Combined)

```python
# Complete pick-and-place operation
backend.rga_transfer_labware(
    labware="MyPlate_1",
    target_location="Hotel_Slot_2",
    grip_force=5
)
```

#### Movement

```python
# Move gripper to safe position
backend.rga_move_to_safe_position()

# Move all arms to safe positions
backend.move_all_arms_to_safe_position()
```

---

### Deck Management

#### Add Labware

```python
# Add labware to deck
backend.add_labware(
    labware_name="SourcePlate_1",
    labware_type="96 Well Microplate",
    target_location="Grid:20/Site:1",
    position=0,
    rotation=0,
    has_lid=False,
    barcode=""
)
```

#### Transfer Labware (Robot Movement)

```python
# Transfer labware using robot gripper
backend.transfer_labware(
    labware_name="SourcePlate_1",
    target_location="Grid:21/Site:1",
    target_position=0
)
```

#### Remove Labware

```python
# Remove labware from deck
backend.remove_labware("SourcePlate_1")
```

---

## PyLabRobot Interface

PyFluent can be used as a PyLabRobot backend for compatibility with PyLabRobot scripts.

### Setup with PyLabRobot

```python
from pylabrobot.liquid_handling import LiquidHandler
from pyfluent import FluentVisionX

# Create backend
backend = FluentVisionX(simulation_mode=True)

# Create liquid handler
lh = LiquidHandler(backend=backend, deck=None)

# Setup
await lh.setup()
```

### Define Resources

```python
from pylabrobot.resources import (
    TIP_CAR_480_A00,
    PLT_CAR_L5AC_A00,
    Cos_96_DW_1mL,
    HTF_L
)

# Add tip rack
tip_rack = TIP_CAR_480_A00(name="tip_rack")
tip_rack[0] = HTF_L(name="tips")
lh.deck.assign_child_resource(tip_rack, rails=1)

# Add plate carrier
plate_carrier = PLT_CAR_L5AC_A00(name="plate_carrier")
plate_carrier[0] = Cos_96_DW_1mL(name="source_plate")
plate_carrier[1] = Cos_96_DW_1mL(name="dest_plate")
lh.deck.assign_child_resource(plate_carrier, rails=10)
```

### Pick Up Tips

```python
# Pick up tips from specific wells
await lh.pick_up_tips(tip_rack["tips"]["A1:H1"])

# Pick up with specific channels
await lh.pick_up_tips(
    tip_rack["tips"]["A1:D1"],
    use_channels=[0, 1, 2, 3]
)
```

### Aspirate

```python
# Aspirate from single well
await lh.aspirate(
    plate_carrier["source_plate"]["A1"],
    vols=100
)

# Aspirate from multiple wells
await lh.aspirate(
    plate_carrier["source_plate"]["A1:H1"],
    vols=[100, 100, 100, 100, 100, 100, 100, 100]
)

# With specific channels
await lh.aspirate(
    plate_carrier["source_plate"]["A1:D1"],
    vols=[100, 100, 100, 100],
    use_channels=[0, 1, 2, 3]
)
```

### Dispense

```python
# Dispense to single well
await lh.dispense(
    plate_carrier["dest_plate"]["A1"],
    vols=100
)

# Dispense to multiple wells
await lh.dispense(
    plate_carrier["dest_plate"]["A1:H1"],
    vols=[100, 100, 100, 100, 100, 100, 100, 100]
)
```

### Drop Tips

```python
# Drop tips back to rack
await lh.drop_tips(tip_rack["tips"]["A1:H1"])

# Drop to waste
await lh.drop_tips(tip_rack["tips"]["A1:H1"])
```

### Complete PyLabRobot Example

```python
from pylabrobot.liquid_handling import LiquidHandler
from pyfluent import FluentVisionX
from pylabrobot.resources import *

async def run_protocol():
    # Setup
    backend = FluentVisionX(simulation_mode=True)
    lh = LiquidHandler(backend=backend, deck=None)
    await lh.setup()
    
    # Define deck layout
    tip_rack = TIP_CAR_480_A00(name="tip_rack")
    tip_rack[0] = HTF_L(name="tips")
    lh.deck.assign_child_resource(tip_rack, rails=1)
    
    plate_carrier = PLT_CAR_L5AC_A00(name="plate_carrier")
    plate_carrier[0] = Cos_96_DW_1mL(name="source_plate")
    plate_carrier[1] = Cos_96_DW_1mL(name="dest_plate")
    lh.deck.assign_child_resource(plate_carrier, rails=10)
    
    # Run protocol
    await lh.pick_up_tips(tip_rack["tips"]["A1:H1"])
    await lh.aspirate(plate_carrier["source_plate"]["A1:H1"], vols=100)
    await lh.dispense(plate_carrier["dest_plate"]["A1:H1"], vols=100)
    await lh.drop_tips(tip_rack["tips"]["A1:H1"])
    
    # Cleanup
    await lh.stop()

# Run
import asyncio
asyncio.run(run_protocol())
```

---

## Protocol Builder

High-level protocol building with automatic command sequencing.

### Create Protocol

```python
from pyfluent import Protocol, FluentVisionX

# Create protocol
protocol = Protocol(name="My Transfer Protocol")

# Or with backend for execution
backend = FluentVisionX()
protocol = Protocol(name="My Protocol", backend=backend)
```

### Add Commands

```python
# Get tips
protocol.get_tips()

# Aspirate
protocol.aspirate(
    labware="SourcePlate_1",
    well="A1",
    volume=100,
    liquid_class="Water Free Single"
)

# Dispense
protocol.dispense(
    labware="DestPlate_1",
    well="A1",
    volume=100
)

# Drop tips
protocol.drop_tips()
```

### Transfer Operations

```python
# Single transfer (aspirate + dispense)
protocol.transfer(
    source_labware="SourcePlate_1",
    source_well="A1",
    dest_labware="DestPlate_1",
    dest_well="A1",
    volume=100,
    new_tip=True
)

# Multi-dispense (aspirate once, dispense to multiple wells)
protocol.multi_dispense(
    source_labware="ReagentTrough_1",
    source_well="A1",
    dest_labware="DestPlate_1",
    dest_wells=["A1", "A2", "A3", "A4"],
    volume=50
)
```

### Execute Protocol

```python
import asyncio

# Execute protocol
asyncio.run(protocol.execute())

# Or with specific backend
asyncio.run(protocol.execute(backend=backend))
```

### Protocol Summary

```python
# Print summary
protocol.print_summary()

# Get summary string
summary = protocol.get_summary()

# Print all steps
protocol.print_steps()
```

---

## Worklist Generation

Generate Tecan-compatible worklist files (GWL format).

### Create Worklist

```python
from pyfluent import Worklist

# Create worklist
wl = Worklist(
    name="MyWorklist",
    liquid_class="Water Free Single",
    tip_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul"
)
```

### Add Operations

```python
# Get new tips
wl.break_tips()

# Aspirate
wl.aspirate(
    rack_label="SourcePlate",
    well="A1",  # or position number
    volume=100.0,
    liquid_class="Water Free Single"
)

# Dispense
wl.dispense(
    rack_label="DestPlate",
    well="A1",
    volume=100.0
)

# Transfer (aspirate + dispense)
wl.transfer(
    source_rack="SourcePlate",
    source_well="A1",
    dest_rack="DestPlate",
    dest_well="A1",
    volume=100.0,
    new_tip=True
)

# Multi-dispense
wl.multi_dispense(
    source_rack="ReagentTrough",
    source_well="A1",
    dest_rack="DestPlate",
    dest_wells=["A1", "A2", "A3", "A4"],
    volume_per_well=50.0
)

# Add comment
wl.comment("Starting dilution series")
```

### Save Worklist

```python
# Save as GWL file
wl.save("my_worklist.gwl")

# Save as CSV
wl.save("my_worklist.csv", format="csv")
```

### Convert PyLabRobot to Worklist

```python
from pyfluent import convert_pylabrobot_operations
from pylabrobot.liquid_handling.standard import Aspiration, Dispense

# Create PyLabRobot operations
asp = Aspiration(resource=source_plate["A1"], volume=100)
disp = Dispense(resource=dest_plate["A1"], volume=100)

# Convert to worklist
wl = convert_pylabrobot_operations(
    aspirations=[asp],
    dispenses=[disp],
    name="ConvertedProtocol"
)

wl.save("converted.gwl")
```

---

## Constants Reference

### Import Constants

```python
from pyfluent import (
    # Liquid classes
    DEFAULT_LIQUID_CLASS,
    WATER_TEST_NO_DETECT,
    
    # Waste locations
    DEFAULT_FCA_WASTE,
    DEFAULT_MCA_WASTE,
    
    # Tip types
    DEFAULT_DITI_TYPE,
    DITI_200UL_FILTERED_SBS,
    
    # Device aliases
    FCA_DEVICE_ALIAS,
    MCA_DEVICE_ALIAS,
    RGA_DEVICE_ALIAS,
    
    # Gripper
    DEFAULT_GRIPPER_FINGERS,
    DEFAULT_GRIP_FORCE,
    
    # Speed
    SPEED_SLOW,
    SPEED_MEDIUM,
    SPEED_FAST,
    
    # Plate dimensions
    ROWS_96_WELL,
    COLS_96_WELL,
)
```

### Liquid Classes

```python
DEFAULT_LIQUID_CLASS = "Water Free Single"
WATER_TEST_NO_DETECT = "Water Test No Detect"

# Use in commands
backend.aspirate_volume(100, "Plate_1", liquid_class=DEFAULT_LIQUID_CLASS)
```

### Waste Locations

```python
DEFAULT_FCA_WASTE = "FCA Thru Deck Waste Chute_1"
DEFAULT_MCA_WASTE = "MCA Thru Deck Waste Chute with Tip Drop Guide_2"

# Use in commands
backend.drop_tips_to_location(DEFAULT_FCA_WASTE)
backend.mca_drop_tips(DEFAULT_MCA_WASTE)
```

### Device Aliases

```python
FCA_DEVICE_ALIAS = "Instrument=1/Device=LIHA:1"
MCA_DEVICE_ALIAS = "Instrument=1/Device=MCA96:1"
RGA_DEVICE_ALIAS = "Instrument=1/Device=RGA:1"
```

### Tip Types

```python
# FCA tips
from pyfluent.tip_types import FCA

FCA.TIPS_50UL_FILTERED
FCA.TIPS_200UL_FILTERED
FCA.TIPS_1000UL_FILTERED
FCA.DEFAULT  # 200µL filtered

# MCA tips
from pyfluent.tip_types import MCA

MCA.TIPS_50UL_FILTERED
MCA.TIPS_150UL_FILTERED
MCA.DEFAULT  # 150µL filtered
```

### Well Conversion Utilities

```python
from pyfluent import well_name_to_offset, offset_to_well_name

# Convert well name to 0-based offset (column-major)
offset = well_name_to_offset("A1")  # Returns 0
offset = well_name_to_offset("B1")  # Returns 1
offset = well_name_to_offset("A2")  # Returns 8

# Convert offset back to well name
well = offset_to_well_name(0)   # Returns "A1"
well = offset_to_well_name(8)   # Returns "A2"
well = offset_to_well_name(15)  # Returns "H2"
```

---

## Complete Examples

### Example 1: Simple 8-Channel Transfer

```python
from pyfluent import FluentVisionX, DEFAULT_LIQUID_CLASS

# Connect
backend = FluentVisionX(simulation_mode=True)
backend.connect()

# Get tips
backend.get_tips()

# Aspirate from column 1
backend.aspirate_volume(
    volumes=[100]*8,
    labware="SourcePlate_1",
    liquid_class=DEFAULT_LIQUID_CLASS,
    well_offsets=[0, 1, 2, 3, 4, 5, 6, 7]  # A1-H1
)

# Dispense to column 1
backend.dispense_volume(
    volumes=[100]*8,
    labware="DestPlate_1",
    well_offsets=[0, 1, 2, 3, 4, 5, 6, 7]
)

# Drop tips
backend.drop_tips_to_location("FCA Thru Deck Waste Chute_1")

# Disconnect
backend.disconnect()
```

### Example 2: 96-Channel Plate Replication

```python
from pyfluent import FluentVisionX

backend = FluentVisionX(simulation_mode=True)
backend.connect()

# Get MCA tips
backend.mca_get_tips()

# Aspirate entire plate
backend.mca_aspirate(
    labware="SourcePlate_1",
    volume=50,
    liquid_class="Water Free Single"
)

# Dispense to destination
backend.mca_dispense(
    labware="DestPlate_1",
    volume=50
)

# Drop tips
backend.mca_drop_tips()

backend.disconnect()
```

### Example 3: Plate Movement with Gripper

```python
from pyfluent import FluentVisionX

backend = FluentVisionX(simulation_mode=True)
backend.connect()

# Transfer plate from deck to hotel
backend.rga_transfer_labware(
    labware="MyPlate_1",
    target_location="Hotel_Slot_1",
    grip_force=5
)

# Later, retrieve it
backend.rga_transfer_labware(
    labware="MyPlate_1",
    target_location="Grid:20/Site:1",
    grip_force=5
)

backend.disconnect()
```

### Example 4: Protocol with Multiple Operations

```python
from pyfluent import Protocol, FluentVisionX

# Create protocol
backend = FluentVisionX(simulation_mode=True)
protocol = Protocol("Serial Dilution", backend=backend)

# Build protocol
protocol.get_tips()

# Initial transfer
protocol.transfer(
    source_labware="ReagentTrough_1",
    source_well="A1",
    dest_labware="Plate_1",
    dest_well="A1",
    volume=200,
    new_tip=False
)

# Serial dilution
for i in range(11):
    source_well = f"A{i+1}"
    dest_well = f"A{i+2}"
    protocol.transfer(
        source_labware="Plate_1",
        source_well=source_well,
        dest_labware="Plate_1",
        dest_well=dest_well,
        volume=100,
        new_tip=False
    )

protocol.drop_tips()

# Execute
import asyncio
backend.connect()
asyncio.run(protocol.execute())
backend.disconnect()
```

---

## Error Handling

```python
from pyfluent import FluentVisionX, TecanError

backend = FluentVisionX()

try:
    backend.connect()
    backend.get_tips()
    backend.aspirate_volume(100, "Plate_1")
    
except TecanError as e:
    print(f"Tecan error: {e}")
    print(f"Error code: {e.error_code}")
    
except Exception as e:
    print(f"General error: {e}")
    
finally:
    if backend.is_connected:
        backend.disconnect()
```

---

## Best Practices

1. **Always use simulation mode for testing**
   ```python
   backend = FluentVisionX(simulation_mode=True)
   ```

2. **Use constants for consistency**
   ```python
   from pyfluent import DEFAULT_LIQUID_CLASS, DEFAULT_FCA_WASTE
   ```

3. **Convert well names properly**
   ```python
   from pyfluent import well_name_to_offset
   offset = well_name_to_offset("A1")
   ```

4. **Handle errors gracefully**
   ```python
   try:
       backend.aspirate_volume(...)
   except TecanError as e:
       logger.error(f"Failed: {e}")
   ```

5. **Move arms to safe positions**
   ```python
   backend.move_all_arms_to_safe_position()
   ```

6. **Use Protocol builder for complex workflows**
   ```python
   protocol = Protocol("MyProtocol", backend=backend)
   protocol.transfer(...)
   ```

7. **Generate worklists for reproducibility**
   ```python
   wl = Worklist("MyWorklist")
   wl.transfer(...)
   wl.save("protocol.gwl")
   ```

---

## Additional Resources

- **Examples**: See `examples/` directory for complete working examples
- **API Reference**: See inline documentation with `help(FluentVisionX)`
- **Constants**: Import from `pyfluent.constants`
- **Tip Types**: Import from `pyfluent.tip_types`

---

**Last Updated**: 2026-02-17
**PyFluent Version**: 0.1.0
