#!/system/bin/sh

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as a root."
  exit
fi
set -x

if [ "$#" -eq 0 ] ; then
	# Diag mode USB composition intended by manufacture for the Fairphone's 5 SoC.
	# Can be overridden by the script's argument.
    MODE="diag,serial_cdev,rmnet,dpl,qdss,adb"
else
    MODE="$1"
fi

if ! test -d /config/usb_gadget ; then
	mkdir -p /config
	mount -t configfs none /config
fi

if ! test -e /dev/ffs-diag/ep0 ; then
	mkdir -p /dev/ffs-diag
	mount -t functionfs diag /dev/ffs-diag -o uid=2000,gid=1000,rmode=0770,fmode=0660,no_disconnect=1
fi

if ! pidof diag-router >/dev/null ; then
	LD_LIBRARY_PATH="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" \
	   nohup "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/diag-router" >/dev/null 2>&1 &
fi

setprop sys.usb.config none
sleep 2
setprop sys.usb.controller a600000.dwc3
sleep 2
setprop sys.usb.configfs 1
sleep 2
setprop sys.usb.ffs.ready 1
sleep 2
setprop sys.usb.config "$MODE"
