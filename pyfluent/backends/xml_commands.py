"""
XML command generators for Tecan Fluent API.
These generate the exact XML structures that work with the Tecan VisionX API.
"""

from typing import List, Optional, Union

# Device aliases
FCA_DEVICE_ALIAS = "Instrument=1/Device=LIHA:1"
MCA_DEVICE_ALIAS = "Instrument=1/Device=MCA96:1"
RGA_DEVICE_ALIAS = "Instrument=1/Device=RGA:1"


def make_get_tips_xml(
    diti_type: str = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:FCA, 200ul",
    airgap_volume: int = 10,
    airgap_speed: int = 70,
    tip_indices: Optional[List[int]] = None
) -> str:
    """Generate GetTips XML command.
    
    Args:
        diti_type: DiTi type string
        airgap_volume: Air gap volume in µL
        airgap_speed: Air gap speed
        tip_indices: List of tip indices to use (0-7). If None, uses all 8 tips.
    
    Returns:
        XML string for GetTips command
    """
    if tip_indices is None:
        tip_indices = list(range(8))
    
    tips_xml = '\n'.join([
        f'                                                <Object Type="System.Int32"><int>{i}</int></Object>'
        for i in tip_indices
    ])
    
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaGetTipsScriptCommandDataV3">
            <LihaGetTipsScriptCommandDataV3>
                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LiHaScriptCommandUsingTipSelectionBaseDataV1">
                    <LiHaScriptCommandUsingTipSelectionBaseDataV1>
                        <SerializedTipsIndexes></SerializedTipsIndexes>
                        <SelectedTipsIndexes>
{tips_xml}
                        </SelectedTipsIndexes>
                        <TipMask></TipMask>
                        <TipOffset>0</TipOffset>
                        <TipSpacing>9</TipSpacing>
                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandDataV1">
                            <LihaScriptCommandDataV1>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                                    <ScriptCommandCommonDataV1>
                                        <LabwareName></LabwareName>
                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                            <DeviceAliasStatementBaseDataV1>
                                                <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                    <DeviceAlias>Instrument=1/Device=LIHA:1</DeviceAlias>
                                                </Alias>
                                                <ID><AvailableID></AvailableID></ID>
                                                <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                    <ScriptStatementBaseDataV1>
                                                        <IsBreakpoint>False</IsBreakpoint>
                                                        <IsDisabledForExecution>False</IsDisabledForExecution>
                                                        <GroupLineNumber>0</GroupLineNumber>
                                                        <LineNumber>1</LineNumber>
                                                    </ScriptStatementBaseDataV1>
                                                </Data>
                                            </DeviceAliasStatementBaseDataV1>
                                        </Data>
                                    </ScriptCommandCommonDataV1>
                                </Data>
                            </LihaScriptCommandDataV1>
                        </Data>
                    </LiHaScriptCommandUsingTipSelectionBaseDataV1>
                </Data>
                <AirgapVolume>{airgap_volume}</AirgapVolume>
                <AirgapSpeed>{airgap_speed}</AirgapSpeed>
                <DitiType><AvailableID>{diti_type}</AvailableID></DitiType>
                <UseNextPosition>True</UseNextPosition>
            </LihaGetTipsScriptCommandDataV3>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_aspirate_xml(
    labware: str,
    volumes: List[int],
    liquid_class: str,
    well_offsets: Optional[List[int]] = None,
    tip_indices: Optional[List[int]] = None
) -> str:
    """Generate Aspirate XML command (V5 format).
    
    Args:
        labware: Labware name
        volumes: List of volumes for each tip (µL)
        liquid_class: Liquid class name
        well_offsets: List of well offsets for each tip. If None, all from well 0.
        tip_indices: List of tip indices to use. If None, uses all tips.
    
    Returns:
        XML string for Aspirate command
    """
    if well_offsets is None:
        well_offsets = [0] * len(volumes)
    if tip_indices is None:
        tip_indices = list(range(len(volumes)))
    
    # Volumes array
    volumes_xml = '\n'.join([
        f'                            <Object Type="System.String"><string>{v}</string></Object>'
        for v in volumes
    ])
    
    # Serialized well indexes (semicolon-separated)
    serialized_wells = ';'.join([str(wo) for wo in well_offsets]) + ';'
    
    # Selected wells string
    if len(set(well_offsets)) == 1:
        # All same well - calculate proper well name
        offset = well_offsets[0]
        col = offset // 8  # Column-major: 8 rows per column
        row = offset % 8
        row_letter = chr(65 + row)  # A=0, B=1, etc.
        well_name = f"{row_letter}{col+1}"
        selected_wells = f"{len(volumes)} * {well_name}"
    else:
        # Multiple different wells - Tecan uses column-major ordering
        well_names = []
        for offset in well_offsets:
            col = offset // 8  # Column-major: 8 rows per column
            row = offset % 8
            row_letter = chr(65 + row)
            well_names.append(f"{row_letter}{col+1}")
        selected_wells = ";".join(well_names)
    
    # Tip indices
    tips_xml = '\n'.join([
        f'                                            <Object Type="System.Int32"><int>{i}</int></Object>'
        for i in tip_indices
    ])
    
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaAspirateScriptCommandDataV5">
            <LihaAspirateScriptCommandDataV5>
                <IsSwitchContainerSourceEnabled>False</IsSwitchContainerSourceEnabled>
                <OffsetX>0</OffsetX>
                <OffsetY>0</OffsetY>
                <Data Type="Tecan.Core.Instrument.Devices.Scripting.Data.LihaPipettingWithVolumesScriptCommandDataV7">
                    <LihaPipettingWithVolumesScriptCommandDataV7>
                        <Volumes>
{volumes_xml}
                        </Volumes>
                        <FlowRates />
                        <IsLiquidClassNameByExpressionEnabled>False</IsLiquidClassNameByExpressionEnabled>
                        <LiquidClassSelectionMode>
                            <LiquidClassSelectionMode>SingleByName</LiquidClassSelectionMode>
                        </LiquidClassSelectionMode>
                        <LiquidClassNameBySelection>{liquid_class}</LiquidClassNameBySelection>
                        <LiquidClassNameByExpression></LiquidClassNameByExpression>
                        <LiquidClassNames />
                        <Compartment>1</Compartment>
                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandUsingWellSelectionBaseDataV1">
                            <LihaScriptCommandUsingWellSelectionBaseDataV1>
                                <SerializedWellIndexes>{serialized_wells}</SerializedWellIndexes>
                                <SelectedWellsString>{selected_wells}</SelectedWellsString>
                                <WellOffset>{well_offsets[0]}</WellOffset>
                                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LiHaScriptCommandUsingTipSelectionBaseDataV1">
                                    <LiHaScriptCommandUsingTipSelectionBaseDataV1>
                                        <SerializedTipsIndexes></SerializedTipsIndexes>
                                        <SelectedTipsIndexes>
{tips_xml}
                                        </SelectedTipsIndexes>
                                        <TipMask></TipMask>
                                        <TipOffset>0</TipOffset>
                                        <TipSpacing>0</TipSpacing>
                                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandDataV1">
                                            <LihaScriptCommandDataV1>
                                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV2">
                                                    <ScriptCommandCommonDataV2>
                                                        <LabwareName>{labware}</LabwareName>
                                                        <LiquidClassVariablesNames />
                                                        <LiquidClassVariablesValues />
                                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                                            <DeviceAliasStatementBaseDataV1>
                                                                <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                                    <DeviceAlias>Instrument=1/Device=LIHA:1</DeviceAlias>
                                                                </Alias>
                                                                <ID>
                                                                    <AvailableID></AvailableID>
                                                                </ID>
                                                                <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                                    <ScriptStatementBaseDataV1>
                                                                        <IsBreakpoint>False</IsBreakpoint>
                                                                        <IsDisabledForExecution>False</IsDisabledForExecution>
                                                                        <GroupLineNumber>0</GroupLineNumber>
                                                                        <LineNumber>2</LineNumber>
                                                                    </ScriptStatementBaseDataV1>
                                                                </Data>
                                                            </DeviceAliasStatementBaseDataV1>
                                                        </Data>
                                                    </ScriptCommandCommonDataV2>
                                                </Data>
                                            </LihaScriptCommandDataV1>
                                        </Data>
                                    </LiHaScriptCommandUsingTipSelectionBaseDataV1>
                                </Data>
                            </LihaScriptCommandUsingWellSelectionBaseDataV1>
                        </Data>
                    </LihaPipettingWithVolumesScriptCommandDataV7>
                </Data>
            </LihaAspirateScriptCommandDataV5>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_dispense_xml(
    labware: str,
    volumes: List[int],
    liquid_class: str,
    well_offsets: Optional[List[int]] = None,
    tip_indices: Optional[List[int]] = None
) -> str:
    """Generate Dispense XML command (V6 format).
    
    Args:
        labware: Labware name
        volumes: List of volumes for each tip (µL)
        liquid_class: Liquid class name
        well_offsets: List of well offsets for each tip. If None, all to well 0.
        tip_indices: List of tip indices to use. If None, uses all tips.
    
    Returns:
        XML string for Dispense command
    """
    if well_offsets is None:
        well_offsets = [0] * len(volumes)
    if tip_indices is None:
        tip_indices = list(range(len(volumes)))
    
    volumes_xml = '\n'.join([
        f'                            <Object Type="System.String"><string>{v}</string></Object>'
        for v in volumes
    ])
    
    serialized_wells = ';'.join([str(wo) for wo in well_offsets]) + ';'
    
    if len(set(well_offsets)) == 1:
        # All same well - calculate proper well name
        offset = well_offsets[0]
        col = offset // 8  # Column-major: 8 rows per column
        row = offset % 8
        row_letter = chr(65 + row)  # A=0, B=1, etc.
        well_name = f"{row_letter}{col+1}"
        selected_wells = f"{len(volumes)} * {well_name}"
    else:
        # Multiple different wells - Tecan uses column-major ordering
        well_names = []
        for offset in well_offsets:
            col = offset // 8  # Column-major: 8 rows per column
            row = offset % 8
            row_letter = chr(65 + row)
            well_names.append(f"{row_letter}{col+1}")
        selected_wells = ";".join(well_names)
    
    tips_xml = '\n'.join([
        f'                                            <Object Type="System.Int32"><int>{i}</int></Object>'
        for i in tip_indices
    ])
    
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaDispenseScriptCommandDataV6">
            <LihaDispenseScriptCommandDataV6>
                <OffsetX>0</OffsetX>
                <OffsetY>0</OffsetY>
                <SkipZOnlyMoveToPipettingPosition>False</SkipZOnlyMoveToPipettingPosition>
                <DispenseDelays />
                <Data Type="Tecan.Core.Instrument.Devices.Scripting.Data.LihaPipettingWithVolumesScriptCommandDataV7">
                    <LihaPipettingWithVolumesScriptCommandDataV7>
                        <Volumes>
{volumes_xml}
                        </Volumes>
                        <FlowRates />
                        <IsLiquidClassNameByExpressionEnabled>False</IsLiquidClassNameByExpressionEnabled>
                        <LiquidClassSelectionMode>
                            <LiquidClassSelectionMode>SingleByName</LiquidClassSelectionMode>
                        </LiquidClassSelectionMode>
                        <LiquidClassNameBySelection>{liquid_class}</LiquidClassNameBySelection>
                        <LiquidClassNameByExpression></LiquidClassNameByExpression>
                        <LiquidClassNames />
                        <Compartment>1</Compartment>
                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandUsingWellSelectionBaseDataV1">
                            <LihaScriptCommandUsingWellSelectionBaseDataV1>
                                <SerializedWellIndexes>{serialized_wells}</SerializedWellIndexes>
                                <SelectedWellsString>{selected_wells}</SelectedWellsString>
                                <WellOffset>{well_offsets[0]}</WellOffset>
                                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LiHaScriptCommandUsingTipSelectionBaseDataV1">
                                    <LiHaScriptCommandUsingTipSelectionBaseDataV1>
                                        <SerializedTipsIndexes></SerializedTipsIndexes>
                                        <SelectedTipsIndexes>
{tips_xml}
                                        </SelectedTipsIndexes>
                                        <TipMask></TipMask>
                                        <TipOffset>0</TipOffset>
                                        <TipSpacing>0</TipSpacing>
                                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandDataV1">
                                            <LihaScriptCommandDataV1>
                                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV2">
                                                    <ScriptCommandCommonDataV2>
                                                        <LabwareName>{labware}</LabwareName>
                                                        <LiquidClassVariablesNames />
                                                        <LiquidClassVariablesValues />
                                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                                            <DeviceAliasStatementBaseDataV1>
                                                                <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                                    <DeviceAlias>Instrument=1/Device=LIHA:1</DeviceAlias>
                                                                </Alias>
                                                                <ID>
                                                                    <AvailableID></AvailableID>
                                                                </ID>
                                                                <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                                    <ScriptStatementBaseDataV1>
                                                                        <IsBreakpoint>False</IsBreakpoint>
                                                                        <IsDisabledForExecution>False</IsDisabledForExecution>
                                                                        <GroupLineNumber>0</GroupLineNumber>
                                                                        <LineNumber>3</LineNumber>
                                                                    </ScriptStatementBaseDataV1>
                                                                </Data>
                                                            </DeviceAliasStatementBaseDataV1>
                                                        </Data>
                                                    </ScriptCommandCommonDataV2>
                                                </Data>
                                            </LihaScriptCommandDataV1>
                                        </Data>
                                    </LiHaScriptCommandUsingTipSelectionBaseDataV1>
                                </Data>
                            </LihaScriptCommandUsingWellSelectionBaseDataV1>
                        </Data>
                    </LihaPipettingWithVolumesScriptCommandDataV7>
                </Data>
            </LihaDispenseScriptCommandDataV6>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_drop_tips_xml(
    labware: str,
    tip_indices: Optional[List[int]] = None
) -> str:
    """Generate DropTips XML command.
    
    Args:
        labware: Labware name (e.g., waste chute)
        tip_indices: List of tip indices to drop. If None, uses all 8 tips.
    
    Returns:
        XML string for DropTips command
    """
    if tip_indices is None:
        tip_indices = list(range(8))
    
    tips_xml = '\n'.join([
        f'                                            <Object Type="System.Int32"><int>{i}</int></Object>'
        for i in tip_indices
    ])
    
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaDropTipsScriptCommandDataV1">
            <LihaDropTipsScriptCommandDataV1>
                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LiHaScriptCommandUsingTipSelectionBaseDataV1">
                    <LiHaScriptCommandUsingTipSelectionBaseDataV1>
                        <SerializedTipsIndexes></SerializedTipsIndexes>
                        <SelectedTipsIndexes>
{tips_xml}
                        </SelectedTipsIndexes>
                        <TipMask></TipMask>
                        <TipOffset>0</TipOffset>
                        <TipSpacing>9</TipSpacing>
                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandDataV1">
                            <LihaScriptCommandDataV1>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                                    <ScriptCommandCommonDataV1>
                                        <LabwareName>{labware}</LabwareName>
                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                            <DeviceAliasStatementBaseDataV1>
                                                <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                    <DeviceAlias>Instrument=1/Device=LIHA:1</DeviceAlias>
                                                </Alias>
                                                <ID><AvailableID></AvailableID></ID>
                                                <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                    <ScriptStatementBaseDataV1>
                                                        <IsBreakpoint>False</IsBreakpoint>
                                                        <IsDisabledForExecution>False</IsDisabledForExecution>
                                                        <GroupLineNumber>0</GroupLineNumber>
                                                        <LineNumber>4</LineNumber>
                                                    </ScriptStatementBaseDataV1>
                                                </Data>
                                            </DeviceAliasStatementBaseDataV1>
                                        </Data>
                                    </ScriptCommandCommonDataV1>
                                </Data>
                            </LihaScriptCommandDataV1>
                        </Data>
                    </LiHaScriptCommandUsingTipSelectionBaseDataV1>
                </Data>
            </LihaDropTipsScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


