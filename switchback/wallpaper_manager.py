"""Wallpaper management via hyprpaper IPC."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Set, Optional


logger = logging.getLogger(__name__)


class WallpaperManager:
    """Manages wallpaper switching through hyprpaper IPC."""

    def __init__(self, monitor: str = ""):
        """
        Initialize wallpaper manager.

        Args:
            monitor: Monitor name (empty string = all monitors)
        """
        self.monitor = monitor
        self.current_wallpaper: Optional[Path] = None
        self.preloaded: Set[Path] = set()

    def _run_command(self, cmd: list[str]) -> bool:
        """
        Execute hyprctl command.

        Args:
            cmd: Command as list of strings

        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            return True
        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr + e.stdout).lower() if e.stderr or e.stdout else ""

            # Check if IPC is disabled
            if 'disabled' in error_msg or ('ipc' in error_msg and 'off' in error_msg):
                logger.error(
                    "Hyprpaper IPC appears to be disabled.\n"
                    "To enable IPC:\n"
                    "  1. Edit ~/.config/hypr/hyprpaper.conf\n"
                    "  2. Change 'ipc = off' to 'ipc = on'\n"
                    "  3. Restart hyprpaper: systemctl --user restart hyprpaper.service"
                )
            # Check if it's an unsupported command (e.g., preload in hyprpaper 0.8.x)
            elif 'unknown' in error_msg and 'request' in error_msg:
                logger.debug(f"Command not supported (ignored): {cmd[2] if len(cmd) > 2 else 'unknown'}")
            else:
                logger.error(f"Command failed: {' '.join(cmd)}\n{e.stderr or e.stdout}")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return False

    def check_hyprpaper_running(self) -> bool:
        """
        Check if hyprpaper is running and responsive.

        Returns:
            True if hyprpaper is running, False otherwise
        """
        try:
            result = subprocess.run(
                ['pgrep', '-x', 'hyprpaper'],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def wait_for_hyprpaper(self, max_wait: int = 30) -> bool:
        """
        Wait for hyprpaper to be ready.

        Args:
            max_wait: Maximum seconds to wait

        Returns:
            True if hyprpaper is ready, False if timeout
        """
        logger.info("Waiting for hyprpaper to be ready...")
        for i in range(max_wait):
            if self.check_hyprpaper_running():
                logger.info("Hyprpaper is ready")
                return True
            time.sleep(1)

        logger.error(f"Hyprpaper not ready after {max_wait} seconds")
        return False

    def preload(self, path: Path) -> bool:
        """
        Preload wallpaper into memory.

        Note: In hyprpaper 0.8.x, preload may not be supported via IPC.
        The wallpaper command will load images automatically, so this is optional.

        Args:
            path: Path to wallpaper file

        Returns:
            True if successful, False otherwise (non-fatal)
        """
        if path in self.preloaded:
            logger.debug(f"Already preloaded: {path.name}")
            return True

        logger.debug(f"Attempting to preload wallpaper: {path.name}")
        success = self._run_command(['hyprctl', 'hyprpaper', 'preload', str(path)])

        if success:
            self.preloaded.add(path)
            logger.debug(f"Successfully preloaded: {path.name}")
        else:
            logger.debug(f"Preload not supported or failed: {path.name} (non-fatal)")

        return success

    def set_wallpaper(self, path: Path) -> bool:
        """
        Set wallpaper for monitor.

        Args:
            path: Path to wallpaper file

        Returns:
            True if successful, False otherwise
        """
        if not path.exists():
            logger.error(f"Wallpaper file not found: {path}")
            return False

        # Try to preload (optional, may not be supported in hyprpaper 0.8.x)
        if path not in self.preloaded:
            self.preload(path)  # Non-fatal if it fails

        # Set wallpaper: format is "monitor,path"
        wallpaper_arg = f"{self.monitor},{path}"
        logger.info(f"Setting wallpaper: {path.name}")

        success = self._run_command(['hyprctl', 'hyprpaper', 'wallpaper', wallpaper_arg])

        if success:
            self.current_wallpaper = path
            logger.info(f"Wallpaper changed to: {path.name}")
        else:
            logger.error(f"Failed to set wallpaper: {path.name}")

        return success

    def unload(self, path: Path) -> bool:
        """
        Unload wallpaper from memory.

        Args:
            path: Path to wallpaper file

        Returns:
            True if successful, False otherwise
        """
        if path not in self.preloaded:
            return True

        logger.debug(f"Unloading wallpaper: {path.name}")
        success = self._run_command(['hyprctl', 'hyprpaper', 'unload', str(path)])

        if success:
            self.preloaded.discard(path)

        return success

    def preload_all(self, paths: list[Path]) -> bool:
        """
        Preload multiple wallpapers.

        Args:
            paths: List of wallpaper paths

        Returns:
            True if all successful, False if any failed
        """
        logger.info(f"Preloading {len(paths)} wallpapers...")
        all_success = True

        for path in paths:
            if not self.preload(path):
                all_success = False

        return all_success
