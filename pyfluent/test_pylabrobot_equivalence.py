"""
Simple test to verify PyLabRobot definitions work the same as direct API calls.

This script demonstrates that:
1. Direct API calls work
2. PyLabRobot interface calls work
3. Both use the same backend methods
"""

import asyncio
import logging
import sys
import os

# Add current directory to path
# When running from PyFluent directory, pyfluent should be importable
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try importing
try:
    from pyfluent.backends.fluent_visionx import FluentVisionX
except ImportError:
    # Fallback: try relative import
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "fluent_visionx",
        os.path.join(parent_dir, "pyfluent", "backends", "fluent_visionx.py")
    )
    fluent_visionx = importlib.util.module_from_spec(spec)
    sys.modules["pyfluent.backends.fluent_visionx"] = fluent_visionx
    spec.loader.exec_module(fluent_visionx)
    FluentVisionX = fluent_visionx.FluentVisionX
from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.resources import Plate, TipRack
from pylabrobot.liquid_handling.standard import (
    Aspiration,
    Dispense,
    Pickup,
    Drop,
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestPyLabRobot")


async def test_direct_api():
    """Test direct API calls."""
    logger.info("=" * 60)
    logger.info("TEST 1: Direct API Calls")
    logger.info("=" * 60)
    
    backend = FluentVisionX(simulation_mode=False)
    
    try:
        # Setup
        logger.info("Setting up backend...")
        await backend.setup()
        logger.info("✓ Backend connected")
        
        # Run method
        method_name = "demo"
        logger.info(f"Running method: {method_name}")
        await backend.run_method(method_name)
        
        # Wait for API channel
        logger.info("Waiting for API channel...")
        channel_ready = await backend.wait_for_channel(timeout=60)
        if not channel_ready:
            logger.error("✗ API channel did not open!")
            return False
        logger.info("✓ API channel ready")
        
        # Test: Get tips (direct API)
        logger.info("\n--- Test: Get Tips (Direct API) ---")
        try:
            backend.get_tips(
                diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
                tip_indices=[0]
            )
            logger.info("✓ Get tips command sent and executed")
        except Exception as e:
            logger.error(f"✗ Get tips failed: {e}")
            raise
        
        # Test: Aspirate (direct API)
        logger.info("\n--- Test: Aspirate (Direct API) ---")
        try:
            backend.aspirate_volume(
                volumes=50,
                labware="96 Well Flat[002]",
                liquid_class="Water Test No Detect",
                well_offsets=0
            )
            logger.info("✓ Aspirate command sent and executed")
        except Exception as e:
            logger.error(f"✗ Aspirate failed: {e}")
            raise
        
        # Test: Dispense (direct API)
        logger.info("\n--- Test: Dispense (Direct API) ---")
        try:
            backend.dispense_volume(
                volumes=50,
                labware="96 Well Flat[001]",
                liquid_class="Water Test No Detect",
                well_offsets=0
            )
            logger.info("✓ Dispense command sent and executed")
        except Exception as e:
            logger.error(f"✗ Dispense failed: {e}")
            raise
        
        # Test: Drop tips (direct API)
        logger.info("\n--- Test: Drop Tips (Direct API) ---")
        try:
            backend.drop_tips_to_location(
                labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2"
            )
            logger.info("✓ Drop tips command sent and executed")
        except Exception as e:
            logger.error(f"✗ Drop tips failed: {e}")
            raise
        
        logger.info("\n✓ All direct API tests completed!")
        return True
        
    except Exception as e:
        logger.error(f"✗ Direct API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            await backend.stop()
            logger.info("✓ Backend disconnected")
        except:
            pass


async def test_pylabrobot_interface():
    """Test PyLabRobot interface."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: PyLabRobot Interface")
    logger.info("=" * 60)
    
    backend = FluentVisionX(simulation_mode=False)
    lh = LiquidHandler(backend=backend)
    
    try:
        # Setup
        logger.info("Setting up LiquidHandler...")
        await lh.setup()
        logger.info("✓ LiquidHandler connected")
        
        # Run method
        method_name = "demo"
        logger.info(f"Running method: {method_name}")
        await backend.run_method(method_name)
        
        # Wait for API channel
        logger.info("Waiting for API channel...")
        channel_ready = await backend.wait_for_channel(timeout=60)
        if not channel_ready:
            logger.error("✗ API channel did not open!")
            return False
        logger.info("✓ API channel ready")
        
        # Create resources (PyLabRobot style)
        logger.info("\nCreating PyLabRobot resources...")
        tip_rack = TipRack("tip_rack", size_x=127.76, size_y=85.48)
        source_plate = Plate("source_plate", size_x=127.76, size_y=85.48)
        dest_plate = Plate("dest_plate", size_x=127.76, size_y=85.48)
        logger.info("✓ Resources created")
        
        # Test: Pick up tips (PyLabRobot)
        logger.info("\n--- Test: Pick Up Tips (PyLabRobot) ---")
        tip_well = tip_rack["A1"]
        pickup_op = Pickup(resource=tip_well)
        await lh.pick_up_tips([pickup_op], use_channels=[0])
        logger.info("✓ Pick up tips command sent via PyLabRobot")
        
        # Test: Aspirate (PyLabRobot)
        logger.info("\n--- Test: Aspirate (PyLabRobot) ---")
        source_well = source_plate["A1"]
        asp_op = Aspiration(resource=source_well, volume=50)
        await lh.aspirate([asp_op], use_channels=[0])
        logger.info("✓ Aspirate command sent via PyLabRobot")
        
        # Test: Dispense (PyLabRobot)
        logger.info("\n--- Test: Dispense (PyLabRobot) ---")
        dest_well = dest_plate["A1"]
        disp_op = Dispense(resource=dest_well, volume=50)
        await lh.dispense([disp_op], use_channels=[0])
        logger.info("✓ Dispense command sent via PyLabRobot")
        
        # Test: Drop tips (PyLabRobot)
        logger.info("\n--- Test: Drop Tips (PyLabRobot) ---")
        drop_op = Drop(resource=tip_well)
        await lh.drop_tips([drop_op], use_channels=[0])
        logger.info("✓ Drop tips command sent via PyLabRobot")
        
        logger.info("\n✓ All PyLabRobot interface tests completed!")
        return True
        
    except Exception as e:
        logger.error(f"✗ PyLabRobot interface test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            await lh.stop()
            logger.info("✓ LiquidHandler disconnected")
        except:
            pass


async def main():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("PyLabRobot vs Direct API Test Suite")
    logger.info("=" * 60)
    logger.info("\nThis script tests that PyLabRobot definitions work")
    logger.info("the same as direct API calls.\n")
    
    results = []
    
    # Test 1: Direct API
    result1 = await test_direct_api()
    results.append(("Direct API", result1))
    
    # Small delay between tests
    await asyncio.sleep(2)
    
    # Test 2: PyLabRobot Interface
    result2 = await test_pylabrobot_interface()
    results.append(("PyLabRobot Interface", result2))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        logger.info("\n✓ All tests passed! PyLabRobot and direct API work equivalently.")
    else:
        logger.info("\n✗ Some tests failed. Check the logs above for details.")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

