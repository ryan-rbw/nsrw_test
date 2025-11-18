"""
Host-side mirror of emulator table definitions.

Implements HOST_SPEC_RPi.md section 18: TUI Views and Emulator Table Catalog.
Maps emulator tables to host views and field definitions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from nss_host.icd_fields import FieldDef, FieldType


class TableID(Enum):
    """Emulator table identifiers."""

    DYNAMICS = 0x00
    SETPOINTS = 0x01
    LIMITS = 0x02
    PROTECTIONS = 0x03
    FAULTS = 0x04
    SERIAL_STATUS = 0x05
    LINK_STATUS = 0x06


@dataclass
class TableDef:
    """
    Table definition.

    Attributes:
        id: Table identifier.
        name: Table name.
        description: Table description.
        fields: List of field definitions.
        base_addr: Base address for PEEK/POKE.
        size_bytes: Total size in bytes.
    """

    id: TableID
    name: str
    description: str
    fields: List[FieldDef]
    base_addr: int
    size_bytes: int


# Define emulator tables and fields
# These definitions match the emulator's table catalog

DYNAMICS_TABLE = TableDef(
    id=TableID.DYNAMICS,
    name="Dynamics",
    description="Real-time dynamics state",
    base_addr=0x1000,
    size_bytes=32,
    fields=[
        FieldDef("speed_rpm", FieldType.Q15_16, 0, "RPM", 1.0, -5000.0, 5000.0, "Wheel speed"),
        FieldDef("torque_nm", FieldType.Q15_16, 4, "Nm", 1.0, -1.0, 1.0, "Applied torque"),
        FieldDef("current_a", FieldType.Q15_16, 8, "A", 1.0, -5.0, 5.0, "Motor current"),
        FieldDef("power_w", FieldType.Q15_16, 12, "W", 1.0, 0.0, 100.0, "Electrical power"),
        FieldDef("mode", FieldType.UINT8, 16, "", 1.0, 0.0, 3.0, "Operating mode"),
        FieldDef("flags", FieldType.UINT16, 18, "", 1.0, 0.0, 0xFFFF, "Status flags"),
    ],
)

SETPOINTS_TABLE = TableDef(
    id=TableID.SETPOINTS,
    name="Setpoints",
    description="Control setpoints",
    base_addr=0x1020,
    size_bytes=16,
    fields=[
        FieldDef(
            "speed_rpm_sp", FieldType.Q15_16, 0, "RPM", 1.0, -5000.0, 5000.0, "Speed setpoint"
        ),
        FieldDef(
            "current_a_sp", FieldType.Q15_16, 4, "A", 1.0, -5.0, 5.0, "Current setpoint"
        ),
        FieldDef("torque_nm_sp", FieldType.Q15_16, 8, "Nm", 1.0, -1.0, 1.0, "Torque setpoint"),
    ],
)

LIMITS_TABLE = TableDef(
    id=TableID.LIMITS,
    name="Limits",
    description="Operational limits",
    base_addr=0x1040,
    size_bytes=16,
    fields=[
        FieldDef(
            "max_speed_rpm", FieldType.UQ16_16, 0, "RPM", 1.0, 0.0, 6000.0, "Maximum speed"
        ),
        FieldDef("max_current_a", FieldType.UQ16_16, 4, "A", 1.0, 0.0, 10.0, "Maximum current"),
        FieldDef("max_power_w", FieldType.UQ16_16, 8, "W", 1.0, 0.0, 200.0, "Maximum power"),
    ],
)

PROTECTIONS_TABLE = TableDef(
    id=TableID.PROTECTIONS,
    name="Protections",
    description="Protection thresholds",
    base_addr=0x1060,
    size_bytes=16,
    fields=[
        FieldDef(
            "overspeed_rpm",
            FieldType.UQ16_16,
            0,
            "RPM",
            1.0,
            0.0,
            6000.0,
            "Overspeed trip threshold",
        ),
        FieldDef(
            "overcurrent_a",
            FieldType.UQ16_16,
            4,
            "A",
            1.0,
            0.0,
            10.0,
            "Overcurrent trip threshold",
        ),
        FieldDef(
            "overtemp_c", FieldType.Q7_8, 8, "°C", 1.0, -40.0, 125.0, "Overtemperature threshold"
        ),
    ],
)

FAULTS_TABLE = TableDef(
    id=TableID.FAULTS,
    name="Faults",
    description="Fault status and latches",
    base_addr=0x1080,
    size_bytes=8,
    fields=[
        FieldDef(
            "fault_live", FieldType.UINT32, 0, "", 1.0, 0.0, 0xFFFFFFFF, "Live fault bits"
        ),
        FieldDef(
            "fault_latched", FieldType.UINT32, 4, "", 1.0, 0.0, 0xFFFFFFFF, "Latched fault bits"
        ),
    ],
)


# Table registry
TABLES: Dict[TableID, TableDef] = {
    TableID.DYNAMICS: DYNAMICS_TABLE,
    TableID.SETPOINTS: SETPOINTS_TABLE,
    TableID.LIMITS: LIMITS_TABLE,
    TableID.PROTECTIONS: PROTECTIONS_TABLE,
    TableID.FAULTS: FAULTS_TABLE,
}


def get_table(table_id: TableID) -> TableDef:
    """
    Get table definition by ID.

    Args:
        table_id: Table identifier.

    Returns:
        Table definition.

    Raises:
        KeyError: If table ID not found.
    """
    return TABLES[table_id]


def get_table_by_name(name: str) -> TableDef:
    """
    Get table definition by name.

    Args:
        name: Table name (case-insensitive).

    Returns:
        Table definition.

    Raises:
        KeyError: If table name not found.
    """
    name_lower = name.lower()
    for table in TABLES.values():
        if table.name.lower() == name_lower:
            return table
    raise KeyError(f"Table '{name}' not found")


def get_field(table: TableDef, field_name: str) -> FieldDef:
    """
    Get field definition from table.

    Args:
        table: Table definition.
        field_name: Field name (case-insensitive).

    Returns:
        Field definition.

    Raises:
        KeyError: If field not found.
    """
    field_name_lower = field_name.lower()
    for field in table.fields:
        if field.name.lower() == field_name_lower:
            return field
    raise KeyError(f"Field '{field_name}' not found in table '{table.name}'")
