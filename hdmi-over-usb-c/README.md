# Display port/HDMI over USB-C on LineageOS

As funny as it may sound either LineageOS or the Fairphone itself (but pretty sure, the former,  
because IIRC it worked out of the box on the stock ROM) is really fussy about how, what, and in  
what order is plugged into the USB-C port, while trying to use the external display.

Nevertheless after going borderline insane, I think I managed to determine the proper 
way to plug in stuff to make LineageOS happy and which works _pretty_ reliably.

# Prerequisites

You need one of those fancy USB-C breakout apparatus, which exposes at least HDMI port outside.  
Later I'll assume that it is already plugged into your phone.  

## Hardware consideration

### Splitter

In my tests I managed to get working pretty much any splitter that I got my hands on.

My splitter of choice, though, is a flat relatively small metal box, with three ports on one side (USB-A, HDMI, USB-C)
with width matching the width of those ports put together next to each other (give or take) and a short USB-C cord on the other, opposite side.

All of those three ports were functional at once in such a configuration: 

- USB-A: where I plugged the USB hub, to which in turn, I plugged external HDD drive and a wireless mouse.
- USB-C on splitter: for charging (no fast charging available, though. Still, battery WAS charged.)
- HDMI: for external display (works with audio, when proper HDMI cable is used)

### Other hardware

Once I've connected the external display as described in following sections, the type of the splitter,
length of the cable (and what not) does not seem to make much of a difference.

It also streamed sound to the display (here you need to make sure the cable supports that, though), hell, it even
worked via the HDMI->DVI adapter.

So, at least in that regard the LineageOS is not too picky :)

# Rootless section

All instructions described in following sub-chapters, should work on non-rooted LineageOS on Fairphone 5.

Be warned, though. The rootless experience on the LineageOS is pretty underwhelming, ~as it appears to only be capable of mirroring the screen
in exact the same resolution (or aspect ratio, rather) as the phone's display.~ Now the resolution may be changed, but effectively it does not change much
with black enveloping area :P

Stock Android's settings does not help here either, as there, you can at most change the orientation of the streamed image,
by flipping it by 90, 180 and 270 degrees.

As far as I can tell the system processes the output image in such a way, that it is scaled to match the best integer scaling ratio
of the external display's resolution.  
And you guessed it, if the ratio is far off, this results in a nasty black filling-up-space displayed around the proper image.

Nevertheless to get it working, closely follow steps in the next sections. 

***NOTE: If you lost the external screen image, unplug everything from the adapter and re-iterate the steps.***

## External display solo

1. When the phone's screen is unlocked; plug in the HDMI cable to both the external display and splitter
   (whether the cable is plugged in first on the side of splitter or display, does not matter here).
2. Confirm the mirroring in the dialog that should pop up in the system
3. Lock the screen
4. Unlock the screen 

And voila! The mirrored image on your external screen should appear in less than 10 seconds.
If not, repeat the steps `3.` - `4.` with longer pause between them.

If you still have problems, make sure there are no wake locks active, as the trigger requires deep sleep engaged between points `3.` and `4.`.
To verify that, invoke. **Requires root access**:
```
dumpsys power | grep -i 'wake locks' -A 10
```
If it says `Wake Locks: size=0` you are good to try again. If not, stop the apps on the list holding the wake lock 
(`DOZE_WAKE_LOCK` held by `dream:doze` is freed automatically, wait a while for it and do not kill app holding it).


## External display with charging

If your splitter also has a port for charging (usually USB-C), plug in the charger ***FIRST***. 
And when battery starts to charge, follow steps in section `External display solo`.

If done the other way around, the phone may report dirt or moisture in the port, and neither
the charging nor any external USB device will work.

## External display with other USB devices

If your splitter aside the HDMI port has also USB port, and
you want to use that for some external USB device, follow the steps in `External display solo` .
Once the screen is already mirrored plug in the other USB devices.

## External display with other USB devices and charging

If your splitter aside the HDMI port has also USB port (one not for charging) and the other -
usually USB-C - destined for charging, and you want to make use of all of them. Do as follows:  
first perform the steps in `External display with charging` and once the screen is already mirrored, plug in the
other USB devices.

# Root section

***Obviously you'll need root access to invoke following commands.***

Normally, I'd recommend screen extension and desktop mode, enabled by tweaking system settings.

But it seems to be broken on LineageOS;   
the external display loves to disconnect (fixable with setting fixed framerate, see further on),
the title bar of the apps does not disappear in the full screen mode,
and to top it off, mouse cursor tends to jump back to the phone's screen (fixable with screen rotation).  
But most importantly: the Android apps struggles a lot, as most of them were never developed with
desktop mode in mind in the first place.
So for now it is no go.  
But be as it may, I paste the settings to change via the terminal, if you'd like to test the desktop mode yourself.
For them, go to the very end of this document.

