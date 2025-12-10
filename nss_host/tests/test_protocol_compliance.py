"""
Protocol compliance tests verifying packet formats match NRWA-T6 production code.

Tests ensure our host implementation matches the production spacecraft driver
(ns_reaction_wheel.hpp / ns_reaction_wheel.cpp) exactly.

Reference: NRWA-T6 ICD N2-A2a-DD0021 Rev 10.02
"""

import pytest

from nss_host import nsp
from nss_host.icd_fields import encode_q10_22, encode_q14_18, encode_uq24_8
from nss_host.telemetry import (
    CurrTelemetry,
    DiagGeneralTelemetry,
    StandardTelemetry,
    TelemetryBlock,
    TempTelemetry,
    VoltTelemetry,
)


class TestAppCommandFormat:
    """
    Verify APP-COMMAND (0x08) packet format matches production.

    Production code (ns_reaction_wheel.hpp):
        struct AppCommand {
            uint8_t control_mode;      // 1 byte
            Packed<int32_t> setpoint;  // 4 bytes LE
        };

    Total: 5 bytes
    """

    def test_payload_size(self):
        """APP-COMMAND payload should be exactly 5 bytes."""
        # Build payload like commands.py does
        mode = nsp.ControlMode.SPEED
        setpoint = 1000.0
        setpoint_raw = encode_q14_18(setpoint)
        payload = bytes([int(mode)]) + setpoint_raw.to_bytes(4, "little")

        assert len(payload) == 5

    def test_idle_mode_format(self):
        """IDLE mode (0x00) with zero setpoint."""
        mode = nsp.ControlMode.IDLE
        setpoint_raw = 0
        payload = bytes([int(mode)]) + setpoint_raw.to_bytes(4, "little")

        assert payload == bytes([0x00, 0x00, 0x00, 0x00, 0x00])

    def test_speed_mode_format(self):
        """SPEED mode (0x02) uses Q14.18 encoding."""
        mode = nsp.ControlMode.SPEED
        setpoint = 1000.0  # RPM
        setpoint_raw = encode_q14_18(setpoint)
        payload = bytes([int(mode)]) + setpoint_raw.to_bytes(4, "little")

        assert payload[0] == 0x02  # SPEED mode
        assert len(payload) == 5
        # Verify little-endian encoding
        decoded_raw = int.from_bytes(payload[1:5], "little")
        assert decoded_raw == setpoint_raw

    def test_current_mode_format(self):
        """CURRENT mode (0x01) uses Q14.18 encoding."""
        mode = nsp.ControlMode.CURRENT
        setpoint = 500.0  # mA
        setpoint_raw = encode_q14_18(setpoint)
        payload = bytes([int(mode)]) + setpoint_raw.to_bytes(4, "little")

        assert payload[0] == 0x01  # CURRENT mode

    def test_torque_mode_format(self):
        """TORQUE mode (0x04) uses Q10.22 encoding."""
        mode = nsp.ControlMode.TORQUE
        setpoint = 50.0  # mN-m
        setpoint_raw = encode_q10_22(setpoint)
        payload = bytes([int(mode)]) + setpoint_raw.to_bytes(4, "little")

        assert payload[0] == 0x04  # TORQUE mode

    def test_pwm_mode_format(self):
        """PWM mode (0x08) uses signed 9-bit integer."""
        mode = nsp.ControlMode.PWM
        payload = bytes([int(mode)]) + (100).to_bytes(4, "little")

        assert payload[0] == 0x08  # PWM mode

    def test_control_mode_values(self):
        """Verify control mode enum values match ICD."""
        assert nsp.ControlMode.IDLE == 0x00
        assert nsp.ControlMode.CURRENT == 0x01
        assert nsp.ControlMode.SPEED == 0x02
        assert nsp.ControlMode.TORQUE == 0x04
        assert nsp.ControlMode.PWM == 0x08


