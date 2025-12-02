# PyFluent

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PyFluent** is a Python library for controlling Tecan Fluent liquid handling robots. It provides a clean, Pythonic interface to control Tecan Fluent systems through the Tecan VisionX .NET API, with full PyLabRobot compatibility.

## ✨ Features

- ✅ **Direct .NET API Integration** - Uses Tecan's native VisionX .NET API (Tecan.VisionX.API.V2), same as the C# SiLA2 server
- ✅ **Full PyLabRobot Integration** - Works seamlessly with PyLabRobot's universal liquid handling interface
- ✅ **Worklist Generation** - Convert PyLabRobot-style operations to Tecan GWL/CSV worklist files
- ✅ **Multi-Channel Support** - Handle different volumes and wells per channel
- ✅ **Comprehensive Documentation** - Full guides and API reference
- ✅ **Production Ready** - Tested and working with real Tecan Fluent systems

## 🚀 Quick Start

### Installation

```bash
pip install pythonnet  # Required for .NET API access
```

### Basic Usage

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

### PyLabRobot Integration

```python
from pylabrobot.liquid_handling import LiquidHandler
from pyfluent import FluentVisionX
from pylabrobot.resources import Plate, TipRack

# Create backend
backend = FluentVisionX(num_channels=8)
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

### Convert PyLabRobot Operations to Worklists

```python
from pyfluent.worklist_converter import OperationRecord, convert_operations_to_worklist

# Define operations (PyLabRobot style)
operations = [
    OperationRecord(operation_type="pickup"),
    OperationRecord(
        operation_type="aspirate",
        resource=source_plate,
        well="A1",
        volume=100.0,
        liquid_class="Water Test No Detect"
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
wl.save("my_protocol.gwl")  # Save as Tecan GWL format
```

## 📖 Documentation

- **[Full Documentation](docs/README.md)** - Complete guide with examples
- **[Worklists Guide](docs/worklists.md)** - Worklist generation and conversion
- **[Architecture](docs/ARCHITECTURE.md)** - Internal architecture details

## 🎯 Key Features

### Direct API Control

- Start/stop FluentControl
- Prepare and run methods
- Get tips, aspirate, dispense, drop tips
- Multi-channel with different volumes and wells
- Labware management

### PyLabRobot Compatible

- Full `LiquidHandlerBackend` implementation
- Works with PyLabRobot's `LiquidHandler`
- Cross-platform protocol compatibility

### Worklist Generation

- Create Tecan GWL/CSV worklist files
- Convert PyLabRobot operations to worklists
- Batch protocol execution

## 📋 Requirements

- **Windows** - Required for .NET API access
- **Python 3.9+**
- **Tecan VisionX/FluentControl** - Must be installed
- **pythonnet** - `pip install pythonnet`
- **pylabrobot** - `pip install pylabrobot` (for PyLabRobot integration)

## 📦 Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/PyFluent.git
cd PyFluent

# Install in development mode
pip install -e .

# Or install dependencies
pip install -r requirements.txt
```

## 🧪 Examples

See the `examples/` directory for complete examples:

- `simple_pyfluent_usage.py` - Basic direct API usage
- `simple_csv_runner.py` - Run protocols from CSV files
- `pylabrobot_to_worklist.py` - Convert PyLabRobot operations to worklists

## 🏗️ Architecture

PyFluent connects Python to Tecan FluentControl using:

1. **Python.NET (pythonnet)** - Bridges Python and .NET
2. **Tecan.VisionX.API.V2.dll** - Tecan's .NET API
3. **FluentControl Application** - Tecan's control software

```
Python Code
    ↓
FluentVisionX Backend
    ↓ (Python.NET / clr)
Tecan.VisionX.API.V2.dll (.NET)
    ↓
FluentControl Application
    ↓
Robot Hardware
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed information.

## 🧩 Components

- **`FluentVisionX`** - Main backend class
- **`Worklist`** - Generate Tecan GWL/CSV worklist files
- **`Protocol`** - Build protocols programmatically
- **`FluentDeck`** - Manage deck layout and labware
- **`MethodManager`** - Manage FluentControl methods
- **`WorklistConverter`** - Convert PyLabRobot operations to worklists

## 🔧 Troubleshooting

### "Could not find Tecan.VisionX.API.V2.dll"

- Ensure Tecan VisionX/FluentControl is installed
- Check that the DLL is in the expected location
- The backend searches multiple common paths automatically

### "No execution channel available"

- Make sure you've run a method with an "API Channel" action
- Wait for the channel to open: `await backend.wait_for_channel()`
- Check that the method is actually running in FluentControl

### Robot doesn't move

- Check that you're not in simulation mode
- Verify liquid class names match your FluentControl setup
- Ensure labware names match exactly (case-sensitive)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on top of [PyLabRobot](https://github.com/pylabrobot/pylabrobot)
- Uses Tecan's VisionX .NET API (Tecan.VisionX.API.V2) - same as the C# SiLA2 server

## 📞 Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/YOUR_USERNAME/PyFluent/issues)
- **Documentation**: See `docs/` directory for detailed guides

---

**Made with ❤️ for the lab automation community**
