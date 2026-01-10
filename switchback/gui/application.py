"""GTK4 Application class for Switchback GUI."""

import sys
from gi.repository import Gtk
from switchback.gui.main_window import SwitchbackWindow


class SwitchbackApp(Gtk.Application):
    """Main GTK4 application for Switchback."""

    def __init__(self):
        super().__init__(
            application_id='com.github.switchback',
            flags=0
        )

    def do_activate(self):
        """Create or present the main window."""
        # Get active window if it exists
        win = self.props.active_window
        if not win:
            # Create new window
            win = SwitchbackWindow(application=self)
        # Present window to user
        win.present()


def main():
    """Entry point for switchback-gui command."""
    try:
        app = SwitchbackApp()
        return app.run(None)
    except Exception as e:
        print(f"Error launching Switchback GUI: {e}", file=sys.stderr)
        print("\nMake sure python-gobject is installed:", file=sys.stderr)
        print("  pacman -S python-gobject", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
