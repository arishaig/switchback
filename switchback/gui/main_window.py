"""Main window for Switchback GUI."""

import yaml
from datetime import datetime
from pathlib import Path
from gi.repository import Gtk, GLib
from switchback.config import Config, get_default_config_path
from switchback.sun_calculator import SunCalculator
from switchback.time_period import get_current_period, TimePeriod
from switchback.gui.widgets import WallpaperChooser


class SwitchbackWindow(Gtk.ApplicationWindow):
    """Main application window with status and configuration tabs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Window properties
        self.set_title("Switchback Configuration")
        self.set_default_size(700, 550)

        # Load config
        self.config_path = get_default_config_path()
        self.config = None
        self.sun_calc = None
        self.original_config_data = None

        try:
            self.config = Config.load(self.config_path)
            self.sun_calc = SunCalculator(
                self.config.latitude,
                self.config.longitude,
                self.config.timezone
            )
            # Store original config data for revert
            with open(self.config_path) as f:
                self.original_config_data = f.read()

        except FileNotFoundError:
            self.show_error_dialog(
                "Configuration file not found",
                f"Please create a configuration file at:\n{self.config_path}\n\n"
                f"You can use 'switchback init' to create a template."
            )
        except Exception as e:
            self.show_error_dialog("Error loading configuration", str(e))

        # Build UI
        self.build_ui()

        # Start periodic updates if config loaded successfully
        if self.config:
            GLib.timeout_add_seconds(1, self.update_status)

    def show_error_dialog(self, title, message):
        """Show an error dialog."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()

    def build_ui(self):
        """Build the main UI with tabs."""
        # Create stack for tabs
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Create stack switcher
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher.set_stack(stack)
        stack_switcher.set_halign(Gtk.Align.CENTER)

        # Add pages
        status_page = self.create_status_page()
        stack.add_titled(status_page, "status", "Status")

        config_page = self.create_config_page()
        stack.add_titled(config_page, "config", "Configuration")

        transitions_page = self.create_transitions_page()
        stack.add_titled(transitions_page, "transitions", "Transitions")

        # Create header bar with stack switcher
        header = Gtk.HeaderBar()
        header.set_title_widget(stack_switcher)
        self.set_titlebar(header)

        # Set stack as window content
        self.set_child(stack)

    def create_status_page(self):
        """Create the status display page."""
        # Main box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)
        vbox.set_margin_top(24)
        vbox.set_margin_bottom(24)

        if not self.config:
            label = Gtk.Label(label="Configuration not loaded")
            vbox.append(label)
            return vbox

        # Current period section
        period_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        period_title = Gtk.Label(label="<b>Current Status</b>")
        period_title.set_use_markup(True)
        period_title.set_xalign(0)
        period_box.append(period_title)

        self.period_label = Gtk.Label(label="")
        self.period_label.set_xalign(0)
        self.period_label.set_margin_start(12)
        period_box.append(self.period_label)

        vbox.append(period_box)

        # Sun times section
        sun_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sun_title = Gtk.Label(label="<b>Sun Times Today</b>")
        sun_title.set_use_markup(True)
        sun_title.set_xalign(0)
        sun_box.append(sun_title)

        times_grid = Gtk.Grid()
        times_grid.set_column_spacing(12)
        times_grid.set_row_spacing(6)
        times_grid.set_margin_start(12)

        # Labels
        self.sunrise_label = Gtk.Label(label="")
        self.sunrise_label.set_xalign(0)
        self.noon_label = Gtk.Label(label="")
        self.noon_label.set_xalign(0)
        self.sunset_label = Gtk.Label(label="")
        self.sunset_label.set_xalign(0)

        times_grid.attach(Gtk.Label(label="Sunrise:"), 0, 0, 1, 1)
        times_grid.attach(self.sunrise_label, 1, 0, 1, 1)
        times_grid.attach(Gtk.Label(label="Solar Noon:"), 0, 1, 1, 1)
        times_grid.attach(self.noon_label, 1, 1, 1, 1)
        times_grid.attach(Gtk.Label(label="Sunset:"), 0, 2, 1, 1)
        times_grid.attach(self.sunset_label, 1, 2, 1, 1)

        sun_box.append(times_grid)
        vbox.append(sun_box)

        # Next transition section
        next_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        next_title = Gtk.Label(label="<b>Next Transition</b>")
        next_title.set_use_markup(True)
        next_title.set_xalign(0)
        next_box.append(next_title)

        self.next_label = Gtk.Label(label="")
        self.next_label.set_xalign(0)
        self.next_label.set_margin_start(12)
        next_box.append(self.next_label)

        vbox.append(next_box)

        return vbox

    def create_config_page(self):
        """Create the configuration editing page."""
        # Scrolled window for config content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Main box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)
        vbox.set_margin_top(24)
        vbox.set_margin_bottom(24)

        if not self.config:
            label = Gtk.Label(label="Configuration not loaded")
            vbox.append(label)
            scrolled.set_child(vbox)
            return scrolled

        # Location section
        location_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        location_title = Gtk.Label(label="<b>Location</b>")
        location_title.set_use_markup(True)
        location_title.set_xalign(0)
        location_box.append(location_title)

        location_grid = Gtk.Grid()
        location_grid.set_column_spacing(12)
        location_grid.set_row_spacing(6)
        location_grid.set_margin_start(12)

        # Latitude
        self.lat_entry = Gtk.Entry()
        self.lat_entry.set_text(str(self.config.latitude))
        self.lat_entry.set_width_chars(15)
        location_grid.attach(Gtk.Label(label="Latitude:"), 0, 0, 1, 1)
        location_grid.attach(self.lat_entry, 1, 0, 1, 1)

        # Longitude
        self.lon_entry = Gtk.Entry()
        self.lon_entry.set_text(str(self.config.longitude))
        self.lon_entry.set_width_chars(15)
        location_grid.attach(Gtk.Label(label="Longitude:"), 0, 1, 1, 1)
        location_grid.attach(self.lon_entry, 1, 1, 1, 1)

        # Timezone
        self.tz_entry = Gtk.Entry()
        self.tz_entry.set_text(self.config.timezone)
        self.tz_entry.set_width_chars(25)
        location_grid.attach(Gtk.Label(label="Timezone:"), 0, 2, 1, 1)
        location_grid.attach(self.tz_entry, 1, 2, 1, 1)

        location_box.append(location_grid)
        vbox.append(location_box)

        # Wallpapers section
        wallpaper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        wallpaper_title = Gtk.Label(label="<b>Wallpapers</b>")
        wallpaper_title.set_use_markup(True)
        wallpaper_title.set_xalign(0)
        wallpaper_box.append(wallpaper_title)

        wallpaper_grid = Gtk.Grid()
        wallpaper_grid.set_column_spacing(12)
        wallpaper_grid.set_row_spacing(6)
        wallpaper_grid.set_margin_start(12)

        # Night wallpaper
        night_label = Gtk.Label(label="Night 🌙:")
        night_label.set_xalign(0)
        self.night_chooser = WallpaperChooser(self.config.wallpapers.get('night'))
        wallpaper_grid.attach(night_label, 0, 0, 1, 1)
        wallpaper_grid.attach(self.night_chooser, 1, 0, 1, 1)

        # Morning wallpaper
        morning_label = Gtk.Label(label="Morning 🌅:")
        morning_label.set_xalign(0)
        self.morning_chooser = WallpaperChooser(self.config.wallpapers.get('morning'))
        wallpaper_grid.attach(morning_label, 0, 1, 1, 1)
        wallpaper_grid.attach(self.morning_chooser, 1, 1, 1, 1)

        # Afternoon wallpaper
        afternoon_label = Gtk.Label(label="Afternoon ☀️:")
        afternoon_label.set_xalign(0)
        self.afternoon_chooser = WallpaperChooser(self.config.wallpapers.get('afternoon'))
        wallpaper_grid.attach(afternoon_label, 0, 2, 1, 1)
        wallpaper_grid.attach(self.afternoon_chooser, 1, 2, 1, 1)

        # Make choosers expand
        self.night_chooser.set_hexpand(True)
        self.morning_chooser.set_hexpand(True)
        self.afternoon_chooser.set_hexpand(True)

        wallpaper_box.append(wallpaper_grid)
        vbox.append(wallpaper_box)

        # Buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)

        revert_button = Gtk.Button(label="Revert")
        revert_button.connect("clicked", self.on_revert_clicked)
        button_box.append(revert_button)

        save_button = Gtk.Button(label="Save")
        save_button.add_css_class("suggested-action")
        save_button.connect("clicked", self.on_save_clicked)
        button_box.append(save_button)

        vbox.append(button_box)

        scrolled.set_child(vbox)
        return scrolled

    def create_transitions_page(self):
        """Create the transitions configuration page."""
        # Scrolled window for content
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Main box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        vbox.set_margin_start(24)
        vbox.set_margin_end(24)
        vbox.set_margin_top(24)
        vbox.set_margin_bottom(24)

        if not self.config:
            label = Gtk.Label(label="Configuration not loaded")
            vbox.append(label)
            scrolled.set_child(vbox)
            return scrolled

        # Enable/disable section
        enable_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        enable_title = Gtk.Label(label="<b>Gradual Transitions</b>")
        enable_title.set_use_markup(True)
        enable_title.set_xalign(0)
        enable_box.append(enable_title)

        enable_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        enable_row.set_margin_start(12)
        enable_label = Gtk.Label(label="Enable gradual transitions between wallpapers")
        enable_label.set_xalign(0)
        enable_label.set_hexpand(True)

        self.transitions_switch = Gtk.Switch()
        self.transitions_switch.set_active(self.config.transitions_enabled)
        self.transitions_switch.set_valign(Gtk.Align.CENTER)

        enable_row.append(enable_label)
        enable_row.append(self.transitions_switch)
        enable_box.append(enable_row)
        vbox.append(enable_box)

        # Granularity section
        granularity_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        granularity_title = Gtk.Label(label="<b>Transition Granularity</b>")
        granularity_title.set_use_markup(True)
        granularity_title.set_xalign(0)
        granularity_box.append(granularity_title)

        granularity_desc = Gtk.Label(
            label="How often to update the wallpaper blend (in seconds)"
        )
        granularity_desc.set_xalign(0)
        granularity_desc.set_margin_start(12)
        granularity_desc.add_css_class("dim-label")
        granularity_box.append(granularity_desc)

        # Scale from 300s (5 min) to 7200s (2 hours)
        self.granularity_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            300,   # min: 5 minutes
            7200,  # max: 2 hours
            300    # step: 5 minutes
        )
        self.granularity_scale.set_value(self.config.transitions_granularity)
        self.granularity_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.granularity_scale.set_margin_start(12)
        self.granularity_scale.set_margin_end(12)

        # Format value label
        self.granularity_scale.set_format_value_func(self._format_granularity)

        # Add marks
        self.granularity_scale.add_mark(300, Gtk.PositionType.BOTTOM, "5 min")
        self.granularity_scale.add_mark(1800, Gtk.PositionType.BOTTOM, "30 min")
        self.granularity_scale.add_mark(3600, Gtk.PositionType.BOTTOM, "1 hour")
        self.granularity_scale.add_mark(7200, Gtk.PositionType.BOTTOM, "2 hours")

        granularity_box.append(self.granularity_scale)
        vbox.append(granularity_box)

        # Cache settings section
        cache_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cache_title = Gtk.Label(label="<b>Cache Settings</b>")
        cache_title.set_use_markup(True)
        cache_title.set_xalign(0)
        cache_box.append(cache_title)

        # Cache enable/disable
        cache_enable_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        cache_enable_row.set_margin_start(12)
        cache_label = Gtk.Label(label="Cache blended images for better performance")
        cache_label.set_xalign(0)
        cache_label.set_hexpand(True)

        self.cache_switch = Gtk.Switch()
        self.cache_switch.set_active(self.config.transitions_cache_blends)
        self.cache_switch.set_valign(Gtk.Align.CENTER)

        cache_enable_row.append(cache_label)
        cache_enable_row.append(self.cache_switch)
        cache_box.append(cache_enable_row)

        # Cache directory display
        cache_dir_label = Gtk.Label(
            label=f"Cache directory: {self.config.transitions_cache_dir}"
        )
        cache_dir_label.set_xalign(0)
        cache_dir_label.set_margin_start(12)
        cache_dir_label.add_css_class("dim-label")
        cache_box.append(cache_dir_label)

        # Clear cache button
        clear_cache_button = Gtk.Button(label="Clear Cache")
        clear_cache_button.set_margin_start(12)
        clear_cache_button.set_halign(Gtk.Align.START)
        clear_cache_button.connect("clicked", self.on_clear_cache_clicked)
        cache_box.append(clear_cache_button)

        vbox.append(cache_box)

        scrolled.set_child(vbox)
        return scrolled

    def _format_granularity(self, scale, value):
        """Format granularity scale value."""
        minutes = int(value / 60)
        if minutes < 60:
            return f"{minutes} min"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours}h"
            else:
                return f"{hours}h {remaining_minutes}m"

    def update_status(self):
        """Update status display (called every second)."""
        if not self.config or not self.sun_calc:
            return False  # Stop updating

        try:
            now = datetime.now(self.sun_calc.tz)
            sun_times = self.sun_calc.get_sun_times(now)
            period = get_current_period(sun_times, now)

            # Update period
            emoji = self.get_period_emoji(period)
            self.period_label.set_markup(
                f"<span size='large'>{period.value.title()} {emoji}</span>"
            )

            # Update sun times
            self.sunrise_label.set_text(sun_times['sunrise'].strftime('%H:%M:%S'))
            self.noon_label.set_text(sun_times['noon'].strftime('%H:%M:%S'))
            self.sunset_label.set_text(sun_times['sunset'].strftime('%H:%M:%S'))

            # Update next transition
            next_transition = self.sun_calc.get_next_transition_time(now, period.value)
            time_until = next_transition - now
            hours = int(time_until.total_seconds() // 3600)
            minutes = int((time_until.total_seconds() % 3600) // 60)
            seconds = int(time_until.total_seconds() % 60)

            next_period = self.get_next_period(period)
            self.next_label.set_text(
                f"{next_period.title()} at {next_transition.strftime('%H:%M')} "
                f"(in {hours}h {minutes}m {seconds}s)"
            )

        except Exception as e:
            # Handle errors gracefully
            pass

        return True  # Continue updating

    def get_period_emoji(self, period):
        """Get emoji for a time period."""
        emojis = {
            TimePeriod.NIGHT: "🌙",
            TimePeriod.MORNING: "🌅",
            TimePeriod.AFTERNOON: "☀️"
        }
        return emojis.get(period, "")

    def get_next_period(self, current_period):
        """Get the next period name."""
        if current_period == TimePeriod.NIGHT:
            return "Morning"
        elif current_period == TimePeriod.MORNING:
            return "Afternoon"
        else:
            return "Night"

    def on_save_clicked(self, button):
        """Save configuration to file."""
        try:
            # Validate latitude
            try:
                latitude = float(self.lat_entry.get_text())
                if not (-90 <= latitude <= 90):
                    raise ValueError("Latitude must be between -90 and 90")
            except ValueError as e:
                self.show_error_dialog("Invalid Latitude", str(e))
                return

            # Validate longitude
            try:
                longitude = float(self.lon_entry.get_text())
                if not (-180 <= longitude <= 180):
                    raise ValueError("Longitude must be between -180 and 180")
            except ValueError as e:
                self.show_error_dialog("Invalid Longitude", str(e))
                return

            # Get timezone
            timezone = self.tz_entry.get_text().strip()
            if not timezone:
                self.show_error_dialog("Invalid Timezone", "Timezone cannot be empty")
                return

            # Get wallpaper paths
            night_path = self.night_chooser.get_path()
            morning_path = self.morning_chooser.get_path()
            afternoon_path = self.afternoon_chooser.get_path()

            if not all([night_path, morning_path, afternoon_path]):
                self.show_error_dialog(
                    "Missing Wallpapers",
                    "Please select wallpapers for all three time periods"
                )
                return

            # Get transition settings
            transitions_enabled = self.transitions_switch.get_active()
            transitions_granularity = int(self.granularity_scale.get_value())
            transitions_cache_blends = self.cache_switch.get_active()

            # Build config dict
            config_data = {
                'location': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'timezone': timezone,
                },
                'wallpapers': {
                    'night': str(night_path),
                    'morning': str(morning_path),
                    'afternoon': str(afternoon_path),
                },
                'settings': {
                    'check_interval_fallback': self.config.check_interval_fallback,
                    'preload_all': self.config.preload_all,
                    'monitor': self.config.monitor,
                    'transitions': {
                        'enabled': transitions_enabled,
                        'granularity': transitions_granularity,
                        'cache_blends': transitions_cache_blends,
                        'cache_dir': self.config.transitions_cache_dir,
                    }
                }
            }

            # Write to file
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

            # Reload config
            self.config = Config.load(self.config_path)
            self.sun_calc = SunCalculator(
                self.config.latitude,
                self.config.longitude,
                self.config.timezone
            )

            # Store new original
            with open(self.config_path) as f:
                self.original_config_data = f.read()

            # Show success dialog
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Configuration Saved"
            )
            dialog.format_secondary_text(
                "The configuration has been saved successfully.\n\n"
                "Restart the switchback daemon to apply changes:\n"
                "  systemctl --user restart switchback.service"
            )
            dialog.connect("response", lambda d, r: d.destroy())
            dialog.show()

        except Exception as e:
            self.show_error_dialog("Error Saving Configuration", str(e))

    def on_revert_clicked(self, button):
        """Revert changes to original values."""
        if not self.original_config_data or not self.config:
            return

        # Reload original values
        self.lat_entry.set_text(str(self.config.latitude))
        self.lon_entry.set_text(str(self.config.longitude))
        self.tz_entry.set_text(self.config.timezone)
        self.night_chooser.set_path(self.config.wallpapers.get('night'))
        self.morning_chooser.set_path(self.config.wallpapers.get('morning'))
        self.afternoon_chooser.set_path(self.config.wallpapers.get('afternoon'))

        # Revert transition settings
        self.transitions_switch.set_active(self.config.transitions_enabled)
        self.granularity_scale.set_value(self.config.transitions_granularity)
        self.cache_switch.set_active(self.config.transitions_cache_blends)

    def on_clear_cache_clicked(self, button):
        """Clear the blend cache."""
        from switchback.blender import BlendCache

        cache_dir = Path(self.config.transitions_cache_dir).expanduser()
        cache = BlendCache(cache_dir)

        # Clear the cache
        cache.clear_cache()

        # Show confirmation dialog
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Cache Cleared"
        )
        dialog.format_secondary_text(
            "All cached blended wallpapers have been removed.\n"
            "They will be regenerated as needed."
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show()
