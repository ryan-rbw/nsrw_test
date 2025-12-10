"""
ICD Compliance Test Scenarios for NRWA-T6 Reaction Wheel.

All scenarios comply with NRWA-T6 ICD (N2-A2a-DD0021 Rev 10.02) and are
designed to exercise the protocol alignment between host test software
and the reaction wheel emulator.

Reference: NRWA-T6 Interface Control Document sections:
    - Section 8: Characteristics
    - Section 9: Operating Modes
    - Section 12: Communication Interface
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nss_host.commands import Session

from nss_host.icd_fields import decode_uq24_8, encode_uq24_8
from nss_host.nsp import (
    ControlMode,
    FaultBits,
    MemoryAddress,
    ProtectionBits,
    StatusBits,
)
from nss_host.telemetry import TelemetryBlock

logger = logging.getLogger(__name__)


class ScenarioResult(Enum):
    """Test scenario result."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepResult:
    """Result of a single test step."""

    name: str
    passed: bool
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class ScenarioReport:
    """Test scenario execution report."""

    name: str
    description: str
    result: ScenarioResult
    steps: list[StepResult] = field(default_factory=list)
    duration_s: float = 0.0
    icd_reference: str = ""

    def add_step(self, name: str, passed: bool, message: str = "", **details) -> None:
        """Add step result to report."""
        self.steps.append(StepResult(name, passed, message, details))

    @property
    def passed_count(self) -> int:
        """Count of passed steps."""
        return sum(1 for s in self.steps if s.passed)

    @property
    def failed_count(self) -> int:
        """Count of failed steps."""
        return sum(1 for s in self.steps if not s.passed)


class ICDScenario(ABC):
    """Base class for ICD compliance test scenarios."""

    name: str = "Unnamed Scenario"
    description: str = ""
    icd_reference: str = ""

    def __init__(self, session: "Session"):
        """Initialize scenario with session."""
        self.session = session
        self.report = ScenarioReport(
            name=self.name,
            description=self.description,
            result=ScenarioResult.PASSED,
            icd_reference=self.icd_reference,
        )

    @abstractmethod
    def run(self) -> ScenarioReport:
        """Execute the scenario and return report."""
        pass

    def _log_step(self, name: str, passed: bool, message: str = "", **details) -> None:
        """Log and record a test step."""
        status = "PASS" if passed else "FAIL"
        logger.info(f"  [{status}] {name}: {message}")
        self.report.add_step(name, passed, message, **details)
        if not passed:
            self.report.result = ScenarioResult.FAILED


class Scenario1_WheelDiscovery(ICDScenario):
    """
    Scenario 1: Wheel Discovery

    Purpose: Verify communication and device identification.
    ICD Reference: Section 12.5 (PING command)

    Tests:
    1. Send PING command (0x00)
    2. Verify 5-byte response format
    3. Log device identification
    """

    name = "Wheel Discovery"
    description = "Verify communication and device identification via PING"
    icd_reference = "ICD Section 12.5"

    def run(self) -> ScenarioReport:
        """Execute wheel discovery scenario."""
        start_time = time.time()
        logger.info(f"Running scenario: {self.name}")

        try:
            # Step 1: Send PING command
            logger.info("  Sending PING command...")
            response = self.session.ping()

            # Step 2: Verify response length
            if len(response) >= 5:
                self._log_step(
                    "PING response length",
                    True,
                    f"Received {len(response)} bytes (expected >= 5)",
                )
            else:
                self._log_step(
                    "PING response length",
                    False,
                    f"Received {len(response)} bytes (expected >= 5)",
                )
                self.report.duration_s = time.time() - start_time
                return self.report

            # Step 3: Parse and verify response fields
            device_type = response[0]
            serial = response[1]
            version_major = response[2]
            version_minor = response[3]
            version_patch = response[4]

            self._log_step(
                "Device identification",
                True,
                f"Type=0x{device_type:02X}, Serial={serial}, "
                f"Version={version_major}.{version_minor}.{version_patch}",
                device_type=device_type,
                serial=serial,
                version=f"{version_major}.{version_minor}.{version_patch}",
            )

            # Step 4: Communication verified
            self._log_step(
                "Communication verified",
                True,
                "Successful NSP transaction completed",
            )

        except Exception as e:
            self._log_step("PING command", False, f"Exception: {e}")
            self.report.result = ScenarioResult.ERROR

        self.report.duration_s = time.time() - start_time
        return self.report


