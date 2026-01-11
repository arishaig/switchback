"""Image blending and cache management for gradual wallpaper transitions."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image


logger = logging.getLogger(__name__)


class ImageBlender:
    """Handles wallpaper blending operations."""

    def blend_images(self, img1_path: Path, img2_path: Path, alpha: float) -> Image.Image:
        """
        Blend two images using alpha compositing.

        Args:
            img1_path: Source image (blend FROM)
            img2_path: Target image (blend TO)
            alpha: Blend ratio 0.0-1.0 (0=all img1, 1=all img2)

        Returns:
            Blended PIL Image
        """
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"Alpha must be between 0.0 and 1.0, got {alpha}")

        logger.debug(f"Blending {img1_path.name} -> {img2_path.name} at alpha={alpha:.2f}")

        # Open and convert images to RGBA
        img1 = Image.open(img1_path).convert('RGBA')
        img2 = Image.open(img2_path).convert('RGBA')

        # Resize to match dimensions (use larger of the two)
        target_size = (
            max(img1.width, img2.width),
            max(img1.height, img2.height)
        )

        if img1.size != target_size:
            logger.debug(f"Resizing {img1_path.name} from {img1.size} to {target_size}")
            img1 = img1.resize(target_size, Image.Resampling.LANCZOS)

        if img2.size != target_size:
            logger.debug(f"Resizing {img2_path.name} from {img2.size} to {target_size}")
            img2 = img2.resize(target_size, Image.Resampling.LANCZOS)

        # Blend: result = img1 * (1-alpha) + img2 * alpha
        blended = Image.blend(img1, img2, alpha)

        # Convert back to RGB for saving
        return blended.convert('RGB')

    def calculate_blend_ratio(
        self,
        current_time: datetime,
        period_start: datetime,
        period_end: datetime
    ) -> float:
        """
        Calculate blend ratio based on progress through current period.

        Args:
            current_time: Current datetime
            period_start: Start of current period
            period_end: End of current period

        Returns:
            Float 0.0-1.0 representing progress through period
        """
        total_duration = (period_end - period_start).total_seconds()
        elapsed = (current_time - period_start).total_seconds()

        if total_duration <= 0:
            logger.warning(f"Invalid period duration: {total_duration}s")
            return 0.0

        # Calculate progress ratio
        ratio = elapsed / total_duration

        # Clamp to 0.0-1.0
        ratio = max(0.0, min(1.0, ratio))

        return ratio


class BlendCache:
    """Manages cached blended wallpapers."""

    def __init__(self, cache_dir: Path, max_cache_size_mb: int = 500):
        """
        Initialize blend cache.

        Args:
            cache_dir: Base cache directory
            max_cache_size_mb: Maximum cache size in megabytes
        """
        self.cache_dir = cache_dir / "blends"
        self.metadata_file = cache_dir / "metadata.json"
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize metadata
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        """Load cache metadata from file."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache metadata: {e}")
                return {}
        return {}

    def _save_metadata(self):
        """Save cache metadata to file."""
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save cache metadata: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_cache_key(
        self,
        from_wallpaper: Path,
        to_wallpaper: Path,
        blend_ratio: float
    ) -> str:
        """
        Generate cache key for a blend.

        Args:
            from_wallpaper: Source wallpaper path
            to_wallpaper: Target wallpaper path
            blend_ratio: Blend ratio 0.0-1.0

        Returns:
            Cache filename
        """
        # Round ratio to 2 decimals to limit cache size
        ratio_str = f"{blend_ratio:.2f}"
        return f"{from_wallpaper.stem}-{to_wallpaper.stem}_{ratio_str}.jpg"

    def is_cache_valid(
        self,
        cache_key: str,
        from_wallpaper: Path,
        to_wallpaper: Path
    ) -> bool:
        """
        Check if cached blend is valid.

        Args:
            cache_key: Cache filename
            from_wallpaper: Source wallpaper path
            to_wallpaper: Target wallpaper path

        Returns:
            True if cache is valid, False otherwise
        """
        if cache_key not in self.metadata:
            return False

        entry = self.metadata[cache_key]

        # Check if source wallpapers have changed
        from_hash = self._get_file_hash(from_wallpaper)
        to_hash = self._get_file_hash(to_wallpaper)

        return (
            entry.get('from_hash') == from_hash and
            entry.get('to_hash') == to_hash
        )

    def get_cached_blend(
        self,
        cache_key: str,
        from_wallpaper: Path,
        to_wallpaper: Path
    ) -> Optional[Path]:
        """
        Get cached blend if it exists and is valid.

        Args:
            cache_key: Cache filename
            from_wallpaper: Source wallpaper path
            to_wallpaper: Target wallpaper path

        Returns:
            Path to cached blend if valid, None otherwise
        """
        cached_path = self.cache_dir / cache_key

        if not cached_path.exists():
            return None

        if not self.is_cache_valid(cache_key, from_wallpaper, to_wallpaper):
            logger.debug(f"Cache invalid for {cache_key}, will regenerate")
            # Remove invalid cache entry
            cached_path.unlink(missing_ok=True)
            self.metadata.pop(cache_key, None)
            self._save_metadata()
            return None

        logger.debug(f"Using cached blend: {cache_key}")
        return cached_path

    def save_blend(
        self,
        image: Image.Image,
        cache_key: str,
        from_wallpaper: Path,
        to_wallpaper: Path
    ) -> Path:
        """
        Save blended image to cache.

        Args:
            image: Blended PIL Image
            cache_key: Cache filename
            from_wallpaper: Source wallpaper path
            to_wallpaper: Target wallpaper path

        Returns:
            Path to saved blend
        """
        cache_path = self.cache_dir / cache_key

        # Save image
        image.save(cache_path, "JPEG", quality=98, optimize=True, subsampling=0)
        logger.debug(f"Saved blend to cache: {cache_key}")

        # Update metadata
        self.metadata[cache_key] = {
            'from_hash': self._get_file_hash(from_wallpaper),
            'to_hash': self._get_file_hash(to_wallpaper),
            'created_at': datetime.now().isoformat(),
            'size_bytes': cache_path.stat().st_size
        }
        self._save_metadata()

        # Check cache size and clean up if needed
        self._enforce_cache_limit()

        return cache_path

    def _enforce_cache_limit(self):
        """Enforce cache size limit by removing oldest entries."""
        total_size = sum(
            (self.cache_dir / cache_key).stat().st_size
            for cache_key in self.metadata
            if (self.cache_dir / cache_key).exists()
        )

        if total_size <= self.max_cache_size_bytes:
            return

        logger.info(f"Cache size ({total_size / 1024 / 1024:.1f}MB) exceeds limit, cleaning up...")

        # Sort entries by creation time (oldest first)
        sorted_entries = sorted(
            self.metadata.items(),
            key=lambda x: x[1].get('created_at', '')
        )

        # Remove oldest entries until under limit
        for cache_key, entry in sorted_entries:
            cache_path = self.cache_dir / cache_key
            if cache_path.exists():
                file_size = cache_path.stat().st_size
                cache_path.unlink()
                total_size -= file_size
                logger.debug(f"Removed old cache entry: {cache_key}")

            self.metadata.pop(cache_key, None)

            if total_size <= self.max_cache_size_bytes:
                break

        self._save_metadata()
        logger.info(f"Cache cleanup complete, new size: {total_size / 1024 / 1024:.1f}MB")

    def clear_cache(self):
        """Clear all cached blends."""
        logger.info("Clearing all cached blends...")
        count = 0

        for file in self.cache_dir.glob("*.jpg"):
            file.unlink()
            count += 1

        self.metadata.clear()
        self._save_metadata()

        logger.info(f"Cleared {count} cached blends")
