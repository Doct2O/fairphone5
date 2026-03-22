import warnings
# Ignore warning on fork. It occurs as we are spawning it after creating the pipe
warnings.filterwarnings("ignore", category=DeprecationWarning)

import argparse
import os
import time
import fcntl
import struct
import array
import socket
import select
import sys
import logging
import signal
import multiprocessing
import subprocess
import threading
import pickle

import hmac
import hashlib

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Callable, Any
from multiprocessing.connection import Connection

import py_and_svc_binds as asb

# --- Constants & Config ---
LOG_FORMAT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Linux Input Event Constants
EV_KEY = 0x01
KEY_MAP = {114: "VOLUME_DOWN", 115: "VOLUME_UP", 116: "POWER"}
EVIOCGBIT_KEY = 0x80804521
EVIOCGNAME = 0x80804506

# Buttons dispatcher and discovery config
EXCLUDE_KEYWORDS = ["jack"]
LONG_PRESS_TIME_SEC = 0.8

# HDMI dispatcher and discovery config
EXT_DISP_HW_ANCHOR = "qcom,msm-ext-disp"
EXT_DISP_DRM_STATUS_PATH = "/sys/class/drm/card0-DP-1/status"

KRNL_EVENT_CHANGE_PREFIX = "change@"
KRNL_EVENT_DP_CON_SENTENCE = "STATE=DP=1"
KRNL_EVENT_DP_DIS_SENTENCE = "STATE=DP=0"

# -------------- Security settings & authenticated communication
# Arguments passing settings
ARGS_UNIX_SOCKET_ABSTRACT_ADDRESS = b'\0hw_event_binder_hand_off_arguments_channel'
ARGS_MAX_SER_SZ = 65536 # 65k
ARGS_NONCE_SZ = 128

# Args&Cmds common
SCRIPT_WISE_HASH_ALGO = hashlib.sha3_512

# Commands passing settings and implementation
SCRIPT_WISE_HASH_ALGO_NAME = SCRIPT_WISE_HASH_ALGO().name
SCRIPT_WISE_HASH_ALGO_HEX_DIG_SZ = SCRIPT_WISE_HASH_ALGO().digest_size
PKDF2_SZ = 64
MAX_CMD_DATA_SZ = 4*1024**2 # 4 MiB
CMD_PSK_SZ = 128
PBKDF2_ITERS = 100000

def PBKDF2(password, salt, len_bytes=PKDF2_SZ, iterations=PBKDF2_ITERS):
    return hashlib.pbkdf2_hmac(SCRIPT_WISE_HASH_ALGO_NAME, password, salt, iterations, len_bytes)

# I was going to keep the [root]->[user executor] pipe unauthorized,
# but then I realized, this may cause Arbitrary Write to ACE escalation with user privileges -_-
# So here is overly complex, thread safe and aware (hello there python 3.14)
# implementation of security protocol with authenticated content resilient for reply attacks.
thread_auth_send_context = threading.local()
def gen_auth_thr_cmd(cmd, psk):
    if not hasattr(thread_auth_send_context, "thread_key"):
        thread_auth_send_context.thread_id  = SCRIPT_WISE_HASH_ALGO(str(threading.get_ident()).encode()).digest()
        thread_auth_send_context.thread_key = PBKDF2(psk, thread_auth_send_context.thread_id)
        thread_auth_send_context.nonce = 0
    msg = (str(thread_auth_send_context.nonce).encode() + b'\xff'
           + thread_auth_send_context.thread_id
           + pickle.dumps(cmd))
    msg += hmac.new(thread_auth_send_context.thread_key, msg, SCRIPT_WISE_HASH_ALGO).digest()

    if len(msg) > MAX_CMD_DATA_SZ:
        raise Exception(f"Command too long. Command auth-packet data would exceed hard limit of {MAX_CMD_DATA_SZ} bytes.")

    thread_auth_send_context.nonce += 1
    return msg