# ============================================================================
# FCA (LiHa) MOVEMENT COMMANDS
# ============================================================================

def make_fca_move_to_position_xml(
    labware: str,
    well_offset: int = 0,
    z_position: Optional[float] = None,
    device_alias: str = FCA_DEVICE_ALIAS,
    tip_indices: Optional[List[int]] = None
) -> str:
    """Generate FCA (LiHa) move to position XML command.
    
    Args:
        labware: Target labware name
        well_offset: Well offset (0-based)
        z_position: Z position in mm (None = safe travel height)
        device_alias: Device alias for FCA
        tip_indices: List of tip indices to move. If None, uses all 8 tips.
    
    Returns:
        XML string for FCA move command
    """
    if tip_indices is None:
        tip_indices = list(range(8))
    
    tips_xml = '\n'.join([
        f'                                            <Object Type="System.Int32"><int>{i}</int></Object>'
        for i in tip_indices
    ])
    
    # Calculate well name from offset (column-major)
    col = well_offset // 8
    row = well_offset % 8
    row_letter = chr(65 + row)
    well_name = f"{row_letter}{col+1}"
    
    z_element = f"<ZPosition>{z_position}</ZPosition>" if z_position is not None else "<ZPosition></ZPosition>"
    
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaMoveToPositionScriptCommandDataV1">
            <LihaMoveToPositionScriptCommandDataV1>
                <OffsetX>0</OffsetX>
                <OffsetY>0</OffsetY>
                {z_element}
                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandUsingWellSelectionBaseDataV1">
                    <LihaScriptCommandUsingWellSelectionBaseDataV1>
                        <SerializedWellIndexes>{well_offset};</SerializedWellIndexes>
                        <SelectedWellsString>1 * {well_name}</SelectedWellsString>
                        <WellOffset>{well_offset}</WellOffset>
                        <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LiHaScriptCommandUsingTipSelectionBaseDataV1">
                            <LiHaScriptCommandUsingTipSelectionBaseDataV1>
                                <SerializedTipsIndexes></SerializedTipsIndexes>
                                <SelectedTipsIndexes>
{tips_xml}
                                </SelectedTipsIndexes>
                                <TipMask></TipMask>
                                <TipOffset>0</TipOffset>
                                <TipSpacing>9</TipSpacing>
                                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandDataV1">
                                    <LihaScriptCommandDataV1>
                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                                            <ScriptCommandCommonDataV1>
                                                <LabwareName>{labware}</LabwareName>
                                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                                    <DeviceAliasStatementBaseDataV1>
                                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                                        </Alias>
                                                        <ID><AvailableID></AvailableID></ID>
                                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                            <ScriptStatementBaseDataV1>
                                                                <IsBreakpoint>False</IsBreakpoint>
                                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                                <GroupLineNumber>0</GroupLineNumber>
                                                                <LineNumber>1</LineNumber>
                                                            </ScriptStatementBaseDataV1>
                                                        </Data>
                                                    </DeviceAliasStatementBaseDataV1>
                                                </Data>
                                            </ScriptCommandCommonDataV1>
                                        </Data>
                                    </LihaScriptCommandDataV1>
                                </Data>
                            </LiHaScriptCommandUsingTipSelectionBaseDataV1>
                        </Data>
                    </LihaScriptCommandUsingWellSelectionBaseDataV1>
                </Data>
            </LihaMoveToPositionScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_fca_move_to_safe_position_xml(
    device_alias: str = FCA_DEVICE_ALIAS
) -> str:
    """Generate FCA (LiHa) move to safe/home position XML command.
    
    Args:
        device_alias: Device alias for FCA
    
    Returns:
        XML string for FCA safe position command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaMoveToSafePositionScriptCommandDataV1">
            <LihaMoveToSafePositionScriptCommandDataV1>
                <Data Type="Tecan.Core.Instrument.Devices.LiHa.Scripting.LihaScriptCommandDataV1">
                    <LihaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName></LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </LihaScriptCommandDataV1>
                </Data>
            </LihaMoveToSafePositionScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


# ============================================================================
# MCA (96-CHANNEL) MOVEMENT COMMANDS  
# ============================================================================

def make_mca_get_tips_xml(
    diti_type: str = "TOOLTYPE:LiHa.TecanDiTi/TOOLNAME:MCA, 150ul Filtered SBS",
    airgap_volume: int = 10,
    airgap_speed: int = 70,
    device_alias: str = MCA_DEVICE_ALIAS
) -> str:
    """Generate MCA GetTips XML command.
    
    Args:
        diti_type: DiTi type string for MCA tips
        airgap_volume: Air gap volume in µL
        airgap_speed: Air gap speed
        device_alias: Device alias for MCA
    
    Returns:
        XML string for MCA GetTips command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaGetTipsScriptCommandDataV2">
            <McaGetTipsScriptCommandDataV2>
                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandDataV1">
                    <McaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName></LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </McaScriptCommandDataV1>
                </Data>
                <AirgapVolume>{airgap_volume}</AirgapVolume>
                <AirgapSpeed>{airgap_speed}</AirgapSpeed>
                <DitiType><AvailableID>{diti_type}</AvailableID></DitiType>
                <UseNextPosition>True</UseNextPosition>
            </McaGetTipsScriptCommandDataV2>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_mca_drop_tips_xml(
    labware: str,
    device_alias: str = MCA_DEVICE_ALIAS
) -> str:
    """Generate MCA DropTips XML command.
    
    Args:
        labware: Labware name (e.g., waste chute)
        device_alias: Device alias for MCA
    
    Returns:
        XML string for MCA DropTips command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaDropTipsScriptCommandDataV1">
            <McaDropTipsScriptCommandDataV1>
                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandDataV1">
                    <McaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName>{labware}</LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </McaScriptCommandDataV1>
                </Data>
            </McaDropTipsScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_mca_aspirate_xml(
    labware: str,
    volume: int,
    liquid_class: str,
    well_offset: int = 0,
    device_alias: str = MCA_DEVICE_ALIAS
) -> str:
    """Generate MCA Aspirate XML command.
    
    Args:
        labware: Labware name
        volume: Volume to aspirate in µL (same for all 96 channels)
        liquid_class: Liquid class name
        well_offset: Well offset (0-based, typically 0 for full plate)
        device_alias: Device alias for MCA
    
    Returns:
        XML string for MCA Aspirate command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaAspirateScriptCommandDataV3">
            <McaAspirateScriptCommandDataV3>
                <OffsetX>0</OffsetX>
                <OffsetY>0</OffsetY>
                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaPipettingScriptCommandDataV4">
                    <McaPipettingScriptCommandDataV4>
                        <Volume>{volume}</Volume>
                        <FlowRate></FlowRate>
                        <LiquidClassSelectionMode>
                            <LiquidClassSelectionMode>SingleByName</LiquidClassSelectionMode>
                        </LiquidClassSelectionMode>
                        <LiquidClassNameBySelection>{liquid_class}</LiquidClassNameBySelection>
                        <LiquidClassNameByExpression></LiquidClassNameByExpression>
                        <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandUsingWellSelectionDataV1">
                            <McaScriptCommandUsingWellSelectionDataV1>
                                <WellOffset>{well_offset}</WellOffset>
                                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandDataV1">
                                    <McaScriptCommandDataV1>
                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                                            <ScriptCommandCommonDataV1>
                                                <LabwareName>{labware}</LabwareName>
                                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                                    <DeviceAliasStatementBaseDataV1>
                                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                                        </Alias>
                                                        <ID><AvailableID></AvailableID></ID>
                                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                            <ScriptStatementBaseDataV1>
                                                                <IsBreakpoint>False</IsBreakpoint>
                                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                                <GroupLineNumber>0</GroupLineNumber>
                                                                <LineNumber>1</LineNumber>
                                                            </ScriptStatementBaseDataV1>
                                                        </Data>
                                                    </DeviceAliasStatementBaseDataV1>
                                                </Data>
                                            </ScriptCommandCommonDataV1>
                                        </Data>
                                    </McaScriptCommandDataV1>
                                </Data>
                            </McaScriptCommandUsingWellSelectionDataV1>
                        </Data>
                    </McaPipettingScriptCommandDataV4>
                </Data>
            </McaAspirateScriptCommandDataV3>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_mca_dispense_xml(
    labware: str,
    volume: int,
    liquid_class: str,
    well_offset: int = 0,
    device_alias: str = MCA_DEVICE_ALIAS
) -> str:
    """Generate MCA Dispense XML command.
    
    Args:
        labware: Labware name
        volume: Volume to dispense in µL (same for all 96 channels)
        liquid_class: Liquid class name
        well_offset: Well offset (0-based, typically 0 for full plate)
        device_alias: Device alias for MCA
    
    Returns:
        XML string for MCA Dispense command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaDispenseScriptCommandDataV3">
            <McaDispenseScriptCommandDataV3>
                <OffsetX>0</OffsetX>
                <OffsetY>0</OffsetY>
                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaPipettingScriptCommandDataV4">
                    <McaPipettingScriptCommandDataV4>
                        <Volume>{volume}</Volume>
                        <FlowRate></FlowRate>
                        <LiquidClassSelectionMode>
                            <LiquidClassSelectionMode>SingleByName</LiquidClassSelectionMode>
                        </LiquidClassSelectionMode>
                        <LiquidClassNameBySelection>{liquid_class}</LiquidClassNameBySelection>
                        <LiquidClassNameByExpression></LiquidClassNameByExpression>
                        <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandUsingWellSelectionDataV1">
                            <McaScriptCommandUsingWellSelectionDataV1>
                                <WellOffset>{well_offset}</WellOffset>
                                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandDataV1">
                                    <McaScriptCommandDataV1>
                                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                                            <ScriptCommandCommonDataV1>
                                                <LabwareName>{labware}</LabwareName>
                                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                                    <DeviceAliasStatementBaseDataV1>
                                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                                        </Alias>
                                                        <ID><AvailableID></AvailableID></ID>
                                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                                            <ScriptStatementBaseDataV1>
                                                                <IsBreakpoint>False</IsBreakpoint>
                                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                                <GroupLineNumber>0</GroupLineNumber>
                                                                <LineNumber>1</LineNumber>
                                                            </ScriptStatementBaseDataV1>
                                                        </Data>
                                                    </DeviceAliasStatementBaseDataV1>
                                                </Data>
                                            </ScriptCommandCommonDataV1>
                                        </Data>
                                    </McaScriptCommandDataV1>
                                </Data>
                            </McaScriptCommandUsingWellSelectionDataV1>
                        </Data>
                    </McaPipettingScriptCommandDataV4>
                </Data>
            </McaDispenseScriptCommandDataV3>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_mca_move_to_safe_position_xml(
    device_alias: str = MCA_DEVICE_ALIAS
) -> str:
    """Generate MCA move to safe/home position XML command.
    
    Args:
        device_alias: Device alias for MCA
    
    Returns:
        XML string for MCA safe position command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaMoveToSafePositionScriptCommandDataV1">
            <McaMoveToSafePositionScriptCommandDataV1>
                <Data Type="Tecan.Core.Instrument.Devices.MCA.Scripting.McaScriptCommandDataV1">
                    <McaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName></LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </McaScriptCommandDataV1>
                </Data>
            </McaMoveToSafePositionScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


