# PyFluent Architecture

This document explains how PyFluent works internally.

## Overview

PyFluent connects Python to Tecan FluentControl using:
1. **Python.NET (pythonnet)** - Bridges Python and .NET
2. **Tecan.VisionX.API.V2.dll** - Tecan's .NET API
3. **FluentControl Application** - Tecan's control software

## Connection Flow

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

## Key Components

### 1. FluentVisionX Backend

The main backend class that:
- Manages connection to FluentControl
- Converts Python operations to Tecan commands
- Handles events from FluentControl
- Implements PyLabRobot's `LiquidHandlerBackend` interface

### 2. XML Command Generation

Commands are sent as XML strings wrapped in `GenericCommand`:

```python
from Tecan.VisionX.API.V2.Commands import GenericCommand
from pyfluent.backends.xml_commands import make_aspirate_xml

xml = make_aspirate_xml(
    labware="96 Well Flat[002]",
    volumes=[50, 100, 75],
    liquid_class="Water Test No Detect",
    well_offsets=[0, 1, 2]
)
command = GenericCommand(xml)
channel.ExecuteCommand(command)
```

The XML format matches Tecan's internal scripting format:
- `LihaGetTipsScriptCommandDataV3`
- `LihaAspirateScriptCommandDataV5`
- `LihaDispenseScriptCommandDataV6`
- `LihaDropTipsScriptCommandDataV1`

### 3. Event Handling

The backend subscribes to .NET events:

```python
# Runtime is available
self.fluent_control.RuntimeIsAvailable += on_runtime_available

# API channel opens
self.runtime.ChannelOpens += on_channel_opens

# Mode changes
self.runtime.ModeChanged += on_mode_changed
```

Events are handled using Python.NET's `AddEventHandler`.

### 4. Execution Channel

Commands are sent through an "API Execution Channel":

1. Run a method with an "API Channel" action
2. Wait for `ChannelOpens` event
3. Get `IExecutionChannel` object
4. Send commands via `channel.ExecuteCommand()`

```python
# Wait for channel
await backend.wait_for_channel(timeout=60)

# Send command
channel = backend._get_execution_channel()
channel.ExecuteCommand(command)
```

## Command Execution Flow

### Direct API Call

```python
backend.aspirate_volume(volumes=50, labware="Plate[001]", ...)
```

**Flow:**
1. `aspirate_volume()` called
2. Generate XML using `make_aspirate_xml()`
3. Create `GenericCommand(xml)`
4. Get execution channel
5. `channel.ExecuteCommand(command)`
6. FluentControl executes on robot

### PyLabRobot Call

```python
await lh.aspirate(plate["A1"], vols=100)
```

**Flow:**
1. PyLabRobot's `LiquidHandler.aspirate()` called
2. Creates `Aspiration` operation objects
3. Calls `backend.aspirate(ops, use_channels)`
4. Backend converts to Tecan format (same as direct API)
5. Execute via API channel

## State Management

FluentControl has several states:

- `EditMode` - Ready to prepare/run methods
- `RunModeRunning` - Method executing
- `RunModePreparingRecovery` - Recovering from error
- `RunModePaused` - Method paused

The backend tracks state and waits appropriately:

```python
# Wait for EditMode before preparing method
await backend._wait_for_state("EditMode")

# Wait for API channel after running method
await backend.wait_for_channel()
```

## Multi-Channel Support

The backend supports different volumes and wells per channel:

```python
backend.aspirate_volume(
    volumes=[50, 100, 75, 25],  # Different volume per tip
    labware="Plate[001]",
    well_offsets=[0, 1, 2, 3],  # Different well per tip
    tip_indices=[0, 1, 2, 3]    # Which tips to use
)
```

This generates XML with:
- Multiple `<Volumes>` entries
- `SerializedWellIndexes` with all well offsets
- `SelectedWellsString` with well names
- `SelectedTipsIndexes` with tip indices

## Error Handling

Errors can occur at multiple levels:

1. **Connection Errors** - Can't connect to FluentControl
2. **Method Errors** - Method fails to prepare/run
3. **Command Errors** - Command execution fails
4. **Robot Errors** - Physical errors (tip not found, etc.)

The backend:
- Catches exceptions and converts to `TecanError`
- Logs errors with context
- Provides helpful error messages

## Threading and Async

- **Connection** - Uses `asyncio.run_in_executor()` for blocking .NET calls
- **Events** - Handled in .NET thread, stored in Python
- **Commands** - Executed synchronously (blocking)
- **State Checks** - Polled with `asyncio.sleep()`

## File Locations

- **DLL**: Searches multiple paths for `Tecan.VisionX.API.V2.dll`
- **Worktables**: `C:\ProgramData\Tecan\VisionX\DataBase\SystemSpecific\Worktable\`
- **Methods**: Stored in FluentControl's method database
- **Worklists**: User-specified paths (typically `C:\Worklists\`)

## Security Considerations

- No authentication required for local FluentControl
- Commands execute with FluentControl's permissions
- File operations use standard Windows permissions
- No network exposure (local only)

## Performance

- **Command Latency**: ~100-500ms per command
- **Connection Time**: ~2-5 seconds
- **Method Startup**: ~5-10 seconds
- **XML Generation**: <1ms

Bottlenecks:
- Robot movement (physical)
- FluentControl processing
- .NET interop overhead

## Limitations

1. **Windows Only** - Requires .NET runtime
2. **Local Only** - No remote connection
3. **Single Instance** - One connection per FluentControl
4. **Method Required** - Need method with API channel
5. **Worktable Dependency** - Labware must exist in method's worktable

## Future Enhancements

Possible improvements:
- Remote connection support
- Worklist conversion from PyLabRobot operations
- Better error recovery
- Parallel command execution
- Command queuing

