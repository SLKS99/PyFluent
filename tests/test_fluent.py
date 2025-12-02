"""Test file for Tecan Fluent backend using PyLabRobot.

This file demonstrates how to use the PyLabRobot backend to control a Tecan Fluent
liquid handler through the VisionX COM API.
"""

import logging
import asyncio
import pytest

from pyfluent import FluentVisionX

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FluentTest")

async def initialize_visionx() -> FluentVisionX:
    """Initialize FluentVisionX backend."""
    logger.info("Initializing FluentVisionX backend...")
    fluent = FluentVisionX(
        num_channels=8,
        simulation_mode=True  # Set to False for real hardware
    )

    logger.info("Setting up VisionX connection...")
    await fluent.setup()
    logger.info("Connected successfully")

    return fluent

async def add_labware(fluent: FluentVisionX) -> str:
    """Add labware to the deck."""
    if not fluent:
        raise RuntimeError("Fluent not initialized")

    # Add a 96 well plate to a position
    logger.info("Adding 96 well plate...")
    plate_name = "96WellPlate[001]"
    fluent.add_labware(
        labware_name=plate_name,
        labware_type="96 Well Flat",
        target_location="Nest61mm_Pos",
        position=1
    )
    logger.info("Plate added successfully")

    return plate_name

async def test_methods(fluent: FluentVisionX):
    """Test getting available methods."""
    logger.info("Getting available methods...")
    methods = fluent.get_available_methods()
    logger.info(f"Available methods: {methods}")
    return methods

async def cleanup(fluent: FluentVisionX) -> None:
    """Disconnect from Fluent."""
    if fluent:
        logger.info("Disconnecting from VisionX...")
        await fluent.stop()

async def main():
    fluent = None
    try:
        # Initialize VisionX
        fluent = await initialize_visionx()

        # Test getting methods
        methods = await test_methods(fluent)

        # Test adding labware
        logger.info("Testing labware addition...")
        plate = await add_labware(fluent)

        logger.info("All tests completed successfully!")
    except Exception as e:
        logger.error(f"Error during workflow: {e}")
        raise
    finally:
        if fluent:
            await cleanup(fluent)

if __name__ == "__main__":
    asyncio.run(main())