class ThreadKeyNonceTracker:
    def __init__(self):
        self._nonce = {}
        self._lock_nonce = threading.Lock()
        self._key = {}
        self._lock_key = threading.Lock()
    def get_key(self, tid):
        with self._lock_key:
            return self._key.get(tid, None)
    def set_key(self, tid, key):
        with self._lock_key:
            self._key[tid] = key
    def get_nonce(self, tid):
        with self._lock_nonce:
            return self._nonce.get(tid, 0)
    def increment_nonce(self, tid):
        with self._lock_nonce:
            # This is now safe from race conditions
            current = self._nonce.get(tid, 0)
            self._nonce[tid] = current + 1
        return current
thread_key_nonce_tracker = ThreadKeyNonceTracker()
def get_auth_thr_cmd(raw_data, psk):
    if len(raw_data) > MAX_CMD_DATA_SZ:
        raise Exception("Command auth-packet exceeded hard limit of {MAX_CMD_DATA_SZ} bytes. DoS attempt?. ")
    sigless_raw_data    = raw_data[:-SCRIPT_WISE_HASH_ALGO_HEX_DIG_SZ]
    nonce, raw_data     = raw_data.split(b'\xff', 1); nonce = int(nonce.decode())
    thread_id, raw_data = raw_data[:PKDF2_SZ], raw_data[PKDF2_SZ:]
    cmd_pickled, sig    = raw_data[:-SCRIPT_WISE_HASH_ALGO_HEX_DIG_SZ], raw_data[-SCRIPT_WISE_HASH_ALGO_HEX_DIG_SZ:]

    # Way to quickly bail out, before we calculate computation heavy PBKDF.
    # This may introduce side channel attack, for guessing nonce. But get real,
    # even if attacker has nonce, we still have signed packet. This way is by far less DoS prone.
    # Plus if the nonce is checked after the signature, it is still prone to side channel, but with heavy computation beforehand.
    if nonce != thread_key_nonce_tracker.get_nonce(thread_id):
        raise Exception("Received invalid nonce for a command. Reply attack?")

    thread_key_cached = thread_key_nonce_tracker.get_key(thread_id)
    if not thread_key_cached:
        thread_key = PBKDF2(psk, thread_id)
    else:
        thread_key = thread_key_cached
    sig_computed = hmac.new(thread_key, sigless_raw_data, SCRIPT_WISE_HASH_ALGO).digest()

    if not hmac.compare_digest(sig_computed, sig):
        raise Exception("Received invalid signature for a message. Data tampering/forging attempt?")
    thread_key_nonce_tracker.increment_nonce(thread_id)
    thread_key_cached or thread_key_nonce_tracker.set_key(thread_id, thread_key)

    return pickle.loads(cmd_pickled)
# End of the [root]->[user executor] authentication protocol --------------