## Advisory and word of warning

***For your own sake, do not reset the phone while not in Phone's original resolution.
The settings changed here survive the reboot, and then the phone may use the weirdest resolution
for first unlock, rendering it very hard or in extreme cases impossible to unlock.***

Also I highly recommend connecting the USB mouse to the phone, as in some resolutions it is really hard to use phone via touch screen.
That, or at least to spare the struggle: prepare what you want to mirror FIRST and THEN do the resolution switch.

## Back to defaults

First off, in the `scripts` subdir you can find script named `reset-fp5-defaults.sh`
which resets all the settings to FP5 and LineageOS defaults, so you can save yourself, if you screw something up.

Even better so, it may be bound to the HDMI cable unplug by script of mine, so the defaults restoration happens automatically when the connection
with external display is lost. See `hw-tinkering/hw-event-binder/README.md` path relative to the repo's root, for more details.

## autores-fp5.sh

**MAJOR WARNING. Since recent update of LineageOS, calling the `autores-fp.sh` will cause loss of the main screen layout and icons for good.
I haven't found a proper workaround for that yet, the only option is to backup launcher's settings on `/data` partition and bring them back,
however I cannot assure that will work reliably in general, thus I am not incorporating this in scripts by default.
For details see chapter `My icons are all messed up on the main screen/I've lost my main screen layout, after resetting to default settings`**

Second off, in the `scripts` subdir you can find script named `autores-fp5.sh`
which detects the external's display resolution (and it presence for that matter)
and automatically calculates optimal resolution and DPI to set and the applies them.

***Mind ya, the `autores-fp5.sh` by default completely turns off the phone's screen, so don't be alarmed; that's normal.
It still will react to touch but it is blacked-out to spare the screen lifespan.
If you need to urgently turn it back on again, just lock and unlock the phone.***

Copy the script to the phone and then - once the mirroring is already working - run it as follows. ***Must be run as a root***:
```
./autores-fp5.sh
```

In case when the app which you want to mirror on the external display unconditionally rotates the screen,
call `autores-fp5.sh` with the flag `--landscape`. This swaps the detected height and width,
which should help in such situation. Simply call like this:
```
./autores-fp5.sh --landscape
```

Lastly if `autores-fp5.sh` fails to detect the external screen dimensions (or does it incorrectly)
you can pass it verbosely, to override the detected ones. Like so:
```
./autores-fp5.sh 1920x1080
```

If you need landscape equivalent in this mode, simply swap width and height in the command call i.e:
```
./autores-fp5.sh 1080x1920
```

If phone's screen un-dimmed itself for some reason (rarely, but happens) just re-run the `autores-fp5.sh` script
with the same arguments.

### Overview of tweaked settings

Let's start the description with the most basic setting that gets tweaked: 

- `wm reset` - brings back default DPI (480) and resolution (1224x2770) for the phone

And here the fun begins. You remember those ugly black bezels, caused by the discrepancy of
the aspect ratio of the phone and the external display, described in the section for mortals?  
Yeah, those, here we can fix that.

If instead of `reset` we pass a resolution in format `size <width>x<height>` after that, 
the phone will start to use this resolution as a native now on. 

And if we get the resolution and DPI just right regarding the aspect ratio of  
the external display, we will eliminate the frames completely or severely minimize them.

It all depends on how the app you are currently using displays stuff.

The `reset` command also resets the DPI to default 480. To change that manually,
call `wm density <new DPI>` (for example if navigation buttons are missing, or icons size is inappropriate).

--- 

And here is the description of the rest of poked settings:

- `settings delete system peak_refresh_rate` and  
  `settings put system min_refresh_rate 0.0` - unlocks back the default dynamic refresh rate of the screen
- `settings put secure show_ime_with_hard_keyboard 0` - disables virtual keyboard, once the physical one is detected over USB.
- `settings put global stay_on_while_plugged_in 0` - disables "Keep screen on, while charging" aka "Stay awake" option.
- `settings put system screen_brightness_mode 1` - sets phone screen brightness control to auto
- `echo "130" > /sys/class/backlight/panel0-backlight/brightness` - sets the actual brightness of the phone on the HW level, to anything else than zero.
- `settings put system screen_brightness 130` - sets the actual brightness of the phone on the Android level, to anything else than zero.

But why change those from defaults?

