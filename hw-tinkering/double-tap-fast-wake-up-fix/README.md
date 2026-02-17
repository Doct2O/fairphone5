# Fixing laggy, unresponsive, delayed or completely not responding screen wake up on double tap

This is very specific bug in the LineageOS, which may be unnoticed by most.
Especially as I am not sure how popular the feature of "Double tap to wake up" really is, but I am personally using it extensively,
and I find it really annoying to be sluggish or completely unresponsive.  
Especially since in Fairphone 5 the power button has fingerprint reader on it and each attempt to just check the clock 
and/or notifications on the lock screen causes full blown phone unlock.

### Reproducing the problem
To see if the problem still persists, make sure the `Double tap to wake up` option is enabled in settings. 
If so, lock the screen and wait a while (5 minutes is a safe time margin, for the phone to go into the deep sleep).  
Also make sure there are no active wake locks, by invoking ***AS A ROOT***:
```
dumpsys power | grep -i 'wake locks' -A 10
```
If it says `Wake Locks: size=0` you are good to proceed with the test.

Once the screen is locked and turned off, tap twice. If it does not wake up in like 2-3s, that means the following fix is for you.

### The fix
After painstaking process of troubleshooting this issue, it turns out the problem is caused by putting to sleep the SPI bus, by which the screen is talking to
the system. To keep it awake for all the time, simply invoke ***YOU NEED ROOT ACCESS FOR IT***:
```
echo "on" > /sys/devices/platform/soc/a94000.spi/power/control 
```
After this the wake up function works as intended.

To bring back the default setting, invoke:
```
echo "auto" > /sys/devices/platform/soc/a94000.spi/power/control 
```

Btw. Holding the wake lock all the time, would work as well, but it'd most likely cause increased drain of a battery.  
No such condition has been observed when applying above fix.