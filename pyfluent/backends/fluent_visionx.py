"""Backend implementation for controlling Tecan Fluent using VisionX .NET API.

This backend connects directly to Tecan VisionX/FluentControl through the .NET API
(Tecan.VisionX.API.V2)

Requirements:
- Windows operating system
- Tecan VisionX/FluentControl installed and running
- pythonnet package (pip install pythonnet)
- Tecan.VisionX.API.V2.dll must be accessible
"""

import logging
import sys
import time
import threading
from typing import Any, Dict, List, Optional, Callable, Tuple, Sequence, Union
import asyncio
import warnings
from enum import Enum, auto

# Python.NET support (for .NET API access)
HAS_PYTHONNET = False
try:
    import clr
    import System
    HAS_PYTHONNET = True
except ImportError:
    warnings.warn(
        "\nPython.NET support (pythonnet) not found. "
        "Install it with: pip install pythonnet"
    )

from pylabrobot.liquid_handling.backends.backend import LiquidHandlerBackend
from pylabrobot.liquid_handling.standard import (
    Drop,
    DropTipRack,
    Pickup,
    PickupTipRack,
    Aspiration,
    Dispense,
)
from pylabrobot.resources import Resource, Coordinate

from .errors import TecanError


class FluentState(Enum):
    """States for the Fluent liquid handler."""
    DISCONNECTED = auto()
    CONNECTED = auto()
    EDIT_MODE = auto()
    RUNNING = auto()
    ERROR = auto()
    BUSY = auto()
    READY = auto()


