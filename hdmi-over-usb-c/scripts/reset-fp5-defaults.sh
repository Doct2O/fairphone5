#!/system/bin/sh

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# refresh rate shenanigans
settings delete system peak_refresh_rate
settings put system min_refresh_rate 0.0

# Disable on-screen keyboard, when physical is connected - bring default value back
settings put secure show_ime_with_hard_keyboard 0

# Disable equivalent of "keep screen on while charging" from dev settings
settings put global stay_on_while_plugged_in 0

# Set screen brightness mode to auto
settings put system screen_brightness 1

# Anything, not being 0 so we again can see anything on the Phone's display
# but this is a bit overboard as simple screen lock and screen unlock sequence
# changes it back again
echo "130" > /sys/class/backlight/panel0-backlight/brightness
settings put system screen_brightness 130

wm reset