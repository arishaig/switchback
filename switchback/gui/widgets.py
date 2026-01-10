"""Custom GTK4 widgets for Switchback GUI."""

from pathlib import Path
from gi.repository import Gtk, Gio


class WallpaperChooser(Gtk.Box):
    """File chooser button for selecting wallpaper images."""

    def __init__(self, initial_path=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.path = Path(initial_path) if initial_path else None

        # Label showing current path
        label_text = str(self.path) if self.path else "No file selected"
        self.label = Gtk.Label(label=label_text)
        self.label.set_ellipsize(3)  # Ellipsize at end
        self.label.set_max_width_chars(40)
        self.label.set_xalign(0)  # Align left

        # Choose button
        self.button = Gtk.Button(label="Choose...")
        self.button.connect("clicked", self.on_choose_clicked)

        # Layout
        self.append(self.label)
        self.append(self.button)

        # Set expand for label so it takes available space
        self.label.set_hexpand(True)

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

        dialog.destroy()

    def get_path(self):
        """Get the currently selected path."""
        return self.path

    def set_path(self, path):
        """Set the current path."""
        self.path = Path(path) if path else None
        label_text = str(self.path) if self.path else "No file selected"
        self.label.set_text(label_text)
