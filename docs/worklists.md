# Worklists in PyFluent

PyFluent supports worklists in two ways:

1. **Direct Execution** - Commands sent via API channel (real-time)
2. **Worklist Files** - Generate GWL/CSV files for batch execution

## Direct Execution (Current PyLabRobot Approach)

When using PyLabRobot's `LiquidHandler` with PyFluent, operations are executed **directly** via the API channel:

```python
from pylabrobot.liquid_handling import LiquidHandler
from pyfluent import FluentVisionX

backend = FluentVisionX()
lh = LiquidHandler(backend=backend)
await lh.setup()

# These execute immediately via API channel
await lh.pick_up_tips(tip_rack["A1"])
await lh.aspirate(plate["A1"], vols=100)
await lh.dispense(plate["A2"], vols=100)
await lh.drop_tips(tip_rack["A1"])
```

**How it works:**
1. PyLabRobot calls backend methods (`aspirate()`, `dispense()`, etc.)
2. Backend converts to Tecan XML commands
3. Commands sent via API execution channel
4. FluentControl executes immediately

**Advantages:**
- Real-time execution
- Can check status between operations
- Can handle errors immediately
- No file I/O needed

## Worklist Files (Tecan GWL/CSV Format)

For batch execution or when you want to generate a worklist file:

### Creating Worklists

```python
from pyfluent import Worklist, WorklistFormat

# Create worklist
wl = Worklist("MyProtocol", liquid_class="Water Test No Detect")

# Add operations
wl.aspirate("SourcePlate", "A1", 100)
wl.dispense("DestPlate", "A1", 100)
wl.aspirate("SourcePlate", "B1", 100)
wl.dispense("DestPlate", "B1", 100)

# Save as GWL (Tecan's native format)
wl.save("my_protocol.gwl", format=WorklistFormat.GWL)

# Or save as CSV
wl.save("my_protocol.csv", format=WorklistFormat.CSV)
```

### Using Worklists

1. Generate the worklist file in Python
2. Run a FluentControl method that reads the worklist
3. The method executes all operations from the file

**Advantages:**
- Can review/edit worklist before execution
- Can reuse worklists
- Good for batch operations
- Can be edited in TouchTools

## Converting PyLabRobot Operations to Worklists

Currently, **direct conversion from PyLabRobot operations to worklists is not automatically implemented**. However, you can:

### Option 1: Use Protocol Class

Build your protocol using the `Protocol` class, which can export to worklists:

```python
from pyfluent import Protocol

protocol = Protocol("MyProtocol")
protocol.get_tips()
protocol.aspirate("SourcePlate", "A1", 100)
protocol.dispense("DestPlate", "A1", 100)
protocol.drop_tips()

# Export to worklist
protocol.save_worklist("my_protocol.csv")
```

### Option 2: Manual Conversion

If you have PyLabRobot operations, manually convert them:

```python
from pyfluent import Worklist

wl = Worklist("ConvertedProtocol")

# Convert PyLabRobot operations to worklist
# PyLabRobot: await lh.aspirate(plate["A1"], vols=100)
wl.aspirate("plate", "A1", 100)

# PyLabRobot: await lh.dispense(plate["A2"], vols=100)
wl.dispense("plate", "A2", 100)

wl.save("converted.gwl")
```

### Option 3: Future Enhancement

A helper function could be added to automatically convert PyLabRobot operations to worklists. This would:

1. Capture PyLabRobot operations
2. Convert to `WorklistOperation` objects
3. Generate GWL/CSV file

**Would you like this feature?** It would require:
- Intercepting PyLabRobot operations
- Converting resource names to labware names
- Mapping well coordinates to Tecan positions

## Worklist Format Details

### GWL Format (Tecan Native)

```
C;Worklist: MyProtocol
C;Created: 2024-01-15 10:30:00
C;Operations: 4
C;
A;SourcePlate;;;1;;100.0;Water Test No Detect;;0;
D;DestPlate;;;1;;100.0;Water Test No Detect;;0;
A;SourcePlate;;;2;;100.0;Water Test No Detect;;0;
D;DestPlate;;;2;;100.0;Water Test No Detect;;0;
```

### CSV Format (Simple)

```csv
Command,RackLabel,Position,Volume,LiquidClass,Comment
A,SourcePlate,1,100.0,Water Test No Detect,
D,DestPlate,1,100.0,Water Test No Detect,
A,SourcePlate,2,100.0,Water Test No Detect,
D,DestPlate,2,100.0,Water Test No Detect,
```

## Well Position Conversion

Tecan uses **column-major ordering** for well positions:

- A1 = position 1
- B1 = position 2
- C1 = position 3
- ...
- H1 = position 8
- A2 = position 9
- B2 = position 10
- ...

The `Worklist` class handles this conversion automatically:

```python
wl.aspirate("Plate", "A1", 100)  # Automatically converts to position 1
wl.aspirate("Plate", "B2", 100)  # Automatically converts to position 10
```

## Converting PyLabRobot Operations to Worklists

PyFluent now includes a converter that lets you define operations like PyLabRobot and convert them to worklist files!

### Method 1: Using OperationRecord

Define operations in a PyLabRobot-like style:

```python
from pyfluent.worklist_converter import OperationRecord, convert_operations_to_worklist

# Define operations (like PyLabRobot)
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
        volume=100.0,
        liquid_class="Water Test No Detect"
    ),
    OperationRecord(operation_type="drop"),
]

# Convert to worklist
wl = convert_operations_to_worklist(operations, name="MyProtocol")
wl.save("my_protocol.gwl")
```

### Method 2: Using PyLabRobot Operation Objects

Convert PyLabRobot operation objects directly:

```python
from pyfluent.worklist_converter import convert_pylabrobot_operations
from pylabrobot.liquid_handling.standard import Aspiration, Dispense

# Create PyLabRobot operations
aspirations = [Aspiration(resource=source_plate["A1"], volume=100)]
dispenses = [Dispense(resource=dest_plate["A1"], volume=100)]

# Convert to worklist
wl = convert_pylabrobot_operations(
    aspirations=aspirations,
    dispenses=dispenses,
    name="MyProtocol"
)
wl.save("my_protocol.gwl")
```

### Method 3: Using WorklistRecorder

Record operations as you define them:

```python
from pyfluent.worklist_converter import WorklistRecorder

with WorklistRecorder("MyProtocol") as recorder:
    recorder.record_pickup(tip_rack, well="A1")
    recorder.record_aspirate(source_plate, well="A1", volume=100)
    recorder.record_dispense(dest_plate, well="A1", volume=100)
    recorder.record_drop(None)

wl = recorder.get_worklist()
wl.save("my_protocol.gwl")
```

See `examples/pylabrobot_to_worklist.py` for complete examples!

## Summary

| Approach | Execution | Format | Use Case |
|----------|-----------|--------|----------|
| **Direct API** | Real-time | XML commands | Interactive control, PyLabRobot |
| **Worklist Files** | Batch | GWL/CSV | Batch operations, reusable protocols |
| **PyLabRobot → Worklist** | Convert | GWL/CSV | Convert PyLabRobot operations to worklists |

**Current Status:**
- ✅ Direct execution via API (works with PyLabRobot)
- ✅ Worklist file generation (Tecan format)
- ✅ PyLabRobot → Worklist conversion (NEW!)

You can now define operations like PyLabRobot and convert them to Tecan worklist files!