# ============================================================================
# RGA (GRIPPER) MOVEMENT COMMANDS
# ============================================================================

def make_rga_get_labware_xml(
    labware: str,
    grip_force: int = 5,
    grip_width: Optional[float] = None,
    device_alias: str = RGA_DEVICE_ALIAS
) -> str:
    """Generate RGA (gripper) get labware XML command.
    
    Args:
        labware: Labware name to pick up
        grip_force: Grip force (1-10 scale)
        grip_width: Grip width in mm (None = auto-detect from labware)
        device_alias: Device alias for RGA
    
    Returns:
        XML string for RGA get labware command
    """
    grip_width_element = f"<GripWidth>{grip_width}</GripWidth>" if grip_width else "<GripWidth></GripWidth>"
    
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.RGA.Scripting.RgaGetLabwareScriptCommandDataV1">
            <RgaGetLabwareScriptCommandDataV1>
                <GripForce>{grip_force}</GripForce>
                {grip_width_element}
                <Data Type="Tecan.Core.Instrument.Devices.RGA.Scripting.RgaScriptCommandDataV1">
                    <RgaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName>{labware}</LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </RgaScriptCommandDataV1>
                </Data>
            </RgaGetLabwareScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_rga_put_labware_xml(
    labware: str,
    target_location: str,
    device_alias: str = RGA_DEVICE_ALIAS
) -> str:
    """Generate RGA (gripper) put labware XML command.
    
    Args:
        labware: Labware name being held
        target_location: Target location to place labware
        device_alias: Device alias for RGA
    
    Returns:
        XML string for RGA put labware command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.RGA.Scripting.RgaPutLabwareScriptCommandDataV1">
            <RgaPutLabwareScriptCommandDataV1>
                <TargetLocation>{target_location}</TargetLocation>
                <Data Type="Tecan.Core.Instrument.Devices.RGA.Scripting.RgaScriptCommandDataV1">
                    <RgaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName>{labware}</LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </RgaScriptCommandDataV1>
                </Data>
            </RgaPutLabwareScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''


def make_rga_move_to_safe_position_xml(
    device_alias: str = RGA_DEVICE_ALIAS
) -> str:
    """Generate RGA (gripper) move to safe/home position XML command.
    
    Args:
        device_alias: Device alias for RGA
    
    Returns:
        XML string for RGA safe position command
    """
    return f'''<ScriptGroup>
    <Objects>
        <Object Type="Tecan.Core.Instrument.Devices.RGA.Scripting.RgaMoveToSafePositionScriptCommandDataV1">
            <RgaMoveToSafePositionScriptCommandDataV1>
                <Data Type="Tecan.Core.Instrument.Devices.RGA.Scripting.RgaScriptCommandDataV1">
                    <RgaScriptCommandDataV1>
                        <Data Type="Tecan.Core.Instrument.Helpers.Scripting.ScriptCommandCommonDataV1">
                            <ScriptCommandCommonDataV1>
                                <LabwareName></LabwareName>
                                <Data Type="Tecan.Core.Instrument.Helpers.Scripting.DeviceAliasStatementBaseDataV1">
                                    <DeviceAliasStatementBaseDataV1>
                                        <Alias Type="Tecan.Core.Instrument.DeviceAlias.DeviceAlias">
                                            <DeviceAlias>{device_alias}</DeviceAlias>
                                        </Alias>
                                        <ID><AvailableID></AvailableID></ID>
                                        <Data Type="Tecan.Core.Scripting.Helpers.ScriptStatementBaseDataV1">
                                            <ScriptStatementBaseDataV1>
                                                <IsBreakpoint>False</IsBreakpoint>
                                                <IsDisabledForExecution>False</IsDisabledForExecution>
                                                <GroupLineNumber>0</GroupLineNumber>
                                                <LineNumber>1</LineNumber>
                                            </ScriptStatementBaseDataV1>
                                        </Data>
                                    </DeviceAliasStatementBaseDataV1>
                                </Data>
                            </ScriptCommandCommonDataV1>
                        </Data>
                    </RgaScriptCommandDataV1>
                </Data>
            </RgaMoveToSafePositionScriptCommandDataV1>
        </Object>
    </Objects>
    <Name></Name>
    <IsBreakpoint>False</IsBreakpoint>
    <IsDisabledForExecution>False</IsDisabledForExecution>
    <LineNumber>0</LineNumber>
</ScriptGroup>'''
