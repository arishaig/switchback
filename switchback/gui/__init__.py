"""Optional GTK4 GUI for Switchback configuration."""

try:
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk
    GUI_AVAILABLE = True
except (ImportError, ValueError):
    GUI_AVAILABLE = False

__all__ = ["GUI_AVAILABLE"]
