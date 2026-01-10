#!/usr/bin/env python
import os, pty, json, subprocess, time, signal, atexit, termios, argparse, sys
from datetime import datetime, UTC

LINK_NAME = "gps_vport"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LINK_PATH = os.path.join(SCRIPT_DIR, LINK_NAME)

def calculate_checksum(sentence):
    cksum = 0
    for char in sentence: cksum ^= ord(char)
    return f"{hex(cksum)[2:].upper():0>2}"

def decimal_to_nmea(degrees, is_lat):
    abs_d = abs(degrees)
    dd = int(abs_d)
    mm = (abs_d - dd) * 60
    return f"{dd:0{2 if is_lat else 3}d}{mm:08.5f}", (("N" if degrees >= 0 else "S") if is_lat else ("E" if degrees >= 0 else "W"))

def get_sentences():
    try:
        # Removed timeout to avoid process hanging/killing overhead
        raw = subprocess.check_output(["termux-location"], shell=True)
        d = json.loads(raw)
        lat, ldir = decimal_to_nmea(d.get('latitude', 0.0), True)
        lon, odir = decimal_to_nmea(d.get('longitude', 0.0), False)
        ts = datetime.now(UTC).strftime("%H%M%S.00")
        dt = datetime.now(UTC).strftime("%d%m%y")
        alt = d.get('altitude', 0.0)

        sentences = [
            f"GPRMC,{ts},A,{lat},{ldir},{lon},{odir},0.0,0.0,{dt},,,A",
            f"GPGGA,{ts},{lat},{ldir},{lon},{odir},1,08,1.0,{alt:.1f},M,0.0,M,,",
            f"GPGSA,A,3,01,02,03,04,05,06,07,08,,,,1.5,1.0,1.2"
        ]
        return "".join([f"${s}*{calculate_checksum(s)}\r\n" for s in sentences])
    except Exception:
        return ""

master_fd = None

def cleanup():
    if os.path.exists(LINK_PATH):
        os.remove(LINK_PATH)
    if master_fd:
        os.close(master_fd)

atexit.register(cleanup)
signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))

def run():
    global master_fd
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    if not args.stdout:
        master_fd, slave_fd = pty.openpty()

        # Pure Raw Mode Settings
        attr = termios.tcgetattr(slave_fd)
        attr[0] = 0 # iflag
        attr[1] = 0 # oflag
        attr[2] = termios.CS8 | termios.CLOCAL | termios.CREAD # cflag
        attr[3] = 0 # lflag
        termios.tcsetattr(slave_fd, termios.TCSANOW, attr)

        slave_name = os.ttyname(slave_fd)
        if os.path.exists(LINK_PATH): os.remove(LINK_PATH)
        os.symlink(slave_name, LINK_PATH)
        print(f"[*] PTY active: {LINK_PATH}", file=sys.stderr)

    while True:
        data = get_sentences()
        if data:
            if args.stdout:
                sys.stdout.write(data)
                sys.stdout.flush()
            else:
                os.write(master_fd, data.encode('ascii'))
        time.sleep(1)

if __name__ == "__main__":
    run()
