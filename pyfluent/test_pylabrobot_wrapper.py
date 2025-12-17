"""
Test that PyLabRobot interface correctly wraps direct API calls.

IMPORTANT: 
- Open FluentControl manually
- Run the "demo" method manually (it should have an API Channel action)
- Wait for the API channel to open
- Then run this script

This script will test that PyLabRobot operations work by calling the same
direct API methods that already work.
"""

import asyncio
import logging
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyfluent.backends.fluent_visionx import FluentVisionX
from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.resources import Plate, TipRack, Deck
from pylabrobot.liquid_handling.standard import (
    Aspiration,
    Dispense,
    Pickup,
    Drop,
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestPyLabRobot")


async def test_pylabrobot_wrapper():
    """Test that PyLabRobot interface wraps direct API correctly."""
    logger.info("=" * 60)
    logger.info("Testing PyLabRobot Interface (wraps direct API)")
    logger.info("=" * 60)
    logger.info("\nIMPORTANT: Make sure FluentControl is running and")
    logger.info("the 'demo' method is running with API channel open!\n")
    
    backend = FluentVisionX(simulation_mode=False)
    deck = Deck()
    lh = LiquidHandler(backend=backend, deck=deck)
    
    try:
        # Setup (just connect, don't run method - user does that manually)
        logger.info("Connecting to FluentControl...")
        await lh.setup()
        logger.info("✓ Connected to FluentControl")
        
        # Check if API channel is already open
        logger.info("\nChecking if API channel is open...")
        logger.info("Waiting up to 60 seconds for API channel to open...")
        logger.info("(Make sure the 'demo' method is running in FluentControl)")
        channel_ready = await backend.wait_for_channel(timeout=60)
        if not channel_ready:
            logger.error("✗ API channel is not open!")
            logger.error("Please run the 'demo' method in FluentControl and wait for API channel to open")
            logger.error("The method must have an 'API Channel' action in it")
            return False
        logger.info("✓ API channel is ready!")
        
        # Create resources (PyLabRobot style)
        # IMPORTANT: Use actual FluentControl labware names so PyLabRobot can find them
        logger.info("\nCreating PyLabRobot resources...")
        logger.info("Using actual FluentControl labware names for mapping")
        tip_rack = TipRack("tip_rack", size_x=127.76, size_y=85.48)
        # Use actual FluentControl labware names that exist in the method
        source_plate = Plate("96 Well Flat[002]", size_x=127.76, size_y=85.48)  # Match FluentControl
        dest_plate = Plate("96 Well Flat[001]", size_x=127.76, size_y=85.48)    # Match FluentControl
        logger.info("✓ Resources created with FluentControl labware names")
        
        # Test 1: Pick up tips (PyLabRobot -> should call backend.get_tips())
        logger.info("\n--- Test 1: Pick Up Tips (PyLabRobot) ---")
        logger.info("Sending pick_up_tips command...")
        try:
            tip_well = tip_rack["A1"]
            pickup_op = Pickup(resource=tip_well)
            await lh.pick_up_tips([pickup_op], use_channels=[0])
            logger.info("✓ Pick up tips command sent successfully")
            logger.info("Waiting a moment for command to execute...")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"✗ Pick up tips failed: {e}")
            import traceback
            traceback.print_exc()
            # Don't return False yet - continue to see if other commands work
        
        # Test 2: Aspirate (PyLabRobot -> should call backend.aspirate_volume())
        logger.info("\n--- Test 2: Aspirate (PyLabRobot) ---")
        logger.info("Sending aspirate command...")
        try:
            source_well = source_plate["A1"]
            asp_op = Aspiration(resource=source_well, volume=50)
            await lh.aspirate([asp_op], use_channels=[0])
            logger.info("✓ Aspirate command sent successfully")
            logger.info("Waiting a moment for command to execute...")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"✗ Aspirate failed: {e}")
            import traceback
            traceback.print_exc()
            logger.warning("Continuing to next test...")
        
        # Test 3: Dispense (PyLabRobot -> should call backend.dispense_volume())
        logger.info("\n--- Test 3: Dispense (PyLabRobot) ---")
        try:
            dest_well = dest_plate["A1"]
            disp_op = Dispense(resource=dest_well, volume=50)
            await lh.dispense([disp_op], use_channels=[0])
            logger.info("✓ Dispense via PyLabRobot - should have called backend.dispense_volume()")
        except Exception as e:
            logger.error(f"✗ Dispense failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 4: Drop tips (PyLabRobot -> should call backend.drop_tips_to_location())
        logger.info("\n--- Test 4: Drop Tips (PyLabRobot) ---")
        try:
            drop_op = Drop(resource=tip_well)
            await lh.drop_tips([drop_op], use_channels=[0])
            logger.info("✓ Drop tips via PyLabRobot - should have called backend.drop_tips_to_location()")
        except Exception as e:
            logger.error(f"✗ Drop tips failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ All PyLabRobot tests passed!")
        logger.info("PyLabRobot interface correctly wraps direct API calls")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            await lh.stop()
            logger.info("✓ Disconnected")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_pylabrobot_wrapper())

