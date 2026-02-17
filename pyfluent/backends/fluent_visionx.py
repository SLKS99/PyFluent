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

# Import constants for default values
from pyfluent.constants import (
    DEFAULT_LIQUID_CLASS,
    DEFAULT_DITI_TYPE,
    DEFAULT_MCA_WASTE,
    DEFAULT_AIRGAP_VOLUME,
    DEFAULT_AIRGAP_SPEED,
)
# Import well conversion function
from pyfluent.protocol import well_name_to_offset

# CRITICAL: Set coinit_flags BEFORE importing comtypes
# This is required for COM event handling to work properly
if not hasattr(sys, 'coinit_flags'):
    sys.coinit_flags = 0  # COINIT_MULTITHREADED

# Import comtypes for proper COM event handling
# This MUST be done after setting coinit_flags
HAS_COMTYPES = False
COMTYPES_CLIENT = None
try:
    import comtypes.client
    HAS_COMTYPES = True
    COMTYPES_CLIENT = comtypes.client
    # Verify it actually works by trying to access it
    if hasattr(comtypes.client, 'CreateObject'):
        # Success - comtypes is fully functional
        pass
    else:
        # comtypes imported but not functional
        HAS_COMTYPES = False
        import warnings
        warnings.warn("comtypes imported but CreateObject not available")
except ImportError as e:
    # Log the error for debugging
    import warnings
    warnings.warn(f"comtypes not available: {e}. COM events will not work properly.")
except Exception as e:
    # Catch any other import errors
    import warnings
    warnings.warn(f"Error importing comtypes: {e}. COM events will not work properly.")
    import traceback
    warnings.warn(traceback.format_exc())

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

# Try to import pylabrobot for compatibility, but provide fallbacks for standalone use
try:
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
    PYLABROBOT_AVAILABLE = True
except ImportError:
    PYLABROBOT_AVAILABLE = False
    # Define minimal fallback classes for standalone use
    class LiquidHandlerBackend:
        """Minimal base class for standalone use."""
        def __init__(self):
            pass

    # Define minimal classes to avoid import errors
    class Resource:
        def __init__(self, name: str = ""):
            self.name = name

    class Coordinate:
        def __init__(self, x: float = 0, y: float = 0, z: float = 0):
            self.x, self.y, self.z = x, y, z

    # Define minimal command classes
    class Aspiration:
        def __init__(self, volume=None, **kwargs):
            self.volume = volume

    class Dispense:
        def __init__(self, volume=None, **kwargs):
            self.volume = volume

    class Pickup:
        def __init__(self, **kwargs):
            pass

    class Drop:
        def __init__(self, **kwargs):
            pass

    class PickupTipRack:
        def __init__(self, **kwargs):
            pass

    class DropTipRack:
        def __init__(self, **kwargs):
            pass

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