- ***refresh rate*** - Fairphone uses dynamic refresh rate by default,  
                       when it switches, the connection with the external display may be dropped.
- ***virtual keyboard*** - when you connect external USB device and it happens to mimic the keyboard  
                           (some mouses with extended or media keys), the virtual keyboard on the phone  
                           won't come up, leaving you without ability to type on the phone using the mouse.
- ***keep screen on*** - because it is really annoying when you got everything ready, you operate the phone comfortable   
                         from the distance. And the phone decided to lock, because you didn't do anything for a while.
                         ~And now you need to get up and unlock the phone, as it is impossible to wake the phone on distance. That's why.~ 
                         I don't think this longer applies. Nevertheless auto-lock is still annoying.
- ***screen brightness mode*** - Set to manual, so we can later dim the Phone's screen to zero and we won't need to 
                                 worry about it turning on again by its own, due to the ambient lighting condition change.
- ***HW brightness of the OLED panel*** - as we already are using the external display and we are mirroring image there,
                                          we don't really need the Phone's screen anymore (for some resolutions it may be unreadable, too).
                                          That way we are limiting the battery usage as well as screen burnout. Here I quietly assume
                                          usage of some wireless input device, like mouse.
- ***Android brightness of the OLED panel*** - Dim the brightness to minimum (but it never actually results in turned off screen), to limit
                                               automatic screen's turn on, when turend off on the HW level.

What are correct values for those on Fairphone 5?

- `peak_refresh_rate` and `min_refresh_rate`   
  To fix the refresh rate both must have the same value. And the correct ones are `60` and `90`.
  Any other one is ignored and IIRC you are back to dynamic refresh rate.
  To make the framerate fixed, invoke following commands:
    * 60 fps
      ```
      settings put system min_refresh_rate 60
      settings put system peak_refresh_rate 60
      ```
    * 90 fps
      ```
      settings put system min_refresh_rate 90
      settings put system peak_refresh_rate 90
      ```
    * Default:
      ```
      settings delete system peak_refresh_rate
      settings put system min_refresh_rate 0.0
      ```
- `show_ime_with_hard_keyboard`  
  either `1` or `0`, where obviously:
  `1` means: show the virtual keyboard, despite detection of physical one, and `0` does the opposite.  
  Set as follows:
    * Enable virtual keyboard alongside physical 
    ```
    settings put secure show_ime_with_hard_keyboard 1
    ```
    * Disable (default):
    ```
    settings put secure show_ime_with_hard_keyboard 0
    ```
