"""
Tecan Fluent Tip Type Definitions

This module contains common DiTi (Disposable Tip) type strings
for use with Tecan Fluent robots.

The tip type string format is:
  TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:<arm>, <volume> <filter> <format>

Where:
  - <arm> = FCA (Fixed Channel Arm) or MCA (Multi-Channel Arm)
  - <volume> = 50ul, 200ul, 1000ul, 150ul, etc.
  - <filter> = Filtered or non-filtered
  - <format> = SBS (standard format)
"""


class FCA:
    """Fixed Channel Arm (FCA) tip types - typically 8 channels."""
    
    # Filtered tips
    TIPS_50UL_FILTERED = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 50ul Filtered SBS"
    TIPS_200UL_FILTERED = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul Filtered SBS"
    TIPS_1000UL_FILTERED = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 1000ul Filtered SBS"
    
    # Non-filtered tips
    TIPS_50UL = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 50ul SBS"
    TIPS_200UL = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul SBS"
    TIPS_1000UL = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 1000ul SBS"
    
    # Default
    DEFAULT = TIPS_200UL_FILTERED


class MCA:
    """Multi-Channel Arm (MCA) tip types - typically 96 or 384 channels."""
    
    # Filtered tips
    TIPS_150UL_FILTERED = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 150ul Filtered SBS"
    TIPS_50UL_FILTERED = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 50ul Filtered SBS"
    
    # Non-filtered tips
    TIPS_150UL = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 150ul SBS"
    TIPS_50UL = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 50ul SBS"
    
    # Default
    DEFAULT = TIPS_150UL_FILTERED


# Common liquid classes
class LiquidClass:
    """Common liquid classes for Tecan Fluent."""
    
    WATER_FREE_SINGLE = "Water Free Single"
    WATER_FREE_MULTI = "Water Free Multi"
    WATER_WET = "Water Wet"
    SERUM_FREE = "Serum Free Single"
    DMSO = "DMSO Free Single"
    GLYCEROL_50 = "Glycerol 50% Free Single"
    
    # Default
    DEFAULT = WATER_FREE_SINGLE


# Helper function to get tip type from user-friendly name
def get_tip_type(name: str) -> str:
    """
    Get tip type string from a friendly name.
    
    Args:
        name: Friendly name like "FCA 200", "MCA 150 filtered", etc.
        
    Returns:
        Full tip type string
    """
    name = name.lower().replace("ul", "").replace("µl", "").strip()
    
    # FCA tips
    if "fca" in name:
        if "1000" in name:
            return FCA.TIPS_1000UL_FILTERED if "filter" in name else FCA.TIPS_1000UL
        elif "50" in name:
            return FCA.TIPS_50UL_FILTERED if "filter" in name else FCA.TIPS_50UL
        else:  # Default to 200
            return FCA.TIPS_200UL_FILTERED if "filter" in name else FCA.TIPS_200UL
    
    # MCA tips
    elif "mca" in name:
        if "50" in name:
            return MCA.TIPS_50UL_FILTERED if "filter" in name else MCA.TIPS_50UL
        else:  # Default to 150
            return MCA.TIPS_150UL_FILTERED if "filter" in name else MCA.TIPS_150UL
    
    # Default
    return FCA.DEFAULT


def list_all_tip_types():
    """Print all available tip type definitions."""
    print("\n" + "=" * 60)
    print("  Available Tip Types")
    print("=" * 60)
    
    print("\nFCA (Fixed Channel Arm) Tips:")
    print("-" * 40)
    for attr in dir(FCA):
        if attr.startswith("TIPS"):
            print(f"  FCA.{attr}")
            print(f"    = \"{getattr(FCA, attr)}\"")
    
    print("\nMCA (Multi-Channel Arm) Tips:")
    print("-" * 40)
    for attr in dir(MCA):
        if attr.startswith("TIPS"):
            print(f"  MCA.{attr}")
            print(f"    = \"{getattr(MCA, attr)}\"")
    
    print("\nLiquid Classes:")
    print("-" * 40)
    for attr in dir(LiquidClass):
        if not attr.startswith("_") and attr != "DEFAULT":
            print(f"  LiquidClass.{attr} = \"{getattr(LiquidClass, attr)}\"")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    list_all_tip_types()

