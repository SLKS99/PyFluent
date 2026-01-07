"""
Example: Convert PyLabRobot-style operations to Tecan worklist.

This shows how to define operations like PyLabRobot and convert them
to Tecan worklist files (GWL/CSV format).
"""

from pyfluent.worklist_converter import (
    OperationRecord,
    convert_operations_to_worklist,
    convert_pylabrobot_operations,
    WorklistRecorder,
)
from pyfluent import WorklistFormat
from pylabrobot.resources import Plate, TipRack, Well


def example_1_simple_operations():
    """Example 1: Define operations like PyLabRobot and convert to worklist."""
    print("=" * 60)
    print("Example 1: Simple Operations to Worklist")
    print("=" * 60)
    
    # Define operations (PyLabRobot style)
    # In real usage, these would come from your protocol
    operations = [
        OperationRecord(
            operation_type="pickup",
            comment="Pick up tips from tip rack"
        ),
        OperationRecord(
            operation_type="aspirate",
            resource=None,  # Would be actual resource in real code
            well="A1",
            volume=100.0,
            liquid_class="Water Test No Detect"
        ),
        OperationRecord(
            operation_type="dispense",
            resource=None,
            well="A1",
            volume=100.0,
            liquid_class="Water Test No Detect"
        ),
        OperationRecord(
            operation_type="drop",
            comment="Drop tips to waste"
        ),
    ]
    
    # Convert to worklist
    wl = convert_operations_to_worklist(
        operations,
        name="SimpleTransfer",
        liquid_class="Water Test No Detect"
    )
    
    # Save worklist
    wl.save("simple_transfer.gwl", format=WorklistFormat.GWL)
    print("\n✓ Saved worklist to: simple_transfer.gwl")
    
    # Print summary
    wl.print_summary()


def example_2_with_resources():
    """Example 2: Using actual PyLabRobot resources."""
    print("\n" + "=" * 60)
    print("Example 2: With PyLabRobot Resources")
    print("=" * 60)
    
    # Create resources (PyLabRobot style)
    tip_rack = TipRack("tip_rack", size_x=127.76, size_y=85.48)
    source_plate = Plate("source_plate", size_x=127.76, size_y=85.48)
    dest_plate = Plate("dest_plate", size_x=127.76, size_y=85.48)
    
    # Define operations using resources
    operations = [
        OperationRecord(
            operation_type="pickup",
            resource=tip_rack,
            well="A1"
        ),
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
        OperationRecord(
            operation_type="aspirate",
            resource=source_plate,
            well="B1",
            volume=150.0,
            liquid_class="Water Test No Detect"
        ),
        OperationRecord(
            operation_type="dispense",
            resource=dest_plate,
            well="B1",
            volume=150.0,
            liquid_class="Water Test No Detect"
        ),
        OperationRecord(
            operation_type="drop",
            resource=None  # Waste location
        ),
    ]
    
    # Convert to worklist
    wl = convert_operations_to_worklist(
        operations,
        name="PlateTransfer",
        liquid_class="Water Test No Detect"
    )
    
    # Save worklist
    wl.save("plate_transfer.gwl", format=WorklistFormat.GWL)
    print("\n✓ Saved worklist to: plate_transfer.gwl")
    
    # Print operations
    wl.print_operations()


def example_3_pylabrobot_operations():
    """Example 3: Convert PyLabRobot operation objects directly."""
    print("\n" + "=" * 60)
    print("Example 3: PyLabRobot Operation Objects")
    print("=" * 60)
    
    from pylabrobot.liquid_handling.standard import Aspiration, Dispense, Pickup, Drop
    
    # Create resources
    source_plate = Plate("source", size_x=127.76, size_y=85.48)
    dest_plate = Plate("dest", size_x=127.76, size_y=85.48)
    
    # Create PyLabRobot operations
    # Note: In real usage, these would come from LiquidHandler calls
    aspirations = [
        Aspiration(resource=source_plate["A1"], volume=100),
        Aspiration(resource=source_plate["B1"], volume=150),
    ]
    
    dispenses = [
        Dispense(resource=dest_plate["A1"], volume=100),
        Dispense(resource=dest_plate["B1"], volume=150),
    ]
    
    # Convert to worklist
    wl = convert_pylabrobot_operations(
        aspirations=aspirations,
        dispenses=dispenses,
        name="PyLabRobotProtocol",
        liquid_class="Water Test No Detect"
    )
    
    # Save worklist
    wl.save("pylabrobot_protocol.gwl", format=WorklistFormat.GWL)
    print("\n✓ Saved worklist to: pylabrobot_protocol.gwl")
    
    # Print summary
    wl.print_summary()


