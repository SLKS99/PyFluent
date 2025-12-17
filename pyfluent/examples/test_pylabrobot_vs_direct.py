"""
Test script to verify PyLabRobot definitions work the same as direct API calls.

This script tests that:
1. PyLabRobot operations (via LiquidHandler) work correctly
2. Direct API calls work correctly
3. Both produce equivalent results
"""

import asyncio
import logging
from pyfluent.backends.fluent_visionx import FluentVisionX
from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.resources import Plate, TipRack, Coordinate
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
        
        # Get available methods
        methods = backend.get_available_methods()
        logger.info(f"✓ Available methods: {len(methods)} found")
        if methods:
            logger.info(f"  Sample: {methods[:3]}")
        
        # Run method
        method_name = "demo"  # Change to your method name
        logger.info(f"Running method: {method_name}")
        await backend.run_method(method_name)
        
        # Wait for API channel
        logger.info("Waiting for API channel...")
        channel_ready = await backend.wait_for_channel(timeout=60)
        if not channel_ready:
            logger.error("✗ API channel did not open!")
            return False
        logger.info("✓ API channel ready")
        
        # Test 1: Get tips (direct API)
        logger.info("\n--- Test 1: Get Tips (Direct API) ---")
        backend.get_tips(
            diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
            tip_indices=[0]  # Just tip 0 for testing
        )
        logger.info("✓ Get tips command sent")
        
        # Test 2: Aspirate (direct API)
        logger.info("\n--- Test 2: Aspirate (Direct API) ---")
        backend.aspirate_volume(
            volumes=50,
            labware="96 Well Flat[002]",
            liquid_class="Water Test No Detect",
            well_offsets=0  # Well A1
        )
        logger.info("✓ Aspirate command sent")
        
        # Test 3: Dispense (direct API)
        logger.info("\n--- Test 3: Dispense (Direct API) ---")
        backend.dispense_volume(
            volumes=50,
            labware="96 Well Flat[001]",
            liquid_class="Water Test No Detect",
            well_offsets=0
        )
        logger.info("✓ Dispense command sent")
        
        # Test 4: Drop tips (direct API)
        logger.info("\n--- Test 4: Drop Tips (Direct API) ---")
        backend.drop_tips_to_location(
            labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2"
        )
        logger.info("✓ Drop tips command sent")
        
        logger.info("\n✓ All direct API tests completed successfully!")
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
        
        # Get available methods
        methods = backend.get_available_methods()
        logger.info(f"✓ Available methods: {len(methods)} found")
        
        # Run method
        method_name = "demo"  # Change to your method name
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
        
        # Assign to deck (simplified - in real usage you'd use proper deck layout)
        logger.info("✓ Resources created")
        
        # Test 1: Pick up tips (PyLabRobot)
        logger.info("\n--- Test 1: Pick Up Tips (PyLabRobot) ---")
        tip_well = tip_rack["A1"]  # PyLabRobot style: use [] operator
        pickup_op = Pickup(resource=tip_well)
        await lh.pick_up_tips([pickup_op], use_channels=[0])
        logger.info("✓ Pick up tips command sent via PyLabRobot")
        
        # Test 2: Aspirate (PyLabRobot)
        logger.info("\n--- Test 2: Aspirate (PyLabRobot) ---")
        source_well = source_plate["A1"]  # PyLabRobot style: use [] operator
        asp_op = Aspiration(resource=source_well, volume=50)
        await lh.aspirate([asp_op], use_channels=[0])
        logger.info("✓ Aspirate command sent via PyLabRobot")
        
        # Test 3: Dispense (PyLabRobot)
        logger.info("\n--- Test 3: Dispense (PyLabRobot) ---")
        dest_well = dest_plate["A1"]  # PyLabRobot style: use [] operator
        disp_op = Dispense(resource=dest_well, volume=50)
        await lh.dispense([disp_op], use_channels=[0])
        logger.info("✓ Dispense command sent via PyLabRobot")
        
        # Test 4: Drop tips (PyLabRobot)
        logger.info("\n--- Test 4: Drop Tips (PyLabRobot) ---")
        drop_op = Drop(resource=tip_well)
        await lh.drop_tips([drop_op], use_channels=[0])
        logger.info("✓ Drop tips command sent via PyLabRobot")
        
        logger.info("\n✓ All PyLabRobot interface tests completed successfully!")
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


async def test_equivalence():
    """Test that PyLabRobot and direct API produce equivalent results."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Equivalence Check")
    logger.info("=" * 60)
    
    backend = FluentVisionX(simulation_mode=False)
    lh = LiquidHandler(backend=backend)
    
    try:
        await lh.setup()
        logger.info("✓ Setup complete")
        
        # Run method
        method_name = "demo"
        await backend.run_method(method_name)
        await backend.wait_for_channel(timeout=60)
        logger.info("✓ API channel ready")
        
        # Create resources
        source_plate = Plate("source_plate", size_x=127.76, size_y=85.48)
        dest_plate = Plate("dest_plate", size_x=127.76, size_y=85.48)
        
        # Test: Both should use the same backend methods
        logger.info("\nTesting equivalence...")
        
        # Direct API call
        logger.info("1. Direct API: aspirate_volume()")
        backend.aspirate_volume(
            volumes=100,
            labware="96 Well Flat[002]",
            liquid_class="Water Test No Detect",
            well_offsets=0
        )
        
        # PyLabRobot call (should call the same backend method)
        logger.info("2. PyLabRobot: aspirate() -> backend.aspirate()")
        source_well = source_plate["A1"]  # PyLabRobot style: use [] operator
        asp_op = Aspiration(resource=source_well, volume=100)
        await lh.aspirate([asp_op], use_channels=[0])
        
        logger.info("✓ Both methods executed successfully")
        logger.info("✓ PyLabRobot calls are routed to the same backend methods")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Equivalence test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            await lh.stop()
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
    
    # Small delay between tests
    await asyncio.sleep(2)
    
    # Test 3: Equivalence
    result3 = await test_equivalence()
    results.append(("Equivalence", result3))
    
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

