# PyFluent Quick Reference

Fast reference for common PyFluent operations.

---

## Connection

```python
from pyfluent import FluentVisionX

# Production
backend = FluentVisionX()
backend.connect()

# Simulation
backend = FluentVisionX(simulation_mode=True)
backend.connect()

# Disconnect
backend.disconnect()
```

---

## FCA (8-Channel) - Direct API

### Tips
```python
backend.get_tips()                                    # Get all 8 tips
backend.get_tips(tip_indices=[0,1,2,3])              # Get 4 tips
backend.drop_tips_to_location("FCA Thru Deck Waste Chute_1")
```

### Liquid Handling
```python
# Single channel
backend.aspirate_volume(100, "Plate_1", well_offsets=0)
backend.dispense_volume(100, "Plate_1", well_offsets=0)

# All 8 channels, same well
backend.aspirate_volume([100]*8, "Plate_1", well_offsets=0)

# Multiple channels, different wells (A1-D1)
backend.aspirate_volume(
    volumes=[100,100,100,100],
    labware="Plate_1",
    well_offsets=[0,1,2,3],
    tip_indices=[0,1,2,3]
)
```

### Movement
```python
backend.fca_move_to_position("Plate_1", well_offset=0)
backend.fca_move_to_safe_position()
```

---

## MCA (96-Channel) - Direct API

```python
# Tips
backend.mca_get_tips()
backend.mca_drop_tips()

# Liquid handling (all 96 channels, same volume)
backend.mca_aspirate("Plate_1", volume=50)
backend.mca_dispense("Plate_1", volume=50)

# Movement
backend.mca_move_to_safe_position()
```

---

## RGA (Gripper) - Direct API

```python
# Pick and place
backend.rga_get_labware("Plate_1", grip_force=5)
backend.rga_put_labware("Plate_1", "Hotel_Slot_1")

# Combined transfer
backend.rga_transfer_labware("Plate_1", "Hotel_Slot_1")

# Movement
backend.rga_move_to_safe_position()
backend.move_all_arms_to_safe_position()  # All arms
```

---

## PyLabRobot Interface

```python
from pylabrobot.liquid_handling import LiquidHandler
from pyfluent import FluentVisionX

backend = FluentVisionX(simulation_mode=True)
lh = LiquidHandler(backend=backend)
await lh.setup()

# Tips
await lh.pick_up_tips(tip_rack["tips"]["A1:H1"])
await lh.drop_tips(tip_rack["tips"]["A1:H1"])

# Liquid handling
await lh.aspirate(plate["A1:H1"], vols=100)
await lh.dispense(plate["A1:H1"], vols=100)

# Cleanup
await lh.stop()
```

---

## Protocol Builder

```python
from pyfluent import Protocol

protocol = Protocol("MyProtocol", backend=backend)

# Build protocol
protocol.get_tips()
protocol.aspirate("Plate_1", "A1", 100)
protocol.dispense("Plate_2", "A1", 100)
protocol.drop_tips()

# Or use transfer
protocol.transfer(
    source_labware="Plate_1",
    source_well="A1",
    dest_labware="Plate_2",
    dest_well="A1",
    volume=100
)

# Execute
import asyncio
asyncio.run(protocol.execute())
```

---

## Worklist Generation

```python
from pyfluent import Worklist

wl = Worklist("MyWorklist")

# Add operations
wl.break_tips()                                      # Get tips
wl.aspirate("Plate_1", "A1", 100.0)
wl.dispense("Plate_2", "A1", 100.0)

# Or use transfer
wl.transfer("Plate_1", "A1", "Plate_2", "A1", 100.0)

# Save
wl.save("worklist.gwl")
```

---

## Well Conversion

```python
from pyfluent import well_name_to_offset, offset_to_well_name

# Name to offset (0-based, column-major)
well_name_to_offset("A1")   # 0
well_name_to_offset("B1")   # 1
well_name_to_offset("A2")   # 8
well_name_to_offset("H12")  # 95

# Offset to name
offset_to_well_name(0)      # "A1"
offset_to_well_name(8)      # "A2"
offset_to_well_name(95)     # "H12"
```

---

## Constants

