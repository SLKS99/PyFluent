"""
Simple PyFluent Usage Example - Easy like PyLabRobot!

This shows how to use PyFluent with simple, easy-to-understand commands.
"""

import asyncio
from pyfluent.backends.fluent_visionx import FluentVisionX


async def main():
    """Simple example of using PyFluent."""
    
    # Create backend (like PyLabRobot)
    backend = FluentVisionX(
        num_channels=8,
        simulation_mode=False  # Set to True for simulation
    )
    
    # Setup (connects to FluentControl)
    print("Connecting to FluentControl...")
    await backend.setup()
    print("Connected!")
    
    # Get available methods
    print("\nAvailable methods:")
    methods = backend.get_available_methods()
    for method in methods:
        print(f"  - {method}")
    
    # Run a method (must have API Channel action)
    # This will prepare and run it, then wait for API channel
    method_name = "demo"  # Change to your method name
    print(f"\nRunning method: {method_name}")
    print("(This will prepare the method and wait for API channel to open)")
    
    # Run the method (prepares it and runs it)
    await backend.run_method(method_name)
    
    # Wait for API channel to open (if not already open)
    print("Waiting for API channel...")
    channel_ready = await backend.wait_for_channel(timeout=60)
    if not channel_ready:
        print("ERROR: API channel did not open!")
        return
    print("API channel ready!")
    
    # Now you can send commands!
    
    # 1. Get tips
    print("\n1. Getting tips...")
    backend.get_tips(
        diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
        tip_indices=[0]  # Just tip 0, or None for all 8
    )
    print("   ✓ Tips picked up!")
    
    # 2. Aspirate (single channel)
    print("\n2. Aspirating 50ul from plate...")
    backend.aspirate_volume(
        volumes=50,  # Single volume
        labware="96 Well Flat[002]",
        liquid_class="Water Test No Detect",
        well_offsets=0  # Well A1
    )
    print("   ✓ Aspirated!")
    
    # 3. Dispense (single channel)
    print("\n3. Dispensing 50ul to plate...")
    backend.dispense_volume(
        volumes=50,
        labware="96 Well Flat[001]",
        liquid_class="Water Test No Detect",
        well_offsets=0
    )
    print("   ✓ Dispensed!")
    
    # 4. Multi-channel with different volumes and wells
    print("\n4. Multi-channel pipetting...")
    backend.aspirate_volume(
        volumes=[50, 100, 75, 25, 150, 80, 60, 40],  # Different volumes
        labware="96 Well Flat[002]",
        liquid_class="Water Test No Detect",
        well_offsets=[0, 1, 2, 3, 4, 5, 6, 7],  # Different wells (A1-A8)
        tip_indices=[0, 1, 2, 3, 4, 5, 6, 7]  # All 8 tips
    )
    print("   ✓ Multi-channel aspirated!")
    
    backend.dispense_volume(
        volumes=[50, 100, 75, 25, 150, 80, 60, 40],
        labware="96 Well Flat[001]",
        liquid_class="Water Test No Detect",
        well_offsets=[0, 1, 2, 3, 4, 5, 6, 7]
    )
    print("   ✓ Multi-channel dispensed!")
    
    # 5. Drop tips
    print("\n5. Dropping tips...")
    backend.drop_tips_to_location(
        labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2"
    )
    print("   ✓ Tips dropped!")
    
    # Stop
    print("Stopping...")
    await backend.stop()
    
    print("\n✓ All done!")


if __name__ == "__main__":
    asyncio.run(main())

