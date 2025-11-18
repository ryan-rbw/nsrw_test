"""
Scenario runner for emulator.

Implements HOST_SPEC_RPi.md section 19: Scenario Orchestration and Error Injection.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


class ScenarioState(Enum):
    """Scenario execution state."""

    IDLE = "idle"
    LOADED = "loaded"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Scenario:
    """
    Emulator scenario definition.

    Attributes:
        name: Scenario name.
        version: Scenario version.
        description: Scenario description.
        steps: List of scenario steps.
    """

    name: str
    version: str
    description: str
    steps: List[dict]


class ScenarioRunner:
    """
    Scenario orchestration and execution.

    Manages loading, running, and monitoring emulator scenarios.
    """

    def __init__(self, session) -> None:
        """
        Initialize scenario runner.

        Args:
            session: Active NSS Host session.
        """
        self.session = session
        self.current_scenario: Optional[Scenario] = None
        self.state = ScenarioState.IDLE

    def list_scenarios(self, directory: Path) -> List[str]:
        """
        List available scenarios in directory.

        Args:
            directory: Scenario directory path.

        Returns:
            List of scenario names.
        """
        if not directory.exists():
            return []

        scenarios = []
        for file in directory.glob("*.json"):
            scenarios.append(file.stem)

        return sorted(scenarios)

    def load_scenario(self, path: Path) -> Scenario:
        """
        Load scenario from JSON file.

        Args:
            path: Scenario file path.

        Returns:
            Loaded scenario object.

        Raises:
            FileNotFoundError: If scenario file not found.
            ValueError: If scenario format invalid.
        """
        with open(path, "r") as f:
            data = json.load(f)

        scenario = Scenario(
            name=data.get("name", "Unnamed"),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            steps=data.get("steps", []),
        )

        self.current_scenario = scenario
        self.state = ScenarioState.LOADED

        return scenario

    def start(self) -> None:
        """
        Start scenario execution.

        Raises:
            RuntimeError: If no scenario loaded.
        """
        if self.current_scenario is None:
            raise RuntimeError("No scenario loaded")

        # TODO: Implement actual scenario execution
        self.state = ScenarioState.RUNNING

    def pause(self) -> None:
        """Pause scenario execution."""
        if self.state == ScenarioState.RUNNING:
            self.state = ScenarioState.PAUSED

    def resume(self) -> None:
        """Resume scenario execution."""
        if self.state == ScenarioState.PAUSED:
            self.state = ScenarioState.RUNNING

    def stop(self) -> None:
        """Stop scenario execution."""
        self.state = ScenarioState.IDLE
        self.current_scenario = None

    def get_status(self) -> dict:
        """
        Get scenario status.

        Returns:
            Status dictionary with state, progress, etc.
        """
        return {
            "state": self.state.value,
            "scenario": self.current_scenario.name if self.current_scenario else None,
            "version": self.current_scenario.version if self.current_scenario else None,
        }
