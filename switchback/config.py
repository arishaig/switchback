"""Configuration loading and validation."""

import os
import re
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional
import pytz


@dataclass
class GeneratedConfig:
    """Configuration for generated wallpaper mode."""

    logo: Path
    background_colors: Dict[str, str]
    logo_colors: Dict[str, str]
    logo_scale: float = 0.3
    logo_position: str = "center"


@dataclass
class Config:
    """Switchback configuration."""

    latitude: float
    longitude: float
    timezone: str
    mode: str = "wallpaper"
    wallpapers: Optional[Dict[str, Path]] = None
    generated: Optional[GeneratedConfig] = None
    check_interval_fallback: int = 300
    preload_all: bool = True
    monitor: str = ""

    # Transition settings
    transitions_enabled: bool = False
    transitions_granularity: int = 3600
    transitions_cache_blends: bool = True
    transitions_cache_dir: str = "~/.cache/switchback"

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

        # Get mode (default to "wallpaper" for backward compatibility)
        mode = data.get('mode', 'wallpaper')
        if mode not in ('wallpaper', 'generated'):
            raise ValueError(f"Invalid mode: {mode}. Must be 'wallpaper' or 'generated'")

        # Validate mode-specific configuration
        wallpapers = None
        generated = None

        if mode == 'wallpaper':
            # Validate wallpaper paths
            wallpapers_data = data.get('wallpapers', {})
            if not wallpapers_data:
                raise ValueError("Wallpaper mode requires 'wallpapers' section")

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

        elif mode == 'generated':
            # Validate generated configuration
            generated_data = data.get('generated', {})
            if not generated_data:
                raise ValueError("Generated mode requires 'generated' section")

            # Validate logo path
            logo_str = generated_data.get('logo')
            if not logo_str:
                raise ValueError("Generated mode requires 'logo' path")
            logo_path = Path(os.path.expanduser(os.path.expandvars(logo_str)))
            if not logo_path.exists():
                raise ValueError(f"Logo file not found: {logo_path}")
            if not logo_path.is_file():
                raise ValueError(f"Logo path is not a file: {logo_path}")

            # Validate background colors
            bg_colors = generated_data.get('background_colors', {})
            required_periods = {'night', 'morning', 'afternoon'}
            if set(bg_colors.keys()) != required_periods:
                raise ValueError(f"Generated mode requires background_colors for: {required_periods}")

            for period, color in bg_colors.items():
                if not re.match(r'^#[0-9a-fA-F]{6}$', color):
                    raise ValueError(f"Invalid hex color for background {period}: {color}")

            # Validate logo colors
            logo_colors = generated_data.get('logo_colors', {})
            if set(logo_colors.keys()) != required_periods:
                raise ValueError(f"Generated mode requires logo_colors for: {required_periods}")

            for period, color in logo_colors.items():
                if not re.match(r'^#[0-9a-fA-F]{6}$', color):
                    raise ValueError(f"Invalid hex color for logo {period}: {color}")

            # Validate optional parameters
            logo_scale = generated_data.get('logo_scale', 0.3)
            if not (0.0 < logo_scale <= 1.0):
                raise ValueError(f"Logo scale must be between 0.0 and 1.0, got: {logo_scale}")

            logo_position = generated_data.get('logo_position', 'center')
            if logo_position not in ('center', 'top', 'bottom'):
                raise ValueError(f"Logo position must be 'center', 'top', or 'bottom', got: {logo_position}")

            generated = GeneratedConfig(
                logo=logo_path,
                background_colors=bg_colors,
                logo_colors=logo_colors,
                logo_scale=logo_scale,
                logo_position=logo_position
            )

        # Optional settings
        settings = data.get('settings', {})

        # Transition settings (nested under settings.transitions)
        transitions = settings.get('transitions', {})
        transitions_enabled = transitions.get('enabled', False)
        transitions_granularity = transitions.get('granularity', 3600)
        transitions_cache_blends = transitions.get('cache_blends', True)
        transitions_cache_dir = transitions.get('cache_dir', '~/.cache/switchback')

        # Validate transition settings
        if transitions_granularity < 60:
            raise ValueError(
                f"Transition granularity must be at least 60 seconds, got: {transitions_granularity}"
            )
        if transitions_granularity > 86400:
            raise ValueError(
                f"Transition granularity cannot exceed 86400 seconds (24 hours), got: {transitions_granularity}"
            )

        return cls(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            mode=mode,
            wallpapers=wallpapers,
            generated=generated,
            check_interval_fallback=settings.get('check_interval_fallback', 300),
            preload_all=settings.get('preload_all', True),
            monitor=settings.get('monitor', ''),
            transitions_enabled=transitions_enabled,
            transitions_granularity=transitions_granularity,
            transitions_cache_blends=transitions_cache_blends,
            transitions_cache_dir=transitions_cache_dir,
        )

    def get_wallpaper(self, period: str) -> Path:
        """Get wallpaper path for a time period."""
        return self.wallpapers[period]


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
    return Path(xdg_config_home) / 'switchback' / 'config.yaml'