class FluentVisionX(LiquidHandlerBackend if PYLABROBOT_AVAILABLE else object):
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
        self._channel_available_event = None
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
        import os

        # Allow explicit override via env var
        env_dll = os.environ.get("TECAN_VISIONX_DLL")
        env_base = os.environ.get("TECAN_VISIONX_BASE")

        # Common paths for the DLL (direct file targets)
        dll_paths = [
            env_dll,
            r"C:\Program Files\Tecan\VisionX\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan\VisionX\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files\Tecan\FluentControl\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan\FluentControl\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan - Copy\fluentcontrol\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan - Copy\FluentControl\API\Tecan.VisionX.API.V2.dll",
            r"C:\Program Files (x86)\Tecan - Copy\VisionX\API\Tecan.VisionX.API.V2.dll",
        ]

        # Base roots for a recursive search if direct hits fail
        search_roots = [
            env_base,
            r"C:\Program Files\Tecan",
            r"C:\Program Files (x86)\Tecan",
            r"C:\ProgramData\Tecan\VisionX",
        ]

        dll_loaded = False
        for dll_path in dll_paths:
            try:
                if dll_path and os.path.exists(dll_path):
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

        # If still not found, recurse through common roots (and optional env base)
        if not dll_loaded:
            try:
                for root in [p for p in search_roots if p]:
                    if not os.path.exists(root):
                        continue
                    for walk_root, _, files in os.walk(root):
                        for file in files:
                            if file == "Tecan.VisionX.API.V2.dll":
                                candidate = os.path.join(walk_root, file)
                                try:
                                    clr.AddReference(candidate)
                                    self.logger.info(f"Loaded DLL (recursive search): {candidate}")
                                    dll_loaded = True
                                    raise StopIteration  # break all loops
                                except Exception as e:
                                    self.logger.debug(f"Could not load {candidate}: {e}")
                        if dll_loaded:
                            break
            except StopIteration:
                pass
            except Exception as e:
                self.logger.debug(f"Recursive search error: {e}")

        # Final fallback: GAC/current dir
        if not dll_loaded:
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
        """Create FluentControl instance.

        IMPORTANT: We use comtypes.client.CreateObject instead of pythonnet to create
        the FluentControl object. This is critical because:
        1. comtypes objects have QueryInterface, which is needed for COM event subscription
        2. pythonnet objects don't have QueryInterface, so event subscription fails
       

        This allows us to properly receive ChannelOpens/ChannelCloses events.
        """
        try:
            # PREFERRED: Use comtypes for proper COM event handling
            # Try to import comtypes if not already available
            global HAS_COMTYPES, COMTYPES_CLIENT
            
            if not HAS_COMTYPES or not COMTYPES_CLIENT:
                try:
                    import comtypes.client
                    HAS_COMTYPES = True
                    COMTYPES_CLIENT = comtypes.client
                    self.logger.info("comtypes imported successfully (late import)")
                except Exception as e:
                    self.logger.warning(f"Could not import comtypes: {e}")
            
            if HAS_COMTYPES and COMTYPES_CLIENT:
                self.logger.info("Creating FluentControl with comtypes (for COM event support)...")
                try:
                    self.fluent_control = COMTYPES_CLIENT.CreateObject('Tecan.FluentControl')
                    self._using_comtypes = True
                    self.logger.info("✓ Created FluentControl instance (comtypes)")
                    return True
                except Exception as e:
                    self.logger.warning(f"Failed to create FluentControl with comtypes: {e}")
                    self.logger.warning("Falling back to pythonnet...")

            # FALLBACK: Use pythonnet (events won't work properly)
            self.logger.warning("Using pythonnet (COM events may not work)")
            from Tecan.VisionX.API.V2 import FluentControl
            self.fluent_control = FluentControl()
            self._using_comtypes = False
            self.logger.info("Created FluentControl instance (pythonnet)")
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
    
    def _handle_recovery_mode(self):
        """Attempt to bypass or continue past recovery mode.

        This dynamically discovers and tries available API methods to skip recovery mode.
        Uses reflection to find methods that might handle recovery/dialogs.
        """
        try:
            self.logger.info("Attempting to handle recovery mode...")

            # Keywords to search for in method names
            recovery_keywords = ['recovery', 'skip', 'dismiss', 'cancel', 'continue', 'bypass', 'accept', 'confirm', 'ok']
            dialog_keywords = ['dialog', 'message', 'prompt', 'alert', 'confirm']

            # First, try specific known recovery methods that might accept/continue
            if self.runtime:
                # Try specific methods that might accept recovery
                # Based on VisionX logs showing RecoveryHandler and MethodRecovery
                specific_methods = [
                    ('AcceptRecovery', None),
                    ('ContinueFromRecovery', None),
                    ('ConfirmRecovery', None),
                    ('AcceptRecoveryDialog', None),
                    ('ContinueRecovery', None),
                    ('SkipRecoveryDialog', None),
                    ('DismissRecoveryDialog', None),
                    ('AcceptDialog', None),
                    ('ConfirmDialog', None),
                    ('OK', None),
                    ('Accept', None),
                    ('Continue', None),
                    # Additional methods based on VisionX components
                    ('ConfirmRecoveryDialog', None),
                    ('AcceptRecoveryMode', None),
                    ('ContinueRecoveryMode', None),
                    ('SkipRecoveryMode', None),
                    ('DismissRecoveryMode', None),
                    ('RecoveryAccepted', None),
                    ('RecoveryConfirmed', None),
                    ('RecoveryContinue', None),
                ]

                for method_name, args in specific_methods:
                    if hasattr(self.runtime, method_name):
                        try:
                            method = getattr(self.runtime, method_name)
                            if args is None:
                                method()
                                self.logger.info(f"✓ Called Runtime.{method_name}()")
                            else:
                                method(*args)
                                self.logger.info(f"✓ Called Runtime.{method_name}{args}")
                        except Exception as e:
                            self.logger.debug(f"Could not call Runtime.{method_name}: {e}")

            # Try runtime methods - dynamically discover methods
            if self.runtime:
                self.logger.info("Checking RuntimeController for recovery/dialog methods...")
                runtime_methods = [m for m in dir(self.runtime) if not m.startswith('_')]

                for method_name in runtime_methods:
                    method_lower = method_name.lower()
                    # Check if method name contains recovery-related keywords
                    if any(keyword in method_lower for keyword in recovery_keywords + dialog_keywords):
                        # Skip if we already tried this specific method
                        if method_name in [m[0] for m in specific_methods]:
                            continue

                        try:
                            method = getattr(self.runtime, method_name)
                            if callable(method):
                                # Try calling with no arguments first
                                try:
                                    method()
                                    self.logger.info(f"✓ Called Runtime.{method_name}()")
                                except TypeError:
                                    # Method might need arguments, try with boolean True (accept/continue)
                                    try:
                                        method(True)
                                        self.logger.info(f"✓ Called Runtime.{method_name}(True)")
                                    except TypeError:
                                        # Method might need specific arguments, skip it
                                        pass
                        except Exception as e:
                            self.logger.debug(f"Could not call Runtime.{method_name}: {e}")

            # Try FluentControl methods - dynamically discover methods
            if self.fluent_control:
                self.logger.info("Checking FluentControl for recovery/dialog methods...")

                # First try specific known methods
                fc_specific_methods = [
                    ('AcceptRecovery', None),
                    ('ContinueFromRecovery', None),
                    ('ConfirmRecovery', None),
                    ('AcceptRecoveryDialog', None),
                    ('ContinueRecovery', None),
                    ('SkipRecoveryDialog', None),
                    ('DismissRecoveryDialog', None),
                    ('AcceptDialog', None),
                    ('ConfirmDialog', None),
                    ('OK', None),
                    ('Accept', None),
                    ('Continue', None),
                    # Additional methods based on VisionX components
                    ('ConfirmRecoveryDialog', None),
                    ('AcceptRecoveryMode', None),
                    ('ContinueRecoveryMode', None),
                    ('SkipRecoveryMode', None),
                    ('DismissRecoveryMode', None),
                    ('RecoveryAccepted', None),
                    ('RecoveryConfirmed', None),
                    ('RecoveryContinue', None),
                ]

                for method_name, args in fc_specific_methods:
                    if hasattr(self.fluent_control, method_name):
                        try:
                            method = getattr(self.fluent_control, method_name)
                            if args is None:
                                method()
                                self.logger.info(f"✓ Called FluentControl.{method_name}()")
                            else:
                                method(*args)
                                self.logger.info(f"✓ Called FluentControl.{method_name}{args}")
                        except Exception as e:
                            self.logger.debug(f"Could not call FluentControl.{method_name}: {e}")

                fc_methods = [m for m in dir(self.fluent_control) if not m.startswith('_')]

                for method_name in fc_methods:
                    method_lower = method_name.lower()
                    # Check if method name contains recovery-related keywords
                    if any(keyword in method_lower for keyword in recovery_keywords + dialog_keywords):
                        # Skip if we already tried this specific method
                        if method_name in [m[0] for m in fc_specific_methods]:
                            continue

                        try:
                            method = getattr(self.fluent_control, method_name)
                            if callable(method):
                                # Try calling with no arguments first
                                try:
                                    method()
                                    self.logger.info(f"✓ Called FluentControl.{method_name}()")
                                except TypeError:
                                    # Method might need arguments, try with boolean True (accept/continue)
                                    try:
                                        method(True)
                                        self.logger.info(f"✓ Called FluentControl.{method_name}(True)")
                                    except TypeError:
                                        # Method might need specific arguments, skip it
                                        pass
                        except Exception as e:
                            self.logger.debug(f"Could not call FluentControl.{method_name}: {e}")

                # Try Application methods if available
                if hasattr(self.fluent_control, 'Application'):
                    try:
                        app = self.fluent_control.Application
                        self.logger.info("Checking Application for recovery/dialog methods...")

                        # Specific Application methods
                        app_specific_methods = [
                            ('AcceptRecovery', None),
                            ('ContinueFromRecovery', None),
                            ('ConfirmRecovery', None),
                            ('AcceptRecoveryDialog', None),
                            ('ContinueRecovery', None),
                            ('SkipRecoveryDialog', None),
                            ('DismissRecoveryDialog', None),
                            ('DismissAllDialogs', None),
                            ('AcceptDialog', None),
                            ('ConfirmDialog', None),
                            ('OK', None),
                            ('Accept', None),
                            ('Continue', None),
                            # Additional methods based on VisionX components
                            ('ConfirmRecoveryDialog', None),
                            ('AcceptRecoveryMode', None),
                            ('ContinueRecoveryMode', None),
                            ('SkipRecoveryMode', None),
                            ('DismissRecoveryMode', None),
                            ('RecoveryAccepted', None),
                            ('RecoveryConfirmed', None),
                            ('RecoveryContinue', None),
                        ]

                        for method_name, args in app_specific_methods:
                            if hasattr(app, method_name):
                                try:
                                    method = getattr(app, method_name)
                                    if args is None:
                                        method()
                                        self.logger.info(f"✓ Called Application.{method_name}()")
                                    else:
                                        method(*args)
                                        self.logger.info(f"✓ Called Application.{method_name}{args}")
                                except Exception as e:
                                    self.logger.debug(f"Could not call Application.{method_name}: {e}")

                        app_methods = [m for m in dir(app) if not m.startswith('_')]

                        for method_name in app_methods:
                            method_lower = method_name.lower()
                            if any(keyword in method_lower for keyword in recovery_keywords + dialog_keywords):
                                # Skip if we already tried this specific method
                                if method_name in [m[0] for m in app_specific_methods]:
                                    continue

                                try:
                                    method = getattr(app, method_name)
                                    if callable(method):
                                        try:
                                            method()
                                            self.logger.info(f"✓ Called Application.{method_name}()")
                                        except TypeError:
                                            # Method might need arguments, try with boolean True
                                            try:
                                                method(True)
                                                self.logger.info(f"✓ Called Application.{method_name}(True)")
                                            except TypeError:
                                                pass
                                except Exception as e:
                                    self.logger.debug(f"Could not call Application.{method_name}: {e}")
                    except Exception as e:
                        self.logger.debug(f"Could not access Application: {e}")

            # Small delay to let recovery mode be dismissed
            time.sleep(2)
            self.logger.info("Recovery mode handling attempted")

        except Exception as e:
            self.logger.warning(f"Could not handle recovery mode: {e}")
            # Don't fail - recovery might not be dismissible via API
    
    async def wait_for_recovery_mode_dismissed(self, timeout: int = 300) -> bool:
        """Wait for recovery mode to be automatically or manually dismissed.

        This method periodically tries to accept/continue recovery while waiting.

        Args:
            timeout: Maximum time to wait in seconds (default: 300 = 5 minutes)

        Returns:
            bool: True if recovery mode was dismissed, False if timeout
        """
        if not self.runtime:
            return True  # Can't check, assume OK

        self.logger.info("Waiting for recovery mode to be dismissed...")
        self.logger.info("Attempting automatic recovery acceptance...")

        start_time = time.time()
        last_auto_attempt = 0

        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time

            try:
                if hasattr(self.runtime, 'GetFluentStatus'):
                    status = self.runtime.GetFluentStatus()
                    status_str = str(status)

                    # Check if still in recovery mode
                    if "Recovery" not in status_str and "recovery" not in status_str.lower():
                        self.logger.info("✓ Recovery mode dismissed!")
                        await asyncio.sleep(1)  # Brief wait to ensure it's fully dismissed
                        return True

                    # Try automatic acceptance every 5 seconds
                    if elapsed - last_auto_attempt >= 5:
                        last_auto_attempt = elapsed
                        self.logger.info("Attempting to automatically accept recovery...")
                        self._handle_recovery_mode()

            except Exception as e:
                self.logger.debug(f"Error checking recovery status: {e}")

            await asyncio.sleep(2)  # Check every 2 seconds
            elapsed = int(time.time() - start_time)
            if elapsed % 15 == 0:  # More frequent status updates
                self.logger.info(f"Still waiting for recovery mode dismissal... ({elapsed}s / {timeout}s)")
                self.logger.info("If automatic acceptance doesn't work, please manually click 'Continue' or 'OK'")

        self.logger.warning(f"Timeout waiting for recovery mode dismissal after {timeout}s")
        return False

    def _register_api_callback(self, channel=None):
        """Register an API callback function.

        This can be called with a channel object or without one (for runtime-based registration).
        When a method with API Channel action runs, FluentControl expects a callback to be registered.
        """
        try:
            self.logger.info("Attempting to register API callback...")

            # Create a callback function
            def api_callback(command_data):
                try:
                    self.logger.info("=" * 60)
                    self.logger.info("API CALLBACK RECEIVED!")
                    self.logger.info(f"Command data: {command_data}")
                    self.logger.info("=" * 60)
                    # For now, just acknowledge - we'll implement command processing later
                    return "OK"
                except Exception as e:
                    self.logger.error(f"Error processing API command: {e}")
                    return "ERROR"

            callback_registered = False

            # If we have a channel, try channel-based registration
            if channel is not None:
                self.logger.info("Trying channel-based callback registration...")

                # Method 1: Direct registration on channel
                if hasattr(channel, 'RegisterApiCallback'):
                    channel.RegisterApiCallback(api_callback)
                    self.logger.info("SUCCESS: Registered API callback via channel RegisterApiCallback")
                    callback_registered = True

                # Method 2: Set callback property
                elif hasattr(channel, 'ApiCallback'):
                    channel.ApiCallback = api_callback
                    self.logger.info("SUCCESS: Set API callback via channel ApiCallback property")
                    callback_registered = True

                # Method 3: Try generic registration methods on channel
                if not callback_registered:
                    for method_name in ['RegisterCallback', 'SetCallback', 'AddCallback', 'SetApiCallback']:
                        if hasattr(channel, method_name):
                            getattr(channel, method_name)(api_callback)
                            self.logger.info(f"SUCCESS: Registered API callback via channel {method_name}")
                            callback_registered = True
                            break

            # If no channel or channel registration failed, try runtime-based registration
            if not callback_registered and self.runtime:
                self.logger.info("Trying runtime-based callback registration...")

                # Method 4: Register on runtime
                if hasattr(self.runtime, 'RegisterApiCallback'):
                    if channel is not None:
                        self.runtime.RegisterApiCallback(channel, api_callback)
                    else:
                        # Try without channel parameter
                        try:
                            self.runtime.RegisterApiCallback(api_callback)
                        except:
                            # Try with current execution channel if available
                            if self.current_execution_channel:
                                self.runtime.RegisterApiCallback(self.current_execution_channel, api_callback)
                            else:
                                raise
                    self.logger.info("SUCCESS: Registered API callback via runtime RegisterApiCallback")
                    callback_registered = True

                # Method 5: Try setting callback on runtime properties
                elif hasattr(self.runtime, 'ApiCallback'):
                    self.runtime.ApiCallback = api_callback
                    self.logger.info("SUCCESS: Set API callback via runtime ApiCallback property")
                    callback_registered = True

            # Method 6: Try FluentControl-based registration
            if not callback_registered and self.fluent_control:
                self.logger.info("Trying FluentControl-based callback registration...")

                if hasattr(self.fluent_control, 'RegisterApiCallback'):
                    if channel is not None:
                        self.fluent_control.RegisterApiCallback(channel, api_callback)
                    else:
                        self.fluent_control.RegisterApiCallback(api_callback)
                    self.logger.info("SUCCESS: Registered API callback via FluentControl RegisterApiCallback")
                    callback_registered = True

                elif hasattr(self.fluent_control, 'ApiCallback'):
                    self.fluent_control.ApiCallback = api_callback
                    self.logger.info("SUCCESS: Set API callback via FluentControl ApiCallback property")
                    callback_registered = True

            if callback_registered:
                self.logger.info("✓ API callback successfully registered!")
                self.logger.info("The API channel should now be operational.")
                self.logger.info("FluentControl should stop asking to 'register api callback'.")
                return True
            else:
                self.logger.warning("Could not find any method to register API callback")
                self.logger.warning("Available runtime methods:")
                if self.runtime:
                    runtime_methods = [m for m in dir(self.runtime) if not m.startswith('_')]
                    for method in sorted(runtime_methods)[:20]:  # Show first 20
                        self.logger.warning(f"  {method}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to register API callback: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _subscribe_to_runtime_events(self):
        """Subscribe to runtime controller events using COM event handling."""
        if not self.runtime:
            return

        try:
            # Use comtypes to properly subscribe to runtime events
            # This creates a proper COM event sink for all runtime events
            # Try to use COMTYPES_CLIENT if available, otherwise import
            global HAS_COMTYPES, COMTYPES_CLIENT
            comtypes_client = COMTYPES_CLIENT if HAS_COMTYPES and COMTYPES_CLIENT else None
            if not comtypes_client:
                try:
                    import comtypes
                    import comtypes.client
                    comtypes_client = comtypes.client
                    HAS_COMTYPES = True
                    COMTYPES_CLIENT = comtypes.client
                    self.logger.info("comtypes imported for event subscription (late import)")
                except Exception as e:
                    self.logger.warning(f"Could not import comtypes for event subscription: {e}")
                    raise

            # CRITICAL: Set coinit_flags BEFORE importing comtypes.client
            # This must be done at module level, but we try here as well
            import sys
            if not hasattr(sys, 'coinit_flags'):
                sys.coinit_flags = 0  # COINIT_MULTITHREADED

            self.logger.info("Setting up COM event handlers for runtime...")

            # Create a COM event handler class
            class RuntimeEventHandler:
                def __init__(self, backend):
                    self.backend = backend

                def ChannelOpens(self, this, channel):
                    """Called when an execution channel opens."""
                    try:
                        self.backend.logger.info("=" * 60)
                        self.backend.logger.info("EXECUTION CHANNEL OPENED!")
                        self.backend.logger.info(f"Channel: {channel}")
                        self.backend.logger.info("=" * 60)

                        # Store the channel
                        self.backend.current_execution_channel = channel
                        if channel not in self.backend._open_execution_channels:
                            self.backend._open_execution_channels.append(channel)

                        # REGISTER API CALLBACK - This is crucial!
                        # When channel opens, we need to register a callback function
                        # that FluentControl can call to execute commands
                        self.backend._register_api_callback(channel)

                        # Set the event to signal channel is ready
                        if hasattr(self.backend, '_channel_available_event') and self.backend._channel_available_event:
                            self.backend._channel_available_event.set()

                    except Exception as e:
                        self.backend.logger.error(f"Error in channel opens handler: {e}")

                def ChannelCloses(self, this, channel):
                    """Called when an execution channel closes."""
                    try:
                        self.backend.logger.info("Execution channel closed: %s", channel)
                        # Remove from our list
                        with contextlib.suppress(ValueError):
                            self.backend._open_execution_channels.remove(channel)
                        # Clear current channel if it's the one that closed
                        if self.backend.current_execution_channel == channel:
                            self.backend.current_execution_channel = None
                            self.backend.logger.warning("Current execution channel closed!")
                    except Exception as e:
                        self.backend.logger.error(f"Error in channel closes handler: {e}")

                def Error(self, this, message):
                    """Called when a runtime error occurs."""
                    try:
                        error_msg = str(message.Data) if hasattr(message, 'Data') else str(message)
                        self.backend.logger.error("=" * 60)
                        self.backend.logger.error(f"RUNTIME ERROR: {error_msg}")
                        self.backend.logger.error("=" * 60)
                        self.backend._last_error = error_msg
                    except Exception as e:
                        self.backend.logger.error(f"Error in error handler: {e}")

                def ModeChanged(self, this, old_mode, new_mode):
                    """Called when runtime mode changes."""
                    try:
                        self.backend.logger.info(f"Runtime mode changed: {old_mode} -> {new_mode}")
                    except Exception as e:
                        self.backend.logger.error(f"Error in mode changed handler: {e}")

                def ProgressChanged(self, this, value):
                    """Called when progress changes."""
                    try:
                        self.backend.logger.debug(f"Progress changed: {value}")
                    except Exception as e:
                        self.backend.logger.error(f"Error in progress handler: {e}")

                def EnterReadyMode(self, this):
                    """Called when entering ready mode."""
                    try:
                        self.backend.logger.info("Entered ready mode")
                    except Exception as e:
                        self.backend.logger.error(f"Error in ready mode handler: {e}")

            # Create the event handler
            event_handler = RuntimeEventHandler(self)

            # Subscribe to runtime events using comtypes
            # This creates a proper COM event sink
            # Like UniteLabs, we need to get the module first to get the interface
            try:
                # Get the VisionX API module to access the interface definitions
                self._visionx_module = comtypes_client.GetModule(("{86977DF6-167E-4684-AC6B-672CBE095C9B}", 1, 0))
                self._runtime_events = comtypes_client.GetEvents(
                    self.runtime, event_handler, interface=self._visionx_module.IRuntimeControllerEvents
                )
                self.logger.info("SUCCESS: Subscribed to runtime COM events with interface")
            except Exception as e:
                self.logger.warning(f"Could not get interface, trying without: {e}")
                self._runtime_events = comtypes_client.GetEvents(self.runtime, event_handler)
                self.logger.info("SUCCESS: Subscribed to runtime COM events (no interface)")

            self.logger.info("SUCCESS: ChannelOpens/ChannelCloses events will be monitored")

        except ImportError:
            self.logger.warning("comtypes not available, falling back to basic event subscription")

            # Fallback: try basic .NET-style event subscription
            try:
                # Subscribe to ChannelOpens event
                if hasattr(self.runtime, 'ChannelOpens'):
                    def on_channel_opens(sender, channel):
                        self.logger.info("✓ Execution channel opened!")
                        self.current_execution_channel = channel
                        if channel not in self._open_execution_channels:
                            self._open_execution_channels.append(channel)
                        if hasattr(self, '_channel_available_event') and self._channel_available_event:
                            self._channel_available_event.set()

                    self.runtime.ChannelOpens += on_channel_opens
                    self._channel_opens_handler = on_channel_opens
                    self.logger.info("✓ Subscribed to ChannelOpens event (fallback)")

                # Subscribe to Error event
                if hasattr(self.runtime, 'Error'):
                    def on_error(sender, args):
                        error_msg = str(args.Data) if hasattr(args, 'Data') else str(args)
                        self.logger.error(f"Runtime error: {error_msg}")
                        self._last_error = error_msg

                    self.runtime.Error += on_error
                    self._error_handler = on_error
                    self.logger.info("✓ Subscribed to Error event (fallback)")

            except Exception as e:
                self.logger.error(f"Failed to subscribe to events: {e}")
                self.logger.warning("Runtime event subscription disabled")

        except Exception as e:
            self.logger.error(f"Failed to set up runtime events: {e}")
            self.logger.warning("Runtime event subscription disabled")
            
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

        # Initialize connection (run in thread to avoid blocking)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._connect_to_visionx)

        # Start event pump task for COM events (like UniteLabs does)
        self._event_pump_task = asyncio.create_task(self._pump_com_events())

        # Enable tracking if requested
        if self.with_tracking:
            try:
                from pylabrobot.resources import set_tip_tracking, set_volume_tracking
                set_tip_tracking(True)
                set_volume_tracking(True)
            except ImportError:
                # pylabrobot not available, skip tracking setup
                pass
            set_tip_tracking(True)
            set_volume_tracking(True)

        # Initialize visualization if requested
        if self.with_visualization:
            try:
                from pylabrobot.visualizer import Visualizer
                self.visualizer = Visualizer(resource=self)
                await self.visualizer.setup()
            except ImportError:
                # pylabrobot not available, skip visualizer setup
                self.logger.warning("pylabrobot visualizer not available - 3D visualization disabled")
                self.visualizer = None

        self._initialized = True
        self.logger.info("Fluent VisionX backend setup complete")

    async def _pump_com_events(self):
        """Continuously pump COM events to receive ChannelOpens/ChannelCloses events.

        This is critical for receiving events from FluentControl. Without this,
        the ChannelOpens event will never be received and we won't know when
        the API channel is ready.

        UniteLabs does this same thing in their subscribe_events method.
        """
        # Try to import comtypes if not already available
        global HAS_COMTYPES, COMTYPES_CLIENT
        comtypes_client = None
        if HAS_COMTYPES and COMTYPES_CLIENT:
            comtypes_client = COMTYPES_CLIENT
        else:
            try:
                import comtypes.client
                comtypes_client = comtypes.client
                HAS_COMTYPES = True
                COMTYPES_CLIENT = comtypes.client
                self.logger.info("comtypes imported for event pump (late import)")
            except Exception as e:
                self.logger.warning(f"comtypes not available - COM event pump disabled: {e}")
                self.logger.warning("Events may not be received. Install with: pip install comtypes")
                return

        if not comtypes_client:
            self.logger.warning("comtypes not available - COM event pump disabled. Events may not be received.")
            return

        try:
            self.logger.info("Starting COM event pump...")

            while self._initialized or not self._initialized:  # Run until explicitly stopped
                try:
                    comtypes_client.PumpEvents(timeout=0)
                except Exception as e:
                    self.logger.debug(f"Event pump error (may be normal): {e}")
                await asyncio.sleep(0.5)  # Pump events every 500ms

        except asyncio.CancelledError:
            self.logger.info("COM event pump stopped")
        except Exception as e:
            self.logger.error(f"COM event pump failed: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())

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
                self.logger.info("Simulation mode requested - checking FluentControl status...")

                # Check if FluentControl is already running
                try:
                    is_running = self.fluent_control.IsRunning()
                    is_attached = self.fluent_control.IsAttached()
                    self.logger.info(f"FluentControl running: {is_running}, attached: {is_attached}")

                    if is_running and is_attached:
                        self.logger.info("FluentControl already running and attached - using existing instance")
                        # If already running, we don't need to start it
                        # Just ensure it's in simulation mode if possible
                        startup_success = True
                    else:
                        # Try to start FluentControl in simulation mode
                        self.logger.info("Starting FluentControl in simulation mode...")
                        startup_success = False

                        # First try StartAndLogin with simulation option
                        try:
                            if hasattr(self.fluent_control, 'StartAndLogin'):
                                # StartAndLogin expects (username, password, startupOptions)
                                # where startupOptions is an enum/int: 0=None, 1=Simulation, 2=Hidden
                                self.fluent_control.StartAndLogin("Admin", "Admin", 1)  # 1 = Simulation
                                self.logger.info("✓ Called StartAndLogin() with simulation mode")
                                startup_success = True
                        except Exception as e:
                            self.logger.warning(f"StartAndLogin failed: {e}")

                        # If StartAndLogin failed, try StartInSimulationMode
                        if not startup_success:
                            try:
                                if hasattr(self.fluent_control, 'StartInSimulationMode'):
                                    self.fluent_control.StartInSimulationMode()
                                    self.logger.info("✓ Called StartInSimulationMode()")
                                    startup_success = True
                            except Exception as e:
                                self.logger.warning(f"StartInSimulationMode failed: {e}")

                        # If simulation startup failed, try regular StartOrAttach
                        if not startup_success:
                            self.logger.info("Trying StartOrAttach as fallback...")
                            self.fluent_control.StartOrAttach()
                            self.logger.info("✓ Called StartOrAttach() as fallback")
                            startup_success = True

                except Exception as e:
                    self.logger.error(f"Failed to check/start FluentControl: {e}")
                    raise TecanError(f"Failed to start FluentControl in simulation mode: {e}", "VisionX", 1)

                # Give FluentControl time to initialize
                if startup_success:
                    self.logger.info("Waiting for FluentControl to initialize...")
                    time.sleep(5)  # Wait for startup

                    # Try to show the window and 3D viewer
                    try:
                        if hasattr(self.fluent_control, 'Application'):
                            app = self.fluent_control.Application
                            if hasattr(app, 'Show'):
                                app.Show()
                                self.logger.info("Called Application.Show()")
                        if hasattr(self.fluent_control, 'Show'):
                            self.fluent_control.Show()
                            self.logger.info("Called FluentControl.Show()")
                    except Exception as e:
                        self.logger.debug(f"Could not show window: {e}")

                    # Show 3D viewer
                    self.show_3d_viewer()
            elif self.username and self.password:
                # Login mode: start with credentials
                self.logger.info(f"Starting with login: {self.username}")
                # Call StartAndLogin() first - this actually starts FluentControl
                if hasattr(self.fluent_control, 'StartAndLogin'):
                    self.fluent_control.StartAndLogin(self.username, self.password, 0)  # 0 = None
                    self.logger.info("Called StartAndLogin() - this should start FluentControl")
                # Then attach
                if hasattr(self.fluent_control, 'StartOrAttach'):
                    self.fluent_control.StartOrAttach()
                    self.logger.info("Called StartOrAttach() to attach")

                # After StartAndLogin(), the GUI should appear
                # Give it a moment, then ensure window is visible
                time.sleep(3)  # Give FluentControl time to show window

                # Try to show/bring to front the window
                try:
                    if hasattr(self.fluent_control, 'Application'):
                        app = self.fluent_control.Application
                        if hasattr(app, 'Show'):
                            app.Show()
                            self.logger.info("Called Application.Show() to display window")
                        if hasattr(app, 'BringToFront'):
                            app.BringToFront()
                            self.logger.info("Called Application.BringToFront()")

                    # Direct methods on FluentControl
                    if hasattr(self.fluent_control, 'Show'):
                        self.fluent_control.Show()
                        self.logger.info("Called Show() to display window")
                    if hasattr(self.fluent_control, 'BringToFront'):
                        self.fluent_control.BringToFront()
                        self.logger.info("Called BringToFront()")
                    if hasattr(self.fluent_control, 'Activate'):
                        self.fluent_control.Activate()
                        self.logger.info("Called Activate()")
                except Exception as e:
                    self.logger.debug(f"Could not show/activate window: {e}")
            elif self.username and self.password:
                self.logger.info(f"Starting with login: {self.username}")
                # Call StartAndLogin() first - this actually starts FluentControl
                if hasattr(self.fluent_control, 'StartAndLogin'):
                    self.fluent_control.StartAndLogin(self.username, self.password, 0)  # 0 = None
                    self.logger.info("Called StartAndLogin() - this should start FluentControl")
                # Then attach
                if hasattr(self.fluent_control, 'StartOrAttach'):
                    self.fluent_control.StartOrAttach()
                    self.logger.info("Called StartOrAttach() to attach")

                # After StartAndLogin(), the GUI should appear
                # Give it a moment, then ensure window is visible
                time.sleep(3)  # Give FluentControl time to show window

                # Try to show/bring to front the window
                try:
                    if hasattr(self.fluent_control, 'Application'):
                        app = self.fluent_control.Application
                        if hasattr(app, 'Show'):
                            app.Show()
                            self.logger.info("Called Application.Show() to display window")
                        if hasattr(app, 'BringToFront'):
                            app.BringToFront()
                            self.logger.info("Called Application.BringToFront()")

                    # Direct methods on FluentControl
                    if hasattr(self.fluent_control, 'Show'):
                        self.fluent_control.Show()
                        self.logger.info("Called Show() to display window")
                    if hasattr(self.fluent_control, 'BringToFront'):
                        self.fluent_control.BringToFront()
                        self.logger.info("Called BringToFront()")
                    if hasattr(self.fluent_control, 'Activate'):
                        self.fluent_control.Activate()
                        self.logger.info("Called Activate()")
                except Exception as e:
                    self.logger.debug(f"Could not show/activate window: {e}")
            elif self.username and self.password:
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
            else:
                # Default case: just attach to existing instance or start new one
                self.logger.info("Default mode: attaching to FluentControl...")
                self.fluent_control.StartOrAttach()
                self.logger.info("✓ Called StartOrAttach()")
                time.sleep(2)

            # Wait for FluentControl to be fully started and initialized
            # (like C# code waits for runtime to be ready)
            self.logger.info("Waiting for FluentControl to start and initialize...")
            
            # First, verify FluentControl process is actually running
            # StartOrAttach should start it if not running, but let's verify
            # Allow up to 2 minutes for startup (FluentControl can be slow)
            process_started = False
            for i in range(120):  # Wait up to 120 seconds (2 minutes) for process to start
                try:
                    if hasattr(self.fluent_control, 'IsRunning'):
                        if self.fluent_control.IsRunning():
                            self.logger.info("FluentControl process is now running")
                            process_started = True
                            break
                except Exception as e:
                    self.logger.debug(f"Error checking IsRunning: {e}")
                
                time.sleep(1)
                if i % 10 == 0:
                    self.logger.info(f"Waiting for FluentControl to start... ({i}s / 120s)")
            
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
                if runtime_available_event.wait(timeout=120):  # Wait up to 120 seconds (2 minutes) for event
                    self.logger.info("RuntimeIsAvailable event received!")
                else:
                    self.logger.warning("RuntimeIsAvailable event not received within timeout")
            
            # Try to get runtime (either from event or by polling)
            # Allow up to 2 minutes for runtime to become available
            for i in range(120):  # Wait up to 120 seconds (2 minutes)
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
                if i % 10 == 0:
                    self.logger.info(f"Still waiting for runtime... ({i}s / 120s)")

            if not runtime_available:
                self.logger.warning("Runtime not available after waiting - continuing anyway")
                # Don't raise error, just log warning - might work later

            # Handle EditMode and API channel setup differently for simulation vs regular mode
            if self.runtime is not None:
                if self.simulation_mode:
                    # In simulation mode, skip EditMode waiting and just handle recovery if needed
                    self.logger.info("Simulation mode: Skipping EditMode wait (API channels open when methods run)")
                    try:
                        if hasattr(self.runtime, 'GetFluentStatus'):
                            status = self.runtime.GetFluentStatus()
                            status_str = str(status)

                            # Check for recovery mode and handle it
                            if "Recovery" in status_str or "recovery" in status_str.lower():
                                self.logger.warning("Recovery mode detected! Attempting to bypass...")
                                self._handle_recovery_mode()
                                # Brief wait for recovery to be dismissed
                                time.sleep(2)
                    except:
                        pass
                else:
                    # Regular mode: wait for EditMode
                    self.logger.info("Waiting for EditMode...")
                    edit_mode_reached = False
                    recovery_detected = False
                    for i in range(30):  # Reduced wait time for regular mode
                        try:
                            if hasattr(self.runtime, 'GetFluentStatus'):
                                status = self.runtime.GetFluentStatus()
                                status_str = str(status)

                                # Check for recovery mode
                                if "Recovery" in status_str or "recovery" in status_str.lower():
                                    if not recovery_detected:
                                        recovery_detected = True
                                        self.logger.warning("Recovery mode detected! Attempting to bypass...")
                                        self._handle_recovery_mode()

                                # Check if in EditMode
                                if str(status) == "EditMode" or "EditMode" in str(status):
                                    edit_mode_reached = True
                                    break
                        except:
                            pass
                        time.sleep(1)
                        if i % 10 == 0:
                            self.logger.info(f"Still waiting for EditMode... ({i}s)")

                    if not edit_mode_reached:
                        self.logger.warning("EditMode not reached, but continuing...")

                    # Try to prepare a method that opens an API channel (like C# PrepareMethodRun)
                    # This might help establish the connection better
                    try:
                        self.logger.info("Attempting to prepare a method to open API channel...")
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

            # Try to open/show 3D viewer after connection
            if self.simulation_mode:
                self.show_3d_viewer()
                # Enable animation and set reasonable speed
                self.enable_animation(True)
                self.set_simulation_speed(1.0)

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

    def show_3d_viewer(self) -> bool:
        """Open/show the 3D viewer/simulator window through the API.

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info("Attempting to open/show 3D viewer...")

            # Try various methods to show the 3D viewer
            if self.fluent_control:
                # Try Application methods
                if hasattr(self.fluent_control, 'Application'):
                    app = self.fluent_control.Application
                    if hasattr(app, 'Show'):
                        app.Show()
                        self.logger.info("Called Application.Show()")
                    if hasattr(app, 'ShowSimulator'):
                        app.ShowSimulator()
                        self.logger.info("Called Application.ShowSimulator()")
                    if hasattr(app, 'Show3DViewer'):
                        app.Show3DViewer()
                        self.logger.info("Called Application.Show3DViewer()")
                    if hasattr(app, 'Show3DSimulator'):
                        app.Show3DSimulator()
                        self.logger.info("Called Application.Show3DSimulator()")
                    if hasattr(app, 'StartSimulator'):
                        app.StartSimulator()
                        self.logger.info("Called Application.StartSimulator()")

                # Direct methods on FluentControl
                if hasattr(self.fluent_control, 'Show'):
                    self.fluent_control.Show()
                    self.logger.info("Called FluentControl.Show()")
                if hasattr(self.fluent_control, 'ShowSimulator'):
                    self.fluent_control.ShowSimulator()
                    self.logger.info("Called FluentControl.ShowSimulator()")
                if hasattr(self.fluent_control, 'Show3DViewer'):
                    self.fluent_control.Show3DViewer()
                    self.logger.info("Called FluentControl.Show3DViewer()")
                if hasattr(self.fluent_control, 'Show3DSimulator'):
                    self.fluent_control.Show3DSimulator()
                    self.logger.info("Called FluentControl.Show3DSimulator()")
                if hasattr(self.fluent_control, 'StartSimulator'):
                    self.fluent_control.StartSimulator()
                    self.logger.info("Called FluentControl.StartSimulator()")
                if hasattr(self.fluent_control, 'Activate'):
                    self.fluent_control.Activate()
                    self.logger.info("Called FluentControl.Activate()")
                if hasattr(self.fluent_control, 'BringToFront'):
                    self.fluent_control.BringToFront()
                    self.logger.info("Called FluentControl.BringToFront()")

            # Try runtime methods
            if self.runtime:
                if hasattr(self.runtime, 'ShowSimulator'):
                    self.runtime.ShowSimulator()
                    self.logger.info("Called Runtime.ShowSimulator()")
                if hasattr(self.runtime, 'Show3DViewer'):
                    self.runtime.Show3DViewer()
                    self.logger.info("Called Runtime.Show3DViewer()")
                if hasattr(self.runtime, 'Show3DSimulator'):
                    self.runtime.Show3DSimulator()
                    self.logger.info("Called Runtime.Show3DSimulator()")
                if hasattr(self.runtime, 'StartSimulator'):
                    self.runtime.StartSimulator()
                    self.logger.info("Called Runtime.StartSimulator()")

            self.logger.info("3D viewer/simulator should be visible now")
            return True

        except Exception as e:
            self.logger.warning(f"Could not explicitly open 3D viewer: {e}")
            # Don't fail - the window might already be visible
            return False

    def enable_animation(self, enable: bool = True) -> bool:
        """Enable or disable 3D animation in simulation mode.

        Args:
            enable: Whether to enable animation (default: True)

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info(f"Attempting to {'enable' if enable else 'disable'} 3D animation...")

            if self.fluent_control:
                # Try Application methods
                if hasattr(self.fluent_control, 'Application'):
                    app = self.fluent_control.Application
                    if hasattr(app, 'EnableAnimation'):
                        app.EnableAnimation(enable)
                        self.logger.info(f"Called Application.EnableAnimation({enable})")
                    if hasattr(app, 'SetAnimationEnabled'):
                        app.SetAnimationEnabled(enable)
                        self.logger.info(f"Called Application.SetAnimationEnabled({enable})")

                # Direct methods on FluentControl
                if hasattr(self.fluent_control, 'EnableAnimation'):
                    self.fluent_control.EnableAnimation(enable)
                    self.logger.info(f"Called FluentControl.EnableAnimation({enable})")
                if hasattr(self.fluent_control, 'SetAnimationEnabled'):
                    self.fluent_control.SetAnimationEnabled(enable)
                    self.logger.info(f"Called FluentControl.SetAnimationEnabled({enable})")

            # Try runtime methods
            if self.runtime:
                if hasattr(self.runtime, 'EnableAnimation'):
                    self.runtime.EnableAnimation(enable)
                    self.logger.info(f"Called Runtime.EnableAnimation({enable})")
                if hasattr(self.runtime, 'SetAnimationEnabled'):
                    self.runtime.SetAnimationEnabled(enable)
                    self.logger.info(f"Called Runtime.SetAnimationEnabled({enable})")

            self.logger.info(f"Animation {'enabled' if enable else 'disabled'}")
            return True

        except Exception as e:
            self.logger.warning(f"Could not control animation: {e}")
            return False

    def set_simulation_speed(self, speed: float = 1.0) -> bool:
        """Set the simulation speed (how fast movements are animated).

        Args:
            speed: Speed multiplier (1.0 = normal speed, 0.5 = half speed, 2.0 = double speed)

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info(f"Setting simulation speed to {speed}x...")

            if self.fluent_control:
                # Try Application methods
                if hasattr(self.fluent_control, 'Application'):
                    app = self.fluent_control.Application
                    if hasattr(app, 'SetSimulationSpeed'):
                        app.SetSimulationSpeed(speed)
                        self.logger.info(f"Called Application.SetSimulationSpeed({speed})")
                    if hasattr(app, 'SetAnimationSpeed'):
                        app.SetAnimationSpeed(speed)
                        self.logger.info(f"Called Application.SetAnimationSpeed({speed})")

                # Direct methods on FluentControl
                if hasattr(self.fluent_control, 'SetSimulationSpeed'):
                    self.fluent_control.SetSimulationSpeed(speed)
                    self.logger.info(f"Called FluentControl.SetSimulationSpeed({speed})")
                if hasattr(self.fluent_control, 'SetAnimationSpeed'):
                    self.fluent_control.SetAnimationSpeed(speed)
                    self.logger.info(f"Called FluentControl.SetAnimationSpeed({speed})")

            # Try runtime methods
            if self.runtime:
                if hasattr(self.runtime, 'SetSimulationSpeed'):
                    self.runtime.SetSimulationSpeed(speed)
                    self.logger.info(f"Called Runtime.SetSimulationSpeed({speed})")
                if hasattr(self.runtime, 'SetAnimationSpeed'):
                    self.runtime.SetAnimationSpeed(speed)
                    self.logger.info(f"Called Runtime.SetAnimationSpeed({speed})")

            self.logger.info(f"Simulation speed set to {speed}x")
            return True

        except Exception as e:
            self.logger.warning(f"Could not set simulation speed: {e}")
            return False

    def get_available_methods(self) -> List[str]:
        """Get list of available methods from FluentControl (like C# GetAllRunnableMethods).

        Returns:
            List of method names available in FluentControl
        """
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
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            self.logger.info(f"Preparing method: {method_name}")

            # Like C#: _runtime.PrepareMethod(toPrepare);
            self.logger.info(f"CALLING runtime.PrepareMethod('{method_name}')...")
            result = self.runtime.PrepareMethod(method_name)
            self.logger.info(f"PrepareMethod() returned: {result}")

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
        parameters: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = False
    ) -> bool:
        """Run a method on the Fluent (like C# RunMethod).

        Args:
            method_name: Name of the method to run (must be prepared first)
            parameters: Optional parameters for the method (not used yet)
            wait_for_completion: If True, wait for method to complete. If False, just start it.

        Returns:
            bool: True if successful
        """
        if not self.runtime:
            raise RuntimeError("Not connected to VisionX. Call setup() first.")

        try:
            # Check status and handle recovery/error modes BEFORE running method
            if hasattr(self.runtime, 'GetFluentStatus'):
                status = self.runtime.GetFluentStatus()
                status_str = str(status)
                
                self.logger.info(f"Current FluentControl status: {status} ({status_str})")
                
                # CRITICAL: If method is already running (status 12), use it - DON'T close it!
                # Status 12 = RunModeRunning - method is already running, channel should be open
                if status == 12:
                    self.logger.info("=" * 60)
                    self.logger.info("Method is already RUNNING (status 12: RunModeRunning)")
                    self.logger.info("=" * 60)
                    self.logger.info("Skipping PrepareMethod/RunMethod - using existing running method")
                    self.logger.info("Checking if API channel is already available...")
                    self.logger.info("=" * 60)
                    
                    # Try to get the channel immediately if method is running
                    channel_found = False
                    if self.runtime:
                        try:
                            # Try GetCurrentExecutionChannel
                            if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                                channel = self.runtime.GetCurrentExecutionChannel()
                                if channel is not None:
                                    self.current_execution_channel = channel
                                    if channel not in self._open_execution_channels:
                                        self._open_execution_channels.append(channel)
                                    self.logger.info(f"✓ Found execution channel: {channel}")
                                    self._register_api_callback(channel)
                                    channel_found = True
                        except Exception as e:
                            self.logger.debug(f"Could not get channel immediately: {e}")
                    
                    if channel_found:
                        self.logger.info("✓ API channel already available - ready to use!")
                    else:
                        self.logger.info("Channel not immediately available - wait_for_channel will find it")
                    
                    # Return success - channel is available or wait_for_channel will find it
                    return True
                
                # CRITICAL: Check for recovery mode (status 20) or error state (status 19) BEFORE running
                # Status 20 = RunModeRecoveryRunning (stuck in recovery from previous run)
                # Status 19 = RunModeStopOnError (method stopped with error)
                if status == 20 or status == 19:
                    self.logger.warning("=" * 60)
                    if status == 20:
                        self.logger.warning("FluentControl is in RECOVERY MODE (Status 20: RunModeRecoveryRunning)")
                        self.logger.warning("This usually means a previous method failed or was stopped.")
                    elif status == 19:
                        self.logger.warning("FluentControl is in ERROR STATE (Status 19: RunModeStopOnError)")
                        self.logger.warning("Previous method stopped with an error.")
                    
                    self.logger.warning("=" * 60)
                    self.logger.warning("Attempting to clear recovery/error state...")
                    
                    # Try to stop any running method and close it
                    if hasattr(self.runtime, 'StopMethod'):
                        try:
                            self.runtime.StopMethod()
                            self.logger.info("✓ Called StopMethod()")
                            await asyncio.sleep(1)
                        except Exception as e:
                            self.logger.debug(f"StopMethod failed: {e}")
                    
                    # Try to close the method to get back to EditMode
                    if hasattr(self.runtime, 'CloseMethod'):
                        try:
                            self.runtime.CloseMethod()
                            self.logger.info("✓ Called CloseMethod()")
                            await asyncio.sleep(2)
                        except Exception as e:
                            self.logger.debug(f"CloseMethod failed: {e}")
                    
                    # Wait for EditMode (status 6)
                    self.logger.info("Waiting for FluentControl to return to EditMode...")
                    for i in range(30):  # Wait up to 30 seconds
                        await asyncio.sleep(1)
                        try:
                            new_status = self.runtime.GetFluentStatus()
                            if new_status == 6:  # EditMode
                                self.logger.info(f"✓ FluentControl is now in EditMode (status: {new_status})")
                                status = new_status
                                status_str = str(status)
                                break
                            elif i % 5 == 0:
                                self.logger.info(f"  Still waiting for EditMode... (current status: {new_status}, {i}s)")
                        except Exception as e:
                            self.logger.debug(f"Could not check status: {e}")
                    
                    if status != 6:
                        self.logger.warning(f"⚠ Could not return to EditMode (current status: {status})")
                        self.logger.warning("You may need to manually clear the recovery/error in FluentControl GUI")
                        self.logger.warning("Continuing anyway - method execution may fail...")
                
                # Also check for recovery mode in status string (backup check)
                elif "Recovery" in status_str or "recovery" in status_str.lower():
                    self.logger.warning("Recovery mode detected (string check)! Attempting to handle...")
                    self._handle_recovery_mode()
                    await asyncio.sleep(3)
                
                # Even in simulation mode, we should verify EditMode for PrepareMethod
                # The error "Only allowed in Edit Mode!" suggests we need to be in EditMode
                if status == 6:  # EditMode
                    self.logger.info("✓ FluentControl is in EditMode - ready to prepare method")
                elif "Running" in status_str or "running" in status_str.lower() or status == 12:
                    self.logger.info("Method is already running - will prepare new method")
                else:
                    # Not in EditMode - need to wait for it
                    self.logger.info(f"Not in EditMode (status: {status}) - waiting for EditMode...")
                    for i in range(30):
                        await asyncio.sleep(1)
                        if hasattr(self.runtime, 'GetFluentStatus'):
                            try:
                                new_status = self.runtime.GetFluentStatus()
                                if new_status == 6:  # EditMode
                                    self.logger.info(f"✓ Now in EditMode after {i+1}s")
                                    break
                                elif i % 5 == 0:
                                    self.logger.info(f"  Waiting for EditMode... (status: {new_status}, {i+1}s)")
                            except:
                                pass

            # NOTE: InitializeInstrument is not called here because:
            # 1. The method signature doesn't match when using pythonnet (needs WorkspaceSelection enum)
            # 2. In non-simulation mode, pipetting works without explicit initialization
            # 3. The user's method only contains "Create API Channel" and "Wait for API Channel" actions
            # If pipetting commands fail later, we may need to investigate proper initialization
            # For now, we'll try running the method without initialization

            # CRITICAL: Ensure we're in EditMode before PrepareMethod
            # Even though simulation mode might skip this, we should verify
            if not self.simulation_mode:
                # Wait for EditMode in regular mode
                self.logger.info("Waiting for EditMode before preparing method...")
                for i in range(30):
                    if hasattr(self.runtime, 'GetFluentStatus'):
                        try:
                            status = self.runtime.GetFluentStatus()
                            if status == 6:  # EditMode
                                self.logger.info("✓ FluentControl is in EditMode")
                                break
                            elif i % 5 == 0:
                                self.logger.info(f"Waiting for EditMode... (status: {status}, {i}s)")
                        except:
                            pass
                    await asyncio.sleep(1)
            
            # Prepare the method first if not already prepared
            # (In C# server, PrepareMethod is called separately)
            # CRITICAL: PrepareMethod requires EditMode (status 6)
            try:
                # Double-check we're in EditMode before preparing
                if hasattr(self.runtime, 'GetFluentStatus'):
                    status = self.runtime.GetFluentStatus()
                    if status != 6:
                        self.logger.warning(f"Status is {status} (not EditMode=6) before PrepareMethod, but attempting anyway...")
                
                self.prepare_method(method_name)
            except Exception as e:
                # If prepare fails, check if method is already running
                if hasattr(self.runtime, 'IsMethodRunning') and self.runtime.IsMethodRunning():
                    self.logger.info("Method is already running - prepare not needed")
                else:
                    # Check if error is about EditMode
                    error_str = str(e).lower()
                    if "edit mode" in error_str or "editmode" in error_str:
                        self.logger.error("=" * 60)
                        self.logger.error("PrepareMethod failed: Not in EditMode")
                        self.logger.error("=" * 60)
                        self.logger.error("FluentControl must be in EditMode (status 6) to prepare methods.")
                        self.logger.error("Waiting for EditMode and retrying...")
                        # Wait for EditMode and retry
                        for i in range(30):
                            await asyncio.sleep(1)
                            if hasattr(self.runtime, 'GetFluentStatus'):
                                try:
                                    status = self.runtime.GetFluentStatus()
                                    if status == 6:
                                        self.logger.info("✓ Now in EditMode - retrying PrepareMethod...")
                                        self.prepare_method(method_name)
                                        break
                                except:
                                    pass
                            if i >= 29:
                                raise  # Timeout
                    else:
                        raise
            
            # CRITICAL: Wait for method to be fully prepared before running
            # FluentControl needs time to transition states after PrepareMethod
            # Status might transition: 7 -> 10 -> 9 (recovery) or 7 -> 10 -> 8 (preparing run)
            self.logger.info("Waiting for method preparation to complete...")
            
            # Wait and monitor status transitions - sometimes status 9 is just a transient state
            prep_status = None
            for wait_iter in range(10):  # Wait up to 5 seconds, checking every 0.5s
                await asyncio.sleep(0.5)
                if hasattr(self.runtime, 'GetFluentStatus'):
                    try:
                        prep_status = self.runtime.GetFluentStatus()
                        if wait_iter == 0 or wait_iter % 2 == 0:  # Log every second
                            self.logger.debug(f"Preparation status check {wait_iter}: {prep_status}")
                        
                        # Status 10 = RunModeWaitingForSystem - ready to run
                        if prep_status == 10:
                            self.logger.info(f"✓ Method ready to run (status 10: RunModeWaitingForSystem) after {wait_iter * 0.5:.1f}s")
                            break
                        # Status 8 = RunModePreparingRun - also ready
                        elif prep_status == 8:
                            self.logger.info(f"✓ Method preparing to run (status 8: RunModePreparingRun) after {wait_iter * 0.5:.1f}s")
                            break
                        # Status 9 = RunModePreparingRecovery - might be transient, continue waiting
                        elif prep_status == 9:
                            if wait_iter >= 4:  # After 2 seconds, log warning
                                self.logger.warning(f"Status 9 (RunModePreparingRecovery) persists after {wait_iter * 0.5:.1f}s - will try running anyway")
                            # Continue waiting - might transition to status 10
                    except Exception as e:
                        self.logger.debug(f"Could not check status during preparation: {e}")
            
            # Log final status
            if prep_status is not None:
                self.logger.info(f"Final preparation status: {prep_status}")
                if prep_status == 9:
                    self.logger.warning("Status 9 detected - this might be normal, will attempt to run method anyway")

            loop = asyncio.get_event_loop()

            def _run_method():
                # Like C#: _runtime.RunMethod();
                # First verify runtime is ready
                if self.runtime and hasattr(self.runtime, 'IsReady'):
                    is_ready = self.runtime.IsReady()
                    if not is_ready:
                        self.logger.error("=" * 60)
                        self.logger.error("CRITICAL: Runtime is not ready!")
                        self.logger.error("=" * 60)
                        self.logger.error("The instrument may need to be initialized before running methods.")
                        self.logger.error("Try calling InitializeInstrument() first.")
                        self.logger.error("=" * 60)
                        raise TecanError("Runtime is not ready. Instrument may need initialization.", "VisionX", 1)
                
                # Check current status before running
                status_before = None
                if self.runtime and hasattr(self.runtime, 'GetFluentStatus'):
                    try:
                        status_before = self.runtime.GetFluentStatus()
                        self.logger.info(f"FluentControl status before RunMethod: {status_before}")
                    except Exception as e:
                        self.logger.debug(f"Could not get status before run: {e}")
                
                try:
                    self.logger.info("CALLING runtime.RunMethod()...")
                    result = self.runtime.RunMethod()
                    self.logger.info(f"RunMethod() returned: {result}")
                except Exception as e:
                    # Catch COM errors and other exceptions
                    self.logger.error("=" * 60)
                    self.logger.error("CRITICAL: RunMethod() threw an exception!")
                    self.logger.error("=" * 60)
                    self.logger.error(f"Exception type: {type(e).__name__}")
                    self.logger.error(f"Exception message: {str(e)}")
                    
                    # Try to get more details if it's a COM error
                    try:
                        import comtypes
                        if isinstance(e, comtypes.COMError):
                            self.logger.error(f"COM Error details: {e}")
                    except:
                        pass
                    
                    # Get status after error
                    if self.runtime and hasattr(self.runtime, 'GetFluentStatus'):
                        try:
                            status_after = self.runtime.GetFluentStatus()
                            self.logger.error(f"FluentControl status after error: {status_after}")
                        except:
                            pass
                    
                    self.logger.error("=" * 60)
                    import traceback
                    self.logger.error(traceback.format_exc())
                    self.logger.error("=" * 60)
                    raise
                
                # IMMEDIATELY check if method is running (critical for detecting aborts)
                import time
                time.sleep(0.3)  # Brief delay for FluentControl to process
                
                if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                    is_running = self.runtime.IsMethodRunning()
                    self.logger.info(f"Method running status (immediate check): {is_running}")
                    
                    if not is_running:
                        # Method stopped immediately - get detailed error info
                        status = None
                        if hasattr(self.runtime, 'GetFluentStatus'):
                            try:
                                status = self.runtime.GetFluentStatus()
                                self.logger.error(f"FluentControl status immediately after RunMethod: {status}")
                            except Exception as e:
                                self.logger.debug(f"Could not get status: {e}")
                        
                        self.logger.error("=" * 60)
                        self.logger.error("CRITICAL: Method stopped immediately after RunMethod()!")
                        self.logger.error("=" * 60)
                        if status:
                            self.logger.error(f"Status code: {status}")
                            # Status codes: 19=RunModeStopOnError, 20=ErrorState, 6=EditMode
                            if status == 19:
                                self.logger.error("Status: RunModeStopOnError - Method encountered an error")
                            elif status == 20:
                                self.logger.error("Status: ErrorState - FluentControl is in error state")
                            elif status == 6:
                                self.logger.error("Status: EditMode - Method completed/aborted and returned to edit mode")
                        if self._last_error:
                            self.logger.error(f"Error message: {self._last_error}")
                        self.logger.error("=" * 60)
                        self.logger.error("TROUBLESHOOTING:")
                        self.logger.error("  1. Check FluentControl GUI for error dialogs")
                        self.logger.error("  2. Verify method has 'Create API Channel' and 'Wait for API Channel' actions")
                        self.logger.error("  3. Check FluentControl logs: C:\\ProgramData\\Tecan\\VisionX\\Logging\\")
                        self.logger.error("  4. Make sure worktable is configured correctly")
                        self.logger.error("  5. Try running the method manually in FluentControl GUI to see the error")
                        self.logger.error("")
                        self.logger.error("PIPETTING HARDWARE ISSUE:")
                        self.logger.error("  If the method aborts due to pipetting hardware:")
                        self.logger.error("  - In simulation mode, hardware may not be available")
                        self.logger.error("  - The method might be trying to initialize pipetting hardware")
                        self.logger.error("  - Check if the method has any pipetting actions (aspirate/dispense)")
                        self.logger.error("  - The demo method should ONLY have 'Create API Channel' and 'Wait for API Channel'")
                        self.logger.error("  - If the method has pipetting actions, remove them for API-only methods")
                        self.logger.error("=" * 60)
                
                return True

            self.logger.info(f"Running method: {method_name}")
            self._current_state = FluentState.RUNNING
            self._last_error = None  # Clear previous errors

            success = await loop.run_in_executor(None, _run_method)

            # In simulation mode, make sure animation is enabled
            if self.simulation_mode and success:
                self.enable_animation(True)

            # Immediately check if method started successfully
            await asyncio.sleep(0.5)  # Brief wait for method to start
            
            # Check for errors that might have occurred
            if self._last_error:
                self.logger.error(f"Error detected after starting method: {self._last_error}")
            
            # Check method status
            if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                is_running = self.runtime.IsMethodRunning()
                if not is_running:
                    # Method stopped immediately - check why
                    status = None
                    if hasattr(self.runtime, 'GetFluentStatus'):
                        status = self.runtime.GetFluentStatus()
                    
                    self.logger.error("=" * 60)
                    self.logger.error("METHOD STOPPED IMMEDIATELY AFTER STARTING!")
                    self.logger.error("=" * 60)
                    self.logger.error(f"Status: {status}")
                    self.logger.error(f"Last error: {self._last_error}")
                    self.logger.error("Possible causes:")
                    self.logger.error("  1. Method has errors that prevent it from running")
                    self.logger.error("  2. Method doesn't have an 'API Channel' action")
                    self.logger.error("  3. Method requires parameters that weren't provided")
                    self.logger.error("  4. Worktable/labware configuration issues")
                    self.logger.error("=" * 60)
                    
                    # Try to get more error information
                    try:
                        if hasattr(self.runtime, 'GetLastError'):
                            last_err = self.runtime.GetLastError()
                            if last_err:
                                self.logger.error(f"Runtime last error: {last_err}")
                    except:
                        pass
                    
                    raise TecanError(
                        f"Method '{method_name}' stopped immediately after starting. "
                        f"Status: {status}, Error: {self._last_error}",
                        "VisionX", 1
                    )

            if wait_for_completion:
                # Wait for method to complete
                await self._wait_for_method_completion()
                self._current_state = FluentState.READY
                self.logger.info(f"Method {method_name} completed successfully")
            else:
                # Just started the method, don't wait for completion
                self.logger.info(f"Method {method_name} started (not waiting for completion)")
                
                # IMMEDIATELY check method status and FluentControl state
                import time
                time.sleep(0.5)  # Give FluentControl a moment to process
                
                # Verify method is actually running
                if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                    is_running = self.runtime.IsMethodRunning()
                    if is_running:
                        self.logger.info("✓ Method is running - API channel should open soon")
                        
                        # Check FluentControl status
                        if hasattr(self.runtime, 'GetFluentStatus'):
                            try:
                                status = self.runtime.GetFluentStatus()
                                self.logger.info(f"FluentControl status after method start: {status}")
                                
                                # Status 9 = RunModePreparingRecovery
                                # This means FluentControl is preparing to show recovery dialog
                                # The method will continue after recovery is dismissed
                                if status == 9:  # RunModePreparingRecovery
                                    self.logger.warning("=" * 60)
                                    self.logger.warning("RECOVERY MODE DETECTED (Status 9: RunModePreparingRecovery)")
                                    self.logger.warning("=" * 60)
                                    self.logger.warning("FluentControl is preparing to show recovery dialog.")
                                    self.logger.warning("Please manually dismiss the recovery dialog in FluentControl GUI.")
                                    self.logger.warning("The method should continue after recovery is dismissed.")
                                    self.logger.warning("=" * 60)
                                    # Don't return False - let wait_for_channel handle it
                                
                                # Check for error states
                                elif status in [19, 20]:  # RunModeStopOnError, ErrorState
                                    self.logger.error("=" * 60)
                                    self.logger.error("ERROR: Method entered error state immediately!")
                                    self.logger.error(f"Status code: {status}")
                                    if self._last_error:
                                        self.logger.error(f"Error message: {self._last_error}")
                                    self.logger.error("=" * 60)
                                    return False
                            except Exception as e:
                                self.logger.debug(f"Could not get status: {e}")
                        
                        # Try to register API callback proactively since method is running
                        # This might be needed even before channel opens
                        self.logger.info("Attempting proactive API callback registration...")
                        self._register_api_callback()
                    else:
                        # Method stopped immediately - get detailed error info
                        self.logger.error("=" * 60)
                        self.logger.error("⚠ METHOD STOPPED IMMEDIATELY AFTER STARTING!")
                        self.logger.error("=" * 60)
                        
                        # Get status
                        if hasattr(self.runtime, 'GetFluentStatus'):
                            try:
                                status = self.runtime.GetFluentStatus()
                                self.logger.error(f"FluentControl status: {status}")
                            except:
                                pass
                        
                        # Get error info
                        if self._last_error:
                            self.logger.error(f"Last runtime error: {self._last_error}")
                        
                        self.logger.error("=" * 60)
                        self.logger.error("TROUBLESHOOTING:")
                        self.logger.error("  1. Check FluentControl GUI for error dialogs")
                        self.logger.error("  2. Verify method 'demo' has 'Create API Channel' and 'Wait for API Channel' actions")
                        self.logger.error("  3. Check FluentControl logs for detailed error messages")
                        self.logger.error("  4. Make sure worktable is configured correctly")
                        self.logger.error("=" * 60)

            return success

        except Exception as e:
            self.logger.error("=" * 60)
            self.logger.error(f"FAILED TO RUN METHOD: {method_name}")
            self.logger.error("=" * 60)
            self.logger.error(f"Error: {e}")
            if self._last_error:
                self.logger.error(f"Last runtime error: {self._last_error}")
            
            # Check final status
            if self.runtime and hasattr(self.runtime, 'GetFluentStatus'):
                try:
                    status = self.runtime.GetFluentStatus()
                    self.logger.error(f"Final status: {status}")
                except:
                    pass
            
            self._current_state = FluentState.ERROR
            import traceback
            traceback.print_exc()
    
    async def wait_for_channel(self, timeout: int = 60) -> bool:
        """Wait for API execution channel to open and be ready.
        
        Args:
            timeout: Maximum time to wait in seconds (default: 60)
        
        Returns:
            bool: True if channel opened and is ready, False if timeout
        """
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
        
        # CRITICAL: If method is already running, the channel should already exist
        # Try to get it immediately before waiting
        if self.runtime:
            # Check if method is running
            method_running = False
            if hasattr(self.runtime, 'IsMethodRunning'):
                try:
                    method_running = self.runtime.IsMethodRunning()
                    self.logger.info(f"Method running status: {method_running}")
                except:
                    pass
            
            if method_running:
                self.logger.info("Method is running - channel should be available. Attempting immediate detection...")
        
        # Wait a moment for COM events to fire (channel might open via COM event)
        self.logger.info("Waiting 2 seconds for COM events (ChannelOpens event) to fire...")
        await asyncio.sleep(2)
        
        # Check if channel was set by COM event during the wait
        if self.current_execution_channel is not None:
            self.logger.info(f"✓ Channel detected via COM event: {self.current_execution_channel}")
            # Verify it's alive
            is_alive = False
            if hasattr(self.current_execution_channel, 'IsAlive'):
                is_alive = self.current_execution_channel.IsAlive
            elif hasattr(self.current_execution_channel, 'IsOpen'):
                is_alive = self.current_execution_channel.IsOpen
            
            if is_alive:
                self.logger.info("✓ API channel is ready (detected via COM event)!")
                return True
            else:
                self.logger.warning("Channel found but not alive - continuing search...")
        
        # Try to force update the execution channel from runtime
        # This is important - the channel might already be open but we haven't detected it
        if self.runtime:
            try:
                # Try multiple methods to get the current channel
                channel_found = False
                
                if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                    channel = self.runtime.GetCurrentExecutionChannel()
                    if channel is not None:
                        self.current_execution_channel = channel
                        self._open_execution_channels.append(channel)
                        self.logger.info(f"✓ Found execution channel via GetCurrentExecutionChannel: {channel}")
                        # Register API callback for this channel
                        self._register_api_callback(channel)
                        channel_found = True
                
                if not channel_found and hasattr(self.runtime, 'ExecutionChannel'):
                    channel = self.runtime.ExecutionChannel
                    if channel is not None:
                        self.current_execution_channel = channel
                        self._open_execution_channels.append(channel)
                        self.logger.info(f"✓ Found execution channel via ExecutionChannel property: {channel}")
                        # Register API callback for this channel
                        self._register_api_callback(channel)
                        channel_found = True
                
                if not channel_found:
                    # Try to get all open channels
                    if hasattr(self.runtime, 'GetOpenChannels') or hasattr(self.runtime, 'GetExecutionChannels'):
                        try:
                            if hasattr(self.runtime, 'GetOpenChannels'):
                                channels = self.runtime.GetOpenChannels()
                            else:
                                channels = self.runtime.GetExecutionChannels()
                            
                            if channels:
                                for ch in channels:
                                    if ch not in self._open_execution_channels:
                                        self._open_execution_channels.append(ch)
                                        self.logger.info(f"✓ Found open channel: {ch}")
                                        # Register API callback for this channel
                                        self._register_api_callback(ch)
                                        if self.current_execution_channel is None:
                                            self.current_execution_channel = ch
                                            channel_found = True
                        except Exception as e:
                            self.logger.debug(f"Could not get open channels: {e}")
                
            except Exception as e:
                self.logger.warning(f"Failed to get execution channel from runtime: {e}")

        start_time = time.time()
        last_channel_check = 0
        last_status_check = 0
        callback_registered = False

        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            
            # ACTIVELY poll for channel every 0.5 seconds when method is running
            # This is critical when COM events aren't working
            if self.runtime and (elapsed - last_channel_check) >= 0.5:  # Every 0.5 seconds
                last_channel_check = elapsed
                try:
                    # Try to get channel from runtime (works even without COM events)
                    channel_found = False
                    
                    # Method 1: Try GetCurrentExecutionChannel
                    if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                        try:
                            channel = self.runtime.GetCurrentExecutionChannel()
                            if channel is not None:
                                # Check if channel is alive
                                is_alive = False
                                if hasattr(channel, 'IsAlive'):
                                    is_alive = channel.IsAlive
                                elif hasattr(channel, 'IsOpen'):
                                    is_alive = channel.IsOpen
                                
                                if is_alive:
                                    if channel != self.current_execution_channel:
                                        self.logger.info("=" * 60)
                                        self.logger.info("✓ FOUND EXECUTION CHANNEL via GetCurrentExecutionChannel!")
                                        self.logger.info(f"Channel: {channel}")
                                        self.logger.info("=" * 60)
                                        self.current_execution_channel = channel
                                        if channel not in self._open_execution_channels:
                                            self._open_execution_channels.append(channel)
                                        # Register API callback
                                        self._register_api_callback(channel)
                                        channel_found = True
                        except Exception as e:
                            self.logger.debug(f"GetCurrentExecutionChannel failed: {e}")
                    
                    # Method 2: Try ExecutionChannel property
                    if not channel_found and hasattr(self.runtime, 'ExecutionChannel'):
                        try:
                            channel = self.runtime.ExecutionChannel
                            if channel is not None:
                                is_alive = False
                                if hasattr(channel, 'IsAlive'):
                                    is_alive = channel.IsAlive
                                elif hasattr(channel, 'IsOpen'):
                                    is_alive = channel.IsOpen
                                
                                if is_alive:
                                    if channel != self.current_execution_channel:
                                        self.logger.info("=" * 60)
                                        self.logger.info("✓ FOUND EXECUTION CHANNEL via ExecutionChannel property!")
                                        self.logger.info(f"Channel: {channel}")
                                        self.logger.info("=" * 60)
                                        self.current_execution_channel = channel
                                        if channel not in self._open_execution_channels:
                                            self._open_execution_channels.append(channel)
                                        self._register_api_callback(channel)
                                        channel_found = True
                        except Exception as e:
                            self.logger.debug(f"ExecutionChannel property failed: {e}")
                    
                    if channel_found:
                        # Verify channel is still alive after a short delay
                        await asyncio.sleep(2)
                        if self.current_execution_channel:
                            is_alive = False
                            if hasattr(self.current_execution_channel, 'IsAlive'):
                                is_alive = self.current_execution_channel.IsAlive
                            elif hasattr(self.current_execution_channel, 'IsOpen'):
                                is_alive = self.current_execution_channel.IsOpen
                            
                            if is_alive:
                                self.logger.info("✓ API channel is ready!")
                                return True
                            else:
                                self.logger.warning("Channel found but is not alive - continuing search...")
                                self.current_execution_channel = None
                except Exception as e:
                    self.logger.debug(f"Error polling for channel: {e}")
            
            # Check method status periodically to detect if it aborted
            if self.runtime and (elapsed - last_status_check) >= 2:  # Every 2 seconds
                last_status_check = elapsed
                try:
                    # Check if method is still running
                    if hasattr(self.runtime, 'IsMethodRunning'):
                        is_running = self.runtime.IsMethodRunning()
                        if not is_running:
                            # Method stopped - get status and error info
                            status = None
                            if hasattr(self.runtime, 'GetFluentStatus'):
                                status = self.runtime.GetFluentStatus()

                            self.logger.error("=" * 60)
                            self.logger.error("METHOD STOPPED WHILE WAITING FOR API CHANNEL!")
                            self.logger.error("=" * 60)
                            self.logger.error(f"Status: {status}")
                            self.logger.error(f"Last error: {self._last_error}")
                            self.logger.error(f"Elapsed time: {elapsed:.1f}s")

                            # Try to get more error details
                            try:
                                if hasattr(self.runtime, 'GetLastError'):
                                    last_err = self.runtime.GetLastError()
                                    if last_err:
                                        self.logger.error(f"Runtime last error: {last_err}")
                            except:
                                pass

                            self.logger.error("=" * 60)
                            return False
                        else:
                            # Method is still running - try registering callback if not done yet
                            if not callback_registered:
                                self.logger.info("Method still running - attempting API callback registration...")
                                if self._register_api_callback():
                                    callback_registered = True
                                    self.logger.info("✓ API callback registered during channel wait")
                    
                    # Check status for errors
                    if hasattr(self.runtime, 'GetFluentStatus'):
                        status = self.runtime.GetFluentStatus()
                        status_str = str(status)
                        
                        # Check for error states (status 19 = RunModeStopOnError, status 20 = RunModeRecoveryRunning)
                        if status in [19, 20] or "Error" in status_str or "error" in status_str.lower():
                            if status == 19:
                                self.logger.error(f"Error status detected: RunModeStopOnError ({status})")
                            elif status == 20:
                                self.logger.error(f"Error status detected: RunModeRecoveryRunning ({status})")
                            else:
                                self.logger.error(f"Error status detected: {status_str}")
                            if self._last_error:
                                self.logger.error(f"Last error: {self._last_error}")
                        
                        # Check for recovery mode - status 9 = RunModePreparingRecovery, status 20 = RunModeRecoveryRunning
                        if status == 9 or status == 20 or "Recovery" in status_str or "recovery" in status_str.lower():
                            if status == 9:  # Only log once for status 9
                                self.logger.warning("=" * 60)
                                self.logger.warning("RECOVERY MODE DETECTED (Status 9: RunModePreparingRecovery)")
                                self.logger.warning("=" * 60)
                                self.logger.warning("FluentControl is preparing to show recovery dialog.")
                                self.logger.warning("Please manually dismiss the recovery dialog in FluentControl GUI.")
                                self.logger.warning("The method should continue after recovery is dismissed.")
                                self.logger.warning("Waiting for recovery mode to be dismissed...")
                                self.logger.warning("=" * 60)
                                # Try to handle recovery mode automatically
                                self._handle_recovery_mode()
                                # Wait for user to dismiss recovery
                                recovery_dismissed = await self.wait_for_recovery_mode_dismissed(timeout=60)
                                if not recovery_dismissed:
                                    self.logger.warning("Recovery mode not dismissed automatically, but continuing to wait for channel...")
                                    # Don't return False - keep waiting, user might dismiss manually
                except Exception as e:
                    self.logger.debug(f"Error checking method status: {e}")
            
            # Try to refresh channel from runtime periodically (every 5 seconds)
            if self.runtime and (elapsed - last_channel_check) >= 5:
                last_channel_check = elapsed
                try:
                    if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                        channel = self.runtime.GetCurrentExecutionChannel()
                        if channel is not None:
                            if channel != self.current_execution_channel:
                                self.logger.info(f"✓ Found execution channel via periodic check: {channel}")
                                self.current_execution_channel = channel
                            if channel not in self._open_execution_channels:
                                self._open_execution_channels.append(channel)
                except Exception as e:
                    self.logger.debug(f"Periodic channel check failed: {e}")
            
            # Check current channel
            if self.current_execution_channel is not None:
                is_alive = False
                if hasattr(self.current_execution_channel, 'IsAlive'):
                    is_alive = self.current_execution_channel.IsAlive
                elif hasattr(self.current_execution_channel, 'IsOpen'):
                    is_alive = self.current_execution_channel.IsOpen
                else:
                    # If channel doesn't have IsAlive/IsOpen, assume it's alive if it exists
                    is_alive = True
                    self.logger.debug("Channel exists but no IsAlive/IsOpen property - assuming alive")
                
                if is_alive:
                    self.logger.info("✓ API channel detected! Verifying it's ready...")

                    # Verify method is still running - this is critical!
                    method_running = True
                    if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                        method_running = self.runtime.IsMethodRunning()
                        if method_running:
                            self.logger.info("✓ Method is still running")
                        else:
                            self.logger.error("✗ Method stopped running! Channel will close.")
                            self.logger.error("The method must stay running to keep the API channel open.")
                            self.logger.error("Check that your method has an 'API Channel' action that keeps it running.")
                            # Don't return True if method stopped
                            await asyncio.sleep(1)
                            continue

                    # Wait a bit to ensure the channel is fully ready and stable
                    self.logger.info("Waiting for channel to stabilize...")
                    await asyncio.sleep(2.0)

                    # Double-check channel is still alive after wait
                    is_alive_after_wait = False
                    if hasattr(self.current_execution_channel, 'IsAlive'):
                        is_alive_after_wait = self.current_execution_channel.IsAlive
                    elif hasattr(self.current_execution_channel, 'IsOpen'):
                        is_alive_after_wait = self.current_execution_channel.IsOpen
                    else:
                        is_alive_after_wait = True  # Assume alive if no property

                    if not is_alive_after_wait:
                        self.logger.error("✗ Channel closed immediately after opening!")
                        self.logger.error("This usually means the method completed/aborted.")
                        # Clear the channel and continue waiting
                        self.current_execution_channel = None
                        await asyncio.sleep(1)
                        continue

                    # Verify method is still running one more time
                    if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                        if self.runtime.IsMethodRunning():
                            self.logger.info("✓ API channel is ready and method is running!")
                            self.logger.info("You can now send commands that will be visible in the 3D viewer.")
                            return True
                        else:
                            self.logger.error("✗ Channel opened but method stopped running")
                            self.current_execution_channel = None
                            continue
                    else:
                        # If we can't check method status, assume channel is ready
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
            # Verify channel is still alive
            is_alive = False
            if hasattr(self.current_execution_channel, 'IsAlive'):
                is_alive = self.current_execution_channel.IsAlive
            elif hasattr(self.current_execution_channel, 'IsOpen'):
                is_alive = self.current_execution_channel.IsOpen
            
            if not is_alive:
                self.logger.warning("Current execution channel is no longer alive!")
                self.current_execution_channel = None
                # Check if method is still running
                if self.runtime and hasattr(self.runtime, 'IsMethodRunning'):
                    if not self.runtime.IsMethodRunning():
                        self.logger.error("Method stopped running - API channel closed!")
                    else:
                        self.logger.warning("Method is still running but channel closed - may reopen")
            else:
                return self.current_execution_channel
        
        # If still None, try to find in open channels
        if self._open_execution_channels:
            # Check each channel and return the first alive one
            for channel in reversed(self._open_execution_channels):
                is_alive = False
                if hasattr(channel, 'IsAlive'):
                    is_alive = channel.IsAlive
                elif hasattr(channel, 'IsOpen'):
                    is_alive = channel.IsOpen
                
                if is_alive:
                    self.current_execution_channel = channel
                    return channel
            
        return None

    def _create_command_object(self, xml_content: str):
        """Create a command object for sending to the execution channel.

        This uses the same approach as UniteLabs - creating a COM object with the
        command CLSID and setting its Content property.

        Args:
            xml_content: The XML representation of the command to execute

        Returns:
            A command object that can be passed to ExecuteCommand
        """
        try:
            import comtypes.client

            # Create command object using the same CLSID as UniteLabs
            # This is the ICommand interface GUID
            # Use COMTYPES_CLIENT if available, otherwise try to import
            global HAS_COMTYPES, COMTYPES_CLIENT
            comtypes_client = COMTYPES_CLIENT if HAS_COMTYPES and COMTYPES_CLIENT else None
            if not comtypes_client:
                try:
                    import comtypes.client
                    comtypes_client = comtypes.client
                    HAS_COMTYPES = True
                    COMTYPES_CLIENT = comtypes.client
                except:
                    raise TecanError("comtypes required for command creation. Install with: pip install comtypes", "VisionX", 1)
            command = comtypes_client.CreateObject("{44080860-58A0-45E7-82AF-6503C27100D4}")
            command.Content = xml_content
            return command
        except Exception as e:
            self.logger.error(f"Failed to create command object: {e}")
            # Fallback: try to create a simple object with Content property
            try:
                # Try using .NET to create the command
                if HAS_PYTHONNET:
                    # Look for Command class in the API
                    pass
            except:
                pass
            raise TecanError(f"Cannot create command object: {e}", "VisionX", 1)

    def _execute_command(self, command):
        """Execute a command through the execution channel (like C# TriggerCommand).

        IMPORTANT: When using comtypes for the channel (which we do for proper event handling),
        we cannot pass pythonnet objects directly. Instead, we need to:
        1. Convert the command to XML
        2. Create a comtypes command object using CreateObject
        3. Set the Content property to the XML
        4. Pass that to ExecuteCommand

        This is exactly how UniteLabs does it.
        """
        channel = self._get_execution_channel()
        if channel is not None:
            # Check if channel is alive
            is_alive = False
            if hasattr(channel, 'IsAlive'):
                is_alive = channel.IsAlive
            elif hasattr(channel, 'IsOpen'):
                is_alive = channel.IsOpen
            else:
                # If no IsAlive/IsOpen property, assume channel is alive if it exists
                is_alive = True
                self.logger.debug("Channel exists but no IsAlive/IsOpen property - assuming alive")
            
            if is_alive:
                try:
                    # Convert command to XML if it's a .NET object
                    xml_content = None
                    if isinstance(command, str):
                        # Already XML string - this is the preferred format
                        xml_content = command
                    elif hasattr(command, 'Content'):
                        # GenericCommand or comtypes command object - get Content property
                        xml_content = command.Content
                        self.logger.debug(f"Extracted XML from command.Content: {xml_content[:200] if xml_content else 'None'}...")
                    elif hasattr(command, 'ToXml'):
                        # .NET command object - get its XML representation
                        xml_content = command.ToXml()
                        self.logger.debug(f"Converted command to XML via ToXml(): {xml_content[:200] if xml_content else 'None'}...")
                    elif hasattr(command, 'ToXML'):
                        # Some commands use ToXML (capital XML)
                        xml_content = command.ToXML()
                        self.logger.debug(f"Converted command to XML via ToXML(): {xml_content[:200] if xml_content else 'None'}...")
                    else:
                        # Try to serialize it somehow
                        xml_content = str(command)
                        self.logger.warning(f"Command has no Content/ToXml/ToXML method, using str(): {xml_content[:100]}...")

                    if not xml_content:
                        raise TecanError("Could not convert command to XML", "VisionX", 1)

                    # Create comtypes command object (like UniteLabs)
                    # This is the ICommand CLSID
                    # Try to use comtypes if available
                    global HAS_COMTYPES, COMTYPES_CLIENT
                    comtypes_client = COMTYPES_CLIENT if HAS_COMTYPES and COMTYPES_CLIENT else None
                    if not comtypes_client:
                        try:
                            import comtypes.client
                            comtypes_client = comtypes.client
                            HAS_COMTYPES = True
                            COMTYPES_CLIENT = comtypes.client
                        except:
                            raise TecanError("comtypes required for command execution. Install with: pip install comtypes", "VisionX", 1)
                    
                    com_command = comtypes_client.CreateObject("{44080860-58A0-45E7-82AF-6503C27100D4}")
                    com_command.Content = xml_content

                    self.logger.info(f"Executing command via comtypes...")
                    self.logger.debug(f"XML content (first 200 chars): {xml_content[:200] if len(xml_content) > 200 else xml_content}")

                    # Execute the command
                    channel.ExecuteCommand(com_command)

                    self.logger.info("✓ Command sent successfully - waiting for execution...")

                    # In simulation mode, give a small delay for the command to be processed
                    # This is important because simulation needs time to process commands
                    if self.simulation_mode:
                        time.sleep(0.5)  # Small delay for simulation to process

                    return True
                except Exception as e:
                    self.logger.error(f"Error executing command: {e}")
                    self.logger.error(f"Command type: {type(command)}")
                    self.logger.error(f"Channel type: {type(channel)}")
                    import traceback
                    traceback.print_exc()
                    raise TecanError(f"Command execution failed: {str(e)}", "VisionX", 1)
            else:
                self.logger.error(f"Channel exists but is not alive (IsAlive: {is_alive})")
                # Try to refresh channel
                self.current_execution_channel = None
                raise TecanError("Execution channel is not alive. Make sure the method is running.", "VisionX", 1)
        else:
            self.logger.error("No execution channel available")
            # Try to get channel from runtime one more time
            if self.runtime:
                try:
                    if hasattr(self.runtime, 'GetCurrentExecutionChannel'):
                        channel = self.runtime.GetCurrentExecutionChannel()
                        if channel:
                            self.logger.info("Found channel via GetCurrentExecutionChannel - retrying...")
                            self.current_execution_channel = channel
                            return self._execute_command(command)
                except Exception as e:
                    self.logger.debug(f"Could not refresh channel: {e}")

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
        airgap_volume: int = DEFAULT_AIRGAP_VOLUME,
        airgap_speed: int = DEFAULT_AIRGAP_SPEED,
        diti_type: str = DEFAULT_DITI_TYPE,
        tip_indices: Optional[List[int]] = None
    ):
        """Get tips (like C# GetTips).
        
        Args:
            airgap_volume: Air gap volume in µL (default from constants)
            airgap_speed: Air gap speed (default from constants)
            diti_type: DiTi type string (default from constants)
            tip_indices: List of tip indices to use (0-7). If None, uses all 8 tips.
        """
        try:
            from .xml_commands import make_get_tips_xml
            
            self.logger.info(f"Getting tips: {diti_type}")
            xml = make_get_tips_xml(diti_type, airgap_volume, airgap_speed, tip_indices)
            self.logger.debug(f"GetTips XML: {xml[:200]}...")
            
            # Pass XML string directly - _execute_command will create comtypes command object
            self._execute_command(xml)
            
            # In simulation, wait a bit longer for the command to execute visually
            if self.simulation_mode:
                import time
                time.sleep(1.0)  # Give simulation time to show the movement
            
            self.logger.info(f"✓ Got tips: {diti_type}")
            
        except Exception as e:
            self.logger.error(f"Failed to get tips: {e}")
            import traceback
            traceback.print_exc()
            raise TecanError(f"Failed to get tips: {str(e)}", "VisionX", 1)

    def drop_tips_to_location(self, labware: str, tip_indices: Optional[List[int]] = None):
        """Drop tips to a specific location (like C# DropTips).
        
        Args:
            labware: Name of the labware to drop tips to (e.g., waste chute)
            tip_indices: List of tip indices to drop. If None, drops all tips.
        """
        try:
            from .xml_commands import make_drop_tips_xml
            
            self.logger.info(f"Dropping tips to {labware}")
            xml = make_drop_tips_xml(labware, tip_indices)
            self.logger.debug(f"DropTips XML: {xml[:200]}...")
            
            # Pass XML string directly - _execute_command will create comtypes command object
            self._execute_command(xml)
            
            # In simulation, wait a bit longer for the command to execute visually
            if self.simulation_mode:
                import time
                time.sleep(1.0)  # Give simulation time to show the movement
            
            self.logger.info(f"✓ Dropped tips to {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to drop tips: {e}")
            import traceback
            traceback.print_exc()
            raise TecanError(f"Failed to drop tips: {str(e)}", "VisionX", 1)

    # ========================================================================
    # LIQUID HANDLING (Aspirate/Dispense)
    # ========================================================================

    def aspirate_volume(
        self,
        volumes: Union[int, List[int]],
        labware: str,
        liquid_class: str = DEFAULT_LIQUID_CLASS,
        well_offsets: Optional[Union[int, List[int]]] = None,
        tip_indices: Optional[List[int]] = None
    ):
        """Aspirate liquid (like C# Aspirate command).
        
        Args:
            volumes: Volume(s) to aspirate in µL. Can be single int or list for multi-channel.
            labware: Name of the labware to aspirate from
            liquid_class: Liquid class to use (default from constants)
            well_offsets: Well offset(s). Can be single int or list. If None, all from well 0.
            tip_indices: List of tip indices to use. If None, uses all tips.
        """
        try:
            from .xml_commands import make_aspirate_xml
            
            # Convert single values to lists
            if isinstance(volumes, int):
                volumes = [volumes]
            if isinstance(well_offsets, int):
                well_offsets = [well_offsets]
            if well_offsets is None:
                well_offsets = [0] * len(volumes)
            
            self.logger.info(f"Aspirating {volumes}µL from {labware} (wells: {well_offsets})")
            xml = make_aspirate_xml(labware, volumes, liquid_class, well_offsets, tip_indices)
            self.logger.debug(f"Aspirate XML: {xml[:200]}...")
            
            # Pass XML string directly - _execute_command will create comtypes command object
            self._execute_command(xml)
            
            # In simulation, wait longer for the command to execute visually
            if self.simulation_mode:
                import time
                time.sleep(1.5)  # Give simulation time to show the movement
            
            self.logger.info(f"✓ Aspirated {volumes}µL from {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to aspirate: {e}")
            import traceback
            traceback.print_exc()
            raise TecanError(f"Failed to aspirate: {str(e)}", "VisionX", 1)

    def dispense_volume(
        self,
        volumes: Union[int, List[int]],
        labware: str,
        liquid_class: str = DEFAULT_LIQUID_CLASS,
        well_offsets: Optional[Union[int, List[int]]] = None,
        tip_indices: Optional[List[int]] = None
    ):
        """Dispense liquid (like C# Dispense command).
        
        Args:
            volumes: Volume(s) to dispense in µL. Can be single int or list for multi-channel.
            labware: Name of the labware to dispense to
            liquid_class: Liquid class to use (default from constants)
            well_offsets: Well offset(s). Can be single int or list. If None, all to well 0.
            tip_indices: List of tip indices to use. If None, uses all tips.
        """
        try:
            from .xml_commands import make_dispense_xml
            
            # Convert single values to lists
            if isinstance(volumes, int):
                volumes = [volumes]
            if isinstance(well_offsets, int):
                well_offsets = [well_offsets]
            if well_offsets is None:
                well_offsets = [0] * len(volumes)
            
            self.logger.info(f"Dispensing {volumes}µL to {labware} (wells: {well_offsets})")
            xml = make_dispense_xml(labware, volumes, liquid_class, well_offsets, tip_indices)
            self.logger.debug(f"Dispense XML: {xml[:200]}...")
            
            # Pass XML string directly - _execute_command will create comtypes command object
            self._execute_command(xml)
            
            # In simulation, wait longer for the command to execute visually
            if self.simulation_mode:
                import time
                time.sleep(1.5)  # Give simulation time to show the movement
            
            self.logger.info(f"✓ Dispensed {volumes}µL to {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to dispense: {e}")
            import traceback
            traceback.print_exc()
            raise TecanError(f"Failed to dispense: {str(e)}", "VisionX", 1)

    # ========================================================================
    # FCA (LiHa) MOVEMENT OPERATIONS
    # ========================================================================

    def fca_move_to_position(
        self,
        labware: str,
        well_offset: int = 0,
        z_position: Optional[float] = None,
        tip_indices: Optional[List[int]] = None
    ):
        """Move FCA (LiHa) to a specific position above labware.
        
        Args:
            labware: Target labware name
            well_offset: Well offset (0-based)
            z_position: Z position in mm (None = safe travel height)
            tip_indices: List of tip indices to move. If None, uses all 8 tips.
        """
        try:
            from .xml_commands import make_fca_move_to_position_xml
            
            self.logger.info(f"FCA moving to {labware} well offset {well_offset}")
            xml = make_fca_move_to_position_xml(labware, well_offset, z_position, tip_indices=tip_indices)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.0)
            
            self.logger.info(f"✓ FCA moved to position")
            
        except Exception as e:
            self.logger.error(f"Failed to move FCA: {e}")
            raise TecanError(f"Failed to move FCA: {str(e)}", "VisionX", 1)

    def fca_move_to_safe_position(self):
        """Move FCA (LiHa) to safe/home position."""
        try:
            from .xml_commands import make_fca_move_to_safe_position_xml
            
            self.logger.info("FCA moving to safe position")
            xml = make_fca_move_to_safe_position_xml()
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.0)
            
            self.logger.info("✓ FCA at safe position")
            
        except Exception as e:
            self.logger.error(f"Failed to move FCA to safe position: {e}")
            raise TecanError(f"Failed to move FCA to safe position: {str(e)}", "VisionX", 1)

    # ========================================================================
    # MCA (96-CHANNEL) OPERATIONS
    # ========================================================================

    def mca_get_tips(
        self,
        diti_type: str = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 150ul Filtered SBS",
        airgap_volume: int = DEFAULT_AIRGAP_VOLUME,
        airgap_speed: int = DEFAULT_AIRGAP_SPEED
    ):
        """Get tips with MCA (96-channel arm).
        
        Args:
            diti_type: DiTi type string for MCA tips
            airgap_volume: Air gap volume in µL
            airgap_speed: Air gap speed
        """
        try:
            from .xml_commands import make_mca_get_tips_xml
            
            self.logger.info(f"MCA getting tips: {diti_type}")
            xml = make_mca_get_tips_xml(diti_type, airgap_volume, airgap_speed)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.5)
            
            self.logger.info("✓ MCA tips acquired")
            
        except Exception as e:
            self.logger.error(f"Failed to get MCA tips: {e}")
            raise TecanError(f"Failed to get MCA tips: {str(e)}", "VisionX", 1)

    def mca_drop_tips(self, labware: str = DEFAULT_MCA_WASTE):
        """Drop tips with MCA (96-channel arm).
        
        Args:
            labware: Labware name (e.g., waste chute)
        """
        try:
            from .xml_commands import make_mca_drop_tips_xml
            
            self.logger.info(f"MCA dropping tips to {labware}")
            xml = make_mca_drop_tips_xml(labware)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.0)
            
            self.logger.info("✓ MCA tips dropped")
            
        except Exception as e:
            self.logger.error(f"Failed to drop MCA tips: {e}")
            raise TecanError(f"Failed to drop MCA tips: {str(e)}", "VisionX", 1)

    def mca_aspirate(
        self,
        labware: str,
        volume: int,
        liquid_class: str = DEFAULT_LIQUID_CLASS,
        well_offset: int = 0
    ):
        """Aspirate with MCA (96-channel arm).
        
        Args:
            labware: Labware name
            volume: Volume to aspirate in µL (same for all 96 channels)
            liquid_class: Liquid class name
            well_offset: Well offset (0-based, typically 0 for full plate)
        """
        try:
            from .xml_commands import make_mca_aspirate_xml
            
            self.logger.info(f"MCA aspirating {volume}µL from {labware}")
            xml = make_mca_aspirate_xml(labware, volume, liquid_class, well_offset)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.5)
            
            self.logger.info(f"✓ MCA aspirated {volume}µL")
            
        except Exception as e:
            self.logger.error(f"Failed to aspirate with MCA: {e}")
            raise TecanError(f"Failed to aspirate with MCA: {str(e)}", "VisionX", 1)

    def mca_dispense(
        self,
        labware: str,
        volume: int,
        liquid_class: str = DEFAULT_LIQUID_CLASS,
        well_offset: int = 0
    ):
        """Dispense with MCA (96-channel arm).
        
        Args:
            labware: Labware name
            volume: Volume to dispense in µL (same for all 96 channels)
            liquid_class: Liquid class name
            well_offset: Well offset (0-based, typically 0 for full plate)
        """
        try:
            from .xml_commands import make_mca_dispense_xml
            
            self.logger.info(f"MCA dispensing {volume}µL to {labware}")
            xml = make_mca_dispense_xml(labware, volume, liquid_class, well_offset)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.5)
            
            self.logger.info(f"✓ MCA dispensed {volume}µL")
            
        except Exception as e:
            self.logger.error(f"Failed to dispense with MCA: {e}")
            raise TecanError(f"Failed to dispense with MCA: {str(e)}", "VisionX", 1)

    def mca_move_to_safe_position(self):
        """Move MCA (96-channel arm) to safe/home position."""
        try:
            from .xml_commands import make_mca_move_to_safe_position_xml
            
            self.logger.info("MCA moving to safe position")
            xml = make_mca_move_to_safe_position_xml()
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.0)
            
            self.logger.info("✓ MCA at safe position")
            
        except Exception as e:
            self.logger.error(f"Failed to move MCA to safe position: {e}")
            raise TecanError(f"Failed to move MCA to safe position: {str(e)}", "VisionX", 1)

    # ========================================================================
    # RGA (GRIPPER) OPERATIONS
    # ========================================================================

    def rga_get_labware(
        self,
        labware: str,
        grip_force: int = 5,
        grip_width: Optional[float] = None
    ):
        """Pick up labware with RGA (robotic gripper arm).
        
        Args:
            labware: Labware name to pick up
            grip_force: Grip force (1-10 scale, 5 is medium)
            grip_width: Grip width in mm (None = auto-detect from labware)
        """
        try:
            from .xml_commands import make_rga_get_labware_xml
            
            self.logger.info(f"RGA picking up labware: {labware}")
            xml = make_rga_get_labware_xml(labware, grip_force, grip_width)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.5)
            
            self.logger.info(f"✓ RGA picked up {labware}")
            
        except Exception as e:
            self.logger.error(f"Failed to get labware with RGA: {e}")
            raise TecanError(f"Failed to get labware with RGA: {str(e)}", "VisionX", 1)

    def rga_put_labware(
        self,
        labware: str,
        target_location: str
    ):
        """Place labware with RGA (robotic gripper arm).
        
        Args:
            labware: Labware name being held
            target_location: Target location to place labware
        """
        try:
            from .xml_commands import make_rga_put_labware_xml
            
            self.logger.info(f"RGA placing labware {labware} at {target_location}")
            xml = make_rga_put_labware_xml(labware, target_location)
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.5)
            
            self.logger.info(f"✓ RGA placed {labware} at {target_location}")
            
        except Exception as e:
            self.logger.error(f"Failed to put labware with RGA: {e}")
            raise TecanError(f"Failed to put labware with RGA: {str(e)}", "VisionX", 1)

    def rga_move_to_safe_position(self):
        """Move RGA (gripper) to safe/home position."""
        try:
            from .xml_commands import make_rga_move_to_safe_position_xml
            
            self.logger.info("RGA moving to safe position")
            xml = make_rga_move_to_safe_position_xml()
            self._execute_command(xml)
            
            if self.simulation_mode:
                import time
                time.sleep(1.0)
            
            self.logger.info("✓ RGA at safe position")
            
        except Exception as e:
            self.logger.error(f"Failed to move RGA to safe position: {e}")
            raise TecanError(f"Failed to move RGA to safe position: {str(e)}", "VisionX", 1)

    def rga_transfer_labware(
        self,
        labware: str,
        target_location: str,
        grip_force: int = 5
    ):
        """Complete labware transfer using RGA (pick up and place).
        
        This is a convenience method that combines rga_get_labware and rga_put_labware.
        
        Args:
            labware: Labware name to transfer
            target_location: Target location to place labware
            grip_force: Grip force (1-10 scale)
        """
        self.logger.info(f"RGA transferring {labware} to {target_location}")
        self.rga_get_labware(labware, grip_force)
        self.rga_put_labware(labware, target_location)
        self.logger.info(f"✓ RGA transfer complete")

    # ========================================================================
    # COMBINED MOVEMENT OPERATIONS
    # ========================================================================

    def move_all_arms_to_safe_position(self):
        """Move all arms (FCA, MCA, RGA) to their safe positions.
        
        This is useful before starting a new operation or at the end of a protocol.
        """
        self.logger.info("Moving all arms to safe positions...")
        
        errors = []
        
        try:
            self.fca_move_to_safe_position()
        except Exception as e:
            errors.append(f"FCA: {e}")
        
        try:
            self.mca_move_to_safe_position()
        except Exception as e:
            errors.append(f"MCA: {e}")
        
        try:
            self.rga_move_to_safe_position()
        except Exception as e:
            errors.append(f"RGA: {e}")
        
        if errors:
            self.logger.warning(f"Some arms failed to move to safe position: {errors}")
        else:
            self.logger.info("✓ All arms at safe positions")

    # ========================================================================
    # GRIPPER FINGER OPERATIONS (like C# GetFingers, DropFingers)
    # ========================================================================

    def get_fingers(self, device_alias: str, gripper_fingers: str):
        """Get gripper fingers (like C# GetFingers).
        
        Args:
            device_alias: Device alias
            gripper_fingers: Gripper fingers to get
        """
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
        # Convert PyLabRobot operations to direct API format
        volumes = []
        well_offsets = []
        labware_name = None
        liquid_class = DEFAULT_LIQUID_CLASS
        
        for i, channel in enumerate(use_channels):
            if i < len(ops):
                op = ops[i]
                volume = int(op.volume)
                volumes.append(volume)
                
                # Extract labware name from PyLabRobot resource
                # PyLabRobot: plate["A1"] returns a Well object with parent
                well_offset = 0
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
                            # Well name like "A1" - convert to offset (already imported at top)
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
        # Convert PyLabRobot operations to direct API format
        volumes = []
        well_offsets = []
        labware_name = None
        liquid_class = DEFAULT_LIQUID_CLASS
        
        for i, channel in enumerate(use_channels):
            if i < len(ops):
                op = ops[i]
                volume = int(op.volume)
                volumes.append(volume)
                
                # Extract labware name from PyLabRobot resource
                well_offset = 0
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
                            # Well name like "A1" - convert to offset (already imported at top)
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
        self.logger.info(f"PyLabRobot -> Direct API: pick_up_tips() -> get_tips()")
        
        # Get tips - use default diti_type since PyLabRobot resources don't have this info
        # Extract tip_indices from use_channels
        tip_indices = use_channels if use_channels else None
        self.logger.info(f"Calling direct API: get_tips(diti_type=DEFAULT_DITI_TYPE, tip_indices={tip_indices})")
        self.get_tips(
            diti_type=DEFAULT_DITI_TYPE,
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
        self.logger.info(f"PyLabRobot -> Direct API: drop_tips() -> drop_tips_to_location()")
        
        # Drop tips - use default waste location
        # Extract tip_indices from use_channels
        tip_indices = use_channels if use_channels else None
        self.logger.info(f"Calling direct API: drop_tips_to_location(labware=DEFAULT_MCA_WASTE, tip_indices={tip_indices})")
        self.drop_tips_to_location(
            labware=DEFAULT_MCA_WASTE,
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
        # Use Tecan's transfer labware command
        # Note: This is a simplified implementation
        target_location = f"Grid:{int(location.x/100)}/Site:{int(location.y/100)}"
        self.transfer_labware(resource.name, target_location)
