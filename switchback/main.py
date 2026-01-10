"""Main entry point and daemon loop for Switchback."""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from switchback.config import Config, get_default_config_path
from switchback.sun_calculator import SunCalculator
from switchback.wallpaper_manager import WallpaperManager
from switchback.time_period import TimePeriod, get_current_period
from switchback.blender import ImageBlender, BlendCache
from switchback.transition_tracker import TransitionTracker


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging for stdout (systemd compatible)."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def run_daemon(config: Config, verbose: bool = False):
    """
    Run the wallpaper switching daemon.

    Args:
        config: Configuration object
        verbose: Enable verbose logging
    """
    setup_logging(verbose)
    logger.info("Starting Switchback daemon...")

    # Initialize components
    sun_calc = SunCalculator(config.latitude, config.longitude, config.timezone)
    wallpaper_mgr = WallpaperManager(config.monitor)

    # Wait for hyprpaper to be ready
    if not wallpaper_mgr.wait_for_hyprpaper():
        logger.error("Hyprpaper is not running. Please start hyprpaper first.")
        sys.exit(1)

    # Preload all wallpapers if configured (only for hard transition mode)
    if config.preload_all and not config.transitions_enabled:
        wallpaper_paths = list(config.wallpapers.values())
        if not wallpaper_mgr.preload_all(wallpaper_paths):
            logger.warning("Some wallpapers failed to preload, but continuing...")

    # Initialize transition components if enabled
    blender = None
    cache = None
    tracker = None

    if config.transitions_enabled:
        logger.info("Gradual transitions enabled")
        blender = ImageBlender()
        if config.transitions_cache_blends:
            cache_dir = Path(config.transitions_cache_dir).expanduser()
            cache = BlendCache(cache_dir)
            logger.info(f"Blend cache enabled at: {cache_dir}")
        tracker = TransitionTracker(sun_calc)

    # Get current period
    now = datetime.now(sun_calc.tz)
    sun_times = sun_calc.get_sun_times(now)
    current_period = get_current_period(sun_times, now)

    logger.info(f"Current period: {current_period.value}")
    logger.info(f"Sunrise: {sun_times['sunrise'].strftime('%H:%M')}")
    logger.info(f"Solar noon: {sun_times['noon'].strftime('%H:%M')}")
    logger.info(f"Sunset: {sun_times['sunset'].strftime('%H:%M')}")

    # Set initial wallpaper
    if config.transitions_enabled:
        # In gradual mode, set blended wallpaper based on current time
        period_start, period_end = tracker.get_period_boundaries(now, current_period)
        blend_ratio = blender.calculate_blend_ratio(now, period_start, period_end)

        from_period, to_period = tracker.get_transition_wallpapers(current_period)
        from_path = config.get_wallpaper(from_period)
        to_path = config.get_wallpaper(to_period)

        logger.info(f"Initial blend: {from_period} → {to_period} ({blend_ratio:.2f})")

        # Try cache first
        wallpaper_path = None
        if cache:
            cache_key = cache.get_cache_key(from_path, to_path, blend_ratio)
            wallpaper_path = cache.get_cached_blend(cache_key, from_path, to_path)

        # Blend if not cached
        if not wallpaper_path:
            logger.info("Generating blended wallpaper...")
            blended_image = blender.blend_images(from_path, to_path, blend_ratio)
            if cache:
                wallpaper_path = cache.save_blend(blended_image, cache_key, from_path, to_path)
            else:
                temp_path = Path("/tmp/switchback_blend.jpg")
                blended_image.save(temp_path, "JPEG", quality=95)
                wallpaper_path = temp_path

        if not wallpaper_mgr.set_wallpaper(wallpaper_path):
            logger.error("Failed to set initial wallpaper")
            sys.exit(1)
    else:
        # In hard mode, set wallpaper for current period
        wallpaper_path = config.get_wallpaper(current_period.value)
        if not wallpaper_mgr.set_wallpaper(wallpaper_path):
            logger.error("Failed to set initial wallpaper")
            sys.exit(1)

    last_period = current_period

    # Main daemon loop
    logger.info("Daemon loop started")
    while True:
        try:
            now = datetime.now(sun_calc.tz)
            sun_times = sun_calc.get_sun_times(now)
            current_period = get_current_period(sun_times, now)

            if config.transitions_enabled:
                # GRADUAL TRANSITION MODE
                period_start, period_end = tracker.get_period_boundaries(now, current_period)
                blend_ratio = blender.calculate_blend_ratio(now, period_start, period_end)

                from_period, to_period = tracker.get_transition_wallpapers(current_period)
                from_path = config.get_wallpaper(from_period)
                to_path = config.get_wallpaper(to_period)

                logger.debug(f"Blend: {from_period} → {to_period} ({blend_ratio:.2f})")

                # Try cache first
                wallpaper_path = None
                if cache:
                    cache_key = cache.get_cache_key(from_path, to_path, blend_ratio)
                    wallpaper_path = cache.get_cached_blend(cache_key, from_path, to_path)

                # Blend if not cached
                if not wallpaper_path:
                    logger.debug("Generating blended wallpaper...")
                    blended_image = blender.blend_images(from_path, to_path, blend_ratio)
                    if cache:
                        wallpaper_path = cache.save_blend(blended_image, cache_key, from_path, to_path)
                    else:
                        temp_path = Path("/tmp/switchback_blend.jpg")
                        blended_image.save(temp_path, "JPEG", quality=95)
                        wallpaper_path = temp_path

                wallpaper_mgr.set_wallpaper(wallpaper_path)

                # Sleep until next granularity interval
                sleep_seconds = config.transitions_granularity

            else:
                # HARD TRANSITION MODE (original behavior)

                # Check if period changed
                if current_period != last_period:
                    logger.info(f"Period changed: {last_period.value} → {current_period.value}")
                    wallpaper_path = config.get_wallpaper(current_period.value)

                    if wallpaper_mgr.set_wallpaper(wallpaper_path):
                        last_period = current_period
                    else:
                        logger.error("Failed to change wallpaper, will retry...")

                # Calculate next transition time
                next_transition = sun_calc.get_next_transition_time(now, current_period.value)
                sleep_seconds = (next_transition - now).total_seconds()

                # Add small buffer and ensure minimum sleep time
                sleep_seconds = max(60, min(sleep_seconds + 5, config.check_interval_fallback))

            logger.debug(f"Sleeping for {int(sleep_seconds)}s")
            time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}", exc_info=True)
            time.sleep(config.check_interval_fallback)


