"""Abstraction layer for wallpaper sources (files or generated)."""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

from PIL import Image

from switchback.config import Config, GeneratedConfig
from switchback.generator import WallpaperGenerator, blend_colors

logger = logging.getLogger(__name__)


class WallpaperSource(ABC):
    """Abstract base class for wallpaper sources."""

    @abstractmethod
    def get_wallpaper(self, period: str) -> Path:
        """Get wallpaper path for a period."""
        pass

    @abstractmethod
    def supports_preload(self) -> bool:
        """Whether this source supports preloading."""
        pass


class FileWallpaperSource(WallpaperSource):
    """Wallpaper source from image files."""

    def __init__(self, wallpapers: dict):
        """
        Initialize file wallpaper source.

        Args:
            wallpapers: Dictionary mapping periods to file paths
        """
        self.wallpapers = wallpapers

    def get_wallpaper(self, period: str) -> Path:
        """Get wallpaper path for a period."""
        return self.wallpapers[period]

    def supports_preload(self) -> bool:
        """File wallpapers support preloading."""
        return True


class GeneratedWallpaperSource(WallpaperSource):
    """Wallpaper source from generated images."""

    def __init__(
        self,
        generated_config: GeneratedConfig,
        cache_dir: Path,
        screen_size: Tuple[int, int] = (1920, 1080)
    ):
        """
        Initialize generated wallpaper source.

        Args:
            generated_config: Configuration for generated wallpapers
            cache_dir: Base cache directory
            screen_size: Target screen resolution (width, height)
        """
        self.config = generated_config
        self.cache_dir = cache_dir / "generated"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.screen_size = screen_size
        self.generator = WallpaperGenerator(generated_config)
        self.metadata_file = self.cache_dir / "metadata.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        """Load generation metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load metadata: {e}")
                return {}
        return {}

    def _save_metadata(self):
        """Save generation metadata."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save metadata: {e}")

    def _get_config_hash(self) -> str:
        """Generate hash of generation config for cache validation."""
        config_str = json.dumps({
            'logo': str(self.config.logo),
            'bg_colors': self.config.background_colors,
            'logo_colors': self.config.logo_colors,
            'logo_scale': self.config.logo_scale,
            'logo_position': self.config.logo_position,
            'screen_size': self.screen_size
        }, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]

    def _is_cache_valid(self, period: str, cache_path: Path) -> bool:
        """
        Check if cached wallpaper is valid.

        Args:
            period: Time period
            cache_path: Path to cached wallpaper

        Returns:
            True if cache is valid, False otherwise
        """
        if not cache_path.exists():
            return False

        config_hash = self._get_config_hash()
        stored_hash = self.metadata.get(period, {}).get('config_hash')

        return stored_hash == config_hash

    def get_wallpaper(self, period: str) -> Path:
        """
        Get generated wallpaper, using cache if valid.

        Args:
            period: Time period ("night", "morning", "afternoon")

        Returns:
            Path to generated wallpaper
        """
        config_hash = self._get_config_hash()
        cache_filename = f"{period}_{config_hash}.jpg"
        cache_path = self.cache_dir / cache_filename

        # Check cache validity
        if self._is_cache_valid(period, cache_path):
            logger.debug(f"Using cached generated wallpaper: {period}")
            return cache_path

        # Generate new wallpaper
        logger.info(f"Generating wallpaper for {period}...")
        wallpaper_image = self.generator.generate_wallpaper(period, self.screen_size)

        # Save to cache with high quality
        wallpaper_image.save(cache_path, "JPEG", quality=98, optimize=True, subsampling=0)

        # Update metadata
        self.metadata[period] = {
            'config_hash': config_hash,
            'cache_file': cache_filename
        }
        self._save_metadata()

        logger.info(f"Generated wallpaper saved: {cache_path}")
        return cache_path

    def supports_preload(self) -> bool:
        """Generated wallpapers don't support preloading (created on-demand)."""
        return False

    def get_blended_wallpaper(
        self,
        from_period: str,
        to_period: str,
        blend_ratio: float
    ) -> Path:
        """
        Get generated wallpaper with blended colors for transitions.

        Args:
            from_period: Starting time period
            to_period: Ending time period
            blend_ratio: Blend ratio (0.0 = from_period, 1.0 = to_period)

        Returns:
            Path to generated blended wallpaper
        """
        # Blend background colors
        from_bg = self.config.background_colors[from_period]
        to_bg = self.config.background_colors[to_period]
        blended_bg = blend_colors(from_bg, to_bg, blend_ratio)

        # Blend logo colors
        from_logo = self.config.logo_colors[from_period]
        to_logo = self.config.logo_colors[to_period]
        blended_logo = blend_colors(from_logo, to_logo, blend_ratio)

        # Create cache key
        config_hash = self._get_config_hash()
        # Round blend ratio to avoid excessive cache entries
        rounded_ratio = round(blend_ratio, 3)
        cache_filename = f"blend_{from_period}_{to_period}_{rounded_ratio:.3f}_{config_hash}.jpg"
        cache_path = self.cache_dir / cache_filename

        # Check if already cached
        if cache_path.exists():
            logger.debug(f"Using cached blended wallpaper: {from_period}->{to_period} ({rounded_ratio:.3f})")
            return cache_path

        # Generate wallpaper with blended colors
        logger.debug(f"Generating blended wallpaper: {from_period}->{to_period} ({rounded_ratio:.3f})")
        wallpaper_image = self.generator.generate_wallpaper_with_colors(
            blended_bg,
            blended_logo,
            self.screen_size
        )

        # Save to cache with high quality
        wallpaper_image.save(cache_path, "JPEG", quality=98, optimize=True, subsampling=0)
        logger.debug(f"Blended wallpaper saved: {cache_path}")

        return cache_path


def create_wallpaper_source(config: Config) -> WallpaperSource:
    """
    Factory function to create appropriate wallpaper source.

    Args:
        config: Application configuration

    Returns:
        WallpaperSource instance based on config mode

    Raises:
        ValueError: If mode is invalid or required fields are missing
    """
    if config.mode == "generated":
        if not config.generated:
            raise ValueError("Generated mode requires 'generated' config section")

        cache_dir = Path(config.transitions_cache_dir).expanduser()
        # TODO: Detect screen size from hyprland config or use default
        screen_size = (1920, 1080)

        return GeneratedWallpaperSource(config.generated, cache_dir, screen_size)
    elif config.mode == "wallpaper":
        if not config.wallpapers:
            raise ValueError("Wallpaper mode requires 'wallpapers' config section")
        return FileWallpaperSource(config.wallpapers)
    else:
        raise ValueError(f"Unknown mode: {config.mode}")