def example_4_worklist_recorder():
    """Example 4: Using WorklistRecorder to record operations."""
    print("\n" + "=" * 60)
    print("Example 4: WorklistRecorder")
    print("=" * 60)
    
    # Create resources
    tip_rack = TipRack("tip_rack", size_x=127.76, size_y=85.48)
    source_plate = Plate("source", size_x=127.76, size_y=85.48)
    dest_plate = Plate("dest", size_x=127.76, size_y=85.48)
    
    # Use recorder to build worklist
    with WorklistRecorder("RecordedProtocol") as recorder:
        # Record operations (like PyLabRobot calls)
        recorder.record_pickup(tip_rack, well="A1")
        recorder.record_aspirate(source_plate, well="A1", volume=100)
        recorder.record_dispense(dest_plate, well="A1", volume=100)
        recorder.record_aspirate(source_plate, well="B1", volume=150)
        recorder.record_dispense(dest_plate, well="B1", volume=150)
        recorder.record_drop(None)  # Waste
    
    # Get worklist
    wl = recorder.get_worklist()
    
    # Save worklist
    wl.save("recorded_protocol.gwl", format=WorklistFormat.GWL)
    print("\n✓ Saved worklist to: recorded_protocol.gwl")
    
    # Print operations
    wl.print_operations()


def example_5_multi_channel():
    """Example 5: Multi-channel operations."""
    print("\n" + "=" * 60)
    print("Example 5: Multi-Channel Operations")
    print("=" * 60)
    
    source_plate = Plate("source", size_x=127.76, size_y=85.48)
    dest_plate = Plate("dest", size_x=127.76, size_y=85.48)
    
    # Multi-channel: aspirate from A1-A8, dispense to A1-A8
    operations = [
        OperationRecord(operation_type="pickup"),
    ]
    
    # Add 8-channel operations
    for i in range(8):
        row = chr(ord('A') + i)
        well = f"{row}1"
        operations.append(OperationRecord(
            operation_type="aspirate",
            resource=source_plate,
            well=well,
            volume=100.0 - (i * 5),  # Different volumes
            liquid_class="Water Test No Detect"
        ))
        operations.append(OperationRecord(
            operation_type="dispense",
            resource=dest_plate,
            well=well,
            volume=100.0 - (i * 5),
            liquid_class="Water Test No Detect"
        ))
    
    operations.append(OperationRecord(operation_type="drop"))
    
    # Convert to worklist
    wl = convert_operations_to_worklist(
        operations,
        name="MultiChannelTransfer",
        liquid_class="Water Test No Detect"
    )
    
    # Save worklist
    wl.save("multichannel_transfer.gwl", format=WorklistFormat.GWL)
    print("\n✓ Saved worklist to: multichannel_transfer.gwl")
    
    # Print summary
    wl.print_summary()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PyLabRobot to Worklist Conversion Examples")
    print("=" * 60)
    
    # Run examples
    example_1_simple_operations()
    example_2_with_resources()
    example_3_pylabrobot_operations()
    example_4_worklist_recorder()
    example_5_multi_channel()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print("\nGenerated worklist files:")
    print("  - simple_transfer.gwl")
    print("  - plate_transfer.gwl")
    print("  - pylabrobot_protocol.gwl")
    print("  - recorded_protocol.gwl")
    print("  - multichannel_transfer.gwl")
    print("\nYou can now use these worklist files in FluentControl methods!")

