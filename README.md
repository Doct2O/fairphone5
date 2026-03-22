# What's up with this repo

I've created this repo, as I am now in possession of the Fairphone 5, and I want to keep my discoveries somewhere (hopefully someone else can make some use of it).

The trigger for such a device hop was broken physical button (vol down) and deteriorated battery in my previous phone. This wouldn't be a problem in itself - 
I am fully capable to pull off such a fix - but to get it working again I'd need to un-glue whole phone which is tedious. Not to mention that I'd need to find spares first.  
At this point I am fed up with phones breaking and subsequently having harder time fixing them, than it needs to be.

**BESIDES THAT, I REALLY HATE SWITCHING BETWEEN THE PHONES AND TRANSFERRING ALL MY STUFF**

My phone can easily reach a lifespan of 5 years and more (basically until it is foobar), so the longer I am able to rejuvenate it, the better.
Moreover, cutting-edge technology in terms of GPU or camera in a smartphone is secondary for me (Wi-Fi 6 and 5G upgrade alongside transition to FP5 was neat, though).
 
And after seeing some disassembly (which is sooo easy, as a matter of fact) of the Fairphone 5 and confirming that: specs are good enough for me and LineageOS works there too,
it became the device of choice.

# My setup

I am running not modified FP5 in any Hardware way (yet, anyway).  
The phone is powered by LineageOS (https://wiki.lineageos.org/devices/FP5/),
rooted with Apatch (homepage: https://apatch.dev/install.html, github: https://github.com/bmax121/APatch).  
Magisk (https://github.com/topjohnwu/Magisk) is alright too, but it is a longer story, why I switched to Apatch.

Pretty much all instructions/tips/tricks/hacks contained in this repo will silently assume such a setup.

If something is not working, please refer to the date of the commit in which given text was authored, and confront it with
the version of the setup and packages of this time (if not explicitly stated, I am trying to provide this info, tho), as all
stuff described was tested.  

Please also refer to tags placed on commits, to see on which version of LineageOS given repo state was ran upon.
Commits and changes following a tag, refers exclusively to the version from the tag preceding them and there is no guarantee that
they would work on any other version (on the previous ones in particular, as I may be too lazy to keep the tags up-to-date 
if nothing is broken after LineageOS bump :P).

**!!! AND GENERALLY AND I MEAN IT, IT'S BEST TO USE WHOLE REPO AS IS - DON'T SEPARATE SCRIPTS, ESPECIALLY IF THEY DEPEND ON EACH OTHER. IT'S NOT ME, IT'S HOW ANDROID OPERATES !!!**

# Repo layout

I will mostly keep here info/commands/instructions to run to achieve something, this, or scripts if they are absolutely necessary.
Less logic == easier maintenance.

* `doc` - Documentation for the adjacent HW, and the phone itself. Most prominently Fairphone's 5 service manual with complete schematic in it.
* `radio` - Radio-Frequency related stuff. For now: Wi-Fi, GPS and cellular.
* `stock-rom-files-extraction` - Description how to extract files from the stock Fairphone 5 ROM.
* `hdmi-over-usb-c` - Description how to get working the screen mirroring on the external display, via USB-C on LineageOS. It is surprisingly finicky.
* `hw-tinkering` - Instructions on reconfiguring, messing and interfacing with the hardware, not necessarily as makers intended to :)
* `py-and-svc-binds` - Python module with bindings to native Android services and to `libbinder_ndk.so`. Depended scripts sym-links to it, 
  so if you decide to use them outside the repo (**HIGHLY UNRECOMMENDED**) you need to dereference the symlink. Also thorough description of the whole `binder` mess in Android.

# Mandatory disclaimer

I am not responsible for the damage or losses that you can potentially incur to your device by following steps or using scripts stored in here 
(even though it is unlikely, especially if you have at least slightest idea of what you are doing).

Nevertheless messing with root privileges could be nerve wracking, especially since I facilitate that on someone else's device (:

Anyway, have fun!