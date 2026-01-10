# Switchback

Solar-based dynamic wallpaper switcher for hyprpaper. Automatically changes your wallpaper based on the actual position of the sun at your geographic location.

## Features

- Automatically switches wallpapers based on real sun position (sunrise/sunset)
- Three time periods: night, morning, afternoon
- Smart scheduling (sleeps until next transition instead of polling)
- Minimal resource usage
- Systemd integration for automatic startup

## Requirements

- Python 3.10+
- hyprpaper with IPC enabled
- systemd (for service management)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/switchback.git
cd switchback

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

### From AUR

```bash
paru -S switchback
```

or

```bash
yay -S switchback
```

### Optional: Install GUI

Switchback includes an optional GTK4 GUI for configuration. To install GUI support:

```bash
# From source
pip install -e .[gui]

# Or install system package
sudo pacman -S python-gobject

# Launch GUI
switchback-gui
```

The GUI provides:
- Live status display (current period, sun times, next transition)
- Visual configuration editor (no need to manually edit YAML)
- File choosers for selecting wallpapers

**Note:** The GUI requires `python-gobject` and GTK4. On Arch Linux, install with `pacman -S python-gobject gtk4`.

## Configuration

### 1. Enable IPC in hyprpaper

Edit `~/.config/hypr/hyprpaper.conf` and change:

```ini
ipc = off
```

to:

```ini
ipc = on
```

Then restart hyprpaper:

```bash
systemctl --user restart hyprpaper.service
```

### 2. Create configuration file

```bash
# Generate a configuration template
switchback init

# Edit the configuration
$EDITOR ~/.config/switchback/config.yaml
```

Update the configuration with:
- Your latitude and longitude
- Your timezone (IANA format, e.g., "US/Pacific", "Europe/London")
- Paths to your wallpaper images for night, morning, and afternoon

Example configuration:

```yaml
location:
  latitude: 37.7749
  longitude: -122.4194
  timezone: "US/Pacific"

wallpapers:
  night: ~/Pictures/backgrounds/night.jpg
  morning: ~/Pictures/backgrounds/morning.jpg
  afternoon: ~/Pictures/backgrounds/afternoon.jpg

settings:
  check_interval_fallback: 300
  preload_all: true
  monitor: ""
```

## Usage

### Run as daemon (foreground)

```bash
switchback
```

### Test configuration

```bash
# Show current period and next transition
switchback test

# Set wallpaper once and exit
switchback once

# Set specific period (for testing)
switchback once --period morning
```

### Run as systemd service

```bash
# Enable and start the service
systemctl --user enable --now switchback.service

# Check status
systemctl --user status switchback.service

# View logs
journalctl --user -u switchback.service -f
```

## How It Works

Switchback calculates the sunrise, solar noon, and sunset times for your location using the `astral` library. It then determines the current time period:

- **Night:** Before sunrise or after sunset
- **Morning:** Sunrise to solar noon
- **Afternoon:** Solar noon to sunset

Instead of constantly polling, Switchback calculates when the next transition will occur and sleeps until then, making it extremely efficient.

## Time Periods

The wallpaper switches at these solar events:

1. **Sunrise:** Night → Morning
2. **Solar noon:** Morning → Afternoon
3. **Sunset:** Afternoon → Night

These times are calculated daily based on your geographic location, so they automatically adjust throughout the year.

## Troubleshooting

### Wallpaper not changing

1. Check that hyprpaper is running: `pgrep hyprpaper`
2. Verify IPC is enabled in `~/.config/hypr/hyprpaper.conf`
3. Check logs: `journalctl --user -u switchback.service -f`
4. Test manually: `switchback once`

### Configuration errors

- Verify your wallpaper files exist
- Check latitude is between -90 and 90
- Check longitude is between -180 and 180
- Verify timezone is a valid IANA timezone

### Hyprpaper not found

Ensure hyprpaper is installed and in your PATH:

```bash
which hyprctl
pgrep hyprpaper
```

## Development

### Project Structure

```
switchback/
├── __init__.py           # Package metadata
├── main.py              # Entry point and daemon loop
├── sun_calculator.py    # Sun position calculation
├── wallpaper_manager.py # Hyprpaper IPC interface
├── config.py            # Configuration loading
└── time_period.py       # Time period mapping
```

### Running tests

```bash
# Test sun calculations
switchback test

# Test wallpaper switching
switchback once --period night
switchback once --period morning
switchback once --period afternoon
```

## Future Enhancements

- Fade transitions between wallpapers
- More time periods (dawn/dusk using twilight)
- Auto-location detection via IP geolocation
- GUI configuration tool
- Multiple wallpaper sets

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

Built with:
- [astral](https://github.com/sffjunkie/astral) - Sun position calculations
- [PyYAML](https://pyyaml.org/) - Configuration parsing
- [pytz](https://pythonhosted.org/pytz/) - Timezone handling
