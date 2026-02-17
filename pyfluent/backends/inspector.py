"""
Helper functions to inspect FluentControl configuration (labware, liquid classes, etc.)

This module provides functions to list available labware, liquid classes, and other
configuration items from FluentControl so users can verify what's available before
running protocols.
"""

import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger("FluentInspector")


def list_available_labware(backend) -> List[str]:
    """List available labware names from FluentControl worktable.
    
    Args:
        backend: FluentVisionX backend instance (must be connected)
    
    Returns:
        List of labware names as strings
    """
    labware_list = []
    
    if not backend or not backend.runtime:
        logger.warning("Backend not connected - cannot list labware")
        return labware_list
    
    try:
        # Try to get worktable
        if hasattr(backend.runtime, 'GetWorktable'):
            worktable = backend.runtime.GetWorktable()
            if worktable:
                # Try to get labware from worktable
                if hasattr(worktable, 'GetLabware') or hasattr(worktable, 'Labware'):
                    try:
                        if hasattr(worktable, 'GetLabware'):
                            labware_items = worktable.GetLabware()
                        else:
                            labware_items = worktable.Labware
                        
                        # Try to enumerate items
                        if hasattr(labware_items, '__iter__'):
                            for item in labware_items:
                                if hasattr(item, 'Name'):
                                    labware_list.append(str(item.Name))
                                elif hasattr(item, '__str__'):
                                    labware_list.append(str(item))
                    except Exception as e:
                        logger.debug(f"Could not enumerate labware: {e}")
        
        # Try method workspace (which has labware for the method)
        if hasattr(backend.runtime, 'GetMethodWorkspace'):
            try:
                # Try common method names
                for method_name in ['demo', 'Demo', 'API', 'api']:
                    try:
                        workspace = backend.runtime.GetMethodWorkspace(method_name)
                        if workspace and hasattr(workspace, 'Labware'):
                            labware_items = workspace.Labware
                            if hasattr(labware_items, '__iter__'):
                                for item in labware_items:
                                    if hasattr(item, 'Name'):
                                        name = str(item.Name)
                                        if name not in labware_list:
                                            labware_list.append(name)
                                    elif hasattr(item, '__str__'):
                                        name = str(item)
                                        if name not in labware_list:
                                            labware_list.append(name)
                        break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Could not get method workspace: {e}")
    
    except Exception as e:
        logger.warning(f"Error listing labware: {e}")
    
    return labware_list


def list_available_liquid_classes(backend) -> List[str]:
    """List available liquid class names from FluentControl.
    
    Args:
        backend: FluentVisionX backend instance (must be connected)
    
    Returns:
        List of liquid class names as strings
    """
    liquid_classes = []
    
    if not backend or not backend.runtime:
        logger.warning("Backend not connected - cannot list liquid classes")
        return liquid_classes
    
    try:
        # Try to get liquid classes from runtime
        if hasattr(backend.runtime, 'GetLiquidClasses'):
            try:
                lc_items = backend.runtime.GetLiquidClasses()
                if hasattr(lc_items, '__iter__'):
                    for item in lc_items:
                        if hasattr(item, 'Name'):
                            liquid_classes.append(str(item.Name))
                        elif hasattr(item, '__str__'):
                            liquid_classes.append(str(item))
            except Exception as e:
                logger.debug(f"Could not get liquid classes: {e}")
        
        # Try alternative method
        if hasattr(backend.runtime, 'LiquidClasses'):
            try:
                lc_items = backend.runtime.LiquidClasses
                if hasattr(lc_items, '__iter__'):
                    for item in lc_items:
                        if hasattr(item, 'Name'):
                            name = str(item.Name)
                            if name not in liquid_classes:
                                liquid_classes.append(name)
                        elif hasattr(item, '__str__'):
                            name = str(item)
                            if name not in liquid_classes:
                                liquid_classes.append(name)
            except Exception as e:
                logger.debug(f"Could not get liquid classes via property: {e}")
    
    except Exception as e:
        logger.warning(f"Error listing liquid classes: {e}")
    
    return liquid_classes


def print_configuration_summary(backend) -> None:
    """Print a summary of available FluentControl configuration.
    
    This includes:
    - Available labware
    - Available liquid classes (if accessible)
    - Current method name (if running)
    - Runtime status
    
    Args:
        backend: FluentVisionX backend instance (must be connected)
    """
    print("=" * 60)
    print("FluentControl Configuration Summary")
    print("=" * 60)
    
    if not backend or not backend.runtime:
        print("ERROR: Backend not connected")
        return
    
    # Runtime status
    try:
        if hasattr(backend.runtime, 'GetFluentStatus'):
            status = backend.runtime.GetFluentStatus()
            print(f"\nRuntime Status: {status}")
    except:
        pass
    
    # Available labware
    print("\nAvailable Labware:")
    labware = list_available_labware(backend)
    if labware:
        for lw in labware:
            print(f"  - {lw}")
    else:
        print("  (Could not retrieve labware list via API)")
        print("  Please check FluentControl worktable/deck view for labware names")
    
    # Available liquid classes
    print("\nAvailable Liquid Classes:")
    liquid_classes = list_available_liquid_classes(backend)
    if liquid_classes:
        for lc in liquid_classes:
            print(f"  - {lc}")
    else:
        print("  (Could not retrieve liquid classes via API)")
        print("  Please check FluentControl Liquid Classes settings")
    
    print("\n" + "=" * 60)
    print("Note: Labware names must match exactly (case-sensitive)")
    print("      Liquid class names must match exactly (case-sensitive)")
    print("=" * 60)