- `stay_on_while_plugged_in`  
  For a change this is a bit mask. The proper values ranges from `0`-`15`.   
  Where `0` disables this option and the rest goes as follows (according to, https://developer.android.com/reference/android/os/BatteryManager):  
  ```
    BATTERY_PLUGGED_AC 1  
    BATTERY_PLUGGED_USB 2  
    BATTERY_PLUGGED_WIRELESS 4  
    BATTERY_PLUGGED_DOCK 8
  ```
  If you want to enable more than one at the time, simply sum values of the interesting ones
  and set the setting to the result (magic of bit masks). For example:
    - Disable (default)
    ```
    settings put secure show_ime_with_hard_keyboard 0
    ```

    - AC + USB
    ```
    settings put secure show_ime_with_hard_keyboard 3
    ```

    - all
    ```
    settings put secure show_ime_with_hard_keyboard 15
    ```
- `screen_brightness_mode`  
  either `1` or `0`, where,
  `1` means automatic screen brightness control and `0` means manual control.  
  Set as follows:
    * Enable automatic screen brightness control according to the lighting condition
    ```
    settings put secure screen_brightness_mode 1
    ```
    * Enable manual screen brightness control
    ```
    settings put secure screen_brightness_mode 0
    ```
- `/sys/class/backlight/panel0-backlight/brightness`  
  Integer ranging from `0` (turn off the screen completely), to max value
  stored in: `/sys/class/backlight/panel0-backlight/max_brightness`.

     * To check max value:
     ```
     cat /sys/class/backlight/panel0-backlight/max_brightness
     ```
     e.g.:
     ```
     # cat /sys/class/backlight/panel0-backlight/max_brightness
     4095
     ```
   Set as follows:
    * Turn off the screen completely:
    ```
    echo 0 > /sys/class/backlight/panel0-backlight/brightness
    ```
    * Turn on the screen with arbitrary brightness:
    ```
    echo 100 > /sys/class/backlight/panel0-backlight/brightness
    ```
    * Turn on the screen with max possible brightness:
    ```
    echo "$(cat /sys/class/backlight/panel0-backlight/max_brightness)" > /sys/class/backlight/panel0-backlight/brightness
    ```
- `screen_brightness`  
  Integer ranging in from `0` to who knows how much.
  * Dim the screen as much as possible on Android level:
    ```
    settings put system screen_brightness 0
    ```
  * Un-dim the screen:
    ```
    settings put system screen_brightness 130
    ```

## Troubleshooting

#### External screen is disconnecting when I jump between the apps/change view/scroll something

Most likely the adaptive refresh rate is enabled. To confirm that, in dev options search for and enable `Show refresh rate`.
Now the number in the corner of display should appear (on the Phone's screen). It indicates current refresh rate.

Do what you've done earlier, that caused the external screen to disconnect. 
See if the fps counter changes and external display disconnects.

If so, apply following settings from the console for the time of using external display. ***Requires root access***:
```
settings put system min_refresh_rate 60
settings put system peak_refresh_rate 60
```
To reset to normal, adaptive mode:
```
settings delete system peak_refresh_rate
settings put system min_refresh_rate 0.0
```

Remember to disable the FPS counter.

#### Despite using the `autores-fp5.sh` script I still see black framing around the image (image also may seem squished)

Most likely you have changed the rotation for external display in the Adnroid settings.
Bring it back to `standard` under `Settings`->`Connected Devices`->`External Displays`->`Rotation` and you are good to go.
It may require re-running the `autores-fp5.sh` script.

#### The display seems to be not responding and/or be stuck on main screen after reset to defaults 

Perform lock-unlock cycle, until it responds to touch.
Now, although it may not respond to swipe, it should respond to taps. Touch and hold the main screen and enter
screen settings, or open any new app. The main view should be back to normal by now.

#### My icons are all messed up on the main screen/I've lost my main screen layout, after resetting to default settings

~For some reason, from time to time, the main launcher changes the icons grid settings~
~after switching back to default screen settings of the phone.~
~To fix that, simply bring back the grid setting you got before. This is how it's done:~

~- Long press on the main screen~
~- Press: `Wallpaper and style` (or something similar) in the pop up menu~
~- Scroll down and find `Applications grid`, or something similar~
~- The new view shall appear. Choose your previous settings.~

As for now this no longer works, and the icons and main screen layout is gone for good.
The easiest, least intrusive and universal method is to keep a screenshot of your layout to recreate it later manually.
But yeah, this is utterly miserable and annoying that way, so we are not stopping at that, at least not for stock LineageOS launcher.

For LineageOS's Trebuchet or `com.android.launcher3`, the workaround looks like this **Requires root access**:

- First make a backup folder, to store there the settings later on:
```
TREBUCHET_UID=$(stat -c "%u" /data/data/com.android.launcher3)
mkdir -p /data/data/com.android.launcher3/backup/ && chown ${TREBUCHET_UID}:${TREBUCHET_UID} /data/data/com.android.launcher3/backup/
```
- Copy current settings to the folder you've just created (you must do it every time you've changed something on the main screen):
```
cp -r /data/data/com.android.launcher3/databases /data/data/com.android.launcher3/shared_prefs /data/data/com.android.launcher3/backup/
```
- After resetting display to its defaults, bring back the saved Trebuchet settings:
```
cp -r /data/data/com.android.launcher3/backup/* /data/data/com.android.launcher3/
```
- Reset the trebuchet via `am` to apply restored settings:
```
am force-stop com.android.launcher3
```
You may add those two last calls, as an additional commands to be run on the HDMI cable disconnect in script `hw-event-binder.py`, after running `reset-fp5-defaults.sh`.
See `hw-tinkering/hw-event-binder/README.md` path relative to repo's root, for details.

## Desktop mode and screen extending on LineageOS

***Both the desktop mode and screen extending is broken in a many places on LineageOS. Please see introduction to `Root section` to see what's wrong with it.***

To enable somewhat functional extended desktop mode, invoke following commands as a root:
```
settings put global force_desktop_mode_on_external_displays 1
settings put global force_resizable_activities 1
settings put global enable_freeform_support 1
settings put global enable_desktop_windowing_mode 1
settings put global ignore_orientation_request 1
settings put global policy_control "immersive.full=*"
```
***Changing those settings requires reboot.***

To disable:
```
settings put global force_desktop_mode_on_external_displays 0
settings put global force_resizable_activities 0
settings put global enable_freeform_support 0
settings put global enable_desktop_windowing_mode 0
settings put global ignore_orientation_request 0
settings put global policy_control null*
```
***Changing those settings requires reboot.***

Trivia: by mere changing value of those settings, new options
        representing some of them shall appear in the dev menu :)