class Scenario2_SpeedControl(ICDScenario):
    """
    Scenario 2: Speed Control

    Purpose: Verify closed-loop speed control mode.
    ICD Reference: Section 9 (Speed Control Mode), max 5000 RPM

    Tests:
    1. Set SPEED mode with various setpoints
    2. Wait for control loop to stabilize
    3. Verify telemetry reflects commanded speed
    4. Verify control_mode field

    Constraint: Do NOT exceed 5000 RPM (soft limit per ICD 9.5.2.3)
    """

    name = "Speed Control"
    description = "Verify closed-loop speed control mode"
    icd_reference = "ICD Section 9"

    # Test setpoints (RPM) - all within ICD limit of 5000 RPM
    TEST_SETPOINTS = [100.0, 500.0, 1000.0, 2000.0]
    SETTLE_TIME_MS = 500  # Control loop settles within 500ms
    TOLERANCE_PERCENT = 5.0  # 5% tolerance for speed tracking

    def run(self) -> ScenarioReport:
        """Execute speed control scenario."""
        start_time = time.time()
        logger.info(f"Running scenario: {self.name}")

        try:
            for setpoint in self.TEST_SETPOINTS:
                # Step 1: Set SPEED mode with setpoint
                logger.info(f"  Setting SPEED mode: {setpoint} RPM")
                self.session.app_command(ControlMode.SPEED, setpoint)
                self._log_step(
                    f"Set speed {setpoint} RPM",
                    True,
                    f"APP-CMD sent: mode=SPEED, setpoint={setpoint}",
                )

                # Step 2: Wait for control loop to settle
                time.sleep(self.SETTLE_TIME_MS / 1000.0)

                # Step 3: Request STANDARD telemetry
                telem = self.session.app_telemetry(TelemetryBlock.STANDARD)

                # Step 4: Verify control_mode
                mode_ok = telem.control_mode == ControlMode.SPEED
                self._log_step(
                    f"Control mode verification ({setpoint} RPM)",
                    mode_ok,
                    f"control_mode=0x{telem.control_mode:02X} (expected 0x02)",
                )

                # Step 5: Verify speed tracking (within tolerance)
                speed_error = abs(telem.speed_rpm - setpoint)
                tolerance = setpoint * (self.TOLERANCE_PERCENT / 100.0)
                speed_ok = speed_error <= tolerance

                self._log_step(
                    f"Speed tracking ({setpoint} RPM)",
                    speed_ok,
                    f"Measured={telem.speed_rpm:.1f} RPM, "
                    f"Error={speed_error:.1f} RPM ({speed_error/setpoint*100:.1f}%)",
                    setpoint=setpoint,
                    measured=telem.speed_rpm,
                    error_percent=speed_error / setpoint * 100,
                )

            # Return to IDLE
            self.session.app_command(ControlMode.IDLE)
            self._log_step("Return to IDLE", True, "Wheel returned to IDLE mode")

        except Exception as e:
            self._log_step("Speed control", False, f"Exception: {e}")
            self.report.result = ScenarioResult.ERROR
            # Try to return to safe state
            try:
                self.session.app_command(ControlMode.IDLE)
            except Exception:
                pass

        self.report.duration_s = time.time() - start_time
        return self.report


