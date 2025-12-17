"""
Direct API Test for Tecan Fluent.

This script uses the FluentVisionX backend directly (bypassing PyLabRobot)
to verify basic robot control.

Usage:
1. Open FluentControl manually.
2. Run the "demo" method (or any method with an API Channel action).
3. Wait for the API channel to open.
4. Run this script.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyfluent.backends.fluent_visionx import FluentVisionX

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestDirectAPI")


async def test_direct_control():
    """Test direct control of the robot."""
    logger.info("=" * 60)
    logger.info("TESTING DIRECT API CONTROL")
    logger.info("=" * 60)
    
    backend = FluentVisionX(simulation_mode=False)
    
    try:
        # 1. Connect
        logger.info("1. Connecting to FluentControl...")
        await backend.setup()
        logger.info("✓ Connected!")
        
        # 2. Wait for API Channel
        logger.info("\n2. Waiting for API Channel...")
        logger.info("Please ensure your method is running and has reached the API Channel action.")
        
        # Wait up to 60 seconds
        channel_ready = await backend.wait_for_channel(timeout=60)
        
        if not channel_ready:
            logger.error("✗ API Channel not detected!")
            logger.error("Troubleshooting:")
            logger.error("- Is the method running?")
            logger.error("- Does the method have an 'API Channel' action?")
            return
            
        logger.info("✓ API Channel is ready!")
        
        # 3. Get Tips
        logger.info("\n3. Testing Get Tips...")
        logger.info("Sending 'GetTips' command directly...")
        
        try:
            # Use specific DiTi type from your setup
            backend.get_tips(
                diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
                tip_indices=[0]  # Just use the first tip
            )
            logger.info("✓ Command sent successfully!")
            logger.info("Waiting 5 seconds for movement...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"✗ Get Tips failed: {e}")
            import traceback
            traceback.print_exc()
            
        # 4. Drop Tips
        logger.info("\n4. Testing Drop Tips...")
        logger.info("Sending 'DropTips' command directly...")
        
        try:
            # Use specific waste location
            backend.drop_tips_to_location(
                labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2",
                tip_indices=[0]
            )
            logger.info("✓ Command sent successfully!")
            logger.info("Waiting 5 seconds for movement...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"✗ Drop Tips failed: {e}")
            import traceback
            traceback.print_exc()
            
        logger.info("\n" + "=" * 60)
        logger.info("TEST COMPLETE")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        logger.info("\nDisconnecting...")
        await backend.stop()
        logger.info("✓ Disconnected")

if __name__ == "__main__":
    asyncio.run(test_direct_control())

