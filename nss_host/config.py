"""
Configuration management for NSS Host.

Implements HOST_SPEC_RPi.md section 8: Config Files.
Loads/saves TOML configuration for serial parameters, GPIO pins, logging, and defaults bundle.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class SerialConfig(BaseModel):
    """Serial port configuration."""

    port: str = Field(default="/dev/ttyAMA0", description="Serial port device")
    baud: int = Field(default=460800, description="Baud rate (455.6-465.7 kbps tolerated)")
    timeout_ms: int = Field(default=10, description="Reply timeout in milliseconds")
    retries: int = Field(default=2, description="Retry count on CRC/SLIP errors")
    port_select_gpio: Optional[int] = Field(
        default=24, description="GPIO for port A/B selection (0=A, 1=B)"
    )
    de_gpio: Optional[int] = Field(default=18, description="RS-485 Driver Enable GPIO (BCM)")
    nre_gpio: Optional[int] = Field(
        default=23, description="RS-485 Receiver Enable GPIO (BCM, active-low)"
    )
    fault_in_gpio: Optional[int] = Field(default=25, description="FAULT input GPIO")
    reset_out_gpio: Optional[int] = Field(default=12, description="RESET output GPIO")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    frame_dump: bool = Field(default=True, description="Enable frame-level logging")
    log_dir: str = Field(default="~/nss_logs", description="Directory for log files")


class DefaultsBundleConfig(BaseModel):
    """Defaults bundle configuration."""

    path: str = Field(
        default="~/nss_bundles/nrwa_t6_defaults_v1.toml",
        description="Path to versioned defaults bundle",
    )


class Config(BaseModel):
    """Complete NSS Host configuration."""

    serial: SerialConfig = Field(default_factory=SerialConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    defaults_bundle: DefaultsBundleConfig = Field(default_factory=DefaultsBundleConfig)


def get_config_path() -> Path:
    """Get default configuration file path."""
    config_home = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(config_home) / "nss_host" / "config.toml"


def load_config(path: Optional[Path] = None) -> Config:
    """
    Load configuration from TOML file.

    Args:
        path: Configuration file path. If None, uses default location.

    Returns:
        Loaded configuration object.
    """
    if path is None:
        path = get_config_path()

    if not path.exists():
        # Return default config if file doesn't exist
        return Config()

    import tomli

    with open(path, "rb") as f:
        data = tomli.load(f)

    return Config(**data)


def save_config(config: Config, path: Optional[Path] = None) -> None:
    """
    Save configuration to TOML file.

    Args:
        config: Configuration object to save.
        path: Configuration file path. If None, uses default location.
    """
    if path is None:
        path = get_config_path()

    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict and write TOML
    import tomli_w

    with open(path, "wb") as f:
        tomli_w.dump(config.model_dump(), f)
