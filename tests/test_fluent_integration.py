"""Integration test for Tecan Fluent using VisionX COM API."""

import asyncio
from pyfluent import FluentVisionX

async def main():
    try:
        print("Attempting to connect to VisionX...")
        
        # Create the FluentVisionX instance
        fluent = FluentVisionX(
            num_channels=8,
            simulation_mode=True  # Set to False for real hardware
        )

        # Setup and connect
        await fluent.setup()
        print("Connection successful!")

        # Test if we can get available methods
        methods = fluent.get_available_methods()
        print(f"Available methods: {len(methods)} found")
        if methods:
            print(f"Sample methods: {methods[:5]}")

        # Cleanup
        await fluent.stop()
        print("Disconnected successfully")

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
