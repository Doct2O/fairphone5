# Talking with Modem via AT serial interface

**To talk with the modem you'll need root access and ADB shell, or some terminal emulator like termux.**

By default the modem's serial interface is exposed at `/dev/at_mdm0`.
It also seems to be mirrored on the `/dev/smd7` as well. That's at least true for the modem
with the SIM card. I haven't tried to talk with the one using eSIM (yet).

Furthermore I couldn't get the picocom or any similar tool to get working, so here is workaround for that.

---
To read output of the command, spawn in one console:
```bash
cat /dev/at_mdm0
```

The AT commands may be send in other console by:
```bash
echo -e "AT<COMMAND>\r" > /dev/at_mdm0
```
e.g. show modem IMEI:
```bash
echo -e "AT+CGSN\r" > /dev/at_mdm0
```
---
Or in a single console:

Spawn cat:
```bash
cat /dev/at_mdm0&
```
And then send the commands, as follows:
```bash
# `echo \n` and `sleep` are here in case of cat printing back \r and 
# thus obscuring the AT command output with terminal prompt
echo -e "AT<COMMAND>\r" > /dev/at_mdm0 && echo -en "\n" && sleep 0.5
```
e.g. show modem IMEI:
```bash
echo -e "AT+CGSN\r" > /dev/at_mdm0 && echo -en "\n" && sleep 0.5
```
---
The reported list of the commands supported by this modem can be found on root of this repo in the `doc` folder.

- The file: `modem-at-commands-list-AT+CLAC.txt` contains list of commands listed by default `AT+CLAC` call.
- The file: `modem-at-commands-list-AT$QCCLAC.txt` contains list of commands listed by proprietary `AT$QCCLAC` call (which lists some additional, hidden commands).

To find reference for some of Qualcomm proprietary commands see file `Some-Qualcomm-AT-Cmd-Docs.pdf` from `doc` folder on repo root.
For other sources on AT commands search for "AT commands reference" online.
