# Enabling monitor mode

**You have to run all the commands here as a root to get it working.**

To enable Wi-Fi adapter monitor mode, simply call in the console (adb shell, termux):
```bash
svc wifi disable
killall wpa_supplicant

ifconfig wlan0 down
echo "4" > /sys/module/wlan/parameters/con_mode
ifconfig wlan0 up
```

Observant ones may notice that, besides switching the card into the monitor mode, also the `wpa_supplicant` is killed and the wifi service is disabled.
This is done as I noticed that when those two are operable, Android tries to claim back the Wi-Fi interface from time to time,
causing the packets capture abruption.

When the wlan0 is in this mode you can use `airodump-ng` to sniff on the Wi-Fi networks.
Please refer to `aircrack-ng` sibling folder to see how to build aircrack tools suite and run them on the Android.

To reset it to the default state, call:
```bash
ifconfig wlan0 down
echo "0" > /sys/module/wlan/parameters/con_mode
ifconfig wlan0 up

svc wifi enable
```