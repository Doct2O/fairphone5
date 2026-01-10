# aircrack-ng running natively on the Android

## Building the aircrack
The build will be done directly on the target device, using the termux and it's development packages, in contrast to cross-compiling via
Android NDK, as the latter may be a major pain to build Linux destined sources. 

### Prerequsites
- Termux
- Termux packages: `git libtool pkg-config autoconf-archive automake binutils libnl`
   Install by:
   ```bash
   pkg update && pkg upgrade
   pkg install -y git libtool pkg-config autoconf-archive automake binutils libnl
   ```
   This will also install additionally:
   ```
   clang gdbm glib libcompiler-rt libcrypt libffi libicu libllvm libsqlite libxml2 lld llvm ncurses-ui-libs ndk-sysroot python python-ensurepip-wheels python-pip
   ```
   So all packages needed for build should be there. Proceed with the build process in following `Build process` chapter. 

### Recommendations
Build the aircrack (and anything else for that matter), while charging and screen on (you can enable keeping the screen on, while plugged in somewhere in Android's hidden dev options).
This will guarantee that you have most of the performance and the build won't take longer than it needs to take.

Call the built binaries while being in the repo root. This allows to avoid some weird .so library loading errors.

### Build process
1. Clone the sources of the aircrack and checkout the proper version (you can eagerly try latest main, the hash is provided here, just for working reference)
```bash
git clone https://github.com/aircrack-ng/aircrack-ng.git
(cd aircrack-ng && git checkout f333a6a767dc83c7da352de59dbca402fe3bf70c)
```

2. Move to the cloned folder and call `autogen.sh` script:
```bash
cd aircrack-ng
./autogen.sh
```

3. Build the aircrack, simply call:
```bash
make
```
The build should go smoothly, the binaries will be placed at the root of the cloned repo. 
It is recommended to call them while being there, to avoid some weird dynamic library loading errors.

### Running the binaries on Fariphone 5
***Please refer to the monitor-mode sibling folder, to see how to enable monitor mode on your wlan adapter, as it needed for airodump.***

***You need the root access, to run the airodump binary***

Once the ***adapter is in the monitor mode***, simply call `./airodump-ng wlan0`, while being in the repo root folder.
If everything is okay, you should see the Wi-Fi networks around you.

### Capturing the 2.4Ghz and 5Ghz band Wi-Fi networks
In general to select the frequency to perform the sniffing on, one can use `--band` option of airdump-ng.
The option goes as follows:

- `--band a` - sniff on 5Ghz only
- `--band bg` - sniff on 2.4Ghz only (default, when none specified)
- `--band abg` - sniff on both bands 2.4 and 5Ghz

So to capture packets on all bands on Fairphone 5, just call:
`./airodump-ng wlan0 --band abg`

### Geo-tagging packets via GPS
Another neat feature of the `airodump-ng` is ability to geotag the networks that has been detected.
Furthermore regular smartphone is pretty much perfect for that, as all the necessary hardware is usually already there.

The only challenge is that airodump uses `gpsd` service to access current location.
In turn, Android uses completely different framework and philosophy to access the geo-location data.
Saying no more, gpsd does not work on Android out of the box.

Thankfully, I managed to get `gpsd` working. Please refer to the `radio/gps/gpsd` folder for info, how to:
build, setup and start the `gpsd`, to wire it up with `airodump-ng`.

***Mind to actually start gpsd before running the airodump***.

On the airodump site, to enable geotagging, simply add the `--gpsd` flag to the
`airodump-ng` call e.g. for Fairphone 5:
```bash
./airodump-ng wlan0 --band abg --gpsd
```

After that you will see additional `[GPS (...)]` section on top of the status screen. If everything went well, after a while, when GPS
has pinpointed your location, you should see the coordinates and the last time they were updated.
***REMEMBER TO TURN ON THE LOCATION IN ANDROID SETTINGS***

### Further consideration
Please see the aircrack-ng project site (https://www.aircrack-ng.org/) for further info on this tools suite.