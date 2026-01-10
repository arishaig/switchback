"""Configuration loading and validation."""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict
import pytz


@dataclass
class Config:
    """Switchback configuration."""

    latitude: float
    longitude: float
    timezone: str
    wallpapers: Dict[str, Path]
    check_interval_fallback: int = 300
    preload_all: bool = True
    monitor: str = ""

    @classmethod
    def load(cls, config_path: Path) -> "Config":
        """
        Load and validate configuration from YAML file.

        Args:
            config_path: Path to configuration file

        Returns:
            Config instance

        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If config file doesn't exist
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Configuration file is empty")

        # Validate location data
        location = data.get('location', {})
        latitude = location.get('latitude')
        longitude = location.get('longitude')
        timezone = location.get('timezone')

        if latitude is None:
            raise ValueError("Missing required field: location.latitude")
        if longitude is None:
            raise ValueError("Missing required field: location.longitude")
        if timezone is None:
            raise ValueError("Missing required field: location.timezone")

        # Validate ranges
        if not (-90 <= latitude <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got: {latitude}")
        if not (-180 <= longitude <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got: {longitude}")

        # Validate timezone
        if timezone not in pytz.all_timezones:
            raise ValueError(
                f"Invalid timezone: {timezone}. "
                f"Must be a valid IANA timezone (e.g., 'US/Pacific', 'Europe/London')"
            )

        # Validate wallpaper paths
        wallpapers_data = data.get('wallpapers', {})
        if not wallpapers_data:
            raise ValueError("Missing required field: wallpapers")

        required_periods = {'night', 'morning', 'afternoon'}
        missing_periods = required_periods - set(wallpapers_data.keys())
        if missing_periods:
            raise ValueError(f"Missing wallpaper configurations for: {', '.join(missing_periods)}")

        wallpapers = {}
        for period, path_str in wallpapers_data.items():
            # Expand ~ and environment variables
            expanded_path = os.path.expanduser(os.path.expandvars(path_str))
            wp_path = Path(expanded_path)

            if not wp_path.exists():
                raise ValueError(f"Wallpaper file not found for '{period}': {wp_path}")
            if not wp_path.is_file():
                raise ValueError(f"Wallpaper path for '{period}' is not a file: {wp_path}")

            wallpapers[period] = wp_path

        # Optional settings
        settings = data.get('settings', {})

        return cls(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            wallpapers=wallpapers,
            check_interval_fallback=settings.get('check_interval_fallback', 300),
            preload_all=settings.get('preload_all', True),
            monitor=settings.get('monitor', ''),
        )

    def get_wallpaper(self, period: str) -> Path:
        """Get wallpaper path for a time period."""
        return self.wallpapers[period]


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return Path(xdg_config_home) / 'switchback' / 'config.yaml'
