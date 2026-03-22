# Fixing laggy, unresponsive, delayed or completely unresponsive screen wake-up on double tap

This is a very specific bug in the LineageOS, which may be unnoticed by most.
Especially since I am not sure how popular the feature of "Double tap to wake up" really is, but I am personally using it extensively,
and I find it really annoying when it's sluggish or completely unresponsive.  
Especially since on the Fairphone 5 the power button has fingerprint reader on it and each attempt to just check the clock 
and/or notifications on the lock screen causes full-blown phone unlock.

### Reproducing the problem
To see if the problem still persists, make sure the `Double tap to wake up` option is enabled in settings. 
If so, lock the screen and wait a while (5 minutes is a safe time margin, for the phone to go into deep sleep).  
Also make sure there are no active wake locks, by invoking ***AS ROOT***:
```
dumpsys power | grep -i 'wake locks' -A 10
```
If it says `Wake Locks: size=0` you are good to give it a shot. If not, you may try to stop the apps on the list holding the wake lock
(`DOZE_WAKE_LOCK` held by `dream:doze` is freed automatically, wait a while for it and do not kill app holding it).

### The fix
After a painstaking process of troubleshooting this issue, it turns out the problem is caused by putting the SPI bus to sleep, through which the screen is talking to
the system. To keep it awake for all the time, simply invoke ***YOU NEED ROOT ACCESS FOR IT***:
```
echo "on" > /sys/devices/platform/soc/a94000.spi/power/control 
```
After this the wake up function works as intended.

To bring back the default setting, invoke:
```
echo "auto" > /sys/devices/platform/soc/a94000.spi/power/control 
```

Btw holding the wake lock all times would work as well, but it'd most likely cause increased drain of a battery.  
No such condition has been observed when applying above fix.

# Applying the fix automatically at system boot

Well, just like in `hw-event-binder` sibling folder's README, I recommend `Termux:Boot` for that.
Please see `Termux:Boot` section of that README for details. Just mind, if you are going to use
both things, place the below snippet before starting the `hw-event-binder.py` script. 

Here is the snippet to add to the startup script (it does sanity check if the sysfs node actually exists before writing to it):
```
GOODIX_SCREEN_BUS_PWR_CTRL_NODE="/sys/devices/platform/soc/a94000.spi/power/control"
su -c "test -e $GOODIX_SCREEN_BUS_PWR_CTRL_NODE && 
       echo \"on\" > $GOODIX_SCREEN_BUS_PWR_CTRL_NODE"
```