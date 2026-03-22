# Hardware Event to Action Binder

The script stored here is a hardware event listener and dispatcher of actions assigned to corresponding event.
Currently the script maps hardware **long-presses** (Volume and Power buttons) and **HDMI connection states**
to customizable shell commands or system actions like (and currently only) toggling the flashlight.

It was supposed to be a simple shell script, but after considering my use cases and the fact that one cannot simply turn on the flashlight from the 
command line shell, I concluded that a simple script won't cut it, so here we are...

# Disclaimer and advisory

I can more or less guarantee that the script will work on **rooted** Fairphone 5 powered by the LineageOS, as I am actively using it myself. 

**I provide no guarantees for any other device, any other ROM or any other setup, though.**  
In such case, I may answer questions but I won't do any fixes to the script, as it is too much of a hassle, mess and commitment for me.

**Which release of LineageOS is supported?**  
This info is expressed among tags, please see them for that.  
If you want to see if your version of Lineage is supported, look for the version kept in the name of tag.  
All commits coming after and including the tagged base commit should work on that version too, up to and excluding the next commit tagged with other version,
which likely will be incompatible.

**!!! AND ALWAYS, AND I MEAN IT. UPDATE BOTH, THE SCRIPT AND THE `py-and-svc-binds` LIBRARY. 
GENERALLY, IT'S BEST TO USE WHOLE REPO AS IS - DONT'T SEPARATE SCRIPTS, ESPECIALLY IF THEY DEPEND ON EACH OTHER. 
IT'S NOT ME, IT'S HOW ANDROID OPERATES !!!**

It is also best to clone the repo directly on the target device.

# How this thing became, well, a thing?

LineageOS has this neat option of mapping flashlight to the long press of the power button, to which I very much got used to on my previous phone.  
No wonder why. It is very handy to be able to quickly engage the flashlight, without waking up the phone, yet alone looking at it, especially in a pitch black room
and just by using sense of touch (the physical buttons are easy to find this way, duh).

But "Why not just stick to the stock solution?" you might ask. Very good question, I'd answer.  
The underlying reason is pretty much the same as for sibling folder `double-tap-fast-wake-up-fix`.
But long story short. The Fairphone 5 has a fingerprint reader on a power button. 
And in case of this feature - due to the reader - the phone is rather unlocked before/instead of the flashlight turning on. At this point I just could go to the UI and turn it on via widget.  
Plus in such arrangement the screen usually flashes right into your eyes and if I was fond of that, I'd buy a strobe or visit a techno party.

