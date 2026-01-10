#!/system/bin/sh

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as a root."
  exit
fi
set -x

setprop sys.usb.config none
sleep 2
setprop sys.usb.controller dummy_udc.0
sleep 2
setprop sys.usb.configfs 2
sleep 2
setprop sys.usb.ffs.ready 1
sleep 2
setprop sys.usb.config none

