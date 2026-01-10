# The complete story of Qualcomm Diagnostic Mode on the Fairphone 5 and Android in general

### How diag info gets to Android, or a tale of a great waste of my time

To have an insight into diagnostic info from the Qualcomm chip, you need a proper kernel driver.
In previous Android versions, which was running older kernel (according to the QCSuper repo up to 4.14), this was done
via `/dev/diag` and was enabled by `CONFIG_DIAG_CHAR` in the kernel build config.

In such a case qcsuper copies a bridge binary via adb to the device (32 bit ELF btw, it gave me a bit of headache, 
but in the end it doesn't matter, as it was vain attempt on my side).
When already on-site, the bridge binary opens the `/dev/diag` device and streams the diagnostic frames back
and forth via network socket.

---
Why I am talking about it? 
Well, back then, after looking into the sources of the LineageOS kernel I came to the conclusion (wrongly, mind you) that this
driver is missing, and need to be ported. Aside of that, this `[device endpoint]<->[bridge program]<->[qcsuper]`
architecture will come back later, but in a bit different form.

Actually I even managed to port `DIAG_CHAR` driver from Fairphone 4 and get it insmoded on Fairphone 5, without kernel panicking.

But well, long story short: it didn't work.  
I mean the `qcsuper` copied the bridge (recompiled by myself for 64bit system). But it failed to enable the diag mode
at first: there were problems with the frames lengths. Later, after addressing that, driver just didn't respond and crash.  
4 days well spend (that, not including the LineageOS system build).

Okay - I thought to myself - maybe I need to set some props to change the USB composition. 
This is how it worked on my previous phone (and previous phone indeed got the `/dev/diag` device,
 so I didn't take that porting part out of the blue. I promise.).

---
To wrap up the diag device matter.  
As it turns out, in more modern Linux kernels for Android, the `/dev/diag` was somewhat replaced with `/dev/ffs-diag*/ep*`.
Included in kernel with option `CONFIG_CONFIGFS_FS` and `CONFIG_USB_CONFIGFS_F_FS` according to https://github.com/j0lama/diag-router.
Not sure, though if the underlying framework changed, and I am talking here about both: the one which talks with the hardware itself, and the one exposed to the system.  
But I will get back to it in details furthermore.

### USB composition

To get the diag mode working on my previous phone, or at least to enable QPST tools (https://qpsttool.com/) to work with the phone,
the USB composition had to be switched to the proper mode.
The phone in that mode reported itself as a bunch of the COM/serial ports on the host PC.
The `qcsuper` README talks about this as well. So surely this must be it, right?

Well yes, but not entirely.

The problem was that, no variant of the `sys.usb.config` found on the internet worked for Fairphone 5.
The phone never reported more than a mere ADB port (if anything at all).

Nevertheless those sites, are worth mention:

- https://band.radio/diag
- https://droidwin.com/how-to-boot-qualcomm-device-to-diag-mode-via-adb-commands/

So, due to my persistent creature nature, I've started to search for the origin of those props. And boy, I found them.

---
The USB composition and actions taken while it is switched, are stored in the \*.rc scripts on the `/vendor` partition.

Most prominently, for LineageOS it is kept in `/vendor/etc/init/hw/init.qcom.usb.rc` and by searching by known VID+PID of the diag port,
I found couple of promising hits.

As it turns out, on the Fairphone 5 it is not as simple as just setting `sys.usb.config` properly.
When reading the entries in the `init.qcom.usb.rc` one can notice, that more than just a single prop one is considered, while switching USB composition.

Namely:

- `sys.usb.controller`, which must be set to the proper device - `a600000.dwc3`
- `sys.usb.configfs`, which must be set to `1`. At first it is indeed 1, but then it is changed to 2 when bootloaders are done bootloading.
- `sys.usb.ffs.ready`, which must be set to `1`. It indicates, that `/dev/ffs-diag*/ep*` endpoints are available.

Retrospectively may set by ***(Must be run as root)***:

- `setprop sys.usb.controller a600000.dwc3`
- `setprop sys.usb.configfs 1`
- `setprop sys.usb.ffs.ready 1`

And after reading some more boot scripts from `/vendor`, to be precise `/vendor/bin/init.qcom.usb.sh` of LinegeOS build.
It turns out the proper value of `sys.usb.config` for Fairphone 5 and its SoC is: `diag,serial_cdev,rmnet,dpl,qdss,adb`.
Other ones work as well (for the most part). But this one is intended by the manufacturer.

---

Now about the `sys.usb.controller` set as `a600000.dwc3`. Originally it equals to `dummy_udc.0` when phone is fully booted. 
The value of this prop in fact comes from `vendor.usb.controller`, as defined in the `init.qcom.usb.rc` script. 
And in turn `vendor.usb.controller` comes from file `/vendor/etc/init/hw/init.target.rc` of the LineageOS, and is hardcoded there to `a600000.dwc3`.
After checking it against the device tree, it seemed to be correct. Didn't investigate why it was dummy in the first place, but don't really care.

Btw. I wouldn't be myself, if I didn't check what happens if you use `dummy_udc.0` instead of the proper device. Long story short,
kernel panic occurs and phone reboots (:

Lovely! So, we are done, right? ...nope, not even close, as you probably may tell, by mere existence and abundance of the next chapters.

### Diag router

And here comes "Well yes, but not entirely." part of the previous chapter.
As it turned out the composition is well and good, but it still it doesn't report ANY USB device to the PC.

Now, in the desperate move I started to search for anything `diag` related on the vendor partition.
Saying no more I found a lot of hits, but just a single one was particularly interesting - 
an entry in file related to seLinux config called: `/vendor/etc/selinux/vendor_file_contexts`, 
the entry looks like this: `/vendor/bin/diag-router         u:object_r:vendor_diag-router_exec:s0`.

---

Soo, by pure deduction:<br/>
On the `/vendor` partition, surely there is a `diag-router` binary, which has something to do with the diagnostics. 
It does reminisces bridge from the qcsuper, when `/dev/diag` endpoint is present, doesn't it?

Soo, I was wrong in the first part - there is no such binary in the Lineage's vendor partition. Bummer.  
But on the bright side, now I know that my guess pretty much nailed what this binary does ;)  
Maybe in the end porting the diag driver and diving into inner workings wasn't futile after all...ehh, silver-lining.

Enter the Internet. It surely comes for rescue with such an executable, right?

Well, again, partially true but don't get ahead of myself.

---

I've found something like this: 
https://github.com/j0lama/diag-router

As it turns out, according to the README of that repo, you need to have enabled following options in your Kernel (can be verified by grepping `zcat /proc/config.gz`): 

- CONFIG_CONFIGFS_FS
- CONFIG_USB_CONFIGFS_F_FS 
- CONFIG_USB_GADGET

to get the diag mode working. Thankfully LineageOS enables all of them by default in Fairphone 5.

The first one responds for the diagnostic devices `/dev/ffs-diag*/ep*`. The one which we are particularly interested in, can be mounted like this:
```
mkdir -p /dev/ffs-diag
mount -t functionfs diag /dev/ffs-diag -o uid=2000,gid=1000,rmode=0770,fmode=0660,no_disconnect=1
```
Again inspired by vendor's .rc script `/vendor/etc/init/hw/init.qcom.usb.rc`.

The two former ones (as far as I understand) are responsible for generating and sending the messages to the USB stack via USB gadget (kernel's way to enable userspace programs to send data via USB stack). The configfs can be mounted as follows:
```
mkdir -p /config
mount -t configfs none /config
```
Also inspired by vendor's .rc script `/vendor/etc/init/hw/init.qcom.usb.rc`.

And it MUST be mounted on the root of the filesystem and not in `/sys/kernel/` as `diag-router` repo describes, since Fairphone 5 vendor's
.rc scripts expect it to be on the root.

But going back to the `diag-router`. After commenting out lines the at beginning of the file `Makefile`:
```
HAVE_LIBUDEV=1
HAVE_LIBQRTR=1
```
and adding `#include <strings.h>` in the file `router/socket.c` and then calling `make`, it even builds under termux.

Lovely, running it as a root...
```
# ./diag-router
```
and boom! We got our device listed on the PC, even the diagnostic port is there!

So... happy ending?

### More of the diag-router

Well, not exactly a happy nor an ending.

At this point all that left was try to run qcserial on the PC host. To my surprise it indeed talked via the diag protocol and seemed to enable the diag logging.
And to my other surprise, it stopped here and became silent:
```
$ ./qcsuper.py -vvvv --usb-modem auto --pcap-dump /tmp/my_pcap.pcap
(...)
[23:44:26 | DEBUG @ _base_input.py:384 ] [<] Received response DIAG_LOG_CONFIG_F of length 83: b'\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\r\x00\x00\x00\xff\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
[23:44:26 | INFO @ _enable_log_mixin.py:141 ] Enabled logging for: 1X (1), WCDMA (4), GSM (5), UMTS (7), DTV (10), APPS/LTE/WIMAX (11), TDSCDMA (13)
```

---
The pcap file didn't grow in size either, so something was clearly wrong. But at this point I had no idea what.

When you encounter predicament like this, there is only one thing you can do in such a situation:
~~change chaotically all the parameters and pray. Then, when that does not work, cry in the corner~~.   
Ekhem, I meant to say: reassess all the possibilities, then make an educated guess and test the most possible root cause based on your own experience
(too shame I didn't have any experience in that department at that time XD).

So I made my uneducated guess, or more like 5th one (but at least I didn't cry in the corner).  
I decided to glimpse into the original `/vendor` partition from the Fairphone, to look for the clues 
(frankly, at this point I didn't even know whether the diag mode works on the stock ROM, but I had nothing else to work with).  
To see how to dump files from the stock ROM, please refer to README in the folder `stock-rom-files-extraction` from this repo root.

In there, I found definition of the `vendor.diag-router` service, which is starting the `diag-router`. The definition is stored in the file `etc/init/vendor.qti.diag.rc`.  
Frankly it looked promising, so I swept through the `/vendor/bin` for the `diag-router` binary and
this time - like the brightest star in the sky (yeah I mean the sun) - it was sitting right there.

I transferred it to my LineageOS, resolving along the way problems with missing .so libs: `libqrtr.so libqsocket.so` 
by copying them from the Faiphone's stock ROM `/vendor/lib64`.

Ran it as root (providing that .so libs copied from vendor are next to the `diag-router` binary):
```
LD_LIBRARY_PATH=. ./diag-router 
```

Give it another go with qcsuper.py. And this time, surely, it worked.  
The festies had no end, the battle was legendary, and so on and on with this kind of nonsense.

### diag-router... router...?

The story could end right here, right now. As a matter of fact, by the glorious victory.

Still, though, I had this intrusive thought: "Wouldn't it be so cool, to get this running all locally on the smartphone, without need for external USB host?".
Thus, I couldn't help myself and I kept poking the `diag-router` binary to see if this pony knows any other trick.
And girl, it is full blown unicorn.

If you look at the help string of it:
```
# LD_LIBRARY_PATH=. ./diag-router -h         
User space application for diag interface

usage: diag [-hsud]

options:
   -h   show this usage
   -s   <socket address[:port]>
   -u   <uart device name[@baudrate]>
   -d   <debug level mask>
```
Particularly curious option of `-s` unfolds.
Careful readers could also notice something else - the program by default is called `diag`, as stated in `usage` line.
So in general it is worth also to search for `diag` binary if `diag-router` is nowhere to be found.

But back to our `-s` option. There were two possibilities what it does:

- Either it consumes diag data on this socket, instead of `/dev/ffs-diag` and passes it to USB
- Or it still takes diag data from `/dev` but instead to USB gadget, it streams it via socket.

And there is only one way to find out.  
Enters socat (naturally you need to have it installed in Termux for that `pkg install socat`).  
For a quick verification I put together a simple: TCP socket listener to TCP socket listener socat bridge, as luckily the upstream qcsuper is also
capable of connecting to TCP server for diag data.

Here is the socat command:
```
socat TCP-LISTEN:4321,reuseaddr,fork TCP-LISTEN:1234,reuseaddr,fork
```

So in theory, now we can start diag server and point it to one end of socat, like this (given the .so libs copied from vendor are next to the `diag-router` binary)
***You need to run this command as root***:
```
LD_LIBRARY_PATH=. ./diag-router -s 127.0.0.1:4321
```

And on the other end, it should be possible to connect using qcsuper, and hopefully it will work just like through USB:
```
./qcsuper.py -vvvv --tcp 127.0.0.1:1234 --pcap-dump dump.pcap
```

And surely enough it worked!
```
[16:02:06 | INFO @ _enable_log_mixin.py:141 ] Enabled logging for: 1X (1), WCDMA (4), GSM (5), UMTS (7), DTV (10), APPS/LTE/WIMAX (11), TDSCDMA (13)
[16:02:12 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python hex bytes>'
```

Sooo, now we confirmed that we actually do not need the USB gadget at all. And everything can go through network.
Lovely, but there is just a tiny tiny (it doesn't sound so good on paper :P) problem.

The `diag-router` can be spawned only once and if it is terminated for any reason, and re-spawned later on, the diag protocol does not work and refuses to stream the frames anymore.
Consequentially we either cannot terminate the socat's bridge in such a setup, cause the diag router won't reconnect to another socket, as it only does it at the start-up.

And this poses a security threat, as if that would going like this in the background, pretty much anyone can read diagnostic messages from the socket on your phone. And I don't know
how about you, but for me it is a major concern. 

Besides that, it would be nice to have some more flexibility and be able to change the port, or listening address to not listen for everything all the time.
Ideally I'd like to have some local tty, to which qcsuper would connect, if I don't want to collect the frames externally. And if I feel like remote diag collection, close this
tty and switch to the remote port. And finally if I don't need diag messages right now, I'd like to shut down the other end completely and just stay connected with `diag-router`.

With that being said, I ran some additional tests, and it turns out, that qcsuper happily accepts not only real ttyUSB but also pseudo terminal slave endpoint as well.  
In general described functionality could be realized by spawning two socats, but it gets pretty cumbersome pretty quickly.

---
Knowing all that, I rolled up ~~my~~ chat's sleeves (Don't hate on me for vibe-coding. I was away from PC back then only with my phone,
and it is way more convenient to just generate script, than borderline impossible write it on the phone's virtual keyboard.
But if you feel uncomfortable with this, PRs are welcome :) )
And in the result I got the script `diag-router-router.py` (everything wasn't so rainbow and sunshine with the LLM's code, though, and I got to make some fixes by hand anyways).
But at least it seem to be functional now.
Keep in mind, though, this is still more like a PoC than a final script.

Here are steps how to put together such setup:

1. Spawn the script, you can either specify the `diag-router`'s side port via `-p` or the ephemeral one will be used.

For ephemeral port (the script will report the port on which it listens):
```
$ ./diag-router-router.py&
2026-01-08 16:35:06,641 [INFO] Port A listening on 127.0.0.1:39713
```
If you missed that you can also ask for the status:
```
$ ./diag-router-router.py --cmd status
PORT_A_PORT=42925
PORT_A_CONNECTED=no
BACKEND_TYPE=none
BACKEND_INFO=none
BACKEND_LISTENER_ACTIVE=no
```

For concrete port, simply call:
```
./diag-router-router.py -p 4321&
2026-01-08 16:35:06,641 [INFO] Port A listening on 127.0.0.1:4321
```

2. Get the port from the point 1, and run the `diag-router` accordingly e.g. (given the .so libs copied from vendor are next to the `diag-router` binary) 
***You need to run this command as root.***:
```
LD_LIBRARY_PATH=. ./diag-router -s 127.0.0.1:4321&
```

3. Now the `diag-router` will route the diag frames to the `diag-router-router` (the sound of this sentence is killing me XD), and will keep the connection alive.  
***DO NOT KILL EITHER OF THEM***, as after termination, the diag session cannot be re-established with the system. To do so device reboot is required.
If you want to run it continuously it is recommended to launch it via `nohup`.

4. Expose the other end of the `diag-router-router`:

- via socket: `./diag-router-router.py --cmd "bind 127.0.0.1 1234"`
- via pty:    `./diag-router-router.py --cmd pty`

To switch between them/reopen, first close the active backend.
```
./diag-router-router.py --cmd close
```
And then call variant of one of commands from the begining of this point according to your likings.

5. Connect to this via `qcsuper`:

- via socket (requires upstream master branch): `./qcsuper.py -vvvv --tcp 127.0.0.1:1234 --pcap-dump dump.pcap`
- via pty: `./qcsuper.py -vvv --usb-modem /dev/pts/4 --pcap-dump dump.pcap`

If you are unsure if the `diag-router-router` is currently active and where the data is streamed, simply call `status` command i.e.:

PTY:
```
$ ./diag-router-router.py --cmd status
PORT_A_PORT=42925
PORT_A_CONNECTED=no
BACKEND_TYPE=pty
BACKEND_INFO=/dev/pts/4
BACKEND_LISTENER_ACTIVE=no
```

socket:
```
$ ./diag-router-router.py --cmd status
PORT_A_PORT=42925
PORT_A_CONNECTED=yes
BACKEND_TYPE=socket_b
BACKEND_INFO=127.0.0.1 1234
BACKEND_LISTENER_ACTIVE=yes
```

6. Once you are done with sniffing around, simply close the `qcsuper` first (so the diag session will be gracefully closed) and then its side of a bridge, by calling:
```
./diag-router-router.py --cmd close
```
The `qcsuper` side can be reopened at any time in any mode at demand.

7. Profit

I am also providing a nifty scripts which abstract out this whole struggle, either to use diag mode locally: `diag-on-loc.sh` and `diag-off-loc.sh`
or via USB: `diag-on-usb.sh` and `diag-off-usb.sh`. But please remember if you make your mind and give a go for one family of scripts, the other won't
work until you restart the phone (`diag-router` must be re-ran with different arguments and after its termination diag session in system is lost for good).

But for detailed instruction on their usage please see the main README of this folder.