class ActionDispatcher:
    """Executes actions in the user context to keep the environment clean."""
    def __init__(self, conn: Connection, cmds_psk: bytes):
        self.conn = conn
        self.psk = cmds_psk
        self.executor = ThreadPoolExecutor(max_workers=4)

    def _execute(self, pickled_auth_cmd, psk):
        try:
            cmd = get_auth_thr_cmd(pickled_auth_cmd, psk)
            logging.info(f"Dispatching to user space: {cmd}")
            subprocess.Popen(cmd, shell=True, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logging.error(f"Execution error: {e}")

    def start(self):
        try:
            while True:
                pickled_auth_cmd = self.conn.recv_bytes()
                logging.info(f"Command executor received bytes count: {len(pickled_auth_cmd)}")
                self.executor.submit(self._execute, pickled_auth_cmd, self.psk)
        except (EOFError, KeyboardInterrupt):
            pass

class HardwareMonitor:
    def __init__(self, bindings_buttons: Dict[str, Callable], bindings_hdmi: Dict[str, Callable]):
        self.bindings_buttons = bindings_buttons
        self.bindings_hdmi = bindings_hdmi
        self.input_fds: List[int] = []
        self.uevent_sock = None
        # To make kill responsive and to avoid halting on proper read(), for who knows how long
        self.kill_threads_r, self.kill_threads_w = os.pipe()
        self._setup_arch()
        self._setup_signals()

    def _setup_arch(self):
        is_64bit = struct.calcsize("P") == 8
        self.event_format = "QQHHi" if is_64bit else "llHHi"
        self.event_size = struct.calcsize(self.event_format)

    def _setup_signals(self):
        def handler(sig, frame):
            os.write(self.kill_threads_w, '¡Hasta la vista, baby!'.encode())
            self.cleanup()
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def cleanup(self):
        for fd in self.input_fds:
            try: os.close(fd)
            except: pass
        self.uevent_sock and self.uevent_sock.close()

    def _hw_longpress_buttons_dispatcher(self, action_queue, input_list):
        active_keys = {}
        wakelock = None

        input_list.append(self.kill_threads_r)
        logging.info("Monitoring Buttons long-presses now...")
        try:
            while True:
                timeout = LONG_PRESS_TIME_SEC if active_keys else None
                readable, _, _ = select.select(input_list, [], [], timeout)
                if self.kill_threads_r in readable:
                    break

                # 1. ACQUIRE LOCK IMMEDIATELY ON WAKE
                if readable:
                    if not wakelock and asb:
                        wakelock = asb.acquire_wake_lock()

                # 2. HANDLE LONG PRESS TIMEOUT
                if not readable and active_keys:
                    for key, (off, lock) in active_keys.items():
                        if action := self.bindings_buttons.get(key):
                            action_queue.submit(action, key, off, lock)
                    active_keys.clear()
                    if wakelock:
                        wakelock.release(); wakelock = None
                    continue

                # 3. PROCESS ALL PENDING EVENTS
                for fd in readable:
                    try:
                        data = os.read(fd, self.event_size)
                        if len(data) < self.event_size:
                            continue

                        _, _, ev_type, code, val = struct.unpack(self.event_format, data)
                        btn = KEY_MAP.get(code) if ev_type == EV_KEY else None

                        if btn:
                            if val == 1: # Key Down
                                active_keys[btn] = (
                                    asb.is_display_off(),
                                    asb.is_keyguard_active()
                                )
                            elif val == 0: # Key Up
                                active_keys.pop(btn, None)
                    except OSError:
                        continue

                # 4. CONDITIONAL RELEASE
                # If no keys are being tracked as "held", let the CPU sleep.
                if not active_keys:
                    if wakelock:
                        wakelock.release(); wakelock = None
        finally:
            wakelock and wakelock.release()

    def _hdmi_state_dispatcher(self, action_queue, uevent_sock):
        def _is_display_physically_connected():
            # Verify if the display is actually connected via DRM status.
            if os.path.exists(EXT_DISP_DRM_STATUS_PATH):
                try:
                    with open(EXT_DISP_DRM_STATUS_PATH, "r") as f:
                        return f.read().strip() == "connected"
                except:
                    return False
            return False

        logging.info("Monitoring FP5 HDMI port state now...")
        was_connected = _is_display_physically_connected()
        krnl_raw_event = ""

        input_list = [uevent_sock.fileno(), self.kill_threads_r]
        while True:
            readable, _, _ = select.select(input_list, [], [])
            if self.kill_threads_r in readable:
                break
            if krnl_raw_event := uevent_sock.recv(4096).decode('utf-8', errors='ignore'):
                if not krnl_raw_event.startswith(KRNL_EVENT_CHANGE_PREFIX) or EXT_DISP_HW_ANCHOR not in krnl_raw_event:
                    continue # quick bail out, to avoid acquiring wake lock ON EVERY SINGLE EVENT

                with asb.acquire_wake_lock() as wl: # Acquire wake lock as soon as possible
                    new_conn_state = was_connected
                    if KRNL_EVENT_DP_CON_SENTENCE in krnl_raw_event:
                        new_conn_state = True
                    if KRNL_EVENT_DP_DIS_SENTENCE in krnl_raw_event:
                        new_conn_state = False
                    if new_conn_state != was_connected:
                        # Debounce wake-up flicker. Increase sleep value if you get double events.
                        time.sleep(1)
                        is_still_connected = _is_display_physically_connected()

                        if is_still_connected == new_conn_state:
                            key = "HDMI_CONNECTED" if new_conn_state else "HDMI_DISCONNECTED"
                            action = self.bindings_hdmi.get(key)
                            # We don't care about screen being off or locked for HDMI event
                            action and action_queue.submit(action, key)
                        was_connected = is_still_connected

    def discover(self, bind_buttons, bind_uevent):
        # Buttons
        if bind_buttons:
            base = "/dev/input/"
            if not os.path.exists(base):
                logging.error(f"Base path for input devices '{base}' does not exist! Buttons events binding won't work.")
                sys.exit(1)
            for node in sorted(os.listdir(base)):
                if not node.startswith("event"): continue
                path = os.path.join(base, node)
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    buf = array.array('B', [0] * 128)
                    fcntl.ioctl(fd, EVIOCGBIT_KEY, buf, True)
                    if any(buf[code // 8] & (1 << (code % 8)) for code in KEY_MAP):
                        name_buf = array.array('B', [0] * 128)
                        fcntl.ioctl(fd, EVIOCGNAME, name_buf, True)
                        name = "".join(chr(c) for c in name_buf if c != 0)
                        if not any(kw in name.lower() for kw in EXCLUDE_KEYWORDS):
                            self.input_fds.append(fd)
                            logging.info(f"Attached input: {name}, fd: {fd}")
                            continue
                    os.close(fd)
                except (PermissionError, OSError): continue

        # Hdmi
        if bind_uevent:
            if not os.path.exists(EXT_DISP_DRM_STATUS_PATH):
                logging.error(f"Path for passive check of external display status '{EXT_DISP_DRM_STATUS_PATH}' does not exist! HDMI events binding won't work.")
                sys.exit(1)
            self.uevent_sock = None
            # Manual constants
            AF_NETLINK = 16
            SOCK_RAW = 3
            NETLINK_KOBJECT_UEVENT = 15
            try:
                self.uevent_sock = socket.socket(AF_NETLINK, SOCK_RAW, NETLINK_KOBJECT_UEVENT)
                self.uevent_sock.bind((os.getpid(), 1))
                logging.info(f"Attached uevent socket")
            except Exception as e:
                if self.uevent_sock:
                    self.uevent_sock.close()
                    self.uevent_sock = None
                logging.error(f"Failed to open socket in for HDMI state dispatcher, error: {e}")

    def run(self, action_queue: ThreadPoolExecutor):
        threads = []
        if self.input_fds:
            threads.append(threading.Thread(target=self._hw_longpress_buttons_dispatcher, args=(action_queue, self.input_fds)))
        else:
            logging.info("Buttons binds dispatcher is NOT spawned.")
        if self.uevent_sock:
            threads.append(threading.Thread(target=self._hdmi_state_dispatcher, args=(action_queue, self.uevent_sock)))
        else:
            logging.info("HDMI binds dispatcher is NOT spawned.")

        if threads:
            for t in threads: t.start()
            for t in threads: t.join()
        else:
            logging.error("Nothing to bind on, make sure the discovery works alright.")
        self.cleanup()

# --- Logic Handlers ---

def toggle_torch(key: str, was_off: bool, was_locked: bool):
    try:
        is_on = asb.is_torch_on()
        # Toggle OFF: Allowed if interaction started while screen was Off or Locked
        if is_on and (was_off or was_locked):
            asb.set_torch_mode(False)
        # Toggle ON: Only if display was truly Off at moment of initial press
        elif not is_on and was_off:
            asb.set_torch_mode(True)
    except Exception as e:
        logging.error(f"Torch control failure: {e}")

def run_hdmi_cmd(key: str, psk_cmds: bytes, pipe: Connection, cmd: List[str]):
    logging.info(f"Command to send to execute on HDMI event: {cmd}, Key: {key}")
    try:
        pipe.send_bytes(gen_auth_thr_cmd(cmd, psk_cmds))
    except Exception as e:
         logging.error(f"Failed to send command for HDMI event {key}: {e}")

def run_longpress_btn_cmd(key: str, psk_cmds: bytes, pipe: Connection, cmd: List[str], was_off: bool, was_locked: bool):
    logging.info(f"Command to send to execute on Button event: {cmd}, Key: {key}")
    # Rule: Trigger commands if screen was off, or if it's Power on the lockscreen.
    if was_off or (was_locked and key == "POWER"):
        try:
            pipe.send_bytes(gen_auth_thr_cmd(cmd, psk_cmds))
        except Exception as e:
            logging.error(f"Failed to send command for Buttons event {key}: {e}")

# --- Help & Initialization ---

def show_help():
    print(f"""
Hardware Key Binder: Enhanced Service
-------------------------------------
Usage: {sys.argv[0]} [OPTIONS]
NOTE: Run as a normal user. The script handles 'su' internally.

Maps hardware long-presses and HDMI events to actions.

BUTTON OPTIONS:
  --vol-down-torch, --vol-up-torch, --power-torch
  --vol-down-cmd "CMD", --vol-up-cmd "CMD", --power-cmd "CMD"

HDMI OPTIONS:
  --hdmi-conn-cmd "CMD"   Triggers when HDMI state is "connected".
  --hdmi-dis-cmd "CMD"    Triggers when HDMI state is "disconnected".

TECHNICAL SPECS:
  • Long-press Timeout: {LONG_PRESS_TIME_SEC}s
  • HDMI Anchor:        {EXT_DISP_HW_ANCHOR}
  • HDMI Status Path:   {EXT_DISP_DRM_STATUS_PATH}
  • Excluded Devices:   Keywords {EXCLUDE_KEYWORDS}

BEHAVIOR (State snapshotted at first press):
  • Torch OFF:  Works if screen was Locked or Off.
  • Torch ON:   Works only if screen was Off.
  • Commands:   Works if screen was Off (Power button also works if Locked).
                Run commands with the privileges of user starting the script.
  • HDMI:       Triggers regardless of screen or lock state.
""")

if __name__ == "__main__":
    if os.getuid() != 0:
        cmd_c_pipe, cmd_p_pipe = multiprocessing.Pipe(duplex=False)
        psk_cmds = os.urandom(CMD_PSK_SZ)
        if os.fork() == 0:
            cmd_p_pipe.close()
            ActionDispatcher(cmd_c_pipe, psk_cmds).start()
            sys.exit(0)
        else:
            parser = argparse.ArgumentParser(add_help=False, usage='\r        ')
            for p in ["vol-down", "vol-up", "power"]:
                g = parser.add_mutually_exclusive_group()
                g.add_argument(f'--{p}-cmd', nargs='+')
                g.add_argument(f'--{p}-torch', action='store_true')
            hdmi_group = parser.add_argument_group('HDMI Options')
            hdmi_group.add_argument('--hdmi-conn-cmd', nargs='+')
            hdmi_group.add_argument('--hdmi-dis-cmd', nargs='+')

            if len(sys.argv) == 1 or '-h' in sys.argv or '--help' in sys.argv:
                show_help(); sys.exit(0)

            # Parse arguments here, so we exit before transition to root
            try:
                args = parser.parse_args()
            except SystemExit:
                show_help()
                sys.exit(1)
            pickled_args = pickle.dumps((args, psk_cmds))
            if len(pickled_args) > ARGS_MAX_SER_SZ:
                logging.error("The serialized arguments size is too big, please shorten the PATHS.");
                sys.exit(1)

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            # Enable Credential passing (SO_PASSCRED) to be able to make sure on the other side
            # that the data is coming from the launcher and not from anyone else.
            SO_PASSCRED = 16
            sock.setsockopt(socket.SOL_SOCKET, SO_PASSCRED, 1)
            sock.bind(ARGS_UNIX_SOCKET_ABSTRACT_ADDRESS)
            sock.sendto(pickled_args, ARGS_UNIX_SOCKET_ABSTRACT_ADDRESS)

            os.set_inheritable(sock.fileno(), True)
            os.set_inheritable(cmd_p_pipe.fileno(), True)

            nonce_args = os.urandom(ARGS_NONCE_SZ)
            sig = hmac.new(nonce_args, pickled_args, SCRIPT_WISE_HASH_ALGO).hexdigest()
            os.execvp("su", ["su", "-c", f"{sys.executable} {os.path.abspath(__file__)} {cmd_p_pipe.fileno()} {sock.fileno()} {nonce_args.hex()} {sig} {os.getpid()}"])
    else:
        try:
            c_fd, a_fd, nonce_args, sig_args, launcher_pid = int(sys.argv[1]), int(sys.argv[2]), bytes.fromhex(sys.argv[3]), sys.argv[4].strip(), int(sys.argv[5])
            # Check for inheritance from non-standard FDs only
            if c_fd <= 2 or a_fd <= 2:
                logging.error("FD Sanity check failed.");
                sys.exit(1)

            # Paranoiac check. First check if incoming data actually comes from the coupled user's launcher,
            # then make sure somebody else did not tamper with the serialized data sent via pipe.
            # I would not bother normally, but python internally uses pickle to send objects, where mere deserialization may cause ACE,
            # so yeah here we are implementing our own authenticated pickle.
            pickled_args = None
            with socket.fromfd(a_fd, socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                while True: # Drain the socket. Accept only first message coming from the user launcher
                    try:
                        recv_data, ancdata, _, _ = sock.recvmsg(ARGS_MAX_SER_SZ, socket.CMSG_SPACE(struct.calcsize('3i')))
                        _, _, cmsg_data = tuple(ancdata)[0]
                        sender_pid, _, _ = struct.unpack('3i', cmsg_data)
                        if sender_pid == launcher_pid and not pickled_args:
                            pickled_args = recv_data
                    except Exception:
                        if not pickled_args:
                            logging.error("No valid arguments data found on socket.");
                            sys.exit(1)
                        else:
                            break

            sig = hmac.new(nonce_args, pickled_args, SCRIPT_WISE_HASH_ALGO).hexdigest()
            # For a good measure O(1) hash compare, yeah sure, why not.
            if not hmac.compare_digest(sig, sig_args):
                logging.error("SECURITY ALERT: Args HMAC mismatch. It seems someone tampered with arguments sent via UNIX socket.");
                sys.exit(1)

            c_conn = Connection(c_fd)
            args, psk_cmds = pickle.loads(pickled_args)
        except Exception as e:
            logging.error(f"Exception occurred, while starting script: {e}. Did you run this script as a root? Do not do it!")
            sys.exit(1)

        bindings_hdmi = {
            **({"HDMI_CONNECTED":lambda k: run_hdmi_cmd(k, psk_cmds, c_conn, args.hdmi_conn_cmd)} if args.hdmi_conn_cmd else dict()),
            **({"HDMI_DISCONNECTED":lambda k: run_hdmi_cmd(k, psk_cmds, c_conn, args.hdmi_dis_cmd)} if args.hdmi_dis_cmd else dict())
        }
        bindings_buttons = {}
        mapping_buttons  = {
            "VOLUME_DOWN": (args.vol_down_cmd, args.vol_down_torch),
            "VOLUME_UP": (args.vol_up_cmd, args.vol_up_torch),
            "POWER": (args.power_cmd, args.power_torch)
        }
        for k, (c, t) in mapping_buttons.items():
            if c:
                bindings_buttons[k] = lambda k, o, l, cmd=c: run_longpress_btn_cmd(k, psk_cmds, c_conn, cmd, o, l)
            elif t:
                bindings_buttons[k] = toggle_torch

        monitor = HardwareMonitor(bindings_buttons, bindings_hdmi)
        monitor.discover(bindings_buttons, bindings_hdmi)
        with ThreadPoolExecutor(max_workers=4) as q:
            monitor.run(q)