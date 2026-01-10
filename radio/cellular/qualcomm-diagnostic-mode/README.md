# Qualcomm Diagnostic Mode on Fairphone 5

Qualcom Diag Mode allows to peek on the actual cellular network packets, that
are exchanged between the phone and BTS (btw. I am curious if it is possible to abuse Phone's modem to 
see other's packets on different channels - even knowing they are encrypted top to bottom - or send completely custom packets,
kinda like poor's man SDR. But this is topic for another time...).

In the Fairphone 5 case I've seen packets up to the 5G in the capture files.
I am nowhere near to the expert in the field, though, and haven't done a lot of poking around that, so
I cannot say 100% if I've seen actual 5G traffic, or some control packets.

I also won't pretend that I know what I am talking about in terms of cellular. Better reference for what is
actually transferred, can be found in the QCSuper tool repo:
https://github.com/P1sec/QCSuper

And as a matter of fact, I will use this tool extensively later on.

This file only contains minimum of steps to get the diag mode working via USB/locally on the device 
(and yes, both QCSuper and diag mode may be run entirely on the device in question, without dealing with USB at all).

If you are curious what is actually going on in here, which driver interfaces with the Qualcomm chip for diag frames,
what the hell the other files and scripts are for, or simply you need some reference for other device.
Then buckle up, as it is quite of a story and go ahead and open `GettingDiagModeToWorkTheCompleteStory.md`.

# Advisory

***DO NOT*** kill the `diag-router` binary, once it was launched. If you do so, the diag protocol won't work beyond that (even after re-launching the `diag-router`). And you will need to restart the whole device to get it working again.

# TLDR; Enabling Diag Mode to dump frames via USB

## Prerequisites

- Clone QCSuper https://github.com/P1sec/QCSuper on the computer, which will be used to capture diagnostic traffic:
```
git clone https://github.com/P1sec/QCSuper.git
(cd QCSuper && git checkout f5f1501c7ce09f6c167ae623233f674be09cdf87)
```
Also follow Installation steps in that repo, so in the end the script is operational.
For above commit it will be something like this:
```
pip install --upgrade pyserial pyusb crcmod https://github.com/P1sec/pycrate/archive/master.zip
```
- Plug in the phone via USB to the computer 

## Steps to follow

***You need root access to carry on with the instructions***

1. Copy the `qm-diag-mode` sibling folder to the phone.
2. ***As a root.*** Execute `./diag-on-usb.sh` script, and wait for a second after the script is done.
   You should see some commotion about new USB devices on the PC.
3. Navigate to the cloned repo of QCSuper and run the QCSuper on the host PC: 
   ```
   ./qcsuper.py --usb-modem auto --pcap-dump /tmp/my_pcap.pcap
   ```
   If you are unsure whether the packets are actually captured (the pcap file does not need to increase its size immediately),
   run the `QCSuper` in the verbose, debug mode:
   ```
   # More 'v' the better (not really :D)
   ./qcsuper.py -vvvv --usb-modem auto --pcap-dump /tmp/my_pcap.pcap
   ```

   The log from the qcsuper, should look something like this:
   ```
   [15:02:45 | INFO @ _enable_log_mixin.py:141 ] Enabled logging for: 1X (1), WCDMA (4), GSM (5), UMTS (7), DTV (10), APPS/LTE/WIMAX (11), TDSCDMA (13)
   [15:02:50 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:02:54 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:03:02 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:03:03 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:03:06 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 39: b'<redacted python bytes hex string>'
   ```

   If the traffic seems to be dormant (nothing comes after `INFO @ _enable_log_mixin.py:141`), try to dial some USSD code,
   for example, check your credit balance (the code doesn't even need to be valid).
   This should generate a bit of traffic.

4. ***As a root.*** To disable diag mode on the USB, call:
```
./diag-off-usb.sh
```

# TLDR; Dumping diag messages locally on the device/via network - no USB whatsoever variant.

This method is superior to the previous one, as it does not need fiddling with the USB composition at all.
All you need is mounted functionfs, and the `diag-router` binary, which supports sending frames
to network socket instead of default USB gadget (and root access of course).  
Luckily the Fairphone 5 meets both of those criteria.

# Advisory

***DO NOT*** kill the `diag-router` binary nor the `diag-router-router.py` script, once it was launched. If you do so, the diag protocol won't work beyond that (even after re-launching them both). And you will need to restart the whole device to get it working again.

The `diag-router-router.py` allows only one connected client at once on both sides of the socket, so please keep that in mind, if your connection has been rejected.

## Prerequisites

- Termux
- Termux packages `git python python-pip`.
  Install by:
  ```
   pkg update && pkg upgrade
   pkg install -y git python python-pip
  ```
- Clone QCSuper https://github.com/P1sec/QCSuper on the computer/directly to the device, which will be used to capture diagnostic traffic:
```
git clone https://github.com/P1sec/QCSuper.git
(cd QCSuper && git checkout f5f1501c7ce09f6c167ae623233f674be09cdf87)
```
Also follow Installation steps in the QCSuper repo, so in the end the script is operational.
For above commit it will be something like this:
```
pip install --upgrade pyserial pyusb crcmod https://github.com/P1sec/pycrate/archive/master.zip
```

## Steps to follow

***You need root access and `su` binary to carry on with the instructions***

1. Copy the `qm-diag-mode` sibling folder to the phone.
2. Run the `diag-on-loc.sh` ***Do NOT run as root, but still you need working `su` binary***:

- For PTY mode: 
```
./diag-on-loc.sh
```
or
```
./diag-on-loc.sh --pty
```

- For network socket mode:
```
# For access from outside, just use IPv4 address of Wi-Fi adapter 
# accessible via local network, instead of 127.0.0.1, 
./diag-on-loc.sh --socket 127.0.0.1:54321
```

If you change your mind, you can simply switch between them just by running the script again, with different arguments.

3. Run the `qcserial.py` and connect to the created bridge:

- For PTY mode:
```
# The diag-on-loc.sh script creates link to current PTY next to its source file for sake of simplicity,
# but qcsuper accepts char device only, so we resolve the link in fly via readlink.
./qcsuper.py --usb-modem $(readlink -f qm-diag-mode/ttyDiag) --pcap-dump dump.pcap
```

- For socket mode (either on the phone in Termux, or - after changing the IP here - on some other machine in the same network as the phone):
```
./qcsuper.py --tcp 127.0.0.1:54321 --pcap-dump dump.pcap
```

If you are unsure if the packets are actually captured (the pcap file does not need to increase its size immediately),
   run the `QCSuper` in the verbose, debug mode:
   ```
   # More 'v' the better (not really :D)
   ./qcsuper.py -vvvv (...)
   ```

   The log from the qcsuper, should look something like this:
   ```
   [15:02:45 | INFO @ _enable_log_mixin.py:141 ] Enabled logging for: 1X (1), WCDMA (4), GSM (5), UMTS (7), DTV (10), APPS/LTE/WIMAX (11), TDSCDMA (13)
   [15:02:50 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:02:54 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:03:02 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:03:03 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 32: b'<redacted python bytes hex string>'
   [15:03:06 | DEBUG @ _base_input.py:395 ] [<] Received log 0xb0c0 of length 39: b'<redacted python bytes hex string>'
   ```

   If the traffic seems to be dormant (nothing comes after `INFO @ _enable_log_mixin.py:141`), try to dial some USSD code,
   for example, check your credit balance (the code doesn't even need to be valid).
   This should generate a bit of traffic.

4. To terminate the session, end the `qcsuper.py` script first (so the diag session stops gracefully), and then just call:
```
./diag-off-loc.sh
```
This closes the data source on the `qcserial` side, making diagnostic data inaccessible.
To reopen it at any time, just use the script `diag-on-loc.sh` again.

5. ***Extra:*** To check current status of the `diag-router-router.py`, simply call:
```
./diag-on-loc.sh --status
```
e.g.
```
~/qm-diag-mode $ ./diag-on-loc.sh --status
PORT_A_PORT=39299
PORT_A_CONNECTED=yes
BACKEND_TYPE=pty
BACKEND_INFO=/dev/pts/4
BACKEND_LISTENER_ACTIVE=no
```