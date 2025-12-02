"""Simple CSV protocol runner for Tecan Fluent using VisionX COM API.

Note: VisionX uses method-based execution. This runner supports:
- run_method: Execute a VisionX method
- add_labware: Add labware to the worktable

For more complex operations, use VisionX methods directly.
"""

import csv
import logging
import asyncio
from pathlib import Path
from pyfluent import FluentVisionX
import argparse

async def run_protocol(csv_path, simulation_mode=False):
    """Run a Tecan Fluent protocol from a CSV file using VisionX.

    Args:
        csv_path: Path to the CSV protocol file
        simulation_mode: Whether to run in simulation mode
    """
    # Set up basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("FluentCSV")

    # Initialize FluentVisionX
    fluent = FluentVisionX(
        num_channels=8,
        simulation_mode=simulation_mode
    )

    try:
        # Setup and connect to VisionX
        logger.info("Connecting to VisionX...")
        await fluent.setup()
        logger.info("Connected to VisionX successfully")

        # Get available methods
        methods = fluent.get_available_methods()
        logger.info(f"Available methods: {methods}")

        # Keep track of labware we've added
        added_labware = {}

        # Read and execute commands from CSV
        csv_path = Path(csv_path)
        logger.info(f"Starting protocol execution from {csv_path}...")

        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            # Skip header row if present
            try:
                header = next(reader)
                if header[0].lower() not in ['command', 'action', 'operation']:
                    # Not a header, rewind
                    f.seek(0)
                    reader = csv.reader(f)
            except StopIteration:
                pass

            for row in reader:
                if not row or not row[0]:
                    continue
                    
                command = row[0].strip().lower()
                logger.info(f"Executing: {command}")

                try:
                    if command == 'add_labware':
                        if len(row) < 5:
                            logger.error(f"add_labware requires 5 arguments: name, type, location, position")
                            continue
                        name, labware_type, location, position = row[1:5]
                        logger.info(f"Adding labware: {name} of type {labware_type} at {location} position {position}")
                        if name not in added_labware:
                            try:
                                fluent.add_labware(
                                    labware_name=name,
                                    labware_type=labware_type,
                                    target_location=location,
                                    position=int(position)
                                )
                                added_labware[name] = True
                                logger.info(f"Successfully added {labware_type} as {name}")
                            except Exception as e:
                                logger.error(f"Failed to add labware {name}: {str(e)}")
                                raise

                    elif command == 'run_method':
                        if len(row) < 2:
                            logger.error(f"run_method requires method name")
                            continue
                        method_name = row[1]
                        parameters = {}
                        # Parse parameters if provided (format: key=value,key2=value2)
                        if len(row) > 2 and row[2]:
                            for param_str in row[2].split(','):
                                if '=' in param_str:
                                    key, value = param_str.split('=', 1)
                                    parameters[key.strip()] = value.strip()
                        
                        logger.info(f"Running method: {method_name} with parameters: {parameters}")
                        try:
                            success = await fluent.run_method(method_name, parameters if parameters else None)
                            if success:
                                logger.info(f"Method {method_name} completed successfully")
                            else:
                                logger.warning(f"Method {method_name} may have failed")
                        except Exception as e:
                            logger.error(f"Failed to run method {method_name}: {str(e)}")
                            raise

                    else:
                        logger.warning(f"Unknown command: {command}. Skipping.")

                except Exception as e:
                    logger.error(f"Error executing {command}: {e}")
                    raise

        logger.info("Protocol completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Protocol failed: {e}")
        return False

    finally:
        try:
            await fluent.stop()
            logger.info("Disconnected from VisionX")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

def main():
    parser = argparse.ArgumentParser(description='Run a Tecan Fluent protocol from CSV using VisionX')
    parser.add_argument('--csv-path', type=str,
                       default="example_protocol.csv",
                       help='Path to the CSV protocol file')
    parser.add_argument('--simulation-mode', action='store_true',
                       help='Run in simulation mode')

    args = parser.parse_args()

    try:
        print(f"Starting protocol runner (VisionX)...")
        print(f"Simulation mode: {'ON' if args.simulation_mode else 'OFF'}")
        print(f"Using CSV file: {args.csv_path}")
        print(f"Checking if file exists: {Path(args.csv_path).exists()}")

        success = asyncio.run(run_protocol(
            csv_path=args.csv_path,
            simulation_mode=args.simulation_mode
        ))
        print(f"Protocol {'succeeded' if success else 'failed'}")
    except Exception as e:
        print(f"Error running protocol: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