Taking all this into account, and not finding stock option to map long press of volume keys to flashlight. I decided to write my own tool, which will do it properly and maybe enhance that.  
After all, how hard turning on the torch, on the Android... can be?  
Ah yes, famous last words - "We decided to do something, because we thought it'll be easy, not because it is easy. ~Probably Every Engineer Ever".  
...And by a mere look at the code and `README.md` of the library utilized to talk with android `py_and_svc_binds` (which is actually just a symlink to the repo root's `py-and-svc-binds`) you probably, my dear reader, may say: "It is not so simple, nor easy.". And now I - as an author of that library - may only regretfully nod, confirming your deduction.

# Okay, okay. But what this script is capable of? And why it is so long, given the module `py_and_svc_binds` suppose to do all the heavy lifting?

Excellent question! Starting with the latter, in LIFO manner.

## Why it is so long?

Well, it is mostly my fault, as I added some heavies to this lift called script (or elevator if you are American):

- **Firstly**, you need root access, to open endpoints in `/dev/input/`, which is a very convenient way of listening for the buttons strokes, among all things.
  Same goes for the kernel events accessible via `NETLINK_KOBJECT_UEVENT` type socket, which is extension to the original script, actually. More on that in fourth point.

- **Secondly**, I decided to add a neat function of not only mapping flashlight to the hardware event, but also running any custom command.
  And why? Well, starting `airodump-ng` by merely holding a button for a bit longer at any time, without even taking the phone out of the pocket
  was too tempting to pass up. Perfect Watch_Dogs experience™, guaranteed (given how much Watch Dogs game's scripts were broken at the premiere, I might actually not be that far off XD).

- **Thirdly**, okay, we are running as the root, so we can do pretty much anything on the system. You may say.
  And that's mostly right. Mostly, because in such case, one does not do the correction for the Android's permission management.
  Long story short, the permissions in some services, are checked per Linux user's/app's ID. That on its own might not be so hard to circumvent, we have `su` after all.
  The real problem lies in rebuilding seLinux security context, which for some services is also checked (GPS), and I need GPS access to run `airodump-ng` with geotagging.
  In the end it turned out that it is much easier to start as a regular user and then elevate to root and delegating commands execution to the other side of the script, which runs as a regular user,
  than playing with the user context reconstitution. On the flip side, to do this other way around, we just add `su` to the command we want to execute and we are done.

- **Fourthly**, there is another problem; if you screw up the display settings, when messing with external display, you may have hard time resetting them to the defaults on unreadable
  screen. And since this script runs in background anyways while listening for the buttons, it may as well be listening on the external HDMI cable connection/disconnection
  (via kernel events socket) and reset display settings automatically, when the cable is disconnected.
  In fact it is capable of starting any script on connection/disconnection, but in my case I am running display settings reset script 
  from `hdmi-over-usb-c/scripts/reset-fp5-default.sh` relative to this repo's root.

- **Fifthly and lastly**, by splitting the script into root hardware listener, and regular user executor. You introduce a security gap. For example, mere write to whatever the user side
  uses to listen on for commands to execute can escalate from arbitrary write to arbitrary code execution. So no good. This had to be addressed and secured ideally by tightening the
  communications of both parties of the script to only accept data from its counterpart and from nowhere else.

But what do we receive in return?

## TLDR; What this script has to offer?

For me? Mostly quite an assignment to do.  
For you? A handful of features:

- Binding HW actions, like long button press or HDMI port connection changes to custom commands.
- Binding long press of volume buttons to turning on the flashlight in sync with UI.
- Maintaining caller's permissions, security context and the user ID while dispatching custom commands with easy escalation (if needed) to root via `su`.
- Context awareness - the HW buttons bindings are dispatched only when screen was turned off during initial press (off or when on lock screen,
  for turning off the torch and power button bindings). To prevent from, you know, engaging while you are turning up your video (although, now when I think about it,
  the strobe effect for music video here, could be desired. This is how you do it!). This may be annoying while you are listening a podcast in the background, but hey,
  this is supposed to cover. Go ahead and implement yours :P
- Filtering the external devices which may happen to have their own volume up and down buttons.
- Almost zero impact on the battery life, as the script sleeps for the most time (best kind of chores).
- Chef's touch: paranoiac level of security.

And in terms of functionally, that would be it I guess.

It is also worth noting, that the script should not break when python finally gets its true multi-threading,
as I made it fully thread safe (actually it will only benefit from it).

Maybe that's not much, but it is honest and hella expandable work, without even touching the main script sources.

# How do I get this running and what do I need?

## Prerequisites

In general I tried to keep the set of external dependencies as minimal as possible. An that's solely, because I can (GLaDOS would be so proud of me).

So I recommend to install `termux` app, and in the Termux:

- **Root access**, with `su` in PATH, so the script can escalate the permission for events listener side.
  Did you know, that termux comes with `su` which is just a wrapper script for real `su` and you can add there a
  custom path to the target binary? Now you know :)
- `python3`. Which in Termux installs via `pkg install python3`.
- Library from the root of the repo named as `py_and_svc_binds`. 
  This is currently handled by the symlink, but if that fails for you, just copy the whole folder with different name next to the main script.

**I recommend cloning the repo directly on the device in question, to avoid problems like described in the last point above**, so you'll also need `git`.
Install on termux via `pkg install git`.

## Usage examples

In regards of running it (**call as regular, non root user!!**):

1. Simple times version, just turning the flashlight on long press of volume buttons:

Volume down:
```bash
python hw-event-binder.py --vol-down-torch
```
and for volume up:
```bash
python hw-event-binder.py --vol-up-torch
```

2. Instant voice memo on unlock (providing, that the fingerprint reader unlocked the screen):
```bash
python hw-event-binder.py \
        --power-cmd 'su -c "am start -a android.provider.MediaStore.RECORD_SOUND && sleep 0.5 && input keyevent 111 && sleep 0.5 && input keyevent 66 && sleep 0.5 && input keyevent 66"'
```
With this we are causing following chain of events:
```
[power button press] -> [unlock by fingerprint reader] -> [spawning the recorder by binder] -> [delay 0.5s] ->
[spawning power menu] -> [pressing ESC to exit power menu (keycode 111)] -> [delay 0.5s] ->
[pressing Enter (keycode 66) to grab focus back to recorder] ->  [delay 0.5s] ->
[pressing Enter (keycode 66) to actually start recording]
```
TBH, this feels kinda like `vi` style macro shenanigans, and just like `vi` style macro shenanigans it is unreadable and works surprisingly reliable.

3. Discrete silent mode on volume down and restore sound notification on volume up with different haptic feedback:
```bash
python hw-event-binder.py \
        --vol-down-cmd 'su -c "cmd audio set-ringer-mode VIBRATE && cmd vibrator_manager synced oneshot 40 && cmd vibrator_manager synced oneshot -w30 30"' \
        --vol-up-cmd 'su -c "cmd audio set-ringer-mode NORMAL && cmd vibrator_manager synced oneshot 80"'
```
This just asks to be put into script, which will toggle it with a single button (to save the other one for something else, like torch).
But this is a task for the reader :)