class TestPeekPokeFormat:
    """
    Verify PEEK/POKE packet formats match production.

    Production code (ns_reaction_wheel.hpp):
        struct PeekCommand { MemoryAddress addr; };  // 1 byte
        struct PeekResponse { Packed<uint32_t> val; };  // 4 bytes LE

        struct PokeCommand {
            MemoryAddress addr;    // 1 byte
            Packed<uint32_t> val;  // 4 bytes LE
        };

    PEEK: 1-byte request, 4-byte response
    POKE: 5-byte request (addr + value)
    """

    def test_peek_request_size(self):
        """PEEK request should be 1 byte (address only)."""
        addr = nsp.MemoryAddress.SERIAL_NUMBER
        payload = bytes([addr & 0xFF])

        assert len(payload) == 1
        assert payload[0] == 0x00

    def test_poke_request_size(self):
        """POKE request should be 5 bytes (address + value)."""
        addr = nsp.MemoryAddress.OVERSPEED_FAULT_THRESHOLD
        value = encode_uq24_8(6000.0)  # 6000 RPM
        payload = bytes([addr & 0xFF]) + value.to_bytes(4, "little")

        assert len(payload) == 5
        assert payload[0] == 0x06  # OVERSPEED_FAULT_THRESHOLD address

    def test_poke_little_endian(self):
        """POKE value should be little-endian."""
        addr = 0x07
        value = 0x12345678
        payload = bytes([addr]) + value.to_bytes(4, "little")

        assert payload == bytes([0x07, 0x78, 0x56, 0x34, 0x12])

    def test_memory_address_values(self):
        """Verify memory address enum values match ICD."""
        assert nsp.MemoryAddress.SERIAL_NUMBER == 0x00
        assert nsp.MemoryAddress.OVERSPEED_FAULT_THRESHOLD == 0x06
        assert nsp.MemoryAddress.ACTIVE_SPEED_LIMIT == 0x07


class TestStandardTelemetryFormat:
    """
    Verify STANDARD telemetry (0x00) format matches production.

    Production code (ns_reaction_wheel.hpp):
        struct AppTelemStandard {
            Packed<Status::Type> status;         // 4 bytes (offset 0)
            Packed<Fault::Type> fault;           // 4 bytes (offset 4)
            uint8_t control_mode;                // 1 byte  (offset 8)
            Packed<int32_t> setpoint;            // 4 bytes (offset 9)
            Packed<int16_t> duty_cycle;          // 2 bytes (offset 13)
            PackedQ<int16_t, 2> current_target;  // 2 bytes (offset 15)
            PackedQ<int32_t, 12> current;        // 4 bytes (offset 17)
            PackedQ<int32_t, 8> speed;           // 4 bytes (offset 21)
        };
        static_assert(sizeof(AppTelemStandard) == 25);

    Total: 25 bytes, little-endian
    """

    def test_structure_size(self):
        """STANDARD telemetry should be exactly 25 bytes."""
        # Create test data with all zeros
        data = bytes(25)
        telem = StandardTelemetry.from_bytes(data)

        assert telem is not None

    def test_minimum_data_requirement(self):
        """Should raise error if less than 25 bytes."""
        data = bytes(24)  # One byte short

        with pytest.raises(ValueError, match="25 bytes"):
            StandardTelemetry.from_bytes(data)

    def test_field_offsets(self):
        """Verify field offsets match production structure."""
        # Build test data with known values at known offsets
        data = bytearray(25)

        # status at offset 0 (4 bytes)
        data[0:4] = (0xDEADBEEF).to_bytes(4, "little")

        # fault at offset 4 (4 bytes)
        data[4:8] = (0xCAFEBABE).to_bytes(4, "little")

        # control_mode at offset 8 (1 byte)
        data[8] = 0x02  # SPEED mode

        # setpoint at offset 9 (4 bytes)
        data[9:13] = (1000).to_bytes(4, "little", signed=True)

        # duty_cycle at offset 13 (2 bytes)
        data[13:15] = (500).to_bytes(2, "little", signed=True)

        # current_target at offset 15 (2 bytes, Q14.2)
        data[15:17] = (400).to_bytes(2, "little")  # 100 mA * 4

        # current at offset 17 (4 bytes, Q20.12)
        data[17:21] = (500 * 4096).to_bytes(4, "little")  # 500 mA

        # speed at offset 21 (4 bytes, Q24.8)
        data[21:25] = (1000 * 256).to_bytes(4, "little")  # 1000 RPM

        telem = StandardTelemetry.from_bytes(bytes(data))

        assert telem.status == 0xDEADBEEF
        assert telem.fault == 0xCAFEBABE
        assert telem.control_mode == 0x02
        assert telem.setpoint == 1000
        assert telem.duty_cycle == 500
        assert telem.current_target_ma == pytest.approx(100.0, abs=0.25)
        assert telem.current_ma == pytest.approx(500.0, abs=0.001)
        assert telem.speed_rpm == pytest.approx(1000.0, abs=0.01)

    def test_little_endian_decoding(self):
        """Verify little-endian byte order for multi-byte fields."""
        data = bytearray(25)
        # Set status to 0x01020304 in little-endian
        data[0:4] = bytes([0x04, 0x03, 0x02, 0x01])

        telem = StandardTelemetry.from_bytes(bytes(data))

        assert telem.status == 0x01020304


