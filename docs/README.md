# PyFluent Documentation

PyFluent is a Python library for controlling Tecan Fluent liquid handling robots using the VisionX .NET API. It provides both a direct API for Tecan operations and full PyLabRobot compatibility.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Direct API Usage](#direct-api-usage)
5. [PyLabRobot Integration](#pylabrobot-integration)
6. [Worklists](#worklists)
7. [Backend API Reference](#backend-api-reference)
8. [Examples](#examples)

## Overview

PyFluent provides two ways to control Tecan Fluent:

1. **Direct API** - Simple, Pythonic interface for Tecan-specific operations
2. **PyLabRobot Backend** - Full compatibility with PyLabRobot's `LiquidHandler` for cross-platform protocols

### Key Features

✅ **Direct .NET API Integration** - Uses Tecan's native VisionX .NET API (same as C# SiLA2 server)  
✅ **PyLabRobot Compatible** - Works as a backend for PyLabRobot's `LiquidHandler`  
✅ **Worklist Generation** - Create Tecan GWL/CSV worklists programmatically  
✅ **Multi-channel Support** - Handle different volumes and wells per channel  
✅ **Easy to Use** - Simple API similar to PyLabRobot  

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Python Code                     │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
               │                          │
    ┌──────────▼──────────┐    ┌─────────▼──────────┐
    │   Direct API        │    │  PyLabRobot       │
    │   (Simple)          │    │  LiquidHandler    │
    └──────────┬──────────┘    └─────────┬──────────┘
               │                          │
               │                          │
    ┌──────────▼──────────────────────────▼──────────┐
    │         FluentVisionX Backend                   │
    │  (Implements LiquidHandlerBackend interface)    │
    └──────────┬──────────────────────────────────────┘
               │
               │ Python.NET (clr)
               │
    ┌──────────▼──────────────────────────────────────┐
    │      Tecan.VisionX.API.V2.dll (.NET API)        │
    └──────────┬──────────────────────────────────────┘
               │
               │
    ┌──────────▼──────────────────────────────────────┐
    │         FluentControl Application                │
    │         (Tecan's Control Software)              │
    └─────────────────────────────────────────────────┘
```

### Components

- **`FluentVisionX`** - Main backend class that connects to FluentControl
- **`Worklist`** - Generate Tecan GWL/CSV worklist files
- **`Protocol`** - Build protocols programmatically
- **`FluentDeck`** - Manage deck layout and labware
- **`MethodManager`** - Manage FluentControl methods

## Quick Start

### Installation

```bash
pip install pythonnet  # Required for .NET API access
```

### Basic Example (Direct API)

```python
import asyncio
from pyfluent.backends.fluent_visionx import FluentVisionX

async def main():
    # Create backend
    backend = FluentVisionX(simulation_mode=False)
    
    # Connect
    await backend.setup()
    
    # Run a method (must have API Channel action)
    await backend.run_method("demo")
    await backend.wait_for_channel(timeout=60)
    
    # Get tips
    backend.get_tips(
        diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul"
    )
    
    # Aspirate
    backend.aspirate_volume(
        volumes=50,
        labware="96 Well Flat[002]",
        liquid_class="Water Test No Detect",
        well_offsets=0  # Well A1
    )
    
    # Dispense
    backend.dispense_volume(
        volumes=50,
        labware="96 Well Flat[001]",
        liquid_class="Water Test No Detect",
        well_offsets=0
    )
    
    # Drop tips
    backend.drop_tips_to_location(
        labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2"
    )
    
    # Cleanup
    await backend.stop()

asyncio.run(main())
```

## Direct API Usage

The direct API provides simple methods for controlling Tecan Fluent without PyLabRobot.

### Connection and Setup

```python
from pyfluent.backends.fluent_visionx import FluentVisionX

backend = FluentVisionX(
    num_channels=8,
    simulation_mode=False  # Set to True for simulation
)

await backend.setup()  # Connect to FluentControl
```

### Methods

```python
# Get available methods
methods = backend.get_available_methods()

# Prepare a method
backend.prepare_method("MyMethod")

# Run a method (opens API channel)
await backend.run_method("MyMethod")
await backend.wait_for_channel(timeout=60)
```

### Tip Operations

```python
# Get tips (pick up from nest)
backend.get_tips(
    diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
    tip_indices=[0, 1, 2, 3, 4, 5, 6, 7]  # All 8 tips, or None for all
)

# Drop tips
backend.drop_tips_to_location(
    labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2"
)
```

### Liquid Handling

#### Single Channel

```python
# Aspirate
backend.aspirate_volume(
    volumes=50,  # Single volume
    labware="96 Well Flat[002]",
    liquid_class="Water Test No Detect",
    well_offsets=0  # Well A1
)

# Dispense
backend.dispense_volume(
    volumes=50,
    labware="96 Well Flat[001]",
    liquid_class="Water Test No Detect",
    well_offsets=0
)
```

#### Multi-Channel with Different Volumes and Wells

```python
# Aspirate from different wells with different volumes
backend.aspirate_volume(
    volumes=[50, 100, 75, 25, 150, 80, 60, 40],  # Different volumes per tip
    labware="96 Well Flat[002]",
    liquid_class="Water Test No Detect",
    well_offsets=[0, 1, 2, 3, 4, 5, 6, 7],  # Wells A1-A8
    tip_indices=[0, 1, 2, 3, 4, 5, 6, 7]  # All 8 tips
)

# Dispense to different wells
backend.dispense_volume(
    volumes=[50, 100, 75, 25, 150, 80, 60, 40],
    labware="96 Well Flat[001]",
    liquid_class="Water Test No Detect",
    well_offsets=[0, 1, 2, 3, 4, 5, 6, 7]
)
```

### Labware Management

```python
# Add labware to worktable
backend.add_labware(
    labware_name="SourcePlate[001]",
    labware_type="96 Well Flat",
    target_location="FCA DiTi Nest[004]",
    position=0,
    rotation=0,
    has_lid=False,
    barcode=""
)

# Remove labware
backend.remove_labware("SourcePlate[001]")

# Transfer labware (robot gripper)
backend.transfer_labware(
    labware_name="SourcePlate[001]",
    target_location="Nest61mm_Pos",
    target_position=1
)
```

## PyLabRobot Integration

PyFluent implements PyLabRobot's `LiquidHandlerBackend` interface, so you can use it with PyLabRobot's `LiquidHandler`:

```python
from pylabrobot.liquid_handling import LiquidHandler
from pyfluent import FluentVisionX
from pylabrobot.resources import Plate, TipRack

# Create backend
backend = FluentVisionX(num_channels=8)

# Create liquid handler
lh = LiquidHandler(backend=backend)

# Setup
await lh.setup()

# Define resources
tip_rack = TipRack("tip_rack", size_x=127.76, size_y=85.48)
source_plate = Plate("source", size_x=127.76, size_y=85.48)
dest_plate = Plate("dest", size_x=127.76, size_y=85.48)

# Load resources
await lh.assign_child_resource(tip_rack, rails=1)
await lh.assign_child_resource(source_plate, rails=2)
await lh.assign_child_resource(dest_plate, rails=3)

# Perform operations
await lh.pick_up_tips(tip_rack["A1"])
await lh.aspirate(source_plate["A1"], vols=100)
await lh.dispense(dest_plate["A1"], vols=100)
await lh.drop_tips(tip_rack["A1"])

# Cleanup
await lh.stop()
```

### How It Works

When you call PyLabRobot methods like `aspirate()` or `dispense()`, they are converted to Tecan commands:

1. PyLabRobot's `LiquidHandler` calls backend methods like `aspirate(ops, use_channels)`
2. `FluentVisionX` converts these to Tecan XML commands
3. Commands are sent via the API execution channel
4. FluentControl executes the commands on the robot

## Worklists

PyFluent supports worklists in two ways:

### Current Status

- ✅ **Direct Execution** - PyLabRobot operations execute directly via API (real-time)
- ✅ **Worklist File Generation** - Create Tecan GWL/CSV files programmatically
- ⚠️ **PyLabRobot → Worklist Conversion** - Not yet automatically implemented

**Note:** PyLabRobot operations currently execute directly via the API channel. To generate worklist files, use the `Worklist` or `Protocol` classes.

### 1. Direct Worklist Generation

Create Tecan GWL/CSV files programmatically:

```python
from pyfluent import Worklist

# Create worklist
wl = Worklist("MyProtocol", liquid_class="Water Test No Detect")

# Add operations
wl.aspirate("SourcePlate", "A1", 100)
wl.dispense("DestPlate", "A1", 100)
wl.aspirate("SourcePlate", "B1", 100)
wl.dispense("DestPlate", "B1", 100)

# Save as GWL (Tecan format)
wl.save("C:/Worklists/my_protocol.gwl", format=WorklistFormat.GWL)

# Or save as CSV
wl.save("C:/Worklists/my_protocol.csv", format=WorklistFormat.CSV)
```

### 2. Protocol to Worklist Conversion

Convert `Protocol` objects to worklists:

```python
from pyfluent import Protocol

# Create protocol
protocol = Protocol("MyProtocol")
protocol.get_tips()
protocol.aspirate("SourcePlate", "A1", 100)
protocol.dispense("DestPlate", "A1", 100)
protocol.drop_tips()

# Export as worklist
protocol.save_worklist("my_protocol.csv")
```

### 3. PyLabRobot Operations to Worklist

**NEW!** You can now convert PyLabRobot-style operations to worklist files:

```python
from pyfluent.worklist_converter import OperationRecord, convert_operations_to_worklist

# Define operations like PyLabRobot
operations = [
    OperationRecord(operation_type="pickup"),
    OperationRecord(
        operation_type="aspirate",
        resource=source_plate,
        well="A1",
        volume=100.0
    ),
    OperationRecord(
        operation_type="dispense",
        resource=dest_plate,
        well="A1",
        volume=100.0
    ),
    OperationRecord(operation_type="drop"),
]

# Convert to worklist
wl = convert_operations_to_worklist(operations, name="MyProtocol")
wl.save("my_protocol.gwl")
```

**Also Available:**
- Convert PyLabRobot operation objects directly
- Use `WorklistRecorder` to record operations
- See `examples/pylabrobot_to_worklist.py` for complete examples

See `docs/worklists.md` for detailed information about worklists.

## Backend API Reference

### FluentVisionX Class

#### Constructor

```python
FluentVisionX(
    num_channels: int = 8,
    simulation_mode: bool = False,
    with_visualization: bool = False,
    with_tracking: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None
)
```

#### Connection Methods

- `async setup()` - Connect to FluentControl and initialize
- `async stop()` - Disconnect and cleanup
- `async wait_for_channel(timeout=60)` - Wait for API execution channel to open

#### Method Management

- `get_available_methods()` - Get list of available methods
- `prepare_method(method_name)` - Prepare a method for execution
- `async run_method(method_name, parameters=None)` - Run a method

#### Tip Operations

- `get_tips(diti_type, airgap_volume=10, airgap_speed=70, tip_indices=None)` - Pick up tips
- `drop_tips_to_location(labware, tip_indices=None)` - Drop tips to waste

#### Liquid Handling

- `aspirate_volume(volumes, labware, liquid_class, well_offsets=None, tip_indices=None)` - Aspirate liquid
- `dispense_volume(volumes, labware, liquid_class, well_offsets=None, tip_indices=None)` - Dispense liquid

#### Labware Management

- `add_labware(labware_name, labware_type, target_location, position=0, rotation=0, has_lid=False, barcode="")` - Add labware
- `remove_labware(labware_name)` - Remove labware
- `transfer_labware(labware_name, target_location, target_position=0)` - Move labware with gripper

#### PyLabRobot Interface

- `async aspirate(ops, use_channels)` - PyLabRobot aspirate
- `async dispense(ops, use_channels)` - PyLabRobot dispense
- `async pick_up_tips(ops, use_channels)` - PyLabRobot pick up tips
- `async drop_tips(ops, use_channels)` - PyLabRobot drop tips

## Examples

See the `examples/` directory for complete examples:

- `simple_pyfluent_usage.py` - Basic direct API usage
- `simple_csv_runner.py` - Run protocols from CSV files
- `pylabrobot_to_worklist.py` - Convert PyLabRobot operations to worklists

## Requirements

- **Windows** - Required for .NET API access
- **Tecan VisionX/FluentControl** - Must be installed
- **pythonnet** - `pip install pythonnet`
- **pylabrobot** - `pip install pylabrobot` (for PyLabRobot integration)

## Troubleshooting

### "Could not find Tecan.VisionX.API.V2.dll"

- Ensure Tecan VisionX/FluentControl is installed
- Check that the DLL is in the expected location
- The backend searches multiple common paths automatically

### "No execution channel available"

- Make sure you've run a method with an "API Channel" action
- Wait for the channel to open: `await backend.wait_for_channel()`
- Check that the method is actually running in FluentControl

### "Method aborted"

- Check the method configuration in TouchTools
- Ensure the worktable is correctly configured
- Verify labware names match exactly (case-sensitive)

### Robot doesn't move

- Check that you're not in simulation mode
- Verify the XML command format is correct
- Ensure liquid class names match your FluentControl setup
- Check that labware names match exactly

## Architecture Details

### XML Commands

PyFluent sends commands to FluentControl as XML strings wrapped in `GenericCommand`. The XML format matches what Tecan's internal scripting uses:

- `LihaGetTipsScriptCommandDataV3` - Get tips
- `LihaAspirateScriptCommandDataV5` - Aspirate
- `LihaDispenseScriptCommandDataV6` - Dispense
- `LihaDropTipsScriptCommandDataV1` - Drop tips

These XML structures are generated in `pyfluent/backends/xml_commands.py`.

### Event Handling

The backend subscribes to .NET events:

- `RuntimeIsAvailable` - Fires when runtime is ready
- `ChannelOpens` - Fires when API execution channel opens
- `ModeChanged` - Fires when FluentControl mode changes

### State Management

FluentControl has several states:
- `EditMode` - Ready to prepare/run methods
- `RunModeRunning` - Method is executing
- `RunModePreparingRecovery` - Recovering from error

The backend tracks these states and waits appropriately.

## License

See LICENSE file.

## Support

For issues or questions, please check:
1. The examples in `examples/`
2. The API reference above
3. Tecan VisionX documentation