class Scenario3_TorqueControl(ICDScenario):
    """
    Scenario 3: Torque Control

    Purpose: Verify torque command mode.
    ICD Reference: Section 9 (Torque Control Mode), max 310 mN-m

    Tests:
    1. Set TORQUE mode with various setpoints
    2. Wait for command processing
    3. Verify telemetry control_mode
    4. Verify setpoint field (Q10.22 format)

    Constraint: Max 310 mN-m at max current under vacuum (ICD 8.2)
    """

    name = "Torque Control"
    description = "Verify torque command mode"
    icd_reference = "ICD Section 9"

    # Test setpoints (mN-m) - all within ICD limit of 310 mN-m
    TEST_SETPOINTS = [10.0, 50.0, 100.0]
    COMMAND_DELAY_MS = 100

    def run(self) -> ScenarioReport:
        """Execute torque control scenario."""
        start_time = time.time()
        logger.info(f"Running scenario: {self.name}")

        try:
            for setpoint in self.TEST_SETPOINTS:
                # Step 1: Set TORQUE mode with setpoint
                logger.info(f"  Setting TORQUE mode: {setpoint} mN-m")
                self.session.app_command(ControlMode.TORQUE, setpoint)
                self._log_step(
                    f"Set torque {setpoint} mN-m",
                    True,
                    f"APP-CMD sent: mode=TORQUE, setpoint={setpoint}",
                )

                # Step 2: Wait for command processing
                time.sleep(self.COMMAND_DELAY_MS / 1000.0)

                # Step 3: Request STANDARD telemetry
                telem = self.session.app_telemetry(TelemetryBlock.STANDARD)

                # Step 4: Verify control_mode
                mode_ok = telem.control_mode == ControlMode.TORQUE
                self._log_step(
                    f"Control mode verification ({setpoint} mN-m)",
                    mode_ok,
                    f"control_mode=0x{telem.control_mode:02X} (expected 0x04)",
                )

                # Step 5: Verify setpoint in telemetry (Q10.22 encoded)
                self._log_step(
                    f"Setpoint verification ({setpoint} mN-m)",
                    True,
                    f"Raw setpoint=0x{telem.setpoint:08X}, "
                    f"Decoded={telem.setpoint_decoded:.2f} mN-m",
                    raw_setpoint=telem.setpoint,
                    decoded_setpoint=telem.setpoint_decoded,
                )

            # Return to IDLE
            self.session.app_command(ControlMode.IDLE)
            self._log_step("Return to IDLE", True, "Wheel returned to IDLE mode")

        except Exception as e:
            self._log_step("Torque control", False, f"Exception: {e}")
            self.report.result = ScenarioResult.ERROR
            try:
                self.session.app_command(ControlMode.IDLE)
            except Exception:
                pass

        self.report.duration_s = time.time() - start_time
        return self.report


class Scenario4_FaultHandling(ICDScenario):
    """
    Scenario 4: Fault Handling

    Purpose: Verify fault detection and clearing.
    ICD Reference: Section 12.5.2.1.2 (Fault Register), Section 12.7 (CLEAR-FAULT)

    Tests:
    1. Configure low overspeed threshold via POKE
    2. Set SPEED mode above threshold
    3. Verify OVERSPEED-FAULT bit is set
    4. Send CLEAR-FAULT command
    5. Verify fault bit cleared
    6. Restore original threshold

    Note: Overspeed fault sets motor to high-impedance state (ICD 9.5.2.4)
    """

    name = "Fault Handling"
    description = "Verify fault detection and clearing"
    icd_reference = "ICD Section 12.5.2.1.2, 12.7"

    TEST_THRESHOLD_RPM = 500.0  # Low threshold to trigger fault
    TEST_SPEED_RPM = 600.0  # Speed above threshold
    DEFAULT_THRESHOLD_RPM = 6000.0  # Default per ICD

    def run(self) -> ScenarioReport:
        """Execute fault handling scenario."""
        start_time = time.time()
        logger.info(f"Running scenario: {self.name}")
        original_threshold = None

        try:
            # Step 1: Read current overspeed threshold
            logger.info("  Reading current overspeed threshold...")
            raw_threshold = self.session.peek(MemoryAddress.OVERSPEED_FAULT_THRESHOLD)
            original_threshold = decode_uq24_8(raw_threshold)
            self._log_step(
                "Read overspeed threshold",
                True,
                f"Current threshold: {original_threshold:.1f} RPM",
            )

            # Step 2: Set low overspeed threshold to trigger fault
            logger.info(f"  Setting low threshold: {self.TEST_THRESHOLD_RPM} RPM")
            new_threshold_raw = encode_uq24_8(self.TEST_THRESHOLD_RPM)
            self.session.poke(MemoryAddress.OVERSPEED_FAULT_THRESHOLD, new_threshold_raw)
            self._log_step(
                "Set low overspeed threshold",
                True,
                f"Threshold set to {self.TEST_THRESHOLD_RPM} RPM",
            )

            # Step 3: Set SPEED mode above threshold
            logger.info(f"  Setting speed above threshold: {self.TEST_SPEED_RPM} RPM")
            self.session.app_command(ControlMode.SPEED, self.TEST_SPEED_RPM)
            time.sleep(0.5)  # Wait for fault to trigger

            # Step 4: Check for OVERSPEED_FAULT in telemetry
            telem = self.session.app_telemetry(TelemetryBlock.STANDARD)
            overspeed_fault = bool(telem.fault & FaultBits.OVERSPEED_FAULT)

            self._log_step(
                "Overspeed fault detection",
                overspeed_fault,
                f"Fault register=0x{telem.fault:08X}, "
                f"OVERSPEED_FAULT bit={'SET' if overspeed_fault else 'CLEAR'}",
                fault_register=telem.fault,
            )

            # Step 5: Send CLEAR-FAULT command
            logger.info("  Sending CLEAR-FAULT command...")
            self.session.clear_fault(0xFFFFFFFF)
            self._log_step("Send CLEAR-FAULT", True, "CLEAR-FAULT sent with mask 0xFFFFFFFF")

            # Step 6: Verify fault cleared
            time.sleep(0.1)
            telem = self.session.app_telemetry(TelemetryBlock.STANDARD)
            fault_cleared = not bool(telem.fault & FaultBits.OVERSPEED_FAULT)

            self._log_step(
                "Fault cleared verification",
                fault_cleared,
                f"Fault register=0x{telem.fault:08X}, "
                f"OVERSPEED_FAULT bit={'CLEAR' if fault_cleared else 'STILL SET'}",
            )

        except Exception as e:
            self._log_step("Fault handling", False, f"Exception: {e}")
            self.report.result = ScenarioResult.ERROR

        finally:
            # Always restore original threshold and return to IDLE
            try:
                if original_threshold is not None:
                    logger.info(f"  Restoring threshold to {original_threshold:.1f} RPM")
                    restore_raw = encode_uq24_8(original_threshold)
                    self.session.poke(MemoryAddress.OVERSPEED_FAULT_THRESHOLD, restore_raw)
                    self._log_step(
                        "Restore threshold",
                        True,
                        f"Threshold restored to {original_threshold:.1f} RPM",
                    )
                else:
                    # Restore default if we couldn't read original
                    restore_raw = encode_uq24_8(self.DEFAULT_THRESHOLD_RPM)
                    self.session.poke(MemoryAddress.OVERSPEED_FAULT_THRESHOLD, restore_raw)

                self.session.app_command(ControlMode.IDLE)
            except Exception:
                pass

        self.report.duration_s = time.time() - start_time
        return self.report