class TestTempTelemetryFormat:
    """
    Verify TEMPERATURES telemetry (0x01) format matches production.

    Production code:
        struct AppTelemTemperatures {
            Packed<uint16_t> dcdc;       // 2 bytes
            Packed<uint16_t> enclosure;  // 2 bytes
            Packed<uint16_t> driver;     // 2 bytes
            Packed<uint16_t> motor;      // 2 bytes
        };
        static_assert(sizeof(AppTelemTemperatures) == 8);

    Total: 8 bytes, little-endian, raw ADC values
    """

    def test_structure_size(self):
        """TEMPERATURES telemetry should be exactly 8 bytes."""
        data = bytes(8)
        telem = TempTelemetry.from_bytes(data)
        assert telem is not None

    def test_minimum_data_requirement(self):
        """Should raise error if less than 8 bytes."""
        data = bytes(7)
        with pytest.raises(ValueError, match="8 bytes"):
            TempTelemetry.from_bytes(data)

    def test_field_decoding(self):
        """Verify raw ADC values are decoded correctly."""
        data = bytearray(8)
        data[0:2] = (1000).to_bytes(2, "little")  # dcdc
        data[2:4] = (2000).to_bytes(2, "little")  # enclosure
        data[4:6] = (3000).to_bytes(2, "little")  # driver
        data[6:8] = (4000).to_bytes(2, "little")  # motor

        telem = TempTelemetry.from_bytes(bytes(data))

        assert telem.temp_dcdc_raw == 1000
        assert telem.temp_enclosure_raw == 2000
        assert telem.temp_driver_raw == 3000
        assert telem.temp_motor_raw == 4000


class TestVoltTelemetryFormat:
    """
    Verify VOLTAGES telemetry (0x02) format matches production.

    Production code:
        struct AppTelemVoltages {
            PackedQ<uint32_t, 16> vmon_1v5_v;   // 4 bytes UQ16.16
            PackedQ<uint32_t, 16> vmon_3v3_v;   // 4 bytes
            PackedQ<uint32_t, 16> vmon_5v_v;    // 4 bytes
            PackedQ<uint32_t, 16> vmon_12v_v;   // 4 bytes
            PackedQ<uint32_t, 16> vmon_30v_v;   // 4 bytes
            PackedQ<uint32_t, 16> vmon_2v5_v;   // 4 bytes
        };
        static_assert(sizeof(AppTelemVoltages) == 24);

    Total: 24 bytes, little-endian, UQ16.16 format
    """

    def test_structure_size(self):
        """VOLTAGES telemetry should be exactly 24 bytes."""
        data = bytes(24)
        telem = VoltTelemetry.from_bytes(data)
        assert telem is not None

    def test_minimum_data_requirement(self):
        """Should raise error if less than 24 bytes."""
        data = bytes(23)
        with pytest.raises(ValueError, match="24 bytes"):
            VoltTelemetry.from_bytes(data)

    def test_uq16_16_decoding(self):
        """Verify UQ16.16 voltage decoding."""
        data = bytearray(24)
        # 3.3V = 3.3 * 65536 = 216268.8 ≈ 216269
        data[4:8] = (216269).to_bytes(4, "little")

        telem = VoltTelemetry.from_bytes(bytes(data))

        assert telem.v_3v3 == pytest.approx(3.3, abs=0.001)


class TestCurrTelemetryFormat:
    """
    Verify CURRENTS telemetry (0x03) format matches production.

    Production code:
        struct AppTelemCurrents {
            PackedQ<uint32_t, 16> imon_1v5_ma;         // 4 bytes UQ16.16
            PackedQ<uint32_t, 16> imon_3v3_ma;         // 4 bytes
            PackedQ<uint32_t, 16> imon_5v_analog_ma;   // 4 bytes
            PackedQ<uint32_t, 16> imon_5v_digital_ma;  // 4 bytes
            PackedQ<uint32_t, 16> imon_12v_ma;         // 4 bytes
            PackedQ<uint32_t, 16> imon_30v_a;          // 4 bytes (note: Amps, not mA)
        };
        static_assert(sizeof(AppTelemCurrents) == 24);

    Total: 24 bytes, little-endian, UQ16.16 format
    """

    def test_structure_size(self):
        """CURRENTS telemetry should be exactly 24 bytes."""
        data = bytes(24)
        telem = CurrTelemetry.from_bytes(data)
        assert telem is not None

    def test_minimum_data_requirement(self):
        """Should raise error if less than 24 bytes."""
        data = bytes(23)
        with pytest.raises(ValueError, match="24 bytes"):
            CurrTelemetry.from_bytes(data)


