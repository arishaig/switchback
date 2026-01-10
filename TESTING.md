# Testing Switchback

This guide covers how to test Switchback before deploying it as a systemd service.

## Prerequisites

1. **Install dependencies:**

```bash
# Using pip
pip install -r requirements.txt

# Or install system packages (Arch)
sudo pacman -S python-astral python-yaml python-pytz
```

2. **Enable IPC in hyprpaper:**

Edit `~/.config/hypr/hyprpaper.conf`:
```ini
ipc = on
```

Restart hyprpaper:
```bash
systemctl --user restart hyprpaper.service
```

3. **Verify hyprpaper is running:**
```bash
pgrep hyprpaper
```

## Testing Steps

### 1. Generate Configuration

```bash
# From the project directory
python -m switchback.main init
```

This creates `~/.config/switchback/config.yaml`.

### 2. Edit Configuration

Update the config with your:
- Location (latitude, longitude, timezone)
- Wallpaper paths (ensure files exist!)

Example:
```yaml
location:
  latitude: 37.7749
  longitude: -122.4194
  timezone: "America/Los_Angeles"

wallpapers:
  night: /usr/share/backgrounds/fluent-building-night.jpg
  morning: /usr/share/backgrounds/fluent-building-morning.jpg
  afternoon: /usr/share/backgrounds/fluent-building-day.jpg
```

### 3. Test Sun Calculations

```bash
python -m switchback.main test
```

**Expected output:**
```
Current time: 2026-01-09 14:30:00 PST

Sun times for today:
  Sunrise:     07:15:23
  Solar noon:  12:23:45
  Sunset:      17:32:10

Current period: afternoon
Current wallpaper: /usr/share/backgrounds/fluent-building-day.jpg

Next transition: 2026-01-09 17:32:10
Time until transition: 3h 1m
```

### 4. Test Wallpaper Switching

Test each period manually:

```bash
# Test night wallpaper
python -m switchback.main once --period night

# Test morning wallpaper
python -m switchback.main once --period morning

# Test afternoon wallpaper
python -m switchback.main once --period afternoon

# Auto-detect current period
python -m switchback.main once
```

**Expected behavior:**
- Wallpaper should change immediately
- Check logs for "Wallpaper changed to: <filename>"

### 5. Test Daemon in Foreground

Run the daemon in the foreground to see live logs:

```bash
python -m switchback.main --verbose
```

**Expected output:**
```
2026-01-09 14:30:00 - switchback.main - INFO - Starting Switchback daemon...
2026-01-09 14:30:00 - switchback.wallpaper_manager - INFO - Waiting for hyprpaper to be ready...
2026-01-09 14:30:00 - switchback.wallpaper_manager - INFO - Hyprpaper is ready
2026-01-09 14:30:00 - switchback.wallpaper_manager - INFO - Preloading 3 wallpapers...
2026-01-09 14:30:00 - switchback.wallpaper_manager - INFO - Preloading wallpaper: fluent-building-night.jpg
2026-01-09 14:30:01 - switchback.wallpaper_manager - INFO - Preloading wallpaper: fluent-building-morning.jpg
2026-01-09 14:30:01 - switchback.wallpaper_manager - INFO - Preloading wallpaper: fluent-building-day.jpg
2026-01-09 14:30:01 - switchback.main - INFO - Current period: afternoon
2026-01-09 14:30:01 - switchback.main - INFO - Sunrise: 07:15
2026-01-09 14:30:01 - switchback.main - INFO - Solar noon: 12:23
2026-01-09 14:30:01 - switchback.main - INFO - Sunset: 17:32
2026-01-09 14:30:01 - switchback.wallpaper_manager - INFO - Setting wallpaper: fluent-building-day.jpg
2026-01-09 14:30:01 - switchback.wallpaper_manager - INFO - Wallpaper changed to: fluent-building-day.jpg
2026-01-09 14:30:01 - switchback.main - INFO - Daemon loop started
```

Press Ctrl+C to stop.

### 6. Test Systemd Service (Local)

Install locally for testing:

```bash
# Install in development mode
pip install -e .

# Copy service file
mkdir -p ~/.config/systemd/user
cp switchback.service ~/.config/systemd/user/

# Reload systemd
systemctl --user daemon-reload

# Start service
systemctl --user start switchback.service

# Check status
systemctl --user status switchback.service

# View logs
journalctl --user -u switchback.service -f
```

### 7. Test Period Transitions

To test transitions without waiting hours:

**Option 1: Modify config temporarily**

Change your timezone to one where a transition is about to happen.

**Option 2: Wait for natural transition**

Run the daemon and wait for the next sunrise/noon/sunset. Monitor logs:

```bash
journalctl --user -u switchback.service -f
```

You should see:
```
Period changed: morning → afternoon
Wallpaper changed to: fluent-building-day.jpg
```

## Common Issues

### "Hyprpaper is not running"

- Check: `pgrep hyprpaper`
- Start: `systemctl --user start hyprpaper.service`

### "Command failed" errors

- Verify IPC is enabled in hyprpaper.conf
- Check hyprpaper logs: `journalctl --user -u hyprpaper.service`

### "Wallpaper file not found"

- Verify all paths in config.yaml exist
- Use absolute paths or properly expand ~ in paths

### "Invalid timezone"