def run_once(config: Config, period: str = None):
    """
    Set wallpaper once and exit (for testing).

    Args:
        config: Configuration object
        period: Specific period to set (night/morning/afternoon), or None for auto-detect
    """
    setup_logging(verbose=True)

    wallpaper_mgr = WallpaperManager(config.monitor)

    if not wallpaper_mgr.wait_for_hyprpaper(max_wait=5):
        logger.error("Hyprpaper is not running")
        sys.exit(1)

    if period:
        # Set specific period (always use hard transition for specific period)
        if period not in config.wallpapers:
            logger.error(f"Unknown period: {period}")
            sys.exit(1)

        wallpaper_path = config.get_wallpaper(period)
        logger.info(f"Setting wallpaper for period: {period}")
    else:
        # Auto-detect current period
        sun_calc = SunCalculator(config.latitude, config.longitude, config.timezone)
        now = datetime.now(sun_calc.tz)
        sun_times = sun_calc.get_sun_times(now)
        current_period = get_current_period(sun_times, now)

        logger.info(f"Current period: {current_period.value}")

        # Check if gradual transitions are enabled
        if config.transitions_enabled:
            logger.info("Gradual transitions enabled")
            if config.transitions_cache_blends:
                cache_dir = Path(config.transitions_cache_dir).expanduser()
                logger.info(f"Blend cache enabled at: {cache_dir}")

            # Initialize transition components
            blender = ImageBlender()
            cache = BlendCache(cache_dir) if config.transitions_cache_blends else None
            tracker = TransitionTracker(sun_calc)

            # Get period boundaries and calculate blend ratio
            period_start, period_end = tracker.get_period_boundaries(now, current_period)
            blend_ratio = blender.calculate_blend_ratio(now, period_start, period_end)

            from_period, to_period = tracker.get_transition_wallpapers(current_period)
            from_path = config.get_wallpaper(from_period)
            to_path = config.get_wallpaper(to_period)

            logger.info(f"Initial blend: {from_period} → {to_period} ({blend_ratio:.2f})")

            # Try cache first
            wallpaper_path = None
            if cache:
                cache_key = cache.get_cache_key(from_path, to_path, blend_ratio)
                wallpaper_path = cache.get_cached_blend(cache_key, from_path, to_path)

            # Blend if not cached
            if not wallpaper_path:
                logger.info("Generating blended wallpaper...")
                blended_image = blender.blend_images(from_path, to_path, blend_ratio)
                if cache:
                    wallpaper_path = cache.save_blend(blended_image, cache_key, from_path, to_path)
                else:
                    temp_path = Path("/tmp/switchback_blend.jpg")
                    blended_image.save(temp_path, "JPEG", quality=95)
                    wallpaper_path = temp_path
        else:
            # Hard transition mode
            wallpaper_path = config.get_wallpaper(current_period.value)

    if wallpaper_mgr.set_wallpaper(wallpaper_path):
        logger.info("Wallpaper set successfully")
    else:
        logger.error("Failed to set wallpaper")
        sys.exit(1)


