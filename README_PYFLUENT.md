# PyFluent - Easy Tecan Fluent Control

PyFluent provides a simple, PyLabRobot-like interface for controlling Tecan Fluent liquid handlers using the VisionX .NET API.

## Quick Start

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
    
    # Aspirate (single channel)
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
    
    # Multi-channel with different volumes and wells
    backend.aspirate_volume(
        volumes=[50, 100, 75, 25, 150, 80, 60, 40],  # Different volumes
        labware="96 Well Flat[002]",
        liquid_class="Water Test No Detect",
        well_offsets=[0, 1, 2, 3, 4, 5, 6, 7],  # Wells A1-A8
        tip_indices=[0, 1, 2, 3, 4, 5, 6, 7]  # All 8 tips
    )
    
    # Drop tips
    backend.drop_tips_to_location(
        labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2"
    )
    
    # Cleanup
    backend.finish_execution()
    await backend.stop()

asyncio.run(main())
```

## Key Features

✅ **Get Tips** - Pick up tips from nests  
✅ **Aspirate** - Single or multi-channel with different volumes and wells  
✅ **Dispense** - Single or multi-channel with different volumes and wells  
✅ **Drop Tips** - Drop tips to waste  
✅ **Start/Stop** - Control FluentControl  
✅ **Methods** - Prepare and run methods  
✅ **Easy API** - Simple, PyLabRobot-like interface  

## Main Methods

### Setup and Control

- `await backend.setup()` - Connect to FluentControl
- `await backend.stop()` - Disconnect
- `backend.get_available_methods()` - List available methods
- `backend.prepare_method(name)` - Prepare a method
- `await backend.run_method(name)` - Run a method
- `await backend.wait_for_channel(timeout=60)` - Wait for API channel

### Pipetting

- `backend.get_tips(diti_type, tip_indices=None)` - Get tips
- `backend.aspirate_volume(volumes, labware, liquid_class, well_offsets=None, tip_indices=None)` - Aspirate
- `backend.dispense_volume(volumes, labware, liquid_class, well_offsets=None, tip_indices=None)` - Dispense
- `backend.drop_tips_to_location(labware, tip_indices=None)` - Drop tips

### Parameters

- `volumes`: Single `int` or `List[int]` for multi-channel
- `well_offsets`: Single `int` or `List[int]` (0=A1, 1=A2, 12=B1, etc.)
- `tip_indices`: `List[int]` of tip indices (0-7), or `None` for all
- `liquid_class`: Liquid class name (e.g., "Water Test No Detect")

## Examples

See `examples/simple_pyfluent_usage.py` for a complete example.

