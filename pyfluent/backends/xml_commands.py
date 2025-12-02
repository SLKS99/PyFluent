"""
XML command generators for Tecan Fluent API.
These generate the exact XML structures that work with the Tecan VisionX API.
"""

from typing import List, Optional


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
                                                <ID><AvailableID>USB:TECAN,MYRIUS,1310005667/LIHA:1</AvailableID></ID>
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
        selected_wells = f"{len(volumes)} * A1"
    else:
        # Multiple different wells
        well_names = []
        for offset in well_offsets:
            row = offset // 12
            col = offset % 12
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
                                                                    <AvailableID>USB:TECAN,MYRIUS,1310005667/LIHA:1</AvailableID>
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
        selected_wells = f"{len(volumes)} * A1"
    else:
        well_names = []
        for offset in well_offsets:
            row = offset // 12
            col = offset % 12
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
                                                                    <AvailableID>USB:TECAN,MYRIUS,1310005667/LIHA:1</AvailableID>
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
                                                <ID><AvailableID>USB:TECAN,MYRIUS,1310005667/LIHA:1</AvailableID></ID>
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

