"""Main window for Switchback GUI."""

import logging
import yaml
import subprocess
from datetime import datetime
from pathlib import Path
from gi.repository import Gtk, GLib, GObject
from switchback.config import Config, get_default_config_path
from switchback.sun_calculator import SunCalculator
from switchback.time_period import get_current_period, TimePeriod
from switchback.wallpaper_manager import WallpaperManager
from switchback.gui.widgets import WallpaperChooser, ColorButton

logger = logging.getLogger(__name__)


class SwitchbackWindow(Gtk.ApplicationWindow):
    """Main application window with status and configuration tabs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Window properties
        self.set_title("Switchback Configuration")
        self.set_default_size(900, 650)

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

        generated_page = self.create_generated_page()
        stack.add_titled(generated_page, "generated", "Generated")

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

        # Use a horizontal box to display wallpaper choosers side by side
        wallpaper_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        wallpaper_hbox.set_margin_start(12)
        wallpaper_hbox.set_homogeneous(True)

        # Night wallpaper
        night_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        night_label = Gtk.Label(label="Night 🌙")
        night_label.set_xalign(0)
        night_box.append(night_label)
        self.night_chooser = WallpaperChooser(
            self.config.wallpapers.get('night') if self.config.wallpapers else None,
            on_change_callback=lambda path: self.on_wallpaper_changed_and_check('night', path)
        )
        night_box.append(self.night_chooser)
        wallpaper_hbox.append(night_box)

        # Morning wallpaper
        morning_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        morning_label = Gtk.Label(label="Morning 🌅")
        morning_label.set_xalign(0)
        morning_box.append(morning_label)
        self.morning_chooser = WallpaperChooser(
            self.config.wallpapers.get('morning') if self.config.wallpapers else None,
            on_change_callback=lambda path: self.on_wallpaper_changed_and_check('morning', path)
        )
        morning_box.append(self.morning_chooser)
        wallpaper_hbox.append(morning_box)

        # Afternoon wallpaper
        afternoon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        afternoon_label = Gtk.Label(label="Afternoon ☀️")
        afternoon_label.set_xalign(0)
        afternoon_box.append(afternoon_label)
        self.afternoon_chooser = WallpaperChooser(
            self.config.wallpapers.get('afternoon') if self.config.wallpapers else None,
            on_change_callback=lambda path: self.on_wallpaper_changed_and_check('afternoon', path)
        )
        afternoon_box.append(self.afternoon_chooser)
        wallpaper_hbox.append(afternoon_box)

        wallpaper_box.append(wallpaper_hbox)
        vbox.append(wallpaper_box)

        # Unsaved changes indicator
        self.unsaved_label = Gtk.Label()
        self.unsaved_label.set_markup("<span color='#f39c12'>⚠ Unsaved changes</span>")
        self.unsaved_label.set_visible(False)
        self.unsaved_label.set_halign(Gtk.Align.START)
        self.unsaved_label.set_margin_top(12)
        vbox.append(self.unsaved_label)

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

        # Connect change handlers for location fields
        self.lat_entry.connect("changed", lambda w: self.check_for_changes())
        self.lon_entry.connect("changed", lambda w: self.check_for_changes())
        self.tz_entry.connect("changed", lambda w: self.check_for_changes())

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

        # Unsaved changes indicator (shared with config page)
        if hasattr(self, 'unsaved_label'):
            unsaved_indicator = Gtk.Label()
            unsaved_indicator.set_markup("<span color='#f39c12'>⚠ Unsaved changes</span>")
            unsaved_indicator.set_visible(False)
            unsaved_indicator.set_halign(Gtk.Align.START)
            unsaved_indicator.set_margin_top(12)
            # Bind visibility to the config page indicator
            self.unsaved_label.bind_property(
                "visible",
                unsaved_indicator,
                "visible",
                GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL
            )
            vbox.append(unsaved_indicator)

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

        # Connect change handlers for transitions settings
        self.transitions_switch.connect("state-set", lambda w, s: self.check_for_changes())
        self.granularity_scale.connect("value-changed", lambda w: self.check_for_changes())
        self.cache_switch.connect("state-set", lambda w, s: self.check_for_changes())

        scrolled.set_child(vbox)
        return scrolled

    def create_generated_page(self):
        """Create the generated wallpapers configuration page."""
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

        # Mode selector
        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mode_title = Gtk.Label(label="<b>Wallpaper Source</b>")
        mode_title.set_use_markup(True)
        mode_title.set_xalign(0)
        mode_box.append(mode_title)

        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        mode_row.set_margin_start(12)

        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.append("wallpaper", "Use Wallpaper Images (from Configuration tab)")
        self.mode_combo.append("generated", "Generate from Logo + Colors (configured below)")
        self.mode_combo.set_active_id(self.config.mode)
        self.mode_combo.connect("changed", lambda w: self.check_for_changes())

        mode_row.append(self.mode_combo)
        mode_box.append(mode_row)

        # Mode description
        mode_desc = Gtk.Label(
            label="• Use Wallpaper Images: Display image files you selected in the Configuration tab\n"
                  "• Generate from Logo + Colors: Create wallpapers by overlaying your logo on solid color backgrounds"
        )
        mode_desc.set_xalign(0)
        mode_desc.set_margin_start(12)
        mode_desc.set_wrap(True)
        mode_desc.add_css_class("dim-label")
        mode_box.append(mode_desc)

        vbox.append(mode_box)

        # Logo section
        logo_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        logo_title = Gtk.Label(label="<b>Logo</b>")
        logo_title.set_use_markup(True)
        logo_title.set_xalign(0)
        logo_box.append(logo_title)

        # Logo file chooser (just path display and button, no preview)
        initial_logo = None
        if self.config.mode == "generated" and self.config.generated:
            initial_logo = self.config.generated.logo

        chooser_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chooser_box.set_margin_start(12)

        # Path display
        self.logo_path_label = Gtk.Label(label=str(initial_logo) if initial_logo else "No logo selected")
        self.logo_path_label.set_ellipsize(3)  # Ellipsize at end
        self.logo_path_label.set_max_width_chars(40)
        self.logo_path_label.set_xalign(0)
        self.logo_path_label.set_hexpand(True)
        chooser_box.append(self.logo_path_label)

        # Choose button
        choose_button = Gtk.Button(label="Choose...")
        choose_button.connect("clicked", self.on_logo_choose_clicked)
        chooser_box.append(choose_button)

        logo_box.append(chooser_box)

        # Store logo path
        self.logo_path = initial_logo

        # Quick access to bundled logos
        preselected_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        preselected_box.set_margin_start(12)

        preselected_label = Gtk.Label(label="Quick select:")
        preselected_label.add_css_class("dim-label")
        preselected_box.append(preselected_label)

        # Arch Linux logo button
        arch_button = self._create_logo_button("Arch Linux", "archlinux.svg", self.on_arch_logo_clicked)
        preselected_box.append(arch_button)

        # Ubuntu logo button
        ubuntu_button = self._create_logo_button("Ubuntu", "ubuntu.svg", self.on_ubuntu_logo_clicked)
        preselected_box.append(ubuntu_button)

        logo_box.append(preselected_box)

        # Side-by-side preview section
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        preview_box.set_margin_start(12)

        preview_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        preview_hbox.set_homogeneous(True)

        # Original logo preview
        original_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        original_label = Gtk.Label(label="Original")
        original_label.add_css_class("dim-label")
        original_vbox.append(original_label)

        self.original_logo_preview = Gtk.Picture()
        self.original_logo_preview.set_can_shrink(True)
        self.original_logo_preview.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.original_logo_preview.set_size_request(200, 150)

        original_frame = Gtk.Frame()
        original_frame.set_child(self.original_logo_preview)
        original_vbox.append(original_frame)
        preview_hbox.append(original_vbox)

        # Colored logo preview with background
        colored_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        colored_label = Gtk.Label(label="With Current Colors")
        colored_label.add_css_class("dim-label")
        colored_vbox.append(colored_label)

        # Create a DrawingArea for the colored preview with background
        self.colored_preview_area = Gtk.DrawingArea()
        self.colored_preview_area.set_content_width(200)
        self.colored_preview_area.set_content_height(150)
        self.colored_preview_area.set_draw_func(self._draw_colored_preview)

        colored_frame = Gtk.Frame()
        colored_frame.set_child(self.colored_preview_area)
        colored_vbox.append(colored_frame)
        preview_hbox.append(colored_vbox)

        preview_box.append(preview_hbox)

        # Spinner for loading state
        self.generation_spinner = Gtk.Spinner()
        self.generation_spinner.set_size_request(24, 24)
        self.generation_status = Gtk.Label(label="")
        self.generation_status.add_css_class("dim-label")

        spinner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        spinner_box.set_halign(Gtk.Align.CENTER)
        spinner_box.set_margin_top(6)
        spinner_box.append(self.generation_spinner)
        spinner_box.append(self.generation_status)
        preview_box.append(spinner_box)

        logo_box.append(preview_box)

        # Store preview data
        self.colored_logo_pixbuf = None
        self.current_bg_color = None
        vbox.append(logo_box)

        # Background colors section
        bg_colors_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bg_colors_title = Gtk.Label(label="<b>Background Colors</b>")
        bg_colors_title.set_use_markup(True)
        bg_colors_title.set_xalign(0)
        bg_colors_box.append(bg_colors_title)

        bg_colors_grid = Gtk.Grid()
        bg_colors_grid.set_column_spacing(12)
        bg_colors_grid.set_row_spacing(6)
        bg_colors_grid.set_margin_start(12)

        # Get initial colors
        night_bg = "#1a1a2e"
        morning_bg = "#ff6b6b"
        afternoon_bg = "#4ecdc4"
        if self.config.mode == "generated" and self.config.generated:
            night_bg = self.config.generated.background_colors.get('night', night_bg)
            morning_bg = self.config.generated.background_colors.get('morning', morning_bg)
            afternoon_bg = self.config.generated.background_colors.get('afternoon', afternoon_bg)

        # Night background
        self.night_bg_color = ColorButton(night_bg, lambda c: self.on_generated_changed_and_check())
        bg_colors_grid.attach(Gtk.Label(label="Night 🌙:"), 0, 0, 1, 1)
        bg_colors_grid.attach(self.night_bg_color, 1, 0, 1, 1)

        # Morning background
        self.morning_bg_color = ColorButton(morning_bg, lambda c: self.on_generated_changed_and_check())
        bg_colors_grid.attach(Gtk.Label(label="Morning 🌅:"), 0, 1, 1, 1)
        bg_colors_grid.attach(self.morning_bg_color, 1, 1, 1, 1)

        # Afternoon background
        self.afternoon_bg_color = ColorButton(afternoon_bg, lambda c: self.on_generated_changed_and_check())
        bg_colors_grid.attach(Gtk.Label(label="Afternoon ☀️:"), 0, 2, 1, 1)
        bg_colors_grid.attach(self.afternoon_bg_color, 1, 2, 1, 1)

        bg_colors_box.append(bg_colors_grid)
        vbox.append(bg_colors_box)

        # Logo colors section
        logo_colors_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        logo_colors_title = Gtk.Label(label="<b>Logo Colors</b>")
        logo_colors_title.set_use_markup(True)
        logo_colors_title.set_xalign(0)
        logo_colors_box.append(logo_colors_title)

        logo_colors_grid = Gtk.Grid()
        logo_colors_grid.set_column_spacing(12)
        logo_colors_grid.set_row_spacing(6)
        logo_colors_grid.set_margin_start(12)

        # Get initial logo colors
        night_logo = "#eeeeee"
        morning_logo = "#ffe66d"
        afternoon_logo = "#ffffff"
        if self.config.mode == "generated" and self.config.generated:
            night_logo = self.config.generated.logo_colors.get('night', night_logo)
            morning_logo = self.config.generated.logo_colors.get('morning', morning_logo)
            afternoon_logo = self.config.generated.logo_colors.get('afternoon', afternoon_logo)

        # Night logo
        self.night_logo_color = ColorButton(night_logo, lambda c: self.on_generated_changed_and_check())
        logo_colors_grid.attach(Gtk.Label(label="Night 🌙:"), 0, 0, 1, 1)
        logo_colors_grid.attach(self.night_logo_color, 1, 0, 1, 1)

        # Morning logo
        self.morning_logo_color = ColorButton(morning_logo, lambda c: self.on_generated_changed_and_check())
        logo_colors_grid.attach(Gtk.Label(label="Morning 🌅:"), 0, 1, 1, 1)
        logo_colors_grid.attach(self.morning_logo_color, 1, 1, 1, 1)

        # Afternoon logo
        self.afternoon_logo_color = ColorButton(afternoon_logo, lambda c: self.on_generated_changed_and_check())
        logo_colors_grid.attach(Gtk.Label(label="Afternoon ☀️:"), 0, 2, 1, 1)
        logo_colors_grid.attach(self.afternoon_logo_color, 1, 2, 1, 1)

        logo_colors_box.append(logo_colors_grid)
        vbox.append(logo_colors_box)

        # Unsaved changes indicator
        if hasattr(self, 'unsaved_label'):
            unsaved_indicator = Gtk.Label()
            unsaved_indicator.set_markup("<span color='#f39c12'>⚠ Unsaved changes</span>")
            unsaved_indicator.set_visible(False)
            unsaved_indicator.set_halign(Gtk.Align.START)
            unsaved_indicator.set_margin_top(12)
            # Bind visibility to the config page indicator
            self.unsaved_label.bind_property(
                "visible",
                unsaved_indicator,
                "visible",
                GObject.BindingFlags.SYNC_CREATE | GObject.BindingFlags.BIDIRECTIONAL
            )
            vbox.append(unsaved_indicator)

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

        # Update logo previews if we loaded an initial logo from config
        if self.logo_path:
            self._update_logo_previews()

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

            # Get mode
            mode = self.mode_combo.get_active_id()

            # Get transition settings
            transitions_enabled = self.transitions_switch.get_active()
            transitions_granularity = int(self.granularity_scale.get_value())
            transitions_cache_blends = self.cache_switch.get_active()

            # Build config dict based on mode
            config_data = {
                'location': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'timezone': timezone,
                },
                'mode': mode,
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

            if mode == "wallpaper":
                # Validate wallpaper paths
                night_path = self.night_chooser.get_path()
                morning_path = self.morning_chooser.get_path()
                afternoon_path = self.afternoon_chooser.get_path()

                if not all([night_path, morning_path, afternoon_path]):
                    self.show_error_dialog(
                        "Missing Wallpapers",
                        "Please select wallpapers for all three time periods"
                    )
                    return

                config_data['wallpapers'] = {
                    'night': str(night_path),
                    'morning': str(morning_path),
                    'afternoon': str(afternoon_path),
                }

            elif mode == "generated":
                # Validate logo path
                if not self.logo_path:
                    self.show_error_dialog(
                        "Missing Logo",
                        "Please select a logo image for generated wallpapers"
                    )
                    return

                # Get colors
                config_data['generated'] = {
                    'logo': str(self.logo_path),
                    'background_colors': {
                        'night': self.night_bg_color.get_color(),
                        'morning': self.morning_bg_color.get_color(),
                        'afternoon': self.afternoon_bg_color.get_color(),
                    },
                    'logo_colors': {
                        'night': self.night_logo_color.get_color(),
                        'morning': self.morning_logo_color.get_color(),
                        'afternoon': self.afternoon_logo_color.get_color(),
                    },
                    'logo_scale': 0.3,
                    'logo_position': 'center',
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

            # Clear unsaved changes indicator
            self.unsaved_label.set_visible(False)

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

        # Revert mode
        self.mode_combo.set_active_id(self.config.mode)

        # Revert wallpaper paths if in wallpaper mode
        if self.config.mode == "wallpaper" and self.config.wallpapers:
            self.night_chooser.set_path(self.config.wallpapers.get('night'))
            self.morning_chooser.set_path(self.config.wallpapers.get('morning'))
            self.afternoon_chooser.set_path(self.config.wallpapers.get('afternoon'))

        # Revert generated settings if in generated mode
        if self.config.mode == "generated" and self.config.generated:
            self.logo_path = self.config.generated.logo
            self.logo_path_label.set_text(str(self.config.generated.logo))
            self.night_bg_color.set_color(self.config.generated.background_colors['night'])
            self.morning_bg_color.set_color(self.config.generated.background_colors['morning'])
            self.afternoon_bg_color.set_color(self.config.generated.background_colors['afternoon'])
            self.night_logo_color.set_color(self.config.generated.logo_colors['night'])
            self.morning_logo_color.set_color(self.config.generated.logo_colors['morning'])
            self.afternoon_logo_color.set_color(self.config.generated.logo_colors['afternoon'])

        # Revert transition settings
        self.transitions_switch.set_active(self.config.transitions_enabled)
        self.granularity_scale.set_value(self.config.transitions_granularity)
        self.cache_switch.set_active(self.config.transitions_cache_blends)

        # Check for changes (should hide indicator since we reverted)
        self.check_for_changes()

    def check_for_changes(self):
        """Check if GUI values differ from saved config and show/hide indicator."""
        if not self.config:
            return

        has_changes = False

        # Check location fields
        try:
            if float(self.lat_entry.get_text()) != self.config.latitude:
                has_changes = True
        except ValueError:
            pass

        try:
            if float(self.lon_entry.get_text()) != self.config.longitude:
                has_changes = True
        except ValueError:
            pass

        if self.tz_entry.get_text().strip() != self.config.timezone:
            has_changes = True

        # Check mode
        if hasattr(self, 'mode_combo'):
            if self.mode_combo.get_active_id() != self.config.mode:
                has_changes = True

        # Check wallpaper paths (only if in wallpaper mode)
        if self.config.mode == "wallpaper" and self.config.wallpapers:
            night_path = self.night_chooser.get_path()
            morning_path = self.morning_chooser.get_path()
            afternoon_path = self.afternoon_chooser.get_path()

            if night_path != self.config.wallpapers.get('night'):
                has_changes = True
            if morning_path != self.config.wallpapers.get('morning'):
                has_changes = True
            if afternoon_path != self.config.wallpapers.get('afternoon'):
                has_changes = True

        # Check generated settings (only if in generated mode)
        if self.config.mode == "generated" and hasattr(self, 'logo_path'):
            if self.config.generated:
                # Check logo
                if self.logo_path != self.config.generated.logo:
                    has_changes = True

                # Check background colors
                if self.night_bg_color.get_color() != self.config.generated.background_colors['night']:
                    has_changes = True
                if self.morning_bg_color.get_color() != self.config.generated.background_colors['morning']:
                    has_changes = True
                if self.afternoon_bg_color.get_color() != self.config.generated.background_colors['afternoon']:
                    has_changes = True

                # Check logo colors
                if self.night_logo_color.get_color() != self.config.generated.logo_colors['night']:
                    has_changes = True
                if self.morning_logo_color.get_color() != self.config.generated.logo_colors['morning']:
                    has_changes = True
                if self.afternoon_logo_color.get_color() != self.config.generated.logo_colors['afternoon']:
                    has_changes = True
            else:
                # Config is generated mode but has no generated config yet - any value is a change
                has_changes = True

        # Check transition settings if available
        if hasattr(self, 'transitions_switch'):
            if self.transitions_switch.get_active() != self.config.transitions_enabled:
                has_changes = True
            if int(self.granularity_scale.get_value()) != self.config.transitions_granularity:
                has_changes = True
            if self.cache_switch.get_active() != self.config.transitions_cache_blends:
                has_changes = True

        # Show/hide indicator
        self.unsaved_label.set_visible(has_changes)

    def on_wallpaper_changed_and_check(self, period, path):
        """Handle wallpaper change: apply if current period, then check for changes."""
        self.on_wallpaper_changed(period, path)
        self.check_for_changes()

    def _create_logo_button(self, label, logo_filename, callback):
        """Create a button with an icon and label for quick logo selection."""
        from pathlib import Path
        from gi.repository import GdkPixbuf
        import os

        button = Gtk.Button()
        button.connect("clicked", callback)

        # Create box for icon + label
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Try to load and display the logo icon
        possible_paths = [
            # Development: running from source
            Path(__file__).parent.parent / "logos" / logo_filename,
            # Installed via pip
            Path(os.__file__).parent / "switchback" / "logos" / logo_filename,
            # Installed system-wide (Arch package)
            Path("/usr/share/switchback/logos") / logo_filename,
            Path("/usr/local/share/switchback/logos") / logo_filename,
        ]

        icon_loaded = False
        for path in possible_paths:
            if path.exists():
                try:
                    # Load SVG/image at small size for button icon
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        str(path),
                        width=24,
                        height=24,
                        preserve_aspect_ratio=True
                    )
                    image = Gtk.Image.new_from_pixbuf(pixbuf)
                    box.append(image)
                    icon_loaded = True
                    break
                except Exception:
                    pass  # Couldn't load icon, just show text

        # Add label
        label_widget = Gtk.Label(label=label)
        box.append(label_widget)

        button.set_child(box)
        return button

    def _find_bundled_logo(self, logo_filename):
        """Find a bundled logo in common locations."""
        from pathlib import Path
        import os

        possible_paths = [
            # Development: running from source
            Path(__file__).parent.parent / "logos" / logo_filename,
            # Installed via pip
            Path(os.__file__).parent / "switchback" / "logos" / logo_filename,
            # Installed system-wide (Arch package)
            Path("/usr/share/switchback/logos") / logo_filename,
            Path("/usr/local/share/switchback/logos") / logo_filename,
        ]

        for path in possible_paths:
            if path.exists():
                return path
        return None

    def on_logo_choose_clicked(self, button):
        """Open file chooser for logo."""
        from gi.repository import Gio

        dialog = Gtk.FileChooserDialog(
            title="Choose Logo",
            action=Gtk.FileChooserAction.OPEN,
        )

        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)

        # Add image filter
        filter_images = Gtk.FileFilter()
        filter_images.set_name("Images")
        filter_images.add_mime_type("image/*")
        filter_images.add_pattern("*.png")
        filter_images.add_pattern("*.jpg")
        filter_images.add_pattern("*.jpeg")
        filter_images.add_pattern("*.svg")
        filter_images.add_pattern("*.svgz")
        dialog.add_filter(filter_images)

        # Set initial folder if we have a path
        if self.logo_path and self.logo_path.exists():
            file = Gio.File.new_for_path(str(self.logo_path.parent))
            dialog.set_current_folder(file)

        dialog.connect("response", self.on_logo_dialog_response)
        dialog.show()

    def on_logo_dialog_response(self, dialog, response):
        """Handle logo file chooser dialog response."""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                from pathlib import Path
                self.logo_path = Path(file.get_path())
                self.logo_path_label.set_text(str(self.logo_path))
                self.on_generated_changed_and_check()

        dialog.destroy()

    def _draw_colored_preview(self, area, cr, width, height):
        """Draw the colored logo preview with background color."""
        import cairo

        # Fill with background color
        if self.current_bg_color:
            # Parse hex color
            color = self.current_bg_color.lstrip('#')
            r = int(color[0:2], 16) / 255.0
            g = int(color[2:4], 16) / 255.0
            b = int(color[4:6], 16) / 255.0
            cr.set_source_rgb(r, g, b)
        else:
            # Default gray background
            cr.set_source_rgb(0.9, 0.9, 0.9)

        cr.rectangle(0, 0, width, height)
        cr.fill()

        # Draw the colored logo if available
        if self.colored_logo_pixbuf:
            from gi.repository import Gdk
            pixbuf = self.colored_logo_pixbuf

            # Center the image
            img_width = pixbuf.get_width()
            img_height = pixbuf.get_height()

            x = (width - img_width) / 2
            y = (height - img_height) / 2

            Gdk.cairo_set_source_pixbuf(cr, pixbuf, x, y)
            cr.paint()

    def on_arch_logo_clicked(self, button):
        """Load the bundled Arch Linux logo."""
        logo_path = self._find_bundled_logo("archlinux.svg")

        if logo_path:
            self.logo_path = logo_path
            self.logo_path_label.set_text(str(logo_path))
            self.on_generated_changed_and_check()
        else:
            self.show_error_dialog(
                "Logo Not Found",
                "Could not find the bundled Arch Linux logo.\n"
                "Please use the file chooser to select your own logo."
            )

    def on_ubuntu_logo_clicked(self, button):
        """Load the bundled Ubuntu logo."""
        logo_path = self._find_bundled_logo("ubuntu.svg")

        if logo_path:
            self.logo_path = logo_path
            self.logo_path_label.set_text(str(logo_path))
            self.on_generated_changed_and_check()
        else:
            self.show_error_dialog(
                "Logo Not Found",
                "Could not find the bundled Ubuntu logo.\n"
                "Please use the file chooser to select your own logo."
            )

    def on_generated_changed_and_check(self):
        """Handle generated wallpaper setting change: apply if current period, then check for changes."""
        self.on_generated_changed()
        self.check_for_changes()

    def _update_logo_previews(self):
        """Update the logo preview images (original and colored)."""
        from gi.repository import GdkPixbuf
        from pathlib import Path
        import tempfile

        # Get logo path
        if not self.logo_path or not self.logo_path.exists():
            # Clear previews
            self.original_logo_preview.set_pixbuf(None)
            self.colored_logo_pixbuf = None
            self.colored_preview_area.queue_draw()
            return

        try:
            # Show original logo
            original_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(self.logo_path),
                width=180,
                height=130,
                preserve_aspect_ratio=True
            )
            self.original_logo_preview.set_pixbuf(original_pixbuf)

            # Generate colored preview
            if not self.sun_calc:
                return

            from switchback.generator import WallpaperGenerator
            from switchback.config import GeneratedConfig
            from switchback.time_period import get_current_period
            from datetime import datetime

            # Get current period
            now = datetime.now(self.sun_calc.tz)
            sun_times = self.sun_calc.get_sun_times(now)
            current_period = get_current_period(sun_times, now)

            # Get colors based on transition settings
            if self.config.transitions_enabled:
                # Calculate blended colors
                from switchback.transition_tracker import TransitionTracker
                from switchback.blender import ImageBlender
                from switchback.generator import blend_colors

                tracker = TransitionTracker(self.sun_calc)
                blender = ImageBlender()

                # Get period boundaries and blend ratio
                period_start, period_end = tracker.get_period_boundaries(now, current_period)
                blend_ratio = blender.calculate_blend_ratio(now, period_start, period_end)

                # Get the periods to transition between
                from_period, to_period, blend_ratio = tracker.get_transition_wallpapers(current_period, blend_ratio)

                # Get colors
                bg_colors = {
                    'night': self.night_bg_color.get_color(),
                    'morning': self.morning_bg_color.get_color(),
                    'afternoon': self.afternoon_bg_color.get_color(),
                }
                logo_colors = {
                    'night': self.night_logo_color.get_color(),
                    'morning': self.morning_logo_color.get_color(),
                    'afternoon': self.afternoon_logo_color.get_color(),
                }

                # Blend the colors
                from_bg = bg_colors[from_period]
                to_bg = bg_colors[to_period]
                bg_color = blend_colors(from_bg, to_bg, blend_ratio)

                from_logo = logo_colors[from_period]
                to_logo = logo_colors[to_period]
                logo_color = blend_colors(from_logo, to_logo, blend_ratio)
            else:
                # No transitions - use exact color for current period
                bg_color = getattr(self, f'{current_period.value}_bg_color').get_color()
                logo_color = getattr(self, f'{current_period.value}_logo_color').get_color()

            # Store background color for drawing
            self.current_bg_color = bg_color

            # Create temporary config
            gen_config = GeneratedConfig(
                logo=self.logo_path,
                background_colors={
                    'night': self.night_bg_color.get_color(),
                    'morning': self.morning_bg_color.get_color(),
                    'afternoon': self.afternoon_bg_color.get_color(),
                },
                logo_colors={
                    'night': self.night_logo_color.get_color(),
                    'morning': self.morning_logo_color.get_color(),
                    'afternoon': self.afternoon_logo_color.get_color(),
                },
                logo_scale=0.3,
                logo_position='center'
            )

            # Generate just the colored logo (not full wallpaper)
            generator = WallpaperGenerator(gen_config)
            colored_logo = generator._apply_color_to_logo(generator.logo_image, logo_color)

            # Save to temp file for preview
            temp_file = Path(tempfile.gettempdir()) / "switchback_logo_preview.png"
            colored_logo.save(temp_file, "PNG")

            # Load and store pixbuf
            self.colored_logo_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(temp_file),
                width=180,
                height=130,
                preserve_aspect_ratio=True
            )

            # Trigger redraw of colored preview area
            self.colored_preview_area.queue_draw()

        except Exception as e:
            logger.error(f"Failed to update logo previews: {e}")

    def on_generated_changed(self):
        """Called when a generated wallpaper setting is changed in the GUI."""
        if not self.sun_calc:
            return

        # Get logo path
        if not self.logo_path or not self.logo_path.exists():
            return  # Can't generate without a logo

        # Show loading state
        self.generation_spinner.start()
        self.generation_status.set_text("Generating...")

        # Update previews immediately
        self._update_logo_previews()

        # Get colors
        bg_colors = {
            'night': self.night_bg_color.get_color(),
            'morning': self.morning_bg_color.get_color(),
            'afternoon': self.afternoon_bg_color.get_color(),
        }
        logo_colors = {
            'night': self.night_logo_color.get_color(),
            'morning': self.morning_logo_color.get_color(),
            'afternoon': self.afternoon_logo_color.get_color(),
        }

        # Get current period
        now = datetime.now(self.sun_calc.tz)
        sun_times = self.sun_calc.get_sun_times(now)
        current_period = get_current_period(sun_times, now)

        try:
            # Generate wallpaper for current period
            from switchback.generator import WallpaperGenerator
            from switchback.config import GeneratedConfig
            from pathlib import Path
            import tempfile

            # Create temporary config
            gen_config = GeneratedConfig(
                logo=self.logo_path,
                background_colors=bg_colors,
                logo_colors=logo_colors,
                logo_scale=0.3,
                logo_position='center'
            )

            # Generate wallpaper based on transition settings
            generator = WallpaperGenerator(gen_config)
            # TODO: Get actual screen size

            if self.config.transitions_enabled:
                # Use gradual transitions - calculate blended colors
                from switchback.transition_tracker import TransitionTracker
                from switchback.blender import ImageBlender
                from switchback.generator import blend_colors

                tracker = TransitionTracker(self.sun_calc)
                blender = ImageBlender()

                # Get period boundaries and blend ratio
                period_start, period_end = tracker.get_period_boundaries(now, current_period)
                blend_ratio = blender.calculate_blend_ratio(now, period_start, period_end)

                # Get the periods to transition between
                from_period, to_period, blend_ratio = tracker.get_transition_wallpapers(current_period, blend_ratio)

                # Blend the colors
                from_bg = bg_colors[from_period]
                to_bg = bg_colors[to_period]
                blended_bg = blend_colors(from_bg, to_bg, blend_ratio)

                from_logo = logo_colors[from_period]
                to_logo = logo_colors[to_period]
                blended_logo = blend_colors(from_logo, to_logo, blend_ratio)

                # Generate with blended colors
                wallpaper_image = generator.generate_wallpaper_with_colors(
                    blended_bg,
                    blended_logo,
                    screen_size=(1920, 1080)
                )
            else:
                # No transitions - use exact color for current period
                wallpaper_image = generator.generate_wallpaper(current_period.value, screen_size=(1920, 1080))

            # Save to temp file
            temp_file = Path(tempfile.gettempdir()) / "switchback_preview.jpg"
            wallpaper_image.save(temp_file, "JPEG", quality=98, subsampling=0)

            # Apply wallpaper
            wallpaper_mgr = WallpaperManager(self.config.monitor)

            if not wallpaper_mgr.wait_for_hyprpaper(max_wait=5):
                self.generation_spinner.stop()
                self.generation_status.set_text("")
                self.show_error_dialog(
                    "Hyprpaper Not Running",
                    "Hyprpaper must be running to set wallpapers."
                )
                return

            if not wallpaper_mgr.set_wallpaper(temp_file):
                self.show_error_dialog(
                    "Failed to Apply Wallpaper",
                    f"Could not set generated wallpaper"
                )

            # Hide loading state
            self.generation_spinner.stop()
            self.generation_status.set_text("")

        except Exception as e:
            # Hide loading state on error
            self.generation_spinner.stop()
            self.generation_status.set_text("")

            self.show_error_dialog(
                "Error Generating Wallpaper",
                f"An error occurred:\n{str(e)}"
            )

    def on_wallpaper_changed(self, period, path):
        """Called when a wallpaper is changed in the GUI."""
        if not self.sun_calc:
            return

        # Get current period
        now = datetime.now(self.sun_calc.tz)
        sun_times = self.sun_calc.get_sun_times(now)
        current_period = get_current_period(sun_times, now)

        # If the changed wallpaper is for the current period, auto-apply
        if current_period.value == period:
            try:
                # Apply the wallpaper directly using WallpaperManager
                wallpaper_mgr = WallpaperManager(self.config.monitor)

                if not wallpaper_mgr.wait_for_hyprpaper(max_wait=5):
                    self.show_error_dialog(
                        "Hyprpaper Not Running",
                        "Hyprpaper must be running to set wallpapers."
                    )
                    return

                if not wallpaper_mgr.set_wallpaper(path):
                    self.show_error_dialog(
                        "Failed to Apply Wallpaper",
                        f"Could not set wallpaper to: {path.name}"
                    )

            except Exception as e:
                self.show_error_dialog(
                    "Error Applying Wallpaper",
                    f"An error occurred:\n{str(e)}"
                )

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