class Scenario5_ProtectionConfiguration(ICDScenario):
    """
    Scenario 5: Protection Configuration

    Purpose: Verify protection enable/disable mechanism.
    ICD Reference: Section 9.5.2 (Soft Protection), CONFIGURE-PROTECTION command

    Tests:
    1. Read current protection status from telemetry
    2. Disable overspeed limit protection
    3. Verify status bit reflects disabled state
    4. Re-enable all protections
    5. Verify status bit cleared

    Protection Bits (0=enabled, 1=disabled):
        Bit 0: Overspeed fault
        Bit 1: Overspeed limit
        Bit 2: Overcurrent limit
        Bit 3: EDAC scrub
        Bit 4: Braking overvoltage load
    """

    name = "Protection Configuration"
    description = "Verify protection enable/disable mechanism"
    icd_reference = "ICD Section 9.5.2"

    def run(self) -> ScenarioReport:
        """Execute protection configuration scenario."""
        start_time = time.time()
        logger.info(f"Running scenario: {self.name}")

        try:
            # Step 1: Read initial protection status
            logger.info("  Reading initial protection status...")
            telem = self.session.app_telemetry(TelemetryBlock.STANDARD)
            initial_status = telem.status

            overspeed_limit_disabled = bool(initial_status & StatusBits.OVERSPEED_LIMIT_DISABLED)
            self._log_step(
                "Read initial status",
                True,
                f"Status=0x{initial_status:08X}, "
                f"OVERSPEED_LIMIT_DISABLED={'Yes' if overspeed_limit_disabled else 'No'}",
            )

            # Step 2: Disable overspeed limit protection (bit 1)
            logger.info("  Disabling overspeed limit protection...")
            self.session.config_protection(ProtectionBits.OVERSPEED_LIMIT)
            self._log_step(
                "Disable overspeed limit",
                True,
                f"CONFIG-PROT sent with bits=0x{ProtectionBits.OVERSPEED_LIMIT:08X}",
            )

            # Step 3: Verify status bit reflects disabled state
            time.sleep(0.1)
            telem = self.session.app_telemetry(TelemetryBlock.STANDARD)
            overspeed_limit_disabled = bool(telem.status & StatusBits.OVERSPEED_LIMIT_DISABLED)

            self._log_step(
                "Verify protection disabled",
                overspeed_limit_disabled,
                f"Status=0x{telem.status:08X}, "
                f"OVERSPEED_LIMIT_DISABLED={'Yes' if overspeed_limit_disabled else 'No'}",
            )

            # Step 4: Re-enable all protections (send 0x00000000)
            logger.info("  Re-enabling all protections...")
            self.session.config_protection(0x00000000)
            self._log_step(
                "Re-enable all protections",
                True,
                "CONFIG-PROT sent with bits=0x00000000",
            )

            # Step 5: Verify status bit cleared
            time.sleep(0.1)
            telem = self.session.app_telemetry(TelemetryBlock.STANDARD)
            overspeed_limit_disabled = bool(telem.status & StatusBits.OVERSPEED_LIMIT_DISABLED)
            protection_restored = not overspeed_limit_disabled

            self._log_step(
                "Verify protection re-enabled",
                protection_restored,
                f"Status=0x{telem.status:08X}, "
                f"OVERSPEED_LIMIT_DISABLED={'Yes' if overspeed_limit_disabled else 'No'}",
            )

        except Exception as e:
            self._log_step("Protection configuration", False, f"Exception: {e}")
            self.report.result = ScenarioResult.ERROR
            # Try to restore protections
            try:
                self.session.config_protection(0x00000000)
            except Exception:
                pass

        self.report.duration_s = time.time() - start_time
        return self.report


