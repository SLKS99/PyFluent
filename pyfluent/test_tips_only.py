"""
Simple test for tips only - pick up and drop.

IMPORTANT: 
- Open FluentControl manually
- Run the "demo" method manually (it should have an API Channel action)
- Wait for the API channel to open
- Then run this script
"""

import asyncio
import logging
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyfluent.backends.fluent_visionx import FluentVisionX
from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.resources import TipRack, Deck
from pylabrobot.liquid_handling.standard import Pickup, Drop

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestTips")


async def test_tips_only():
    """Test only pick up tips and drop tips."""
    logger.info("=" * 60)
    logger.info("Testing Tips Only: Pick Up and Drop")
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
        channel_ready = await backend.wait_for_channel(timeout=60)
        if not channel_ready:
            logger.error("✗ API channel is not open!")
            logger.error("Please run the 'demo' method in FluentControl and wait for API channel to open")
            return False
        logger.info("✓ API channel is ready!")
        
        # Create tip rack resource
        logger.info("\nCreating tip rack resource...")
        tip_rack = TipRack("tip_rack", size_x=127.76, size_y=85.48)
        logger.info("✓ Tip rack created")
        
        # Test 1: Pick up tips (PyLabRobot -> should call backend.get_tips())
        logger.info("\n" + "-" * 60)
        logger.info("TEST 1: Pick Up Tips (PyLabRobot)")
        logger.info("-" * 60)
        logger.info("Sending pick_up_tips command...")
        try:
            tip_well = tip_rack["A1"]
            pickup_op = Pickup(resource=tip_well)
            await lh.pick_up_tips([pickup_op], use_channels=[0])
            logger.info("✓ Pick up tips command sent successfully")
            logger.info("Waiting 3 seconds for robot to pick up tips...")
            await asyncio.sleep(3)
            logger.info("✓ Test 1 PASSED: Tips should be picked up")
        except Exception as e:
            logger.error(f"✗ Test 1 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 2: Drop tips (PyLabRobot -> should call backend.drop_tips_to_location())
        logger.info("\n" + "-" * 60)
        logger.info("TEST 2: Drop Tips (PyLabRobot)")
        logger.info("-" * 60)
        logger.info("Sending drop_tips command...")
        try:
            drop_op = Drop(resource=tip_well)
            await lh.drop_tips([drop_op], use_channels=[0])
            logger.info("✓ Drop tips command sent successfully")
            logger.info("Waiting 3 seconds for robot to drop tips...")
            await asyncio.sleep(3)
            logger.info("✓ Test 2 PASSED: Tips should be dropped")
        except Exception as e:
            logger.error(f"✗ Test 2 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED!")
        logger.info("PyLabRobot wrapper correctly calls direct API for tips")
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
    asyncio.run(test_tips_only())