def run_test(config: Config):
    """
    Show current period and next transition time (for testing).

    Args:
        config: Configuration object
    """
    setup_logging(verbose=True)

    sun_calc = SunCalculator(config.latitude, config.longitude, config.timezone)
    now = datetime.now(sun_calc.tz)
    sun_times = sun_calc.get_sun_times(now)
    current_period = get_current_period(sun_times, now)

    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"\nSun times for today:")
    print(f"  Sunrise:     {sun_times['sunrise'].strftime('%H:%M:%S')}")
    print(f"  Solar noon:  {sun_times['noon'].strftime('%H:%M:%S')}")
    print(f"  Sunset:      {sun_times['sunset'].strftime('%H:%M:%S')}")
    print(f"\nCurrent period: {current_period.value}")
    print(f"Current wallpaper: {config.get_wallpaper(current_period.value)}")

    next_transition = sun_calc.get_next_transition_time(now, current_period.value)
    print(f"\nNext transition: {next_transition.strftime('%Y-%m-%d %H:%M:%S')}")

    time_until = next_transition - now
    hours = int(time_until.total_seconds() // 3600)
    minutes = int((time_until.total_seconds() % 3600) // 60)
    print(f"Time until transition: {hours}h {minutes}m\n")


def init_config():
    """Generate a configuration template."""
    config_path = get_default_config_path()

    if config_path.exists():
        response = input(f"Config file already exists at {config_path}. Overwrite? [y/N] ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    # Create config directory
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Simple template
    template = """# Switchback configuration

location:
  latitude: 37.7749      # Your latitude
  longitude: -122.4194   # Your longitude
  timezone: "US/Pacific" # Your IANA timezone

wallpapers:
  night: ~/Pictures/backgrounds/night.jpg
  morning: ~/Pictures/backgrounds/morning.jpg
  afternoon: ~/Pictures/backgrounds/afternoon.jpg

settings:
  check_interval_fallback: 300  # Safety check interval (seconds)
  preload_all: true             # Preload all wallpapers at startup
  monitor: ""                   # Monitor name (empty = all monitors)

  # Gradual wallpaper transitions (optional)
  transitions:
    enabled: false                # Enable gradual transitions between wallpapers
    granularity: 3600             # How often to update wallpaper blend (seconds, default: 1 hour)
    cache_blends: true            # Cache blended images for better performance
    cache_dir: "~/.cache/switchback"  # Where to store cached blends
"""

    config_path.write_text(template)
    print(f"Configuration template created at: {config_path}")
    print("\nPlease edit this file with your location and wallpaper paths.")


def cli():
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Switchback - Solar-based dynamic wallpaper switcher"
    )
    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='Path to configuration file (default: ~/.config/switchback/config.yaml)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Test command
    subparsers.add_parser('test', help='Show current period and next transition')

    # Once command
    once_parser = subparsers.add_parser('once', help='Set wallpaper once and exit')
    once_parser.add_argument(
        '--period',
        choices=['night', 'morning', 'afternoon'],
        help='Specific period to set (default: auto-detect)'
    )

    # Init command
    subparsers.add_parser('init', help='Generate configuration template')

    args = parser.parse_args()

    # Handle init command (doesn't need config)
    if args.command == 'init':
        init_config()
        return

    # Load configuration
    config_path = args.config or get_default_config_path()

    try:
        config = Config.load(config_path)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        print(f"Run 'switchback init' to create a template.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Execute command
    if args.command == 'test':
        run_test(config)
    elif args.command == 'once':
        run_once(config, period=args.period)
    else:
        # Default: run daemon
        run_daemon(config, verbose=args.verbose)


if __name__ == '__main__':
    cli()