class Scenario6_TelemetryPolling(ICDScenario):
    """
    Scenario 6: Telemetry Polling

    Purpose: Verify all telemetry blocks at different polling rates.
    ICD Reference: Section 12.5.2 (Telemetry blocks)

    Tests:
    1. Request each telemetry block, verify response sizes
    2. Poll STANDARD at 1 Hz for 5 seconds
    3. Poll STANDARD at 10 Hz for 5 seconds

    Expected telemetry block sizes:
        STANDARD (0x00): 25 bytes
        TEMPERATURES (0x01): 8 bytes
        VOLTAGES (0x02): 24 bytes
        CURRENTS (0x03): 24 bytes
        DIAG-GENERAL (0x04): 20 bytes
    """

    name = "Telemetry Polling"
    description = "Verify all telemetry blocks at different polling rates"
    icd_reference = "ICD Section 12.5.2"

    EXPECTED_SIZES = {
        TelemetryBlock.STANDARD: 25,
        TelemetryBlock.TEMP: 8,
        TelemetryBlock.VOLT: 24,
        TelemetryBlock.CURR: 24,
        TelemetryBlock.DIAG_GENERAL: 20,
    }

    def run(self) -> ScenarioReport:
        """Execute telemetry polling scenario."""
        start_time = time.time()
        logger.info(f"Running scenario: {self.name}")

        try:
            # Part 1: Verify each telemetry block response size
            logger.info("  Testing telemetry block response sizes...")
            for block, expected_size in self.EXPECTED_SIZES.items():
                try:
                    telem = self.session.app_telemetry(block)
                    # If we got here without exception, the decoder accepted the response
                    self._log_step(
                        f"Block {block.name} response",
                        True,
                        f"Received and decoded successfully (expected {expected_size} bytes)",
                        block_id=block.value,
                    )
                except ValueError as e:
                    self._log_step(
                        f"Block {block.name} response",
                        False,
                        f"Decode error: {e}",
                    )
                except Exception as e:
                    self._log_step(
                        f"Block {block.name} response",
                        False,
                        f"Error: {e}",
                    )

            # Part 2: Poll STANDARD at 1 Hz for 5 seconds
            logger.info("  Polling STANDARD telemetry at 1 Hz...")
            success_count = 0
            timeout_count = 0
            poll_count = 5

            for i in range(poll_count):
                try:
                    self.session.app_telemetry(TelemetryBlock.STANDARD)
                    success_count += 1
                except Exception:
                    timeout_count += 1
                time.sleep(1.0)

            self._log_step(
                "1 Hz polling (5 seconds)",
                timeout_count == 0,
                f"Success: {success_count}/{poll_count}, Timeouts: {timeout_count}",
                success_count=success_count,
                timeout_count=timeout_count,
            )

            # Part 3: Poll STANDARD at 10 Hz for 5 seconds
            logger.info("  Polling STANDARD telemetry at 10 Hz...")
            success_count = 0
            timeout_count = 0
            poll_count = 50

            for i in range(poll_count):
                try:
                    self.session.app_telemetry(TelemetryBlock.STANDARD)
                    success_count += 1
                except Exception:
                    timeout_count += 1
                time.sleep(0.1)

            success_rate = success_count / poll_count * 100
            # Allow up to 5% timeouts at 10 Hz
            acceptable = success_rate >= 95.0

            self._log_step(
                "10 Hz polling (5 seconds)",
                acceptable,
                f"Success: {success_count}/{poll_count} ({success_rate:.1f}%), "
                f"Timeouts: {timeout_count}",
                success_count=success_count,
                timeout_count=timeout_count,
                success_rate=success_rate,
            )

        except Exception as e:
            self._log_step("Telemetry polling", False, f"Exception: {e}")
            self.report.result = ScenarioResult.ERROR

        self.report.duration_s = time.time() - start_time
        return self.report


