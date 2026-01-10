# gpsd running natively on the Android

## Building the gpsd service
The build will be done directly on the target device, using the termux and it's development packages, in contrast to cross-compiling via
Android NDK, as the latter may be a major pain to build Linux destined sources. 

### Prerequsites
- Termux
- Termux packages: `git python python-pip libandroid-shmem binutils`
   Install by:
   ```bash
   pkg update && pkg upgrade
   pkg install -y git python python-pip libandroid-shmem binutils
   ```
- python package: `scons`
   Install by:
   ```
   pip install scons 
   ```
   After this all packages needed for build should be there. Proceed with the build process in following `Build process` chapter. 

### Recommendations
Build the gpsd (and anything else for that matter), while charging and screen on (you can enable keeping the screen on, while plugged in somewhere in Android's hidden dev options).
This will guarantee that you have most of the performance and the build won't take longer than it needs to take.

***SECURITY AND PRIVACY CONCERN***  
Please run the `gpsd` only when it is necessary and when you actually are using it (that's why I disable daemon mode by adding flag `-N`,
which should make the process end with user's session).  
Gpsd is by default streaming the location data via socket open for everyone locally (and thankfully not 0.0.0.0).  
Now, I am not sure how seLinux policies are working for sockets on Android, but it does not matter here, as we circumvent them anyway,
by starting `gpsd` as a root and in particular by `su` binary.  
If gpsd is not launched via `su` it does not work properly, likely due to some seLinux policies, but rather not due sockets restrictions (netcat has no problem with establishing connection on port 2947).  
To put it straight, this is a major loophole in the Android permissions control.
And for exactly this reason, in later "Fully terminal approach" my translation script outputs the NMEA sentences via PTY bound to current user and root (in contrast to net socket).
So no one else have access to it.

### Build process
1. Clone the sources of the gpsd and checkout the proper version (you can eagerly try latest main, the commit is provided here just for working reference)
```bash
git clone https://gitlab.com/gpsd/gpsd.git
cd gpsd && git checkout 92660f43b3279e6279ec59010c662b157af4e8de
```

2. Open `SConscript` file to add missing libraries of Android, just after `env` variable declaration, around here:
```
(...)
for var in import_env:
    if var in os.environ:
        envs[var] = os.environ[var]
envs["GPSD_HOME"] = os.getcwd() + os.sep + 'gpsd'

env = Environment(tools=["default", "tar", "textfile"], options=opts, ENV=envs)

# <----------------------------------- around here

# Release identification begins here.
(...)
```

Add following snippet replacing `# <----------------------------------- around here` in the example above:
```
env.Append(LINKFLAGS=[
     '-landroid-shmem'
])
```

So it looks like this:
```
(...)
for var in import_env:
    if var in os.environ:
        envs[var] = os.environ[var]
envs["GPSD_HOME"] = os.getcwd() + os.sep + 'gpsd'

env = Environment(tools=["default", "tar", "textfile"], options=opts, ENV=envs)

env.Append(LINKFLAGS=[
     '-landroid-shmem',
])

# Release identification begins here.
(...)
```
---
Alternatively you can simply apply the patch from the `patches` sub-directory (make sure you are using the commit specified at the beginning,
as the patch may be incompatible otherwise).
Copy the patch to the cloned repo root, and invoke following command in there, to apply:
```bash
git apply 0001-Add-Android-Missing-Lib-To-SConscript.patch
```

3. Build the gpsd. Simply call:
```bash
scons
```
The build should go smoothly, the gpsd binary is placed at: 
`./gpsd-3.27.4~dev/gpsd/gpsd`
Or similar in case of different commit.

### Running the gpsd binary on Android

***You need the root access, to run the gpsd binary, otherwise it does not work. Ask me how I know :)***

Here is the tricky part, as the gpsd expects retrieving the location data by NMEA sentences via network/serial device.
There are couple of ways to achieve that. I'll describe two:

1. The easiest one I could devise is by using `gpsdRelay` app from over here: 
https://github.com/project-kaat/gpsdRelay
The installable apk can be downloaded from releases in there (also can be found on F-Droid).

Once the app is installed, allow the access to the GPS all the time, not only when the app is in the foreground. 

In the app:

- Press the `+` icon at the right bottom
- Select TCP/UDP server (does not really matter which, but some subsequent commands must be adjusted accordingly)
- Input IPv4 as `127.0.0.1` and any port above 1024 and below 65535, really. I'll be further using `12345`.
- Keep only `NMEA generation` on, as the `NMEA relaying` causes aircrack-ng to loose the location periodically
- Press `Add`
- Enable the settings you've just added (the slider next to it must be on)
- Enable GPS
- Press `Play` button at the app top bar (next to the settings gear).

Go back to the Termux and `gpsd` repo folder:

***You need to run following commands as a root***

- Start the gpsd background job as follows for UDP gpsdRelay server:
  ```
  ./gpsd-3.27.4~dev/gpsd/gpsd -n -N udp://127.0.0.1:12345&
  ```
  Start the gpsd background job as follows for TCP gpsdRelay server:
  ```
  ./gpsd-3.27.4~dev/gpsd/gpsd -n -N tcp://127.0.0.1:12345&
  ```

The gpsd should now be running, do not worry if you see something like this, just after starting the gpsd:
```
:/data/data/com.termux/files/home/gpsd # gpsd:ERROR: CORE: stat(udp://127.0.0.1:12345) failed, errno No such file or directory(2)
```
This is normal for network mode.

2. Fully terminal approach.  
This is especially useful when you want to automate everything by a script, without dealing with the external GUI apps.

- Install Termux API extension app: https://github.com/termux/termux-api, the apk can be found there in the releases. It is also available on F-Droid.

- In the Android app settings, assign the location permission and allow constant access to the location, not only while the app is active.
  This will allow us to get the location data in the console. I also highly recommend disabling the notification for the app, as you can be
  easily spammed by them when GPS signal is lost and while constantly querying for the location (which we will).
  
- In the Termux console install Termux's CLI counterpart; termux-api:
  ```bash
  pkg install termux-api
  ```
  Now enable the location on the device, and invoke `termux-location`. The output should look something like this:
  ***This MUST NOT be run as the root***
  ```bash
  ~ $ termux-location
   {
     "latitude": 50.<redacted>,
     "longitude": 18.<redacted>,
     "altitude": <redacted (:>,
     "accuracy": <redacted (:>,
     "vertical_accuracy": <redacted (:>,
     "bearing": 0.0,
     "speed": 0.0,
     "elapsedMs": 13,
     "provider": "gps"
   }
  ```
  If not, make sure the location is enabled on the device and GPS signal is reachable. Confirm that in some maps or something.

- Now, all we need is something that will translate the `termux-location` json to the NMEA sentences, so we can shove that to the gpsd.
  For that, I've vibe-coded (don't judge me, I was away from my PC back then, only with the smartphone in hand. And generating the script is
  much more convenient than writing it on the touch screen ;) ) following python script `termux-api-gps-to-nmea-pty.py`. It can be found in the `scripts`
  folder.

