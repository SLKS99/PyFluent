"""
Test to pick up tips and aspirate from a well plate in simulation mode.

This test will:
1. Connect to FluentControl in simulation mode
2. Start the API channel method
3. Pick up tips
4. Aspirate from a well plate
"""

import sys
import os

if not hasattr(sys, 'coinit_flags'):
    sys.coinit_flags = 0

try:
    import comtypes.client
except ImportError:
    pass

import asyncio
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyfluent.backends.fluent_visionx import FluentVisionX
from pyfluent.backends.inspector import print_configuration_summary

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
LOG = logging.getLogger("TipsAndAspirateTest")


async def main():
    LOG.info("=" * 60)
    LOG.info("Tips and Aspirate Test")
    LOG.info("=" * 60)
    LOG.info("This test will:")
    LOG.info("  1. Connect to FluentControl in simulation mode")
    LOG.info("  2. Show available labware and liquid classes")
    LOG.info("  3. Start method 'demo' (or use existing running method)")
    LOG.info("  4. Wait for API channel")
    LOG.info("  5. Pick up tips (get_tips)")
    LOG.info("  6. Aspirate 50µL from well A1 of a 96-well plate")
    LOG.info("  7. Dispense 50µL to well A2 of the same plate")
    LOG.info("=" * 60)
    LOG.info("")
    
    backend = FluentVisionX(num_channels=8, simulation_mode=True, with_visualization=False)
    
    try:
        # Connect
        LOG.info("1. Connecting to FluentControl...")
        await backend.setup()
        LOG.info("✓ Connected\n")
        
        # Show available configuration
        LOG.info("2. Checking available configuration...")
        print_configuration_summary(backend)
        LOG.info("")
        
        # Show 3D viewer
        LOG.info("3. Showing 3D viewer...")
        backend.show_3d_viewer()
        backend.enable_animation(True)
        backend.set_simulation_speed(1.0)
        LOG.info("✓ 3D viewer enabled\n")
        
        # Run method (or use existing)
        LOG.info("4. Starting/running method 'demo'...")
        success = await backend.run_method("demo", wait_for_completion=False)
        LOG.info(f"   RunMethod result: {success}\n")
        
        # Wait for channel
        LOG.info("5. Waiting for API channel...")
        channel_ready = await backend.wait_for_channel(timeout=90)
        if channel_ready:
            LOG.info("✓ API channel is ready!\n")
        else:
            LOG.error("✗ API channel did not open")
            return
        
        # Wait a moment for everything to be ready
        await asyncio.sleep(2)
        
        # Test get_tips
        LOG.info("6. Picking up tips...")
        LOG.info("   (You should see the pipette move to pick up tips in the 3D viewer)")
        try:
            backend.get_tips()
            LOG.info("✓ get_tips() command executed successfully!")
            # Wait for movement to complete in simulation
            await asyncio.sleep(3)
        except Exception as e:
            LOG.error(f"✗ get_tips() failed: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Test aspirate from well plate
        LOG.info("")
        LOG.info("6. Aspirating 50µL from well A1 of a 96-well plate...")
        LOG.info("   (You should see the pipette move to the plate and aspirate)")
        LOG.info("")
        LOG.info("   NOTE: The labware name must match exactly what's in FluentControl worktable.")
        LOG.info("   If you get a 'Select a valid labware' error, check FluentControl worktable")
        LOG.info("   for the exact labware name and update the script.")
        LOG.info("")
        
        # Labware names must match exactly what's in FluentControl worktable
        # Check the configuration summary above for available labware names
        source_labware = "96 Well Flat[001]"  # Source plate for aspirate
        dest_labware = "96 Well Flat[001]"  # Destination plate for dispense (can be same or different)
        
        # Try liquid classes: "DMSO Free Single_1", "Empty Tip", and "Ethanol Free single"
        liquid_classes_to_try = ["DMSO Free Single_1", "Empty Tip", "Ethanol Free single"]
        aspirate_success = False
        working_liquid_class = None
        
        for liquid_class in liquid_classes_to_try:
            try:
                LOG.info(f"   Trying liquid class: '{liquid_class}'...")
                backend.aspirate_volume(
                    volumes=[50],  # 50µL
                    labware=source_labware,
                    liquid_class=liquid_class,
                    well_offsets=[0],  # Well A1 (offset 0)
                    tip_indices=[0]  # Use tip 0 (first tip)
                )
                LOG.info(f"✓ aspirate_volume() succeeded with liquid class '{liquid_class}'!")
                aspirate_success = True
                working_liquid_class = liquid_class  # Save the working liquid class
                # Wait for movement to complete in simulation
                await asyncio.sleep(3)
                break
            except Exception as e:
                LOG.warning(f"✗ Liquid class '{liquid_class}' failed: {e}")
                if liquid_class != liquid_classes_to_try[-1]:
                    LOG.info(f"   Trying next liquid class...")
                    await asyncio.sleep(1)  # Brief pause between attempts
        
        if not aspirate_success:
            LOG.error("✗ aspirate_volume() failed with all liquid classes tried")
            LOG.error("")
            LOG.error("Tried liquid classes:")
            for lc in liquid_classes_to_try:
                LOG.error(f"  - '{lc}'")
            LOG.error("")
            LOG.error("If you get a 'Liquid subclass missing' error:")
            LOG.error("  1. Open FluentControl")
            LOG.error("  2. Go to Liquid Classes (or check your method's liquid class settings)")
            LOG.error("  3. Find the liquid class name for 'FCA DiTi 200µl' tips")
            LOG.error("  4. Update 'liquid_classes_to_try' list in this script to match")
            LOG.error("")
            LOG.error("If you get a 'Select a valid labware' error:")
            LOG.error("  1. Check the labware name in FluentControl worktable")
            LOG.error("  2. Update 'source_labware' or 'dest_labware' in this script to match exactly")
            import traceback
            traceback.print_exc()
            return
        
        # Test dispense to another well
        if aspirate_success:
            LOG.info("")
            LOG.info("8. Dispensing 50µL to well A2 (offset 1) of the same plate...")
            LOG.info("   (You should see the pipette move to A2 and dispense)")
            
            try:
                # Use the same liquid class that worked for aspirate
                if working_liquid_class:
                    liquid_class = working_liquid_class
                else:
                    # Fallback to the first one in the list (DMSO Free Single_1)
                    liquid_class = "DMSO Free Single_1"
                
                backend.dispense_volume(
                    volumes=[50],  # 50µL
                    labware=dest_labware,
                    liquid_class=liquid_class,
                    well_offsets=[1],  # Well A2 (offset 1)
                    tip_indices=[0]  # Use tip 0 (first tip)
                )
                LOG.info(f"✓ dispense_volume() succeeded with liquid class '{liquid_class}'!")
                # Wait for movement to complete in simulation
                await asyncio.sleep(3)
            except Exception as e:
                LOG.error(f"✗ dispense_volume() failed: {e}")
                import traceback
                traceback.print_exc()
        
        LOG.info("")
        LOG.info("=" * 60)
        LOG.info("Test complete!")
        LOG.info("=" * 60)
        LOG.info("If you saw movement in the 3D viewer:")
        LOG.info("  - Pipette moving to pick up tips")
        LOG.info("  - Pipette moving to well plate and aspirating from A1")
        LOG.info("  - Pipette moving to well A2 and dispensing")
        LOG.info("Then PyFluent is working correctly in simulation mode!")
        LOG.info("")
        LOG.info("You can now try more complex protocols with multiple wells, transfers, etc.")
        
        # Keep running for a bit so user can see the result
        LOG.info("Waiting 5 seconds before closing...")
        await asyncio.sleep(5)
        
    except Exception as e:
        LOG.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if backend:
            try:
                await backend.stop()
            except:
                pass


if __name__ == "__main__":
    asyncio.run(main())