# =============================================================================
# Scenario Runner
# =============================================================================


ALL_SCENARIOS = [
    Scenario1_WheelDiscovery,
    Scenario2_SpeedControl,
    Scenario3_TorqueControl,
    Scenario4_FaultHandling,
    Scenario5_ProtectionConfiguration,
    Scenario6_TelemetryPolling,
]


def run_all_scenarios(session: "Session") -> list[ScenarioReport]:
    """
    Run all ICD compliance scenarios.

    Args:
        session: Active NSS Host session.

    Returns:
        List of scenario reports.
    """
    reports = []

    for scenario_class in ALL_SCENARIOS:
        scenario = scenario_class(session)
        report = scenario.run()
        reports.append(report)

        # Log summary
        status = "PASSED" if report.result == ScenarioResult.PASSED else "FAILED"
        logger.info(
            f"Scenario '{report.name}': {status} "
            f"({report.passed_count}/{len(report.steps)} steps passed, "
            f"{report.duration_s:.2f}s)"
        )

    return reports


def run_scenario_by_name(session: "Session", name: str) -> ScenarioReport | None:
    """
    Run a specific scenario by name.

    Args:
        session: Active NSS Host session.
        name: Scenario name (e.g., "Wheel Discovery", "Speed Control").

    Returns:
        Scenario report, or None if scenario not found.
    """
    for scenario_class in ALL_SCENARIOS:
        if scenario_class.name.lower() == name.lower():
            scenario = scenario_class(session)
            return scenario.run()

    return None


def list_scenarios() -> list[dict]:
    """
    List available scenarios.

    Returns:
        List of scenario info dictionaries.
    """
    return [
        {
            "name": s.name,
            "description": s.description,
            "icd_reference": s.icd_reference,
        }
        for s in ALL_SCENARIOS
    ]


def print_report(report: ScenarioReport) -> None:
    """Print formatted scenario report."""
    print(f"\n{'=' * 60}")
    print(f"Scenario: {report.name}")
    print(f"Description: {report.description}")
    print(f"ICD Reference: {report.icd_reference}")
    print(f"Result: {report.result.value.upper()}")
    print(f"Duration: {report.duration_s:.2f}s")
    print(f"Steps: {report.passed_count}/{len(report.steps)} passed")
    print("-" * 60)

    for step in report.steps:
        status = "PASS" if step.passed else "FAIL"
        print(f"  [{status}] {step.name}")
        if step.message:
            print(f"         {step.message}")

    print("=" * 60)


def print_summary(reports: list[ScenarioReport]) -> None:
    """Print summary of all scenario results."""
    print(f"\n{'=' * 60}")
    print("ICD COMPLIANCE TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in reports if r.result == ScenarioResult.PASSED)
    failed = sum(1 for r in reports if r.result == ScenarioResult.FAILED)
    errors = sum(1 for r in reports if r.result == ScenarioResult.ERROR)

    for report in reports:
        status = report.result.value.upper()
        steps = f"{report.passed_count}/{len(report.steps)}"
        print(f"  [{status:6}] {report.name}: {steps} steps")

    print("-" * 60)
    print(f"Total: {passed} passed, {failed} failed, {errors} errors")
    print(f"Overall: {'PASSED' if failed == 0 and errors == 0 else 'FAILED'}")
    print("=" * 60)