```python
from pyfluent import (
    DEFAULT_LIQUID_CLASS,           # "Water Free Single"
    DEFAULT_FCA_WASTE,              # "FCA Thru Deck Waste Chute_1"
    DEFAULT_MCA_WASTE,              # "MCA Thru Deck Waste Chute..."
    DEFAULT_DITI_TYPE,              # FCA 200µL tips
    FCA_DEVICE_ALIAS,               # "Instrument=1/Device=LIHA:1"
    MCA_DEVICE_ALIAS,               # "Instrument=1/Device=MCA96:1"
    RGA_DEVICE_ALIAS,               # "Instrument=1/Device=RGA:1"
)
```

---

## Tip Types

```python
from pyfluent.tip_types import FCA, MCA

# FCA (8-channel)
FCA.TIPS_50UL_FILTERED
FCA.TIPS_200UL_FILTERED
FCA.TIPS_1000UL_FILTERED

# MCA (96-channel)
MCA.TIPS_50UL_FILTERED
MCA.TIPS_150UL_FILTERED
```

---

## Common Patterns

### 8-Channel Column Transfer
```python
backend.get_tips()
backend.aspirate_volume([100]*8, "Plate_1", well_offsets=list(range(8)))
backend.dispense_volume([100]*8, "Plate_2", well_offsets=list(range(8)))
backend.drop_tips_to_location(DEFAULT_FCA_WASTE)
```

### 96-Well Plate Replication
```python
backend.mca_get_tips()
backend.mca_aspirate("Plate_1", 50)
backend.mca_dispense("Plate_2", 50)
backend.mca_drop_tips()
```

### Serial Dilution (8-channel)
```python
from pyfluent import well_name_to_offset

backend.get_tips()
for i in range(11):
    src = well_name_to_offset(f"A{i+1}")
    dst = well_name_to_offset(f"A{i+2}")
    backend.aspirate_volume(100, "Plate_1", well_offsets=src)
    backend.dispense_volume(100, "Plate_1", well_offsets=dst)
backend.drop_tips_to_location(DEFAULT_FCA_WASTE)
```

### Multi-Dispense (Reagent Addition)
```python
protocol = Protocol("Reagent Addition")
protocol.get_tips()
protocol.multi_dispense(
    source_labware="Trough_1",
    source_well="A1",
    dest_labware="Plate_1",
    dest_wells=["A1", "A2", "A3", "A4", "A5", "A6"],
    volume=50
)
protocol.drop_tips()
```

### Plate Transfer with Gripper
```python
# Move plate from deck to hotel
backend.rga_transfer_labware("Plate_1", "Hotel_Slot_1")

# Process plate
backend.mca_get_tips()
backend.mca_aspirate("Plate_1", 50)
backend.mca_dispense("Plate_1", 50)
backend.mca_drop_tips()

# Return plate to deck
backend.rga_transfer_labware("Plate_1", "Grid:20/Site:1")
```

---

## Error Handling

```python
from pyfluent import TecanError

try:
    backend.get_tips()
except TecanError as e:
    print(f"Error: {e}")
finally:
    backend.disconnect()
```

---

## Complete Minimal Example

```python
from pyfluent import FluentVisionX

# Setup
backend = FluentVisionX(simulation_mode=True)
backend.connect()

# Protocol
backend.get_tips()
backend.aspirate_volume(100, "Plate_1", well_offsets=0)
backend.dispense_volume(100, "Plate_2", well_offsets=0)
backend.drop_tips_to_location("FCA Thru Deck Waste Chute_1")

# Cleanup
backend.disconnect()
```

---

## Deck Locations

Common deck location formats:
- Grid format: `"Grid:20/Site:1"`
- Hotel slots: `"Hotel_Slot_1"`, `"Hotel_Slot_2"`, etc.
- Carriers: `"MP 3Pos_1"`, `"Trough_Carrier_1"`, etc.

---

## Liquid Classes

Common liquid classes:
- `"Water Free Single"` - Default, no detection
- `"Water Test No Detect"` - Testing without detection
- `"Water Free Multi"` - Multi-dispense
- `"Serum Free Single"` - Serum handling
- `"DMSO Free Single"` - DMSO handling

---

## Tips & Tricks

1. **Always test in simulation first**
2. **Use constants instead of hardcoded strings**
3. **Move arms to safe position before/after operations**
4. **Check `backend.is_connected` before operations**
5. **Use Protocol builder for complex workflows**
6. **Generate worklists for reproducible protocols**
7. **Handle errors with try/except blocks**

---

**See Also**: 
- Full API Guide: `docs/API_METHOD_GUIDE.md`
- Examples: `examples/` directory
- Simulation Guide: `examples/simulation_mode_guide.ipynb`