- Get the script to the device and run it in the background `python termux-api-gps-to-nmea-pty.py&`. ***This MUST NOT be run as the root.***  
  This script creates a link next to the its source file, to the pseudo terminal slave named `gps_vport`.
  The data printed on the pty slave end is the termux-location json output converted to the NMEA sentences.
  This device can be directly passed to the `gpsd` to read location data from there.

  ***ALTHOUGHT THE SCRIPT DOES A CLEANUP ON EXIT, MAKE SURE THE LINK TO PTY DOES NOT EXIST BEFORE RUNNING THE SCRIPT***

- Move to the gpsd repo root folder and run the gpsd. Point the source of location data as the pty link. ***This MUST BE run as a root***:
  ```
  ./gpsd-3.27.4~dev/gpsd/gpsd -n -N <wherever your script is>/gps_vport&
  ```
  e.g. assuming the binary is running and is placed in the home folder `~` -> `/data/data/com.termux/files/home`:
  ```
  ./gpsd-3.27.4~dev/gpsd/gpsd -n -N /data/data/com.termux/files/home/gps_vport&
  ```

- **Extra:** As we are talking about full in-console automation, the GPS can be enabled in console, by invoking:

***Following commands MUST BE run as a root***

GPS only:
```
settings put secure location_mode 1
```
High precision (GPS+From network):
```
settings put secure location_mode 3
```
Disable location:
```
settings put secure location_mode 0
```