4. My use case: 
- volume up for flashlight
- volume down for Wi-Fi traffic capture
- power button for camera. I am taking advantage of simultaneous unlock via fingerprint here, to get
  the camera ready right away after unlock.
- HDMI cable disconnect for resetting to default settings of the display
```bash
python hw-event-binder.py \
                --vol-up-torch \
                --vol-down-cmd '/data/data/com.termux/files/home/aircrack-ng/capture-toggle.sh' \
                --power-cmd 'su -c "/system/bin/am start -a android.media.action.IMAGE_CAPTURE"' \
                --hdmi-dis-cmd 'su -c "/data/data/com.termux/files/home/fairphone5/hdmi-over-usb-c/scripts/reset-fp5-defaults.sh"'
```

Remember, for convenience, each bound command is spawned in a shell, so all constructs like logical and `&&`, or `||`, pipes `|` or redirection to files works just fine directly
from the specified command to execute, but they must be properly quoted, though. At some point it may be easier to just move that to dedicated script and call that.

Also mind, that only one action can be assigned to the button, so you can't use it to both run a command and toggle torch. 
In any other case you may mix the commands anyhow you see fit.

# How do I get this thing running on a system startup?

A couple of ways come to mind to achieve that, but majority of them risks soft bricking a phone, so I won't even mention them.
My preferred way to do this, especially since you likely have `Termux` already installed, is to use extension of it called `Termux:Boot`.

## Termux:Boot

`Termux:Boot` is an add-on app, that can be installed alongside the `Termux` (it uses shared App's user feature of Android, which can only be pulled off
if the apps are signed with the same key) to give it access to the `Termux` environment. 
This is by far the safest, simplest and most flexible way of handling auto-start.

## Where to find it
The apk can be found here [Termux:Boot](https://github.com/termux/termux-boot), available also on F-Droid. 
Naturally, it requires base `Termux` apk to operate.

## How it works?

Simple, just create/upload a script with execute and read access in directory `~/.termux/boot/` (`/data/data/com.termux/files/home/.termux/boot`) in Termux app.
And the `Termux:Boot` will execute it on the next system start up.

If you are doing upload of boot script through adb, make sure the target script owner is the same, as the Termux's app base folder (/data/data/com.termux).

## Example

We are going to invoke commands directly in Termux, including `nano`, which can be installed in Termux via `pkg install nano`.

1. Create the script's base folder, and make sure it has proper permissions:
```bash
mkdir -p /data/data/com.termux/files/home/.termux/boot
chmod 700 /data/data/com.termux/files/home/.termux/boot
TERMUX_UID=$(stat -c "%u" /data/data/com.termux); chown $TERMUX_UID:$TERMUX_UID /data/data/com.termux/files/home/.termux/boot
```

2. Open your script via `nano` editor (here called `init.sh`):
```bash
nano /data/data/com.termux/files/home/.termux/boot/init.sh
```

3. Paste the content. I recommend to use full paths, plus make sure the `hw-event-binder.py` script call is at the very end of the boot script.
   Example invocation in `init.sh` script, for my use case:
```bash
#!/data/data/com.termux/files/usr/bin/bash

# <Some other commands to execute on boot. THEY MUST BE NON-BLOCKING.>

/data/data/com.termux/files/usr/bin/python \
        /data/data/com.termux/files/home/fairphone5/hw-tinkering/hw-event-binder/hw-event-binder.py \
                --vol-up-torch \
                --vol-down-cmd '/data/data/com.termux/files/home/aircrack-ng/capture-toggle.sh' \
                --power-cmd 'su -c "/system/bin/am start -a android.media.action.IMAGE_CAPTURE"' \
                --hdmi-dis-cmd 'su -c "/data/data/com.termux/files/home/fairphone5/hdmi-over-usb-c/scripts/reset-fp5-defaults.sh"' \
        >/dev/null 2>&1 # Do not care about logs. We can always re-run it later manually if something is wrong.
```

Exit `nano` by pressing `ctrl+x`. Termux should have extended keys overlay above the standard virtual keyboard, with the `ctrl` key.

4. Make sure the permissions are right, invoke (assuming that the script is called `init.sh`)
```bash
chown $TERMUX_UID:$TERMUX_UID /data/data/com.termux/files/home/.termux/boot/init.sh
chmod 700 /data/data/com.termux/files/home/.termux/boot/init.sh
```

Now your `init.sh` script should be invoked on the boot, alongside all the commands inside.

## Caveats

Make sure the `hw-event-binder.py` script is the last thing executed in the init script, as it never exits blocking the execution of subsequent commands.

## Limitations

The only downside I can think of regarding this method is that, the phone must be unlocked for the first time after the reboot, to get the auto-start going.
By extension it won't save you if you screw up so bad, that you won't be able to unlock the phone for the first time.
