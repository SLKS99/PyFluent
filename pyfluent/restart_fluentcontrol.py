"""
Restart FluentControl - kills the process and starts fresh.
"""

import subprocess
import time
import sys
import os

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Enable verbose backend logging for diagnosis
os.environ["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "DEBUG")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyfluent.backends.fluent_visionx import FluentVisionX
import asyncio

async def restart_fluentcontrol():
    """Restart FluentControl by killing the process and starting fresh."""
    print("=" * 60)
    print("Restarting FluentControl")
    print("=" * 60)
    
    # Step 1: Kill FluentControl processes
    print("\n1. Killing FluentControl processes...")
    try:
        # Kill SystemSW.exe (FluentControl)
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "SystemSW.exe"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("OK: Killed SystemSW.exe")
        else:
            print(f"  SystemSW.exe: {result.stderr.strip()}")
    except Exception as e:
        print(f"  Error killing SystemSW.exe: {e}")
    
    # Wait a bit for processes to fully terminate
    print("\n2. Waiting for processes to terminate...")
    time.sleep(3)
    
    # Step 2: Start FluentControl fresh
    print("\n3. Starting FluentControl...")
    backend = FluentVisionX(simulation_mode=False)
    
    try:
        await backend.setup()
        print("OK: FluentControl started successfully!")
        print("\nFluentControl is now running. You can:")
        print("  - Run your method with API channel")
        print("  - Then run the test scripts")
        
        # Keep it running - don't disconnect
        print("\nFluentControl will stay connected. Press Ctrl+C to exit.")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\nDisconnecting...")
            await backend.stop()
            print("OK: Disconnected")
            
    except Exception as e:
        print(f"ERROR: Error starting FluentControl: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(restart_fluentcontrol())

