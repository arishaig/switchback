"""Wallpaper generation from backgrounds and logo composites."""

import logging
import io
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageColor

from switchback.config import GeneratedConfig

logger = logging.getLogger(__name__)


def blend_colors(color1: str, color2: str, ratio: float) -> str:
    """
    Blend between two hex colors.

    Args:
        color1: First hex color (e.g., "#ff0000")
        color2: Second hex color (e.g., "#0000ff")
        ratio: Blend ratio from color1 to color2 (0.0 = color1, 1.0 = color2)

    Returns:
        Blended hex color string
    """
    # Parse colors
    r1, g1, b1 = ImageColor.getrgb(color1)
    r2, g2, b2 = ImageColor.getrgb(color2)

    # Blend
    r = int(r1 * (1 - ratio) + r2 * ratio)
    g = int(g1 * (1 - ratio) + g2 * ratio)
    b = int(b1 * (1 - ratio) + b2 * ratio)

    # Return as hex
    return f"#{r:02x}{g:02x}{b:02x}"


class WallpaperGenerator:
    """Generates wallpapers from background colors and logo composites."""

    def __init__(self, generated_config: GeneratedConfig):
        """
        Initialize wallpaper generator.

        Args:
            generated_config: GeneratedConfig with logo and color specifications
        """
        self.config = generated_config
        self.logo_image = self._load_logo()

    def _load_logo(self) -> Image.Image:
        """Load and cache the logo image (supports PNG and SVG)."""
        try:
            logo_path = Path(self.config.logo)

            # Check if SVG
            if logo_path.suffix.lower() in ['.svg', '.svgz']:
                # Render SVG to high-resolution PNG
                import cairosvg

                # Render at very high resolution for quality (will be scaled down later)
                # Using 4K resolution as base for crisp results
                svg_data = cairosvg.svg2png(
                    url=str(logo_path),
                    output_width=3840,
                    output_height=2160
                )

                logo = Image.open(io.BytesIO(svg_data)).convert('RGBA')
                logger.debug(f"Loaded SVG logo: {self.config.logo} (rendered to {logo.size})")
            else:
                # Load PNG/JPG directly
                logo = Image.open(self.config.logo).convert('RGBA')
                logger.debug(f"Loaded logo: {self.config.logo} ({logo.size})")

            return logo

        except Exception as e:
            logger.error(f"Failed to load logo from {self.config.logo}: {e}")
            raise

    def _apply_color_to_logo(self, logo: Image.Image, color: str) -> Image.Image:
        """
        Apply a color tint to logo while preserving transparency and luminosity.

        Args:
            logo: Logo image (RGBA)
            color: Hex color string (e.g., "#ff0000")

        Returns:
            Colored logo image
        """
        # Parse target color
        r, g, b = ImageColor.getrgb(color)

        # Create a colored version of the logo
        colored = Image.new('RGBA', logo.size, (0, 0, 0, 0))

        # Get pixel data
        pixels = logo.load()
        colored_pixels = colored.load()

        # Apply color while preserving luminosity
        for y in range(logo.height):
            for x in range(logo.width):
                original = pixels[x, y]
                alpha = original[3]

                if alpha > 0:
                    # Calculate luminosity of original pixel
                    lum = (original[0] + original[1] + original[2]) / 3 / 255

                    # Apply tint color with original luminosity
                    colored_pixels[x, y] = (
                        int(r * lum),
                        int(g * lum),
                        int(b * lum),
                        alpha
                    )

        return colored

    def _calculate_logo_size(self, screen_size: Tuple[int, int]) -> Tuple[int, int]:
        """
        Calculate logo size based on screen dimensions and scale factor.

        Args:
            screen_size: Screen dimensions (width, height)

        Returns:
            Logo dimensions (width, height)
        """
        screen_width, screen_height = screen_size
        target_height = int(screen_height * self.config.logo_scale)

        # Maintain aspect ratio
        aspect_ratio = self.logo_image.width / self.logo_image.height
        target_width = int(target_height * aspect_ratio)

        return (target_width, target_height)

    def _calculate_logo_position(
        self,
        screen_size: Tuple[int, int],
        logo_size: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Calculate logo position based on configuration.

        Args:
            screen_size: Screen dimensions (width, height)
            logo_size: Logo dimensions (width, height)

        Returns:
            Logo position (x, y)
        """
        screen_width, screen_height = screen_size
        logo_width, logo_height = logo_size

        if self.config.logo_position == "center":
            x = (screen_width - logo_width) // 2
            y = (screen_height - logo_height) // 2
        elif self.config.logo_position == "top":
            x = (screen_width - logo_width) // 2
            y = int(screen_height * 0.1)
        elif self.config.logo_position == "bottom":
            x = (screen_width - logo_width) // 2
            y = int(screen_height * 0.9 - logo_height)
        else:
            # Default to center for unknown positions
            x = (screen_width - logo_width) // 2
            y = (screen_height - logo_height) // 2

        return (x, y)

    def generate_wallpaper(
        self,
        period: str,
        screen_size: Tuple[int, int] = (1920, 1080)
    ) -> Image.Image:
        """
        Generate a wallpaper for a specific period.

        Args:
            period: Time period ("night", "morning", "afternoon")
            screen_size: Target screen resolution (width, height)

        Returns:
            Generated wallpaper as PIL Image
        """
        bg_color = self.config.background_colors[period]
        logo_color = self.config.logo_colors[period]
        return self.generate_wallpaper_with_colors(bg_color, logo_color, screen_size)

    def generate_wallpaper_with_colors(
        self,
        bg_color: str,
        logo_color: str,
        screen_size: Tuple[int, int] = (1920, 1080)
    ) -> Image.Image:
        """
        Generate a wallpaper with specific colors.

        Args:
            bg_color: Background hex color (e.g., "#ff0000")
            logo_color: Logo hex color (e.g., "#0000ff")
            screen_size: Target screen resolution (width, height)

        Returns:
            Generated wallpaper as PIL Image
        """
        logger.debug(f"Generating wallpaper at {screen_size}: bg={bg_color}, logo={logo_color}")

        # Create background with solid color
        background = Image.new('RGB', screen_size, bg_color)

        # Apply color to logo
        colored_logo = self._apply_color_to_logo(self.logo_image, logo_color)

        # Resize logo
        logo_size = self._calculate_logo_size(screen_size)
        resized_logo = colored_logo.resize(logo_size, Image.Resampling.LANCZOS)

        # Calculate position and composite
        position = self._calculate_logo_position(screen_size, logo_size)
        background.paste(resized_logo, position, resized_logo)  # Use resized_logo as mask for transparency

        logger.debug(f"Generated wallpaper: {bg_color} background, {logo_color} logo")
        return background
