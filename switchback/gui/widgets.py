"""Custom GTK4 widgets for Switchback GUI."""

from pathlib import Path
from gi.repository import Gtk, Gio, GdkPixbuf, Gdk


class WallpaperChooser(Gtk.Box):
    """File chooser button for selecting wallpaper images with preview."""

    def __init__(self, initial_path=None, on_change_callback=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.path = Path(initial_path) if initial_path else None
        self.on_change_callback = on_change_callback

        # Top row: label and button
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Label showing current path
        label_text = str(self.path) if self.path else "No file selected"
        self.label = Gtk.Label(label=label_text)
        self.label.set_ellipsize(3)  # Ellipsize at end
        self.label.set_max_width_chars(40)
        self.label.set_xalign(0)  # Align left

        # Choose button
        self.button = Gtk.Button(label="Choose...")
        self.button.connect("clicked", self.on_choose_clicked)

        # Layout top row
        top_box.append(self.label)
        top_box.append(self.button)
        self.label.set_hexpand(True)

        self.append(top_box)

        # Preview image
        self.preview = Gtk.Picture()
        self.preview.set_can_shrink(True)
        self.preview.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.preview.set_size_request(200, 150)

        # Frame around preview
        preview_frame = Gtk.Frame()
        preview_frame.set_child(self.preview)
        self.append(preview_frame)

        # Load initial preview if path exists
        self._update_preview()

    def on_choose_clicked(self, button):
        """Open file chooser dialog."""
        # Create file chooser dialog
        dialog = Gtk.FileChooserDialog(
            title="Choose Wallpaper",
            action=Gtk.FileChooserAction.OPEN,
        )

        # Add buttons
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_Open", Gtk.ResponseType.ACCEPT)

        # Add image filter
        filter_images = Gtk.FileFilter()
        filter_images.set_name("Images")
        filter_images.add_mime_type("image/*")
        filter_images.add_pattern("*.png")
        filter_images.add_pattern("*.jpg")
        filter_images.add_pattern("*.jpeg")
        filter_images.add_pattern("*.webp")
        filter_images.add_pattern("*.svg")
        filter_images.add_pattern("*.svgz")
        dialog.add_filter(filter_images)

        # Add all files filter
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        # Set initial folder if we have a path
        if self.path and self.path.exists():
            file = Gio.File.new_for_path(str(self.path.parent))
            dialog.set_current_folder(file)

        # Show dialog and handle response
        dialog.connect("response", self.on_file_dialog_response)
        dialog.show()

    def on_file_dialog_response(self, dialog, response):
        """Handle file chooser dialog response."""
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.path = Path(file.get_path())
                self.label.set_text(str(self.path))
                self._update_preview()

                # Call the change callback if provided
                if self.on_change_callback:
                    self.on_change_callback(self.path)

        dialog.destroy()

    def get_path(self):
        """Get the currently selected path."""
        return self.path

    def set_path(self, path):
        """Set the current path."""
        self.path = Path(path) if path else None
        label_text = str(self.path) if self.path else "No file selected"
        self.label.set_text(label_text)
        self._update_preview()

    def _update_preview(self):
        """Update the preview image based on current path."""
        if self.path and self.path.exists() and self.path.is_file():
            try:
                # Load image as pixbuf
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(self.path),
                    width=400,   # Max width
                    height=300,  # Max height
                    preserve_aspect_ratio=True
                )
                # Set the pixbuf to the picture widget
                self.preview.set_pixbuf(pixbuf)
            except Exception as e:
                # If loading fails, clear the preview
                self.preview.set_pixbuf(None)
        else:
            # Clear preview if no valid path
            self.preview.set_pixbuf(None)


class ColorButton(Gtk.Box):
    """Color picker button with hex color display."""

    def __init__(self, initial_color="#000000", on_change_callback=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.on_change_callback = on_change_callback

        # Parse initial color
        self._parse_color(initial_color)

        # Color button
        self.color_button = Gtk.ColorButton()
        rgba = Gdk.RGBA()
        rgba.parse(self.color)
        self.color_button.set_rgba(rgba)
        self.color_button.connect("color-set", self.on_color_set)

        # Hex entry
        self.hex_entry = Gtk.Entry()
        self.hex_entry.set_text(self.color)
        self.hex_entry.set_width_chars(8)
        self.hex_entry.set_max_length(7)
        self.hex_entry.connect("changed", self.on_hex_changed)

        self.append(self.color_button)
        self.append(self.hex_entry)

    def _parse_color(self, color):
        """Parse and validate hex color."""
        if isinstance(color, str) and color.startswith('#') and len(color) == 7:
            self.color = color.lower()
        else:
            self.color = "#000000"

    def on_color_set(self, button):
        """Called when color is selected from color picker."""
        rgba = button.get_rgba()
        # Convert RGBA to hex
        r = int(rgba.red * 255)
        g = int(rgba.green * 255)
        b = int(rgba.blue * 255)
        hex_color = f"#{r:02x}{g:02x}{b:02x}"

        # Block hex_entry signal to avoid recursion
        self.hex_entry.handler_block_by_func(self.on_hex_changed)
        self.hex_entry.set_text(hex_color)
        self.hex_entry.handler_unblock_by_func(self.on_hex_changed)

        self.color = hex_color

        if self.on_change_callback:
            self.on_change_callback(self.color)

    def on_hex_changed(self, entry):
        """Called when hex entry is manually edited."""
        text = entry.get_text()

        # Validate hex color format
        if len(text) == 7 and text.startswith('#'):
            try:
                int(text[1:], 16)  # Try to parse as hex
                rgba = Gdk.RGBA()
                if rgba.parse(text):
                    # Valid color, update button
                    self.color_button.handler_block_by_func(self.on_color_set)
                    self.color_button.set_rgba(rgba)
                    self.color_button.handler_unblock_by_func(self.on_color_set)

                    self.color = text.lower()

                    if self.on_change_callback:
                        self.on_change_callback(self.color)
            except ValueError:
                pass  # Invalid hex, ignore

    def get_color(self):
        """Get current hex color."""
        return self.color

    def set_color(self, color):
        """Set color from hex string."""
        self._parse_color(color)

        # Update button
        rgba = Gdk.RGBA()
        rgba.parse(self.color)
        self.color_button.handler_block_by_func(self.on_color_set)
        self.color_button.set_rgba(rgba)
        self.color_button.handler_unblock_by_func(self.on_color_set)

        # Update entry
        self.hex_entry.handler_block_by_func(self.on_hex_changed)
        self.hex_entry.set_text(self.color)
        self.hex_entry.handler_unblock_by_func(self.on_hex_changed)
