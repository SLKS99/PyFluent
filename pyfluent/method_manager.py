"""
Method Manager for Tecan Fluent.

This module provides utilities for managing FluentControl methods,
including listing methods, getting info, and running them.

Note: In Tecan FluentControl, the worktable/deck configuration is 
stored within each method file. When you run a method, it uses 
the worktable defined in that method.
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class MethodInfo:
    """Information about a FluentControl method."""
    name: str
    has_variables: bool = False
    variables: Dict[str, str] = None
    has_api_channel: bool = False  # Needs manual verification
    
    def __post_init__(self):
        if self.variables is None:
            self.variables = {}


class MethodManager:
    """
    Manager for FluentControl methods.
    
    Provides utilities to:
    - List available methods
    - Get method information
    - Prepare and run methods
    - Set method variables
    
    Note: Worktables are defined within methods in TouchTools.
    Each method has its own deck configuration.
    """
    
    def __init__(self, runtime=None):
        """
        Initialize the method manager.
        
        Args:
            runtime: RuntimeController instance from FluentVisionX
        """
        self.runtime = runtime
        self._methods_cache: List[MethodInfo] = []
    
    def connect(self):
        """Connect to FluentControl if not already connected."""
        if self.runtime is not None:
            return True
        
        try:
            import clr
            from System.Reflection import Assembly
            
            # Try common paths
            dll_paths = [
                r"C:\Program Files (x86)\Tecan - Copy\fluentcontrol\Tecan.VisionX.API.V2.dll",
                r"C:\Program Files\Tecan\VisionX\API\Tecan.VisionX.API.V2.dll",
                r"C:\Program Files (x86)\Tecan\FluentControl\Tecan.VisionX.API.V2.dll",
            ]
            
            for path in dll_paths:
                if os.path.exists(path):
                    Assembly.LoadFrom(path)
                    break
            
            from Tecan.VisionX.API.V2 import FluentControl
            
            fluent = FluentControl()
            self.runtime = fluent.GetRuntime()
            
            if self.runtime is None:
                print("Warning: Runtime not available. FluentControl may not be logged in.")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error connecting: {e}")
            return False
    
    def get_status(self) -> str:
        """Get current FluentControl status."""
        if not self.runtime:
            return "Not connected"
        
        try:
            return str(self.runtime.GetFluentStatus())
        except:
            return "Unknown"
    
    def is_ready(self) -> bool:
        """Check if FluentControl is ready to run methods."""
        status = self.get_status()
        return "EditMode" in status
    
    def list_methods(self) -> List[str]:
        """
        Get list of available methods.
        
        Returns:
            List of method names
        """
        if not self.runtime:
            return []
        
        try:
            methods = self.runtime.GetAllRunnableMethods()
            return [str(m) for m in methods] if methods else []
        except:
            return []
    
    def get_method_info(self, method_name: str) -> MethodInfo:
        """
        Get information about a method.
        
        Args:
            method_name: Name of the method
            
        Returns:
            MethodInfo object
        """
        info = MethodInfo(name=method_name)
        
        if not self.runtime:
            return info
        
        try:
            # Prepare the method to access its variables
            self.runtime.PrepareMethod(method_name)
            
            # Get variables
            var_names = self.runtime.GetVariableNames()
            if var_names:
                info.has_variables = True
                for v in var_names:
                    try:
                        val = self.runtime.GetVariableValue(str(v))
                        info.variables[str(v)] = str(val)
                    except:
                        info.variables[str(v)] = "(unreadable)"
            
            # Check if name suggests API channel
            if "api" in method_name.lower():
                info.has_api_channel = True
                
        except Exception as e:
            print(f"Error getting method info: {e}")
        
        return info
    
    def prepare_method(self, method_name: str) -> bool:
        """
        Prepare a method for execution.
        
        Args:
            method_name: Name of the method to prepare
            
        Returns:
            True if successful
        """
        if not self.runtime:
            return False
        
        try:
            self.runtime.PrepareMethod(method_name)
            return True
        except Exception as e:
            print(f"Error preparing method: {e}")
            return False
    
    def set_variable(self, name: str, value: str) -> bool:
        """
        Set a method variable value.
        
        Args:
            name: Variable name
            value: Variable value
            
        Returns:
            True if successful
        """
        if not self.runtime:
            return False
        
        try:
            self.runtime.SetVariableValue(name, str(value))
            return True
        except Exception as e:
            print(f"Error setting variable: {e}")
            return False
    
    def run_method(self, method_name: str = None, variables: Dict[str, str] = None) -> bool:
        """
        Run a method.
        
        Args:
            method_name: Method to run (prepares if specified)
            variables: Optional variables to set before running
            
        Returns:
            True if started successfully
        """
        if not self.runtime:
            return False
        
        try:
            # Prepare if method name given
            if method_name:
                self.prepare_method(method_name)
            
            # Set variables if provided
            if variables:
                for name, value in variables.items():
                    self.set_variable(name, value)
            
            # Run
            self.runtime.RunMethod()
            return True
            
        except Exception as e:
            print(f"Error running method: {e}")
            return False
    
    def stop_method(self) -> bool:
        """Stop the currently running method."""
        if not self.runtime:
            return False
        
        try:
            self.runtime.StopMethod()
            return True
        except:
            return False
    
    def pause_method(self) -> bool:
        """Pause the currently running method."""
        if not self.runtime:
            return False
        
        try:
            self.runtime.PauseRun()
            return True
        except:
            return False
    
    def resume_method(self) -> bool:
        """Resume a paused method."""
        if not self.runtime:
            return False
        
        try:
            self.runtime.ResumeRun()
            return True
        except:
            return False
    
    def print_methods(self):
        """Print all available methods with info."""
        methods = self.list_methods()
        
        print("\n" + "=" * 60)
        print("  Available FluentControl Methods")
        print("=" * 60)
        print(f"\nStatus: {self.get_status()}")
        print(f"Found {len(methods)} methods:\n")
        
        for i, name in enumerate(methods):
            info = self.get_method_info(name)
            
            # Markers
            markers = []
            if info.has_api_channel:
                markers.append("API")
            if info.has_variables:
                markers.append(f"{len(info.variables)} vars")
            
            marker_str = f" [{', '.join(markers)}]" if markers else ""
            
            print(f"  {i+1}. {name}{marker_str}")
            
            # Show variables if any
            if info.variables:
                for var_name, var_val in info.variables.items():
                    print(f"       - {var_name} = {var_val}")
        
        print("\n" + "=" * 60)
        print("  Note: Worktables are configured within each method")
        print("  in TouchTools. Run a method to use its deck layout.")
        print("=" * 60 + "\n")


def list_methods():
    """Quick utility to list all available methods."""
    mgr = MethodManager()
    if mgr.connect():
        mgr.print_methods()
    else:
        print("Could not connect to FluentControl")


def run_method(method_name: str, variables: Dict[str, str] = None):
    """Quick utility to run a method."""
    mgr = MethodManager()
    if mgr.connect():
        if not mgr.is_ready():
            print(f"FluentControl not ready. Status: {mgr.get_status()}")
            return False
        return mgr.run_method(method_name, variables)
    return False

