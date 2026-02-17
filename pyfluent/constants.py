"""
Constants for PyFluent.

This module centralizes all default values to ensure consistency across modules.
"""

# ========================================================================
# LIQUID CLASSES
# ========================================================================

# Default liquid class for general use
# "Water Free Single" is safer for simulation and testing
DEFAULT_LIQUID_CLASS = "Water Free Single"

# Alternative liquid class that may work better on some systems
WATER_TEST_NO_DETECT = "Water Test No Detect"

# ========================================================================
# WASTE LOCATIONS
# ========================================================================

# Default waste chute for FCA (8-channel LiHa)
DEFAULT_FCA_WASTE = "FCA Thru Deck Waste Chute_1"

# Default waste chute for MCA (96-channel)
DEFAULT_MCA_WASTE = "MCA Thru Deck Waste Chute with Tip Drop Guide_2"

# Generic waste - use FCA as default
DEFAULT_WASTE_LOCATION = DEFAULT_FCA_WASTE

# ========================================================================
# TIP TYPES
# ========================================================================

# Default 200µL filtered tips for FCA
DEFAULT_DITI_TYPE = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul"

# 200µL filtered SBS format tips
DITI_200UL_FILTERED_SBS = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul Filtered SBS"

# ========================================================================
# DEVICE ALIASES
# ========================================================================

# FCA - Fixed Channel Arm (8-channel LiHa)
FCA_DEVICE_ALIAS = "Instrument=1/Device=LIHA:1"
LIHA_DEVICE_ALIAS = FCA_DEVICE_ALIAS  # Alias for backward compatibility

# MCA - Multi-Channel Arm (96-channel)
MCA_DEVICE_ALIAS = "Instrument=1/Device=MCA96:1"

# RGA - Robotic Gripper Arm
RGA_DEVICE_ALIAS = "Instrument=1/Device=RGA:1"

# Te-VacS - Vacuum system (if present)
TEVACS_DEVICE_ALIAS = "Instrument=1/Device=TeVacS:1"

# ========================================================================
# GRIPPER CONSTANTS
# ========================================================================

# Default gripper finger types
DEFAULT_GRIPPER_FINGERS = "Wide Fingers"
NARROW_GRIPPER_FINGERS = "Narrow Fingers"

# Default grip force (1-10 scale, 5 is medium)
DEFAULT_GRIP_FORCE = 5

# Default grip width for standard SBS plates (mm)
DEFAULT_GRIP_WIDTH_SBS = 85.48  # Standard SBS plate width

# Grip modes
GRIP_MODE_SIDE = "Side"
GRIP_MODE_TOP = "Top"

# ========================================================================
# MOVEMENT SPEEDS
# ========================================================================

# Speed settings (percentage of max, 1-100)
SPEED_SLOW = 30
SPEED_MEDIUM = 60
SPEED_FAST = 100

# Z-axis travel height (mm above deck)
DEFAULT_Z_TRAVEL_HEIGHT = 150.0

# ========================================================================
# WELL PLATE DIMENSIONS
# ========================================================================

# 96-well plate dimensions
ROWS_96_WELL = 8
COLS_96_WELL = 12

# 384-well plate dimensions
ROWS_384_WELL = 16
COLS_384_WELL = 24

# ========================================================================
# AIRGAP DEFAULTS
# ========================================================================

DEFAULT_AIRGAP_VOLUME = 10  # µL
DEFAULT_AIRGAP_SPEED = 70