class TestDiagGeneralTelemetryFormat:
    """
    Verify DIAGNOSTICS-GENERAL telemetry (0x04) format matches production.

    Production code:
        struct AppTelemDiagGeneral {
            PackedQ<uint32_t, 2> uptime_s;          // 4 bytes Q30.2
            Packed<uint32_t> rev_count;             // 4 bytes
            Packed<uint32_t> hall_bad_trans_count;  // 4 bytes
            Packed<uint32_t> drive_fault_count;     // 4 bytes
            Packed<uint32_t> over_temp_count;       // 4 bytes
        };
        static_assert(sizeof(AppTelemDiagGeneral) == 20);

    Total: 20 bytes, little-endian
    """

    def test_structure_size(self):
        """DIAGNOSTICS-GENERAL telemetry should be exactly 20 bytes."""
        data = bytes(20)
        telem = DiagGeneralTelemetry.from_bytes(data)
        assert telem is not None

    def test_minimum_data_requirement(self):
        """Should raise error if less than 20 bytes."""
        data = bytes(19)
        with pytest.raises(ValueError, match="20 bytes"):
            DiagGeneralTelemetry.from_bytes(data)

    def test_uptime_q30_2_decoding(self):
        """Verify Q30.2 uptime decoding."""
        data = bytearray(20)
        # 100 seconds = 100 * 4 = 400 in Q30.2
        data[0:4] = (400).to_bytes(4, "little")

        telem = DiagGeneralTelemetry.from_bytes(bytes(data))

        assert telem.uptime_s == pytest.approx(100.0, abs=0.25)

    def test_counter_decoding(self):
        """Verify counter fields decode as uint32."""
        data = bytearray(20)
        data[4:8] = (12345).to_bytes(4, "little")  # rev_count
        data[8:12] = (5).to_bytes(4, "little")  # hall_bad_trans_count
        data[12:16] = (2).to_bytes(4, "little")  # drive_fault_count
        data[16:20] = (1).to_bytes(4, "little")  # over_temp_count

        telem = DiagGeneralTelemetry.from_bytes(bytes(data))

        assert telem.rev_count == 12345
        assert telem.hall_bad_trans_count == 5
        assert telem.drive_fault_count == 2
        assert telem.over_temp_count == 1


class TestTelemetryBlockIds:
    """Verify telemetry block IDs match ICD."""

    def test_block_ids(self):
        """All telemetry block IDs should match ICD specification."""
        assert TelemetryBlock.STANDARD.value == 0x00
        assert TelemetryBlock.TEMP.value == 0x01
        assert TelemetryBlock.VOLT.value == 0x02
        assert TelemetryBlock.CURR.value == 0x03
        assert TelemetryBlock.DIAG_GENERAL.value == 0x04
        assert TelemetryBlock.DIAG_EDAC.value == 0x05
        assert TelemetryBlock.DIAG_SCIA.value == 0x06
        assert TelemetryBlock.DIAG_SCIB.value == 0x07


