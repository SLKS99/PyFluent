"""
Tecan Fluent Worktable Editor

This module allows programmatic editing of Tecan FluentControl worktables.

WARNING: This modifies FluentControl's database files. 
Always backup before making changes!
"""

import os
import shutil
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import hashlib


# Paths
WORKTABLE_BASE = r"C:\ProgramData\Tecan\VisionX\DataBase\SystemSpecific\Worktable"
WORKSPACES_PATH = os.path.join(WORKTABLE_BASE, "Workspaces")
COMPONENTS_PATH = os.path.join(WORKTABLE_BASE, "Components")
SITES_PATH = os.path.join(WORKTABLE_BASE, "Sites")


@dataclass
class Component:
    """Represents a labware component."""
    guid: str
    name: str
    file_path: str
    component_type: str = ""


@dataclass 
class Site:
    """Represents a site (position) on a carrier."""
    guid: str
    name: str
    carrier_guid: str
    position: int


class WorktableEditor:
    """
    Editor for Tecan FluentControl worktables.
    
    Example:
        editor = WorktableEditor()
        
        # List available worktables
        worktables = editor.list_worktables()
        
        # Load a worktable
        editor.load_worktable("MSL_Fluent_WT_v4-Copy 1-Copy 1")
        
        # List available components
        diti = editor.find_components("DiTi")
        plates = editor.find_components("96 Well")
        
        # Add labware to a site
        editor.add_labware_to_site(diti[0], carrier="4 FCA DiTi Nest[001]", position=3)
        editor.add_labware_to_site(plates[0], carrier="6 Landscape 61mm Nest[001]", position=1)
        
        # Save (creates a copy)
        editor.save("MyNewWorktable")
    """
    
    def __init__(self):
        self.current_worktable = None
        self.current_worktable_path = None
        self.current_tree = None
        self.components_cache = {}
        self.sites_cache = {}
        
        # Load component catalog
        self._load_components()
    
    def _load_components(self):
        """Load all available components into cache."""
        if not os.path.exists(COMPONENTS_PATH):
            print(f"Warning: Components path not found: {COMPONENTS_PATH}")
            return
        
        for f in os.listdir(COMPONENTS_PATH):
            if f.endswith('.xcmp'):
                filepath = os.path.join(COMPONENTS_PATH, f)
                try:
                    tree = ET.parse(filepath)
                    root = tree.getroot()
                    
                    # Find name
                    name = None
                    for elem in root.iter():
                        if 'ObjectName' in elem.tag and elem.text:
                            name = elem.text.strip()
                            break
                    
                    if name:
                        guid = f.replace('.xcmp', '')
                        self.components_cache[guid] = Component(
                            guid=guid,
                            name=name,
                            file_path=filepath
                        )
                except:
                    pass
        
        print(f"Loaded {len(self.components_cache)} components")
    
    def list_worktables(self) -> List[Tuple[str, str]]:
        """
        List all available worktables.
        
        Returns:
            List of (name, filename) tuples
        """
        worktables = []
        
        if not os.path.exists(WORKSPACES_PATH):
            return worktables
        
        for f in os.listdir(WORKSPACES_PATH):
            if f.endswith('.xwsp'):
                filepath = os.path.join(WORKSPACES_PATH, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as file:
                        content = file.read(5000)
                        # Find ObjectName
                        import re
                        match = re.search(r'<ObjectName>([^<]+)</ObjectName>', content)
                        if match:
                            name = match.group(1).strip()
                            worktables.append((name, f))
                except:
                    pass
        
        return worktables
    
    def find_worktable(self, name_pattern: str) -> Optional[str]:
        """Find a worktable by name pattern."""
        for wt_name, wt_file in self.list_worktables():
            if name_pattern.lower() in wt_name.lower():
                return wt_file
        return None
    
    def load_worktable(self, name_or_file: str) -> bool:
        """
        Load a worktable for editing.
        
        Args:
            name_or_file: Worktable name or filename
        """
        # Find file
        if name_or_file.endswith('.xwsp'):
            filepath = os.path.join(WORKSPACES_PATH, name_or_file)
        else:
            wt_file = self.find_worktable(name_or_file)
            if not wt_file:
                print(f"Worktable not found: {name_or_file}")
                return False
            filepath = os.path.join(WORKSPACES_PATH, wt_file)
        
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return False
        
        try:
            self.current_tree = ET.parse(filepath)
            self.current_worktable_path = filepath
            
            # Get name
            root = self.current_tree.getroot()
            for elem in root.iter():
                if 'ObjectName' in elem.tag and elem.text:
                    self.current_worktable = elem.text.strip()
                    break
            
            print(f"Loaded worktable: {self.current_worktable}")
            return True
            
        except Exception as e:
            print(f"Error loading worktable: {e}")
            return False
    
    def find_components(self, pattern: str) -> List[Component]:
        """
        Find components matching a pattern.
        
        Args:
            pattern: Search pattern (e.g., "DiTi", "96 Well")
            
        Returns:
            List of matching components
        """
        matches = []
        pattern_lower = pattern.lower()
        
        for comp in self.components_cache.values():
            if pattern_lower in comp.name.lower():
                matches.append(comp)
        
        return matches
    
    def get_worktable_components(self) -> List[str]:
        """Get list of component GUIDs in current worktable."""
        if not self.current_tree:
            return []
        
        components = []
        root = self.current_tree.getroot()
        
        for elem in root.iter():
            if 'Reference' in elem.tag:
                for child in elem:
                    if 'Guid' in child.tag and child.text:
                        components.append(child.text.strip())
        
        return components
    
    def add_component_reference(self, component: Component) -> bool:
        """
        Add a component reference to the worktable.
        
        Args:
            component: Component to add
        """
        if not self.current_tree:
            print("No worktable loaded")
            return False
        
        root = self.current_tree.getroot()
        
        # Find Payload element
        payload = None
        for elem in root.iter():
            if 'Payload' in elem.tag:
                payload = elem
                break
        
        if payload is None:
            print("Could not find Payload element")
            return False
        
        # Check if already exists
        existing = self.get_worktable_components()
        if component.guid in existing:
            print(f"Component already in worktable: {component.name}")
            return True
        
        # Create Reference element
        # Get namespace from existing references
        ns = ""
        for elem in root.iter():
            if '}' in elem.tag:
                ns = elem.tag.split('}')[0] + '}'
                break
        
        ref = ET.SubElement(payload, f"{ns}Reference")
        guid_elem = ET.SubElement(ref, f"{ns}Guid")
        guid_elem.text = component.guid
        type_elem = ET.SubElement(ref, f"{ns}TypeId")
        type_elem.text = "WorktableComponent"
        name_elem = ET.SubElement(ref, f"{ns}ObjectName")
        name_elem.text = component.guid
        
        print(f"Added component reference: {component.name}")
        return True
    
    def save(self, new_name: str = None, backup: bool = True) -> str:
        """
        Save the worktable.
        
        Args:
            new_name: New name for the worktable (creates copy)
            backup: Whether to create backup of original
            
        Returns:
            Path to saved file
        """
        if not self.current_worktable_path:
            print("No worktable loaded")
            return None
        
        if backup:
            backup_path = self.current_worktable_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(self.current_worktable_path, backup_path)
            print(f"Created backup: {backup_path}")
        
        # Read original file as text to preserve exact formatting
        with open(self.current_worktable_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        if new_name:
            # Replace name in content (preserves all formatting)
            old_name_tag = f"<ObjectName>{self.current_worktable}</ObjectName>"
            new_name_tag = f"<ObjectName>{new_name}</ObjectName>"
            content = content.replace(old_name_tag, new_name_tag, 1)
            
            # Generate new filename
            new_guid = str(uuid.uuid4())
            new_path = os.path.join(WORKSPACES_PATH, f"{new_guid}.xwsp")
        else:
            new_path = self.current_worktable_path
        
        # Write with BOM (UTF-8 with BOM like Tecan expects)
        with open(new_path, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        
        print(f"Saved worktable to: {new_path}")
        print(f"Worktable name: {new_name or self.current_worktable}")
        
        return new_path
    
    def print_components(self, pattern: str = None):
        """Print available components."""
        if pattern:
            components = self.find_components(pattern)
        else:
            components = list(self.components_cache.values())
        
        print(f"\n{'='*60}")
        print(f"  Components ({len(components)} found)")
        print(f"{'='*60}\n")
        
        for comp in components[:30]:
            print(f"  {comp.name}")
            print(f"    GUID: {comp.guid}")
    
    def print_worktable_info(self):
        """Print information about the loaded worktable."""
        if not self.current_tree:
            print("No worktable loaded")
            return
        
        print(f"\n{'='*60}")
        print(f"  Worktable: {self.current_worktable}")
        print(f"{'='*60}")
        
        components = self.get_worktable_components()
        print(f"\nContains {len(components)} component references")
        
        # Show first 10
        print("\nComponents:")
        for guid in components[:10]:
            if guid in self.components_cache:
                print(f"  - {self.components_cache[guid].name}")
            else:
                print(f"  - {guid} (unknown)")


def main():
    """Interactive worktable editor."""
    import sys
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("  Tecan Worktable Editor")
    print("=" * 70)
    
    editor = WorktableEditor()
    
    # List worktables
    print("\nAvailable worktables:")
    for name, file in editor.list_worktables():
        if 'MSL' in name:
            print(f"  * {name}")
    
    # Load target worktable
    print("\nLoading MSL_Fluent_WT_v4-Copy 1-Copy 1...")
    if editor.load_worktable("MSL_Fluent_WT_v4-Copy 1-Copy 1"):
        editor.print_worktable_info()
        
        # Find DiTi components
        print("\n" + "=" * 60)
        print("  Available DiTi Components")
        print("=" * 60)
        diti = editor.find_components("DiTi")
        for d in diti[:10]:
            print(f"  - {d.name}")
        
        # Find plate components
        print("\n" + "=" * 60)
        print("  Available 96-Well Components")
        print("=" * 60)
        plates = editor.find_components("96 Well")
        for p in plates[:10]:
            print(f"  - {p.name}")
        
        # Add components
        print("\n" + "=" * 60)
        print("  Adding Components to Worktable")
        print("=" * 60)
        
        # Add DiTi 200ul Filtered
        diti_200 = editor.find_components("200ul DiTi")
        if diti_200:
            editor.add_component_reference(diti_200[0])
        
        # Add 96 Well Flat
        plate_96 = editor.find_components("96 Well Flat")
        if plate_96:
            editor.add_component_reference(plate_96[0])
        
        # Save as new worktable
        print("\n" + "=" * 60)
        print("  Saving Modified Worktable")
        print("=" * 60)
        
        new_path = editor.save("MSL_Fluent_WT_PyFluent")
        
        if new_path:
            print(f"\nSuccess! New worktable created.")
            print(f"Restart FluentControl to see: MSL_Fluent_WT_PyFluent")


if __name__ == "__main__":
    main()