class FluentVisionX(LiquidHandlerBackend):
    """Backend for controlling Tecan Fluent liquid handlers using VisionX .NET API.

    This backend connects directly to Tecan VisionX/FluentControl through the .NET API
    (Tecan.VisionX.API.V2), exactly like the C# SiLA2 server does. This is the 
    recommended approach as it uses the same API that actually works.

    Example usage:
        fluent = FluentVisionX()

        # Connect to VisionX
        await fluent.setup()

        # Get available methods
        methods = fluent.get_available_methods()

        # Prepare and run a method
        fluent.prepare_method("MyMethod")
        await fluent.run_method("MyMethod")

        # Perform liquid handling operations
        await fluent.aspirate([asp_op], [0])
        await fluent.dispense([disp_op], [0])

        # Cleanup
        await fluent.stop()
    """

    def __init__(
        self,
        num_channels: int = 8,
        simulation_mode: bool = False,
        with_visualization: bool = False,
        with_tracking: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """Create a new Tecan Fluent VisionX backend.

        Args:
            num_channels: Number of channels on the liquid handler (default: 8)
            simulation_mode: Whether to run in simulation mode (default: False)
            with_visualization: Whether to enable visualization (default: False)
            with_tracking: Whether to enable tip and volume tracking (default: False)
            username: Username for login (optional)
            password: Password for login (optional)
        """
        if not HAS_PYTHONNET:
            raise RuntimeError(
                "The Tecan Fluent VisionX backend requires pythonnet. "
                "Please install it with: pip install pythonnet"
            )

        if sys.platform != "win32":
            raise RuntimeError(
                "The Tecan Fluent VisionX backend requires Windows. "
                "This backend uses the .NET API (Tecan.VisionX.API.V2)."
            )

        super().__init__()
        self._num_channels = num_channels
        self.simulation_mode = simulation_mode
        self.with_visualization = with_visualization
        self.with_tracking = with_tracking
        self.username = username
        self.password = password

        # .NET objects (matching C# server implementation)
        self.fluent_control = None  # FluentControl instance
        self.runtime = None  # RuntimeController instance
        self.current_execution_channel = None
        self._open_execution_channels = []  # List of open execution channels
        
        # Event handlers (keep references to prevent garbage collection)
        self._channel_opens_handler = None
        self._mode_changed_handler = None
        self._error_handler = None
        self._progress_handler = None

        # State management
        self._current_state = FluentState.DISCONNECTED
        self._progress = -1
        self._last_error = None
        self._loop = None
        self.visualizer = None
        self._initialized = False  # Required by LiquidHandlerBackend

        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("FluentVisionXBackend")
        
        # Load the .NET assembly
        self._load_assembly()

    def _load_assembly(self):
        """Load the Tecan VisionX API assembly."""
        # Common paths for the DLL
        dll_paths = [
            r"C:\Program Files\Tecan\VisionX\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan\VisionX\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files\Tecan\FluentControl\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan\FluentControl\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan - Copy\fluentcontrol\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan - Copy\FluentControl\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan - Copy\VisionX\API\Tecan.VisionX.API.V2.dll",
        ]

        dll_loaded = False
        for dll_path in dll_paths:
            try:
                import os
                if os.path.exists(dll_path):
                    clr.AddReference(dll_path)
                    self.logger.info(f"Loaded DLL: {dll_path}")
                    dll_loaded = True
                    break
            except Exception as e:
                self.logger.debug(f"Could not load {dll_path}: {e}")
                continue
        
        # If not found in standard paths, try searching in the custom path
        if not dll_loaded:
            custom_base = r"C:\Program Files (x86)\Tecan - Copy\fluentcontrol"
            if os.path.exists(custom_base):
                try:
                    # Search recursively for the DLL
                    for root, dirs, files in os.walk(custom_base):
                        for file in files:
                            if file == "Tecan.VisionX.API.V2.dll":
                                dll_path = os.path.join(root, file)
                                try:
                                    clr.AddReference(dll_path)
                                    self.logger.info(f"Loaded DLL: {dll_path}")
                                    dll_loaded = True
                                    break
                                except Exception as e:
                                    self.logger.debug(f"Could not load {dll_path}: {e}")
                        if dll_loaded:
                            break
                except Exception as e:
                    self.logger.debug(f"Error searching in {custom_base}: {e}")

        if not dll_loaded:
            # Try to find it in GAC or current directory
            try:
                clr.AddReference("Tecan.VisionX.API.V2")
                self.logger.info("Loaded DLL from GAC or current directory")
                dll_loaded = True
            except Exception as e:
                self.logger.warning(f"Could not load from GAC: {e}")

        if not dll_loaded:
            raise RuntimeError(
                "Could not find Tecan.VisionX.API.V2.dll. "
                "Please ensure Tecan VisionX is installed. "
                "The DLL should be in: C:\\Program Files\\Tecan\\VisionX\\API\\"
            )

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _create_fluent_control(self):
        """Create FluentControl instance (like C# code)."""
        try:
            # Import the .NET classes (matching C# using statements)
            from Tecan.VisionX.API.V2 import FluentControl

            # Create instance (like: private readonly FluentControl _process = new FluentControl();)
            self.fluent_control = FluentControl()
            self.logger.info("Created FluentControl instance")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create FluentControl: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_runtime(self):
        """Get RuntimeController (like C# code)."""
        try:
            if not self.fluent_control:
                return False

            # Get runtime (like: _runtime = (RuntimeController)_process.GetRuntime();)
            runtime_obj = self.fluent_control.GetRuntime()

            if runtime_obj is None:
                self.logger.warning("Runtime is None")
                return False

            # RuntimeController is already the correct type
            self.runtime = runtime_obj
            self.logger.info("Got RuntimeController")
            
            # Subscribe to runtime events (like C#: _runtime.ChannelOpens += Runtime_ChannelOpens;)
            self._subscribe_to_runtime_events()
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to get RuntimeController: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _subscribe_to_runtime_events(self):
        """Subscribe to runtime events for execution channel handling."""
        if not self.runtime:
            return
        
        try:
            # Subscribe to ChannelOpens event (like C#: _runtime.ChannelOpens += Runtime_ChannelOpens;)
            if hasattr(self.runtime, 'ChannelOpens'):
                def on_channel_opens(channel):
                    """Called when an execution channel opens (API channel in method)."""
                    self.logger.info(f"Execution channel opened!")
                    self.current_execution_channel = channel
                    self._open_execution_channels.append(channel)
                
                self.runtime.ChannelOpens += on_channel_opens
                self._channel_opens_handler = on_channel_opens
                self.logger.info("Subscribed to ChannelOpens event")
            
            # Subscribe to ModeChanged event
            if hasattr(self.runtime, 'ModeChanged'):
                def on_mode_changed(sender, args):
                    """Called when runtime mode changes."""
                    try:
                        mode_str = str(args.Data) if hasattr(args, 'Data') else str(args)
                        self.logger.info(f"Runtime mode changed: {mode_str}")
                        
                        if 'Running' in mode_str:
                            # When running, use the last opened channel
                            if self._open_execution_channels:
                                self.current_execution_channel = self._open_execution_channels[-1]
                        elif 'Edit' in mode_str:
                            self.current_execution_channel = None
                    except Exception as e:
                        self.logger.debug(f"Error in mode changed handler: {e}")
                
                self.runtime.ModeChanged += on_mode_changed
                self._mode_changed_handler = on_mode_changed
                self.logger.info("Subscribed to ModeChanged event")
            
            # Subscribe to Error event
            if hasattr(self.runtime, 'Error'):
                def on_error(sender, args):
                    """Called when a runtime error occurs."""
                    try:
                        error_msg = str(args.Data) if hasattr(args, 'Data') else str(args)
                        self.logger.error(f"Runtime error: {error_msg}")
                        self._last_error = error_msg
                    except:
                        pass
                
                self.runtime.Error += on_error
                self._error_handler = on_error
                self.logger.info("Subscribed to Error event")
            
            # Subscribe to ProgressChanged event
            if hasattr(self.runtime, 'ProgressChanged'):
                def on_progress_changed(sender, args):
                    """Called when method progress changes."""
                    try:
                        progress = args.Data if hasattr(args, 'Data') else args
                        self._progress = int(progress) if progress is not None else -1
                    except:
                        pass
                
                self.runtime.ProgressChanged += on_progress_changed
                self._progress_handler = on_progress_changed
                self.logger.info("Subscribed to ProgressChanged event")
                
        except Exception as e:
            self.logger.warning(f"Could not subscribe to some runtime events: {e}")

    async def setup(self) -> None:
        """Set up the liquid handler and connect to VisionX."""
        if self._initialized:
            return

        if not self.simulation_mode:
            # Initialize connection (run in thread to avoid blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._connect_to_visionx)

        # Enable tracking if requested
        if self.with_tracking:
            from pylabrobot.resources import set_tip_tracking, set_volume_tracking
            set_tip_tracking(True)
            set_volume_tracking(True)

        # Initialize visualization if requested
        if self.with_visualization:
            from pylabrobot.visualizer import Visualizer
            self.visualizer = Visualizer(resource=self)
            await self.visualizer.setup()

        self._initialized = True
        self.logger.info("Fluent VisionX backend setup complete")

    def _kill_fluent_process(self):
        """Kill the FluentControl process (SystemSW.exe) so we can start fresh."""
        try:
            import subprocess
            result = subprocess.run(
                ['taskkill', '/F', '/IM', 'SystemSW.exe'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.logger.info("Killed SystemSW.exe process")
            else:
                self.logger.debug(f"Could not kill SystemSW.exe: {result.stderr}")
        except Exception as e:
            self.logger.debug(f"Error killing process: {e}")

    def _connect_to_visionx(self):
        """Connect to Tecan VisionX (like C# StartFluentOrAttach)."""
        try:
            self.logger.info("Connecting to Tecan VisionX...")

            # Create FluentControl instance
            if not self._create_fluent_control():
                raise TecanError("Failed to create FluentControl", "VisionX", 1)

            # Check if already running (like C# code: bool alreadyStarted = _process.IsRunning();)
            is_running = False
            try:
                if hasattr(self.fluent_control, 'IsRunning'):
                    is_running = self.fluent_control.IsRunning()
                    if is_running:
                        self.logger.info("FluentControl is already running (background process)")
                        # IMPORTANT: If FluentControl is running but we can't get a runtime,
                        # we need to kill it and start fresh. This is because the background
                        # process (SystemSW.exe) may be running without the GUI.
                        self.logger.info("Checking if runtime is available from existing process...")
                        try:
                            test_runtime = self.fluent_control.GetRuntime()
                            if test_runtime is None:
                                self.logger.info("Runtime not available - killing existing process to start fresh...")
                                self._kill_fluent_process()
                                is_running = False
                                time.sleep(3)  # Wait for process to fully terminate
                            else:
                                self.logger.info("Runtime is available from existing process")
                        except:
                            self.logger.info("Could not check runtime - killing process to start fresh...")
                            self._kill_fluent_process()
                            is_running = False
                            time.sleep(3)
                    else:
                        self.logger.info("FluentControl is not running - will start it")
            except Exception as e:
                self.logger.debug(f"Could not check if running: {e}")

            # Try to subscribe to RuntimeIsAvailable event (like C#: _process.RuntimeIsAvailable += Process_RuntimeIsAvailable;)
            # In Python.NET, we can subscribe to events
            runtime_available_event = threading.Event()
            try:
                if hasattr(self.fluent_control, 'RuntimeIsAvailable'):
                    # Create a callback function for the event
                    def on_runtime_available(sender, args):
                        self.logger.info("RuntimeIsAvailable event fired!")
                        runtime_available_event.set()
                    
                    # Subscribe to the event (Python.NET event subscription)
                    self.fluent_control.RuntimeIsAvailable += on_runtime_available
                    self.logger.info("Subscribed to RuntimeIsAvailable event")
            except Exception as e:
                self.logger.debug(f"Could not subscribe to RuntimeIsAvailable event: {e}")
                # Will fall back to polling

            # Start or attach (like C# code)
            # IMPORTANT: The C# code pattern is:
            # 1. Call StartInSimulationMode() or StartAndLogin() FIRST (this actually starts FluentControl)
            # 2. Then call StartOrAttach() to attach to it
            # StartOrAttach() alone might not start it - we need to call a Start method first
            
            if self.simulation_mode:
                self.logger.info("Starting in simulation mode...")
                # Call StartInSimulationMode() first - this actually starts FluentControl
                if hasattr(self.fluent_control, 'StartInSimulationMode'):
                    self.fluent_control.StartInSimulationMode()
                    self.logger.info("Called StartInSimulationMode() - this should start FluentControl")
                # Then attach
                if hasattr(self.fluent_control, 'StartOrAttach'):
                    self.fluent_control.StartOrAttach()
                    self.logger.info("Called StartOrAttach() to attach")
            elif self.username and self.password:
                self.logger.info(f"Starting with login: {self.username}")
                # Call StartAndLogin() first - this actually starts FluentControl
                if hasattr(self.fluent_control, 'StartAndLogin'):
                    self.fluent_control.StartAndLogin(self.username, self.password)
                    self.logger.info("Called StartAndLogin() - this should start FluentControl")
                # Then attach
                if hasattr(self.fluent_control, 'StartOrAttach'):
                    self.fluent_control.StartOrAttach()
                    self.logger.info("Called StartOrAttach() to attach")
            else:
                self.logger.info("Starting FluentControl...")
                # For normal mode, the C# code just calls StartOrAttach() directly
                # StartOrAttach() should start FluentControl if not running, or attach if running
                # It should also show the GUI window
                if hasattr(self.fluent_control, 'StartOrAttach'):
                    self.fluent_control.StartOrAttach()
                    self.logger.info("Called StartOrAttach() - should start or attach to FluentControl and show GUI")
                elif hasattr(self.fluent_control, 'Start'):
                    self.fluent_control.Start()
                    self.logger.info("Called Start() - this should start FluentControl")
                elif hasattr(self.fluent_control, 'StartFluent'):
                    self.fluent_control.StartFluent()
                    self.logger.info("Called StartFluent() - this should start FluentControl")
                
                # After StartOrAttach(), the GUI should appear
                # Give it a moment, then check if window is visible
                time.sleep(2)  # Give FluentControl time to show window
                
                # Try to show/bring to front if there are methods for that
                try:
                    # Check if there's an Application or Window property we can access
                    if hasattr(self.fluent_control, 'Application'):
                        app = self.fluent_control.Application
                        if hasattr(app, 'Show'):
                            app.Show()
                            self.logger.info("Called Application.Show() to display FluentControl window")
                        if hasattr(app, 'BringToFront'):
                            app.BringToFront()
                            self.logger.info("Called Application.BringToFront()")
                    
                    # Direct methods on FluentControl
                    if hasattr(self.fluent_control, 'Show'):
                        self.fluent_control.Show()
                        self.logger.info("Called Show() to display FluentControl window")
                    if hasattr(self.fluent_control, 'BringToFront'):
                        self.fluent_control.BringToFront()
                        self.logger.info("Called BringToFront() to show FluentControl window")
                    if hasattr(self.fluent_control, 'Activate'):
                        self.fluent_control.Activate()
                        self.logger.info("Called Activate() to activate FluentControl window")
                except Exception as e:
                    self.logger.debug(f"Could not show/activate window: {e}")

            # Wait for FluentControl to be fully started and initialized
            # (like C# code waits for runtime to be ready)
            self.logger.info("Waiting for FluentControl to start and initialize...")
            
            # First, verify FluentControl process is actually running
            # StartOrAttach should start it if not running, but let's verify
            process_started = False
            for i in range(60):  # Wait up to 60 seconds for process to start
                try:
                    if hasattr(self.fluent_control, 'IsRunning'):
                        if self.fluent_control.IsRunning():
                            self.logger.info("FluentControl process is now running")
                            process_started = True
                            break
                except Exception as e:
                    self.logger.debug(f"Error checking IsRunning: {e}")
                
                time.sleep(1)
                if i % 5 == 0:
                    self.logger.info(f"Waiting for FluentControl to start... ({i}s)")
            
            if not process_started:
                self.logger.warning("FluentControl process may not have started - continuing anyway")
            
            # Give it more time to fully initialize (FluentControl can take a while to start)
            self.logger.info("Waiting for FluentControl to initialize (this may take 10-30 seconds)...")
            time.sleep(5)  # Give it more time to initialize
            
            # Now wait for runtime to be available (like C# _waitForRuntimeIsReady.Wait())
            # If not already started, wait for the RuntimeIsAvailable event
            self.logger.info("Waiting for runtime to be available...")
            runtime_available = False
            
            if not is_running:
                # If FluentControl wasn't running, wait for RuntimeIsAvailable event
                self.logger.info("FluentControl was not running - waiting for RuntimeIsAvailable event...")
                if runtime_available_event.wait(timeout=60):  # Wait up to 60 seconds for event
                    self.logger.info("RuntimeIsAvailable event received!")
                else:
                    self.logger.warning("RuntimeIsAvailable event not received within timeout")
            
            # Try to get runtime (either from event or by polling)
            for i in range(60):  # Wait up to 60 seconds
                try:
                    # Try to get runtime
                    runtime_obj = self.fluent_control.GetRuntime()
                    if runtime_obj is not None:
                        self.runtime = runtime_obj
                        runtime_available = True
                        self.logger.info("Got RuntimeController")
                        
                        # Subscribe to runtime events for execution channel handling
                        self._subscribe_to_runtime_events()
                        break
                except Exception as e:
                    # Runtime might not be ready yet, that's OK
                    self.logger.debug(f"Runtime not ready yet: {e}")
                
                time.sleep(1)
                if i % 5 == 0:
                    self.logger.info(f"Still waiting for runtime... ({i}s)")

            if not runtime_available:
                self.logger.warning("Runtime not available after waiting - continuing anyway")
                # Don't raise error, just log warning - might work later

            # Wait for EditMode (like C# _waitForEditMode.Wait())
            if self.runtime is not None:
                self.logger.info("Waiting for EditMode...")
                edit_mode_reached = False
                for i in range(30):  # Wait up to 30 seconds
                    try:
                        if hasattr(self.runtime, 'GetFluentStatus'):
                            status = self.runtime.GetFluentStatus()
                            # Check if in EditMode
                            if str(status) == "EditMode" or "EditMode" in str(status):
                                edit_mode_reached = True
                                break
                    except:
                        pass
                    time.sleep(1)

                if not edit_mode_reached:
                    self.logger.warning("EditMode not reached, but continuing...")
                
                # Try to prepare a method that opens an API channel (like C# PrepareMethodRun)
                # This might help establish the connection better
                try:
                    self.logger.info("Attempting to prepare a method to open API channel...")
                    # The C# code prepares "Method to prepare" - try that or look for a method with API channel
                    methods = self.runtime.GetAllRunnableMethods()
                    if methods and len(methods) > 0:
                        # Try to find a method that might open an API channel, or use the first one
                        method_to_prepare = None
                        for method in methods:
                            method_str = str(method)
                            # Look for methods that might have API channel in the name
                            if "api" in method_str.lower() or "channel" in method_str.lower():
                                method_to_prepare = method_str
                                break
                        
                        if not method_to_prepare:
                            method_to_prepare = str(methods[0])
                        
                        self.logger.info(f"Preparing method '{method_to_prepare}' to open API channel...")
                        self.runtime.PrepareMethod(method_to_prepare)
                        self.logger.info("Method prepared - API channel should be available when method runs")
                except Exception as e:
                    self.logger.debug(f"Could not prepare method for API channel: {e}")
                    # This is optional, so don't fail if it doesn't work
            else:
                self.logger.warning("Runtime not available, skipping EditMode check and API channel setup")

            self._current_state = FluentState.EDIT_MODE
            self.logger.info("Successfully connected to Tecan VisionX!")

        except Exception as e:
            self.logger.error(f"Failed to connect: {e}")
            import traceback
            traceback.print_exc()
            self._last_error = str(e)
            self._current_state = FluentState.ERROR
            raise TecanError(f"Failed to connect: {str(e)}", "VisionX", 1)

    async def stop(self) -> None:
        """Stop the liquid handler and cleanup."""
        if not self._initialized:
            return

        # Stop visualization if active
        if self.visualizer is not None:
            await self.visualizer.stop()
            self.visualizer = None

        # Clean up connection
        if not self.simulation_mode:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._cleanup_connection)

        self._initialized = False
        self.logger.info("Fluent VisionX backend stopped")

    def _cleanup_connection(self):
        """Clean up the connection."""
        try:
            if self.runtime:
                self.runtime = None
            if self.fluent_control:
                self.fluent_control = None

            self._current_state = FluentState.DISCONNECTED
            self.logger.info("Disconnected from Tecan VisionX")

        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")

    @property
    def num_channels(self) -> int:
        """Get the number of channels on the liquid handler."""
        return self._num_channels

    def get_available_methods(self) -> List[str]:
        """Get list of available methods from FluentControl (like C# GetAllRunnableMethods).

        Returns:
            List of method names available in FluentControl
        """
        if self.simulation_mode:
            return ["SimulationMethod1", "SimulationMethod2"]

        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            # Like C#: var methods = _runtime.GetAllRunnableMethods();
            methods = self.runtime.GetAllRunnableMethods()

            if methods is None:
                return []

            # Convert to Python list
            method_list = []
            if hasattr(methods, '__iter__'):
                for method in methods:
                    method_list.append(str(method))
            else:
                # Try to enumerate
                try:
                    count = methods.Count
                    for i in range(count):
                        method_list.append(str(methods[i]))
                except:
                    method_list = [str(methods)]

            self.logger.info(f"Found {len(method_list)} available methods")
            return method_list

        except Exception as e:
            self.logger.error(f"Could not get available methods: {e}")
            import traceback
            traceback.print_exc()
            return []

    def prepare_method(self, method_name: str) -> bool:
        """Prepare a method for execution (like C# PrepareMethod).

        Args:
            method_name: Name of the method to prepare

        Returns:
            bool: True if successful
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Preparing method {method_name}")
            return True

        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            self.logger.info(f"Preparing method: {method_name}")

            # Like C#: _runtime.PrepareMethod(toPrepare);
            self.runtime.PrepareMethod(method_name)

            self.logger.info("Method prepared successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error preparing method: {e}")
            import traceback
            traceback.print_exc()
            self._last_error = str(e)
            raise TecanError(f"Failed to prepare method: {str(e)}", "VisionX", 1)

    async def run_method(
        self,
        method_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Run a method on the Fluent (like C# RunMethod).

        Args:
            method_name: Name of the method to run (must be prepared first)
            parameters: Optional parameters for the method (not used yet)

        Returns:
            bool: True if successful
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Running method {method_name}")
            return True

        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            # Prepare the method first if not already prepared
            # (In C# server, PrepareMethod is called separately)
            self.prepare_method(method_name)

            loop = asyncio.get_event_loop()

            def _run_method():
                # Like C#: _runtime.RunMethod();
                self.runtime.RunMethod()
                return True

            self.logger.info(f"Running method: {method_name}")
            self._current_state = FluentState.RUNNING

            success = await loop.run_in_executor(None, _run_method)

            # Wait for method to complete
            await self._wait_for_method_completion()

            self._current_state = FluentState.READY
            self.logger.info(f"Method {method_name} completed successfully")

            return success

        except Exception as e:
            self.logger.error(f"Failed to run method {method_name}: {e}")
            self._current_state = FluentState.ERROR
            import traceback
    
    async def wait_for_channel(self, timeout: int = 60) -> bool:
        """Wait for API execution channel to open and be ready.
        
        Args:
            timeout: Maximum time to wait in seconds (default: 60)
        
        Returns:
            bool: True if channel opened and is ready, False if timeout
        """
        if self.simulation_mode:
            self.logger.info("Simulation: API channel ready")
            return True
        
        # First check if we already have a channel
        if self.current_execution_channel is not None:
            is_alive = False
            if hasattr(self.current_execution_channel, 'IsAlive'):
                is_alive = self.current_execution_channel.IsAlive
            elif hasattr(self.current_execution_channel, 'IsOpen'):
                is_alive = self.current_execution_channel.IsOpen
            
            if is_alive:
                self.logger.info("Execution channel already available")
                await asyncio.sleep(1.0)
                return True
        
        # Also check the list of open channels
        if self._open_execution_channels:
            for channel in self._open_execution_channels:
                is_alive = False
                if hasattr(channel, 'IsAlive'):
                    is_alive = channel.IsAlive
                elif hasattr(channel, 'IsOpen'):
                    is_alive = channel.IsOpen
                
                if is_alive:
                    self.logger.info("Found open execution channel in list")
                    self.current_execution_channel = channel
                    await asyncio.sleep(1.0)
                    return True
        
        self.logger.info(f"Waiting for API channel (timeout: {timeout}s)...")
        self.logger.info(f"Current channel: {self.current_execution_channel}")
        self.logger.info(f"Open channels: {len(self._open_execution_channels)}")
        
        # Try to force update the execution channel from runtime
        if self.runtime:
            try:
                if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                    self.current_execution_channel = self.runtime.GetCurrentExecutionChannel()
                    self.logger.info(f"Forced update of execution channel: {self.current_execution_channel}")
            except Exception as e:
                self.logger.warning(f"Failed to force update execution channel: {e}")

        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check current channel
            if self.current_execution_channel is not None:
                is_alive = False
                if hasattr(self.current_execution_channel, 'IsAlive'):
                    is_alive = self.current_execution_channel.IsAlive
                elif hasattr(self.current_execution_channel, 'IsOpen'):
                    is_alive = self.current_execution_channel.IsOpen
                
                if is_alive:
                    self.logger.info("API channel opened! Waiting for it to be ready...")
                    # Wait a bit to ensure the channel is fully ready to accept commands
                    # Increased wait time to 5 seconds
                    await asyncio.sleep(5.0)
                    
                    # Verify method is still running
                    if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                        if self.runtime.IsMethodRunning():
                            self.logger.info("✓ API channel is ready and method is running!")
                            return True
                        else:
                            self.logger.warning("Channel opened but method is not running (stopped/aborted)")
                    else:
                        # If we can't check, assume it's ready
                        self.logger.info("✓ API channel is ready!")
                        return True
            
            # Also check the list of open channels
            if self._open_execution_channels:
                for channel in self._open_execution_channels:
                    is_alive = False
                    if hasattr(channel, 'IsAlive'):
                        is_alive = channel.IsAlive
                    elif hasattr(channel, 'IsOpen'):
                        is_alive = channel.IsOpen
                    
                    if is_alive:
                        self.logger.info("Found open execution channel!")
                        self.current_execution_channel = channel
                        await asyncio.sleep(2.0)
                        self.logger.info("✓ API channel is ready!")
                        return True
            
            await asyncio.sleep(0.5)
        
        self.logger.warning(f"Timeout waiting for API channel after {timeout}s")
        return False

    def pause_method(self) -> bool:
        """Pause the running method (like C# PauseRun).

        Returns:
            bool: True if successful
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            # Like C#: _runtime.PauseRun();
            self.runtime.PauseRun()
            self._current_state = FluentState.BUSY
            self.logger.info("Method paused")
            return True
        except Exception as e:
            self.logger.error(f"Error pausing method: {e}")
            raise TecanError(f"Failed to pause method: {str(e)}", "VisionX", 1)

    def resume_method(self) -> bool:
        """Resume a paused method (like C# ResumeRun).

        Returns:
            bool: True if successful
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            # Like C#: _runtime.ResumeRun();
            self.runtime.ResumeRun()
            self._current_state = FluentState.RUNNING
            self.logger.info("Method resumed")
            return True
        except Exception as e:
            self.logger.error(f"Error resuming method: {e}")
            raise TecanError(f"Failed to resume method: {str(e)}", "VisionX", 1)

    def stop_method(self) -> bool:
        """Stop the running method (like C# StopMethod).

        Returns:
            bool: True if successful
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            # Like C#: _runtime.StopMethod();
            self.runtime.StopMethod()
            self._current_state = FluentState.READY
            self.logger.info("Method stopped")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping method: {e}")
            raise TecanError(f"Failed to stop method: {str(e)}", "VisionX", 1)

    async def _wait_for_method_completion(self, timeout: float = 300.0):
        """Wait for a running method to complete.

        Args:
            timeout: Maximum time to wait in seconds
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check method status using runtime
                if self.runtime and hasattr(self.runtime, 'GetFluentStatus'):
                    status = self.runtime.GetFluentStatus()
                    status_str = str(status)
                    # Check if method is still running
                    if 'Running' not in status_str and 'Paused' not in status_str:
                        return
                elif hasattr(self.runtime, 'IsMethodRunning'):
                    if not self.runtime.IsMethodRunning():
                        return

                await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"Error checking method status: {e}")
                await asyncio.sleep(0.5)

    # ========================================================================
    # EXECUTION CHANNEL AND COMMAND HANDLING
    # Commands require an open execution channel (from a method with API channel)
    # ========================================================================

    def _get_execution_channel(self):
        """Get the current execution channel for sending commands."""
        # Always try to get from runtime first if available
        if self.runtime:
            try:
                # The runtime might have a method to get the current channel
                if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                    channel = self.runtime.GetCurrentExecutionChannel()
                    if channel:
                        self.current_execution_channel = channel
                        return channel
                elif hasattr(self.runtime, 'ExecutionChannel'):
                    channel = self.runtime.ExecutionChannel
                    if channel:
                        self.current_execution_channel = channel
                        return channel
            except Exception as e:
                self.logger.debug(f"Could not get execution channel from runtime: {e}")

        if self.current_execution_channel is not None:
            return self.current_execution_channel
        
        # If still None, try to find in open channels
        if self._open_execution_channels:
            return self._open_execution_channels[-1]
            
        return None

    def _execute_command(self, command):
        """Execute a command through the execution channel (like C# TriggerCommand)."""
        channel = self._get_execution_channel()
        if channel is not None:
            # Check if channel is alive
            is_alive = False
            if hasattr(channel, 'IsAlive'):
                is_alive = channel.IsAlive
            elif hasattr(channel, 'IsOpen'):
                is_alive = channel.IsOpen
            
            if is_alive:
                # Verify method is still running before sending command
                if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                    if not self.runtime.IsMethodRunning():
                        raise TecanError("Method is not running. Cannot execute commands.", "VisionX", 1)
                
                try:
                    self.logger.info(f"Executing command on channel (IsAlive: {is_alive})")
                    channel.ExecuteCommand(command)
                    self.logger.info("✓ Command executed successfully - robot should move now")
                    return True
                except Exception as e:
                    self.logger.error(f"Error executing command: {e}")
                    import traceback
                    traceback.print_exc()
                    raise TecanError(f"Command execution failed: {str(e)}", "VisionX", 1)
            else:
                self.logger.error(f"Channel exists but is not alive (IsAlive: {is_alive})")
                raise TecanError("Execution channel is not alive. Make sure the method is running.", "VisionX", 1)
        else:
            self.logger.error("No execution channel available")
            raise TecanError("No execution channel available. Run a method with API channel first.", "VisionX", 1)

    # ========================================================================
    # LABWARE MANAGEMENT (like C# AddLabware, RemoveLabware, TransferLabware)
    # ========================================================================

    def add_labware(
        self,
        labware_name: str,
        labware_type: str,
        target_location: str,
        position: int = 0,
        rotation: int = 0,
        has_lid: bool = False,
        barcode: str = ""
    ):
        """Add labware to the worktable (like C# AddLabware).
        
        Args:
            labware_name: Name of the labware
            labware_type: Type of labware
            target_location: Target location on worktable
            position: Position within location (default: 0)
            rotation: Rotation in degrees (default: 0)
            has_lid: Whether labware has a lid (default: False)
            barcode: Barcode if any (default: "")
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Adding labware {labware_name}")
            return
        
        try:
            # Import command class from VisionX API
            from Tecan.VisionX.API.V2.Commands import AddLabware as AddLabwareCmd
            from Tecan.VisionX.API.V2.Implementation.Commands import AddLabware as AddLabwareImpl
            
            # Create command (like C#: ICommand addLabware = new AddLabware(...))
            command = AddLabwareImpl(labware_name, labware_type, target_location, rotation, position, barcode, has_lid)
            self._execute_command(command)
            self.logger.info(f"Added labware {labware_name} to {target_location}")
            
        except ImportError:
            # Fallback: try generic command
            self.logger.warning("AddLabware command class not found, trying generic approach")
            raise NotImplementedError("AddLabware requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to add labware: {e}")
            raise TecanError(f"Failed to add labware: {str(e)}", "VisionX", 1)

    def remove_labware(self, labware_name: str) -> None:
        """Remove labware from worktable (like C# RemoveLabware).
        
        Args:
            labware_name: Name of labware to remove
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Removing labware {labware_name}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import RemoveLabware as RemoveLabwareImpl
            
            command = RemoveLabwareImpl(labware_name)
            self._execute_command(command)
            self.logger.info(f"Removed labware {labware_name}")
            
        except ImportError:
            raise NotImplementedError("RemoveLabware requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to remove labware: {e}")
            raise TecanError(f"Failed to remove labware: {str(e)}", "VisionX", 1)

    def transfer_labware(
        self,
        labware_name: str,
        target_location: str,
        target_position: int = 0,
        only_use_selected_site: bool = True
    ):
        """Transfer labware to a new location (robotic movement).
        
        Args:
            labware_name: Name of the labware to transfer
            target_location: Target location on worktable
            target_position: Position at target (default: 0)
            only_use_selected_site: Only use selected site (default: True)
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Transferring labware {labware_name} to {target_location}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import TransferLabware as TransferLabwareImpl
            
            command = TransferLabwareImpl(labware_name, target_location, target_position, only_use_selected_site)
            self._execute_command(command)
            self.logger.info(f"Transferred labware {labware_name} to {target_location}")
            
        except ImportError:
            raise NotImplementedError("TransferLabware requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to transfer labware: {e}")
            raise TecanError(f"Failed to transfer labware: {str(e)}", "VisionX", 1)

    def transfer_labware_back_to_base(self, labware_name: str):
        """Transfer labware back to its original location.
        
        Args:
            labware_name: Name of the labware to transfer back
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Transferring labware {labware_name} back to base")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import TransferLabware as TransferLabwareImpl
            
            command = TransferLabwareImpl(labware_name)
            self._execute_command(command)
            self.logger.info(f"Transferred labware {labware_name} back to base")
            
        except ImportError:
            raise NotImplementedError("TransferLabware requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to transfer labware: {e}")
            raise TecanError(f"Failed to transfer labware: {str(e)}", "VisionX", 1)

    # ========================================================================
    # TIP HANDLING (like C# GetTips, DropTips)
    # ========================================================================

    def get_tips(
        self,
        airgap_volume: int = 10,
        airgap_speed: int = 70,
        diti_type: str = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
        tip_indices: Optional[List[int]] = None
    ):
        """Get tips (like C# GetTips).
        
        Args:
            airgap_volume: Air gap volume in µL (default: 10)
            airgap_speed: Air gap speed (default: 70)
            diti_type: DiTi type string (default: FCA, 200ul)
            tip_indices: List of tip indices to use (0-7). If None, uses all 8 tips.
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Getting tips {diti_type}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Commands import GenericCommand
            from .xml_commands import make_get_tips_xml
            
            xml = make_get_tips_xml(diti_type, airgap_volume, airgap_speed, tip_indices)
            command = GenericCommand(xml)
            self._execute_command(command)
            self.logger.info(f"Got tips: {diti_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to get tips: {e}")
            raise TecanError(f"Failed to get tips: {str(e)}", "VisionX", 1)

    def drop_tips_to_location(self, labware: str, tip_indices: Optional[List[int]] = None):
        """Drop tips to a specific location (like C# DropTips).
        
        Args:
            labware: Name of the labware to drop tips to (e.g., waste chute)
            tip_indices: List of tip indices to drop. If None, drops all tips.
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Dropping tips to {labware}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Commands import GenericCommand
            from .xml_commands import make_drop_tips_xml
            
            xml = make_drop_tips_xml(labware, tip_indices)
            command = GenericCommand(xml)
            self._execute_command(command)
            self.logger.info(f"Dropped tips to {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to drop tips: {e}")
            raise TecanError(f"Failed to drop tips: {str(e)}", "VisionX", 1)

    # ========================================================================
    # LIQUID HANDLING (Aspirate/Dispense)
    # ========================================================================

    def aspirate_volume(
        self,
        volumes: Union[int, List[int]],
        labware: str,
        liquid_class: str = "Water Test No Detect",
        well_offsets: Optional[Union[int, List[int]]] = None,
        tip_indices: Optional[List[int]] = None
    ):
        """Aspirate liquid (like C# Aspirate command).
        
        Args:
            volumes: Volume(s) to aspirate in µL. Can be single int or list for multi-channel.
            labware: Name of the labware to aspirate from
            liquid_class: Liquid class to use (default: "Water Test No Detect")
            well_offsets: Well offset(s). Can be single int or list. If None, all from well 0.
            tip_indices: List of tip indices to use. If None, uses all tips.
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Aspirating {volumes}µL from {labware}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Commands import GenericCommand
            from .xml_commands import make_aspirate_xml
            
            # Convert single values to lists
            if isinstance(volumes, int):
                volumes = [volumes]
            if isinstance(well_offsets, int):
                well_offsets = [well_offsets]
            if well_offsets is None:
                well_offsets = [0] * len(volumes)
            
            xml = make_aspirate_xml(labware, volumes, liquid_class, well_offsets, tip_indices)
            command = GenericCommand(xml)
            self._execute_command(command)
            self.logger.info(f"Aspirated {volumes}µL from {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to aspirate: {e}")
            raise TecanError(f"Failed to aspirate: {str(e)}", "VisionX", 1)

    def dispense_volume(
        self,
        volumes: Union[int, List[int]],
        labware: str,
        liquid_class: str = "Water Test No Detect",
        well_offsets: Optional[Union[int, List[int]]] = None,
        tip_indices: Optional[List[int]] = None
    ):
        """Dispense liquid (like C# Dispense command).
        
        Args:
            volumes: Volume(s) to dispense in µL. Can be single int or list for multi-channel.
            labware: Name of the labware to dispense to
            liquid_class: Liquid class to use (default: "Water Test No Detect")
            well_offsets: Well offset(s). Can be single int or list. If None, all to well 0.
            tip_indices: List of tip indices to use. If None, uses all tips.
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Dispensing {volumes}µL to {labware}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Commands import GenericCommand
            from .xml_commands import make_dispense_xml
            
            # Convert single values to lists
            if isinstance(volumes, int):
                volumes = [volumes]
            if isinstance(well_offsets, int):
                well_offsets = [well_offsets]
            if well_offsets is None:
                well_offsets = [0] * len(volumes)
            
            xml = make_dispense_xml(labware, volumes, liquid_class, well_offsets, tip_indices)
            command = GenericCommand(xml)
            self._execute_command(command)
            self.logger.info(f"Dispensed {volumes}µL to {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to dispense: {e}")
            raise TecanError(f"Failed to dispense: {str(e)}", "VisionX", 1)

    # ========================================================================
    # GRIPPER OPERATIONS (like C# GetFingers, DropFingers)
    # ========================================================================

    def get_fingers(self, device_alias: str, gripper_fingers: str):
        """Get gripper fingers (like C# GetFingers).
        
        Args:
            device_alias: Device alias
            gripper_fingers: Gripper fingers to get
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Getting fingers {gripper_fingers}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import GetFingers as GetFingersImpl
            
            command = GetFingersImpl(gripper_fingers, device_alias)
            self._execute_command(command)
            self.logger.info(f"Got fingers: {gripper_fingers}")
            
        except ImportError:
            raise NotImplementedError("GetFingers requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to get fingers: {e}")
            raise TecanError(f"Failed to get fingers: {str(e)}", "VisionX", 1)

    def drop_fingers(self, device_alias: str, docking_station: str):
        """Drop gripper fingers (like C# DropFingers).
        
        Args:
            device_alias: Device alias
            docking_station: Docking station to drop to
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Dropping fingers to {docking_station}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import DropFingers as DropFingersImpl
            
            command = DropFingersImpl(docking_station, device_alias)
            self._execute_command(command)
            self.logger.info(f"Dropped fingers to {docking_station}")
            
        except ImportError:
            raise NotImplementedError("DropFingers requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to drop fingers: {e}")
            raise TecanError(f"Failed to drop fingers: {str(e)}", "VisionX", 1)

    # ========================================================================
    # GENERIC COMMAND (like C# GenericCommand)
    # ========================================================================

    def generic_command(self, content: str):
        """Send a generic command (like C# GenericCommand).
        
        Args:
            content: Command content string
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Generic command: {content}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import GenericCommand as GenericCommandImpl
            
            command = GenericCommandImpl(content)
            self._execute_command(command)
            self.logger.info(f"Executed generic command: {content}")
            
        except ImportError:
            raise NotImplementedError("GenericCommand requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to execute generic command: {e}")
            raise TecanError(f"Failed to execute generic command: {str(e)}", "VisionX", 1)

    # ========================================================================
    # SUBROUTINE EXECUTION
    # ========================================================================

    def run_subroutine(self, subroutine_name: str):
        """Run a subroutine (like C# Subroutine).
        
        Args:
            subroutine_name: Name of the subroutine to run
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Running subroutine {subroutine_name}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import Subroutine as SubroutineImpl
            
            command = SubroutineImpl(subroutine_name)
            self._execute_command(command)
            self.logger.info(f"Executed subroutine: {subroutine_name}")
            
        except ImportError:
            raise NotImplementedError("Subroutine requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to execute subroutine: {e}")
            raise TecanError(f"Failed to execute subroutine: {str(e)}", "VisionX", 1)

    # ========================================================================
    # USER PROMPT
    # ========================================================================

    def user_prompt(self, text: str):
        """Show a user prompt (like C# UserPrompt).
        
        Args:
            text: Text to display to the user
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: User prompt: {text}")
            return
        
        try:
            from Tecan.VisionX.API.V2.Implementation.Commands import UserPrompt as UserPromptImpl
            
            command = UserPromptImpl(text)
            self._execute_command(command)
            self.logger.info(f"Displayed user prompt: {text}")
            
        except ImportError:
            raise NotImplementedError("UserPrompt requires Tecan.VisionX.API.V2.Commands")
        except Exception as e:
            self.logger.error(f"Failed to display user prompt: {e}")
            raise TecanError(f"Failed to display user prompt: {str(e)}", "VisionX", 1)

    # ========================================================================
    # VARIABLE MANAGEMENT
    # ========================================================================

    def get_variable_names(self) -> List[str]:
        """Get list of variable names for the current method.
        
        Returns:
            List of variable names
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")
        
        try:
            variables = self.runtime.GetVariableNames()
            if variables:
                return list(variables)
            return []
        except Exception as e:
            self.logger.error(f"Failed to get variable names: {e}")
            return []

    def get_variable_value(self, variable_name: str) -> str:
        """Get the value of a variable.
        
        Args:
            variable_name: Name of the variable
            
        Returns:
            Value of the variable
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")
        
        try:
            return self.runtime.GetVariableValue(variable_name)
        except Exception as e:
            self.logger.error(f"Failed to get variable value: {e}")
            raise TecanError(f"Failed to get variable value: {str(e)}", "VisionX", 1)

    def set_variable_value(self, variable_name: str, value: str):
        """Set the value of a variable.
        
        Args:
            variable_name: Name of the variable
            value: New value for the variable
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")
        
        try:
            self.runtime.SetVariableValue(variable_name, str(value))
            self.logger.info(f"Set variable {variable_name} = {value}")
        except Exception as e:
            self.logger.error(f"Failed to set variable value: {e}")
            raise TecanError(f"Failed to set variable value: {str(e)}", "VisionX", 1)

    # ========================================================================
    # PYLABROBOT INTERFACE IMPLEMENTATIONS
    # These are the standard PyLabRobot backend interface methods
    # ========================================================================

    async def aspirate(
        self,
        ops: List[Aspiration],
        use_channels: List[int]
    ) -> None:
        """Aspirate liquid (PyLabRobot interface).
        
        This wraps the direct API call (aspirate_volume) and converts PyLabRobot
        resource names to FluentControl labware names.
        
        Args:
            ops: List of aspiration operations
            use_channels: Channels to use
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Aspirating using channels {use_channels}")
            return
        
        # Convert PyLabRobot operations to direct API format
        volumes = []
        well_offsets = []
        labware_name = None
        liquid_class = "Water Test No Detect"
        
        for i, channel in enumerate(use_channels):
            if i < len(ops):
                op = ops[i]
                volume = int(op.volume)
                volumes.append(volume)
                
                # Extract labware name from PyLabRobot resource
                # PyLabRobot: plate["A1"] returns a Well object with parent
                if labware_name is None and hasattr(op, 'resource') and op.resource:
                    resource = op.resource
                    
                    # Check if it's a Well object (has parent)
                    if hasattr(resource, 'parent') and resource.parent:
                        # Get parent plate name - this should match FluentControl labware name
                        parent = resource.parent
                        labware_name = parent.name if hasattr(parent, 'name') else None
                        self.logger.debug(f"Extracted labware name from parent: {labware_name}")
                        
                        # Get well offset
                        if hasattr(resource, 'index'):
                            well_offset = resource.index
                        elif hasattr(resource, 'name'):
                            # Well name like "A1" - convert to offset
                            from pyfluent.protocol import well_name_to_offset
                            well_offset = well_name_to_offset(resource.name)
                        else:
                            well_offset = 0
                    elif hasattr(resource, 'name'):
                        # Direct resource (plate, etc.)
                        labware_name = resource.name
                        well_offset = 0
                        self.logger.debug(f"Extracted labware name directly: {labware_name}")
                    else:
                        self.logger.warning(f"Could not extract labware name from resource: {resource}")
                
                # Get liquid class if specified
                if hasattr(op, 'liquid_class') and op.liquid_class:
                    liquid_class = op.liquid_class
                
                well_offsets.append(well_offset)
        
        # Call the direct API method (which already works)
        if volumes and labware_name:
            self.logger.info(f"PyLabRobot -> Direct API: aspirate_volume(volumes={volumes}, labware='{labware_name}', wells={well_offsets})")
            self.aspirate_volume(volumes, labware_name, liquid_class, well_offsets, use_channels)
        else:
            error_msg = f"Cannot aspirate: volumes={volumes}, labware_name={labware_name}"
            self.logger.error(error_msg)
            raise TecanError(error_msg, "VisionX", 1)

    async def dispense(
        self,
        ops: List[Dispense],
        use_channels: List[int]
    ) -> None:
        """Dispense liquid (PyLabRobot interface).
        
        This wraps the direct API call (dispense_volume) and converts PyLabRobot
        resource names to FluentControl labware names.
        
        Args:
            ops: List of dispense operations
            use_channels: Channels to use
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Dispensing using channels {use_channels}")
            return
        
        # Convert PyLabRobot operations to direct API format
        volumes = []
        well_offsets = []
        labware_name = None
        liquid_class = "Water Test No Detect"
        
        for i, channel in enumerate(use_channels):
            if i < len(ops):
                op = ops[i]
                volume = int(op.volume)
                volumes.append(volume)
                
                # Extract labware name from PyLabRobot resource
                if labware_name is None and hasattr(op, 'resource') and op.resource:
                    resource = op.resource
                    
                    # Check if it's a Well object (has parent)
                    if hasattr(resource, 'parent') and resource.parent:
                        # Get parent plate name - this should match FluentControl labware name
                        parent = resource.parent
                        labware_name = parent.name if hasattr(parent, 'name') else None
                        self.logger.debug(f"Extracted labware name from parent: {labware_name}")
                        
                        # Get well offset
                        if hasattr(resource, 'index'):
                            well_offset = resource.index
                        elif hasattr(resource, 'name'):
                            # Well name like "A1" - convert to offset
                            from pyfluent.protocol import well_name_to_offset
                            well_offset = well_name_to_offset(resource.name)
                        else:
                            well_offset = 0
                    elif hasattr(resource, 'name'):
                        # Direct resource (plate, etc.)
                        labware_name = resource.name
                        well_offset = 0
                        self.logger.debug(f"Extracted labware name directly: {labware_name}")
                    else:
                        self.logger.warning(f"Could not extract labware name from resource: {resource}")
                
                # Get liquid class if specified
                if hasattr(op, 'liquid_class') and op.liquid_class:
                    liquid_class = op.liquid_class
                
                well_offsets.append(well_offset)
        
        # Call the direct API method (which already works)
        if volumes and labware_name:
            self.logger.info(f"PyLabRobot -> Direct API: dispense_volume(volumes={volumes}, labware='{labware_name}', wells={well_offsets})")
            self.dispense_volume(volumes, labware_name, liquid_class, well_offsets, use_channels)
        else:
            error_msg = f"Cannot dispense: volumes={volumes}, labware_name={labware_name}"
            self.logger.error(error_msg)
            raise TecanError(error_msg, "VisionX", 1)

    async def pick_up_tips(
        self,
        ops: List[Pickup],
        use_channels: List[int]
    ) -> None:
        """Pick up tips (PyLabRobot interface).
        
        This wraps the direct API call (get_tips) and converts PyLabRobot
        format to direct API format.
        
        Args:
            ops: List of pickup operations
            use_channels: Channels to use
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Picking up tips on channels {use_channels}")
            return
        
        self.logger.info(f"PyLabRobot -> Direct API: pick_up_tips() -> get_tips()")
        
        # Get tips - use default diti_type since PyLabRobot resources don't have this info
        # Extract tip_indices from use_channels
        tip_indices = use_channels if use_channels else None
        self.logger.info(f"Calling direct API: get_tips(diti_type='FCA, 200ul', tip_indices={tip_indices})")
        self.get_tips(
            diti_type="TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",  # Default
            tip_indices=tip_indices
        )

    async def drop_tips(
        self,
        ops: List[Drop],
        use_channels: List[int]
    ) -> None:
        """Drop tips (PyLabRobot interface).
        
        This wraps the direct API call (drop_tips_to_location) and converts PyLabRobot
        format to direct API format.
        
        Args:
            ops: List of drop operations
            use_channels: Channels to use
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Dropping tips on channels {use_channels}")
            return
        
        self.logger.info(f"PyLabRobot -> Direct API: drop_tips() -> drop_tips_to_location()")
        
        # Drop tips - use default waste location
        # Extract tip_indices from use_channels
        tip_indices = use_channels if use_channels else None
        self.logger.info(f"Calling direct API: drop_tips_to_location(labware='MCA Thru Deck Waste Chute', tip_indices={tip_indices})")
        self.drop_tips_to_location(
            labware="MCA Thru Deck Waste Chute with Tip Drop Guide_2",  # Default waste
            tip_indices=tip_indices
        )

    async def aspirate96(self, *args: Any, **kwargs: Any) -> None:
        """Not implemented for VisionX backend."""
        raise NotImplementedError("aspirate96 not yet implemented for VisionX backend")

    async def dispense96(self, *args: Any, **kwargs: Any) -> None:
        """Not implemented for VisionX backend."""
        raise NotImplementedError("dispense96 not yet implemented for VisionX backend")

    async def pick_up_tips96(self, *args: Any, **kwargs: Any) -> None:
        """Not implemented for VisionX backend."""
        raise NotImplementedError("pick_up_tips96 not yet implemented for VisionX backend")

    async def drop_tips96(self, *args: Any, **kwargs: Any) -> None:
        """Not implemented for VisionX backend."""
        raise NotImplementedError("drop_tips96 not yet implemented for VisionX backend")

    async def move_resource(
        self,
        resource: Resource,
        location: Coordinate,
        resource_offset: Optional[Coordinate] = None,
        pickup_distance_from_top: Optional[float] = None,
        get_direction: Optional[Any] = None,
    ) -> None:
        """Move a resource to a new location (PyLabRobot interface).
        
        Args:
            resource: Resource to move
            location: Target location
            resource_offset: Optional offset
            pickup_distance_from_top: Optional pickup distance
            get_direction: Optional grip direction
        """
        if self.simulation_mode:
            self.logger.info(f"Simulation: Moving resource {resource.name}")
            return
        
        # Use Tecan's transfer labware command
        # Note: This is a simplified implementation
        target_location = f"Grid:{int(location.x/100)}/Site:{int(location.y/100)}"
        self.transfer_labware(resource.name, target_location)