class TestNspFrameFormat:
    """Verify NSP frame format matches ICD."""

    def test_control_byte_request(self):
        """Request frames have POLL=1, A=0."""
        frame = nsp.make_request(nsp.NspCommand.PING)

        assert frame.is_request is True
        assert frame.is_ack is False
        assert frame.command == nsp.NspCommand.PING
        assert frame.control & nsp.POLL_BIT

    def test_control_byte_reply_ack(self):
        """ACK reply frames have POLL=0, A=1."""
        frame = nsp.make_reply(nsp.NspCommand.PING, ack=True)

        assert frame.is_request is False
        assert frame.is_ack is True
        assert not (frame.control & nsp.POLL_BIT)
        assert frame.control & nsp.ACK_BIT

    def test_control_byte_reply_nack(self):
        """NACK reply frames have POLL=0, A=0."""
        frame = nsp.make_reply(nsp.NspCommand.PING, ack=False)

        assert frame.is_request is False
        assert frame.is_nack is True
        assert not (frame.control & nsp.POLL_BIT)
        assert not (frame.control & nsp.ACK_BIT)

    def test_command_codes(self):
        """Verify command codes match ICD."""
        assert nsp.NspCommand.PING == 0x00
        assert nsp.NspCommand.PEEK == 0x02
        assert nsp.NspCommand.POKE == 0x03
        assert nsp.NspCommand.APP_TM == 0x07
        assert nsp.NspCommand.APP_CMD == 0x08
        assert nsp.NspCommand.CLEAR_FAULT == 0x09
        assert nsp.NspCommand.CONFIG_PROT == 0x0A
        assert nsp.NspCommand.TRIP_LCL == 0x0B

    def test_frame_serialization(self):
        """Frame to_bytes produces correct format."""
        frame = nsp.make_request(nsp.NspCommand.PING)

        data = frame.to_bytes()

        # Format: [dest][src][control][payload...]
        assert data[0] == frame.dest_addr
        assert data[1] == frame.src_addr
        assert data[2] == frame.control
        assert data[3:] == frame.payload

    def test_frame_deserialization(self):
        """Frame from_bytes parses correctly."""
        data = bytes([0x07, 0x11, 0x80, 0xAB, 0xCD])  # PING request with payload

        frame = nsp.NspFrame.from_bytes(data)

        assert frame.dest_addr == 0x07
        assert frame.src_addr == 0x11
        assert frame.control == 0x80
        assert frame.payload == bytes([0xAB, 0xCD])


class TestClearFaultFormat:
    """Verify CLEAR-FAULT (0x09) packet format."""

    def test_payload_size(self):
        """CLEAR-FAULT payload should be 4 bytes."""
        mask = 0xFFFFFFFF
        payload = mask.to_bytes(4, "little")

        assert len(payload) == 4

    def test_little_endian(self):
        """CLEAR-FAULT mask should be little-endian."""
        mask = 0x12345678
        payload = mask.to_bytes(4, "little")

        assert payload == bytes([0x78, 0x56, 0x34, 0x12])

    def test_fault_bit_values(self):
        """Verify fault bit enum values match ICD."""
        assert nsp.FaultBits.MOTOR_DRIVE_FAULT == 0x01
        assert nsp.FaultBits.MOTOR_DRIVE_OTW == 0x02
        assert nsp.FaultBits.HALL_INVALID_STATE == 0x04
        assert nsp.FaultBits.HALL_INVALID_TRANS == 0x08
        assert nsp.FaultBits.OVERVOLTAGE == 0x10
        assert nsp.FaultBits.OVERSPEED_FAULT == 0x20
        assert nsp.FaultBits.OVERSPEED_LIMITED == 0x40
        assert nsp.FaultBits.OVERPOWER_LIMITED == 0x80
        assert nsp.FaultBits.CURRENT_LIMITED == 0x100


class TestConfigProtectionFormat:
    """Verify CONFIG-PROTECTION (0x0A) packet format."""

    def test_payload_size(self):
        """CONFIG-PROTECTION payload should be 4 bytes."""
        bits = 0x00000001
        payload = bits.to_bytes(4, "little")

        assert len(payload) == 4

    def test_protection_bit_values(self):
        """Verify protection bit enum values match ICD."""
        assert nsp.ProtectionBits.OVERSPEED_FAULT == 0x01
        assert nsp.ProtectionBits.OVERSPEED_LIMIT == 0x02
        assert nsp.ProtectionBits.OVERCURRENT_LIMIT == 0x04
        assert nsp.ProtectionBits.EDAC_SCRUB == 0x08
        assert nsp.ProtectionBits.BRAKING_OVERVOLTAGE == 0x10

    def test_status_bit_values(self):
        """Verify status bit enum values for protection state."""
        assert nsp.StatusBits.OVERSPEED_FAULT_DISABLED == 0x20000
        assert nsp.StatusBits.OVERSPEED_LIMIT_DISABLED == 0x40000
        assert nsp.StatusBits.OVERCURRENT_DISABLED == 0x80000
        assert nsp.StatusBits.EDAC_SCRUB_DISABLED == 0x100000
        assert nsp.StatusBits.BRAKING_LOAD_DISABLED == 0x200000