- Use IANA timezone format: `America/Los_Angeles`, not `PST`
- List valid timezones: `python -c "import pytz; print(pytz.all_timezones[:10])"`

## Validation Checklist

- [ ] `switchback test` shows correct sun times for your location
- [ ] `switchback once` successfully changes wallpaper
- [ ] All three periods (night/morning/afternoon) work correctly
- [ ] Daemon runs without errors in foreground mode
- [ ] Systemd service starts and shows "active (running)" status
- [ ] Logs show wallpaper changes at expected transition times
- [ ] Service survives system restart (if enabled)

## Testing Gradual Transitions (New Feature)

### 1. Enable Transitions in Config

Edit `~/.config/switchback/config.yaml`:

```yaml
settings:
  transitions:
    enabled: true          # Enable gradual transitions
    granularity: 600       # Update every 10 minutes (for testing)
    cache_blends: true     # Cache blended images
    cache_dir: "~/.cache/switchback"
```

### 2. Test Transition Blending

Run with verbose output to see blend information:

```bash
python -m switchback.main once --verbose
```

**Expected output:**
```
Gradual transitions enabled
Blend cache enabled at: /home/user/.cache/switchback
Current period: night
Initial blend: night → morning (0.42)
Generating blended wallpaper...
Blending night.jpg -> morning.jpg at alpha=0.42
Saved blend to cache: night-morning_0.42.jpg
Wallpaper changed to: night-morning_0.42.jpg
```

### 3. View Cached Blends

```bash
ls -lh ~/.cache/switchback/blends/
cat ~/.cache/switchback/metadata.json | python3 -m json.tool
```

**Expected:**
- Multiple `.jpg` files with names like `night-morning_0.42.jpg`
- `metadata.json` with hash and size information

### 4. Test Different Blend Ratios

Throughout the day, run:
```bash
python -m switchback.main once --verbose
```

The blend ratio should change over time:
- Early in period: `(0.00)` - shows current period wallpaper
- Mid period: `(0.50)` - 50/50 blend
- Late in period: `(1.00)` - shows next period wallpaper

### 5. Test Cache Invalidation

1. Change one of your wallpaper files
2. Run `switchback once --verbose`
3. Cache should regenerate automatically

### 6. Test Daemon with Transitions

Run daemon in foreground with fast granularity for testing:

```bash
python -m switchback.main --verbose
```

**Expected:**
- Initial blend logged
- Wallpaper updates every 10 minutes (or your granularity setting)
- Blend ratio increases over time
- Cache hits on subsequent runs

### 7. Test GUI (if GTK4 installed)

```bash
switchback-gui
```

1. Navigate to "Transitions" tab
2. Toggle "Enable gradual transitions"
3. Adjust granularity slider
4. Click "Save"
5. Click "Clear Cache" to test cache clearing

### 8. Compare Hard vs Gradual Transitions

**Test hard transitions:**
```yaml
transitions:
  enabled: false
```

Run daemon and observe instant changes at period boundaries.

**Test gradual transitions:**
```yaml
transitions:
  enabled: true
  granularity: 600  # 10 minutes for testing
```

Run daemon and observe smooth blending throughout the period.

## Performance Testing

### Memory Usage

Monitor daemon memory usage with transitions enabled:

```bash
# In one terminal
python -m switchback.main --verbose

# In another terminal
watch -n 5 'ps aux | grep switchback'
```

**Expected:** <200MB during blending, <50MB idle

### Cache Size

```bash
du -sh ~/.cache/switchback/
```

**Expected:** Varies based on image size and granularity
- 4K wallpapers: ~10-50MB per blend
- 1080p wallpapers: ~1-5MB per blend
- Max cache: 500MB (configurable)

### Blend Performance

Time a single blend operation:

```bash
time python -m switchback.main once --verbose
```

**Expected:**
- First run (no cache): 1-3 seconds for 4K images
- Subsequent runs (cached): <0.1 seconds

## Validation Checklist (Updated)

### Original Features
- [ ] `switchback test` shows correct sun times for your location
- [ ] `switchback once` successfully changes wallpaper
- [ ] All three periods (night/morning/afternoon) work correctly
- [ ] Daemon runs without errors in foreground mode
- [ ] Systemd service starts and shows "active (running)" status
- [ ] Logs show wallpaper changes at expected transition times

### New Transition Features
- [ ] Blend cache directory created at `~/.cache/switchback/blends/`
- [ ] Blended wallpapers generated with correct ratios (0.00-1.00)
- [ ] Cache hits on subsequent runs with same ratio
- [ ] Cache invalidates when wallpapers change
- [ ] Gradual transitions smooth throughout the day
- [ ] GUI transitions tab functional (if GTK4 available)
- [ ] Hard transition mode still works when disabled
- [ ] Memory usage remains reasonable (<200MB)

## Next Steps

Once all tests pass:

1. Enable the service to start automatically:
   ```bash
   systemctl --user enable switchback.service
   ```

2. Verify it starts on login

3. Monitor logs for the first few days to ensure transitions work correctly

4. Adjust granularity to your preference:
   - Fast (smooth): 600s (10 minutes)
   - Balanced: 3600s (1 hour) - recommended
   - Battery-friendly: 7200s (2 hours)

5. Package for AUR (see PKGBUILD)
