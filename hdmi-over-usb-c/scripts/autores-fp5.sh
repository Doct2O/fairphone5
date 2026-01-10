#!/system/bin/sh

# --- Check Root ---
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: This script must be run as root."
    exit 1
fi

# --- Configuration: Phone Specs ---
PHONE_W=1224
PHONE_H=2770
BASE_DENSITY=480
MIN_DENSITY=80

# --- Variables from arguments ---
INVERT_DIM=0
EXT_RES=""

if [ "$#" -ge 1 ] ||
   ([ "$#" -eq 1 ] && [ "$1" = "-h" ]) ||
   ([ "$#" -eq 1 ] && [ "$1" = "--help" ]) then
    if ([ "$#" -eq 1 ] && [ "$1" = "--landscape" ]) ; then
        INVERT_DIM=1
    elif [ "$#" -eq 1 ] && echo "$1" | grep -qE '[0-9]{3,}x[0-9]{3,}' ; then
        EXT_RES="$(echo "$1" | sed 's/x/ x /g')"
    elif ! [ $1 = "-h" ] && ! [ "$1" = "--help" ] ; then
        echo "Invalid usage. Pass -h/--help for help."
        exit 1
    else
        echo "
Script which automatically detects, calculates and sets most optimal
resolution and density for both the phone and external display.

Usage: $(basename "$0") [--landscape | <width in px>x<height in px>]

Where the argument is either:

    --landscape
                 Swaps the width and height of detected external display.
                 Useful, when app which you want to put on the screen
                 enforces rotation.

    <width in px>x<height in px>
                 User enforced resolution. Useful, if there is problem in
                 auto detection.

Only one argument at the time is valid. If no argument provided, the script
will perform full auto-detection, and set the detected resolution in the
portrait mode.

To swap the W and H while enforcing the resolution, simply pass it
other way around: <height in px>x<width in px>.

Examples:
    $(basename "$0") # Let the magic happen - full auto-detection
    $(basename "$0") --landscape # Auto detection and swap of the W <-> H
    $(basename "$0") 1920x1080 # Verbosely set the resolution.
    $(basename "$0") 1080x1920 # Verbosely set the resolution, --lanscape equivalent
                               # for resolution from previous example.
        "
    	exit 0
    fi
fi

echo "[*] Starting display detection..."

# --- Detect External Display ---
# We use dumpsys display and parse for "External" or "HDMI" devices.
# We extract the first occurrence of standard width x height.
EXT_INFO=$(dumpsys display | grep -iE 'DisplayDeviceInfo.*(type=EXTERNAL|HDMI)' | head -n 1)

if [ -z "$EXT_INFO" ]; then
    echo "[-] No external display detected."
    exit 0
fi

if ! test -v EXT_RES || [ -z "$EXT_RES" ] ; then
    # 2. Parse External Resolution
    # Extract the resolution pattern (Numbers x Numbers)
    EXT_RES=$(echo "$EXT_INFO" | grep -oE '[0-9]{3,} x [0-9]{3,}' | head -n 1)

    if [ -z "$EXT_RES" ]; then
       echo "[-] Error: Could not parse external resolution."
       exit 1
    fi

    echo "[+] External monitor resolution is: ${EXT_RES}"
else
    echo "[+] Forcing external monitor resolution to: ${EXT_RES}"
fi

EXT_W=$(echo "$EXT_RES" | awk '{print $1}')
EXT_H=$(echo "$EXT_RES" | awk '{print $3}')

# Validate extraction
case $EXT_W in
    ''|*[!0-9]*) echo "[-] Error: Could not parse external width."; exit 1 ;;
esac

echo "[+] External Display Found: ${EXT_W}x${EXT_H}"

NEW_W=0
NEW_H=0

if test -v INVERT_DIM && [ "${INVERT_DIM}" -eq 1 ] ; then
   echo "[*] Inverting the dimensions as landscape orientation has been requested"
   TMP="${EXT_W}"
   EXT_W="${EXT_H}"
   EXT_H="${TMP}"
fi

NEW_H=$EXT_H
NEW_W=$EXT_W

echo "[+] Calculated Target Resolution: ${NEW_W}x${NEW_H}"

# --- Calculate Density ---
# We are using just height for that instead of total pixels count, as
# otherwise the navigation menu can be lost.
CALC_DENSITY=$(awk "BEGIN {printf \"%.0f\", ($NEW_H / $PHONE_H) * $BASE_DENSITY}")
echo "[+] Calculated Density: $CALC_DENSITY"

# --- Enforce Minimum Density (80) ---
if [ "$CALC_DENSITY" -lt "$MIN_DENSITY" ]; then

    # Scale up to the next, closes integer multiplication of the original resolution
    # so displayed aspect ratio is right.
    NEW_H=$(awk "BEGIN {printf \"%.0f\", $PHONE_H * ($MIN_DENSITY/$BASE_DENSITY)}")
    NEW_W=$(awk "BEGIN {printf \"%.0f\", $NEW_H * ($EXT_W/$EXT_H)}")
    CALC_DENSITY=$(awk "BEGIN {printf \"%.0f\", ($NEW_H / $PHONE_H) * $BASE_DENSITY}")

    echo "[*] New Scaled Resolution: ${NEW_W}x${NEW_H}"
    echo "[*] New Density: $CALC_DENSITY"
fi

# --- Apply Changes ---
echo "[*] Applying settings..."

wm size "${NEW_W}x${NEW_H}"
wm density "$CALC_DENSITY"
echo "[+] Resolution set to ${NEW_W}x${NEW_H} and Density to ${CALC_DENSITY}."

# --- Apply handful quirks ---
# Hard set 60 fps, disable adaptive refresh rate
# (could be 90, but I imagine) more displays support 60
settings put system peak_refresh_rate 60
settings put system min_refresh_rate 60
# Allow virtual keyboard, even if the physical is connected
settings put secure show_ime_with_hard_keyboard 1
# Do not lock screen automatically as long as phone is charging from AC/USB
settings put global stay_on_while_plugged_in 3
# Hard set manual brightness control, so screen won't turn on by its own
settings put system screen_brightness_mode 0
# First dim the screen fully and then Turn off phone's screen
# completely, reducing power consumption and burnout
# this is not permanent. Lock and unlock to reset.
settings put system screen_brightness 0
echo "0" > /sys/class/backlight/panel0-backlight/brightness