### Troubleshooting gpsd setup

#### Enabling debug logs in gpsd

This never helped me out, but maybe it's just me. To make the binary more verbose on stdout, add flag `-D 4`. E.g.:
```
  ./gpsd-3.27.4~dev/gpsd/gpsd -D 4 -n -N <wherever your script is>/gps_vport&
```
i.e. assuming the binary is running and is placed in the home folder `~` -> `/data/data/com.termux/files/home`:
```
  ./gpsd-3.27.4~dev/gpsd/gpsd -D 4 -n -N /data/data/com.termux/files/home/gps_vport&
```
Analogically for the network mode, I think you get the drill.

#### Testing gpsd output
To check if the gpsd is working properly, you can run the GPS client, that is build alongside the gpsd.
Simply run, in the gpsd repo root folder (while gpsd is running, duh):
```
./gpsd-3.27.4~dev/clients/cgps
```

If everything is alright, and the GPS pinpointed your location, the frame displayed should not be empty (if the frame is empty, either communication
with gpsd does not work via port 2947 or the gpsd is not running as the root),
and should not look like this (if so, either the relay does not generate proper data, or GPS didn't determine your location yet, go outside):
```
┌───────────────────────────────────────────┐
│ Time           n/a                 ( 0)   │
│ Latitude         n/a                      │
│ Longitude        n/a                      │
│ Alt (HAE, MSL)         n/a,        n/a ft │
│ Speed            n/a                  mph │
│ Track (true, var)       n/a,   n/a    deg │
│ Climb            n/a               ft/min │
│ Status          NO FIX (0 secs)           │
│ Long Err  (XDOP, EPX)   n/a ,  n/a        │
│ Lat Err   (YDOP, EPY)   n/a ,  n/a        │
│ Alt Err   (VDOP, EPV)   n/a ,  n/a        │
│ 2D Err    (HDOP, CEP)   n/a ,  n/a        │
│ 3D Err    (PDOP, SEP)   n/a ,  n/a        │
│ Time Err  (TDOP)        n/a               │
│ Geo Err   (GDOP)        n/a               │
│ Speed Err (EPS)             n/a           │
│ Track Err (EPD)         n/a               │
│ Time offset                               │
│ Grid Square             n/a               │
│ ECEF X, VX              n/a    n/a        │
│ ECEF Y, VY              n/a    n/a        │
│ ECEF Z, VZ              n/a    n/a        │
└───────────────────────────────────────────┘

{"class":"VERSION","release":"3.27.4~dev","rev":"release-3.27.3-1-g92660f43b","proto_major":3,"proto_minor":16}
{"class":"DEVICES","devices":[{"class":"DEVICE","path":"udp://127.0.0.1:12345","activated":"2026-01-06T23:25:21.370Z
"}]}
{"class":"WATCH","enable":true,"json":true,"nmea":false,"raw":0,"scaled":false,"timing":false,"split24":false,"pps":
false}

```

The proper version:
```
┌───────────────────────────────────────────┐
│ Time         2026-01-06T23:31:14.000Z ( 0)│
│ Latitude          50.<redacted> N         │
│ Longitude         18.<redacted> E         │
│ Alt (HAE, MSL)         n/a,        n/a ft │
│ Speed              0.00               mph │
│ Track (true, var)       0.0,   0.0    deg │
│ Climb            n/a               ft/min │
│ Status          2D FIX (82 secs)          │
│ Long Err  (XDOP, EPX)   n/a ,  n/a        │
│ Lat Err   (YDOP, EPY)   n/a ,  n/a        │
│ Alt Err   (VDOP, EPV)   n/a ,  n/a        │
│ 2D Err    (HDOP, CEP)   n/a ,  n/a        │
│ 3D Err    (PDOP, SEP)   n/a ,  n/a        │
│ Time Err  (TDOP)        n/a               │
│ Geo Err   (GDOP)        n/a               │
│ Speed Err (EPS)             n/a           │
│ Track Err (EPD)         n/a               │
│ Time offset             <redacted>      s │
│ Grid Square             <redacted>        │
│ ECEF X, VX              n/a    n/a        │
│ ECEF Y, VY              n/a    n/a        │
│ ECEF Z, VZ              n/a    n/a        │
└───────────────────────────────────────────┘
{"class":"TPV","device":"udp://127.0.0.1:12345","mode":2,"time":"2026-01-06T23:30:57.000Z","ept":<redacted>,"lat":50.<redacted>,"lon":18.<redacted>,"track":0.0000,"magtrack":<redacted>,"magvar":<redacted>,"speed":0.000}
{"class":"TPV","device":"udp://127.0.0.1:12345","mode":2,"time":"2026-01-06T23:30:58.000Z","ept":<redacted>,"lat":50.<redacted>,"lon":18.<redacted>,"track":0.0000,"magtrack":<redacted>,"magvar":<redacted>,"speed":0.000}
```

#### Verifying gpsd protocol version

Airdump-ng requires major version of the protocol to be 3, you can easily determine if that is the case in your setup, simply by calling (while gpsd is running):
```bash
nc 127.0.0.1 2947
```
This should return json, more or less like this:
```json
{"class":"VERSION","release":"3.27.4~dev","rev":"release-3.27.3-1-g92660f43b","proto_major":3,"proto_minor":16}
```
The `proto_major` must be 3, or the airodump-ng will reject the data from the gpsd.
As defined here:
https://github.com/aircrack-ng/aircrack-ng/blob/f333a6a767dc83c7da352de59dbca402fe3bf70c/src/airodump-ng/airodump-ng.c#L4768

If that differs, find the gpsd version that is using the same protocol as your airocrack suite.

#### Checking if the gpsdRelay app is actually streaming NMEA sentences

This is as simple as running nc command:

- for UDP relay's server: `nc -u 127.0.0.1 12345`
- for TCP relay's server: `nc 127.0.0.1 12345`

You should see NMEA sentences, like this in a few seconds (depending on settings in the app):
```
1|:/data/data/com.termux/files/home/gpsd # nc 127.0.0.1 12345                                                      
$GPRMC,<redacted>.00,A,5000.<redacted>,N,01800.<redacted>,E,0.0,0.0,<redacted>,,,A,V*2E
$GPRMC,<redacted>.00,A,5000.<redacted>,N,01800.<redacted>,E,0.0,0.0,<redacted>,,,A,V*2E
$GPRMC,<redacted>.00,A,5000.<redacted>,N,01800.<redacted>,E,0.0,0.0,<redacted>,,,A,V*23
$GPRMC,<redacted>.00,A,5000.<redacted>,N,01800.<redacted>,E,0.0,0.0,<redacted>,,,A,V*21
```
If it is silent or you cannot connect, try to forcefully stop the gpsdRelay app in the settings, and then start it again.  
When that fails as well, make sure GPS signal is reachable, the GPS is enabled and the app has proper permissions, along with access to the GPS in the background.

#### Checking if the termux-api-gps-to-nmea-pty.py script is actually streaming NMEA sentences

Simply call `cat gps_vport` on the pty link created by the script. If everything is right, and the
location has been established, you should see NMEA sentences streamed over there. Like this:
```
$GPRMC,<redacted>.00,A,5000.<redacted>,N,01800.<redacted>,E,0.0,0.0,<redacted>,,,A*5A
$GPGGA,<redacted>.00,5000.<redacted>,N,01800.<redacted>,E,1,08,1.0,<redacted>,M,0.0,M,,*5C
```

If this does not work, call `termux-location` to see if the communication between `termux-api-gps-to-nmea-pty.py`->`termux-location` works.
If `termux-location` fails to return location, make sure GPS signal is reachable, the GPS is enabled and Termux API apk is installed and has proper permissions,
along with access to the GPS in the background.
