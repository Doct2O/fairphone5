#!/usr/bin/env python3

import socket
import threading
import argparse
import sys
import os
import fcntl
import pty
import time
import select
import atexit
import logging
import termios
import signal
from abc import ABC, abstractmethod
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Diag-Router-Router")

class Backend(ABC):
    """Abstract interface for a backend (PTY or Socket)."""

    @abstractmethod
    def get_fd(self) -> int:
        """Return the file descriptor to select on."""
        pass

    @abstractmethod
    def read(self, size: int) -> bytes:
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def get_info(self) -> str:
        pass

class PtyBackend(Backend):
    def __init__(self):
        self.master_fd, self.slave_fd = pty.openpty()

        # Raw binary mode to avoid pty's messages reinterpretation shenanigans
        attr = termios.tcgetattr(self.slave_fd)
        attr[0] = 0 # iflag
        attr[1] = 0 # oflag
        attr[2] = termios.CS8 | termios.CLOCAL | termios.CREAD # cflag
        attr[3] = 0 # lflag
        termios.tcsetattr(self.slave_fd, termios.TCSANOW, attr)

        self.slave_name = os.ttyname(self.slave_fd)

    def get_fd(self) -> int:
        return self.master_fd

    def read(self, size: int) -> bytes:
        return os.read(self.master_fd, size)

    def write(self, data: bytes) -> None:
        os.write(self.master_fd, data)

    def close(self) -> None:
        if self.master_fd:
            try: os.close(self.master_fd)
            except OSError: pass
        if self.slave_fd:
            try: os.close(self.slave_fd)
            except OSError: pass
        self.master_fd = None
        self.slave_fd = None

    def get_info(self) -> str:
        return self.slave_name

class SocketBackend(Backend):
    def __init__(self, conn: socket.socket, addr: Tuple[str, int]):
        self.conn = conn
        self.addr = addr
        self.conn.setblocking(False)

    def get_fd(self) -> int:
        return self.conn.fileno()

    def read(self, size: int) -> bytes:
        return self.conn.recv(size)

    def write(self, data: bytes) -> None:
        try:
            self.conn.sendall(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def close(self) -> None:
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
            self.conn.close()
        except OSError:
            pass

    def get_info(self) -> str:
        return f"{self.addr[0]}:{self.addr[1]}"

class DiagRouterRouter:
    def __init__(self, port_a: int, control_path: str):
        self.port_a = port_a
        self.control_path = control_path

        # State
        self.running = True
        self.another_instance_running = None
        self.lock = threading.RLock()

        # Resources A (Client Side)
        self.server_a: Optional[socket.socket] = None
        self.client_a: Optional[socket.socket] = None
        self.actual_port_a: int = 0

        # Resources B (Backend Side)
        self.active_backend: Optional[Backend] = None
        self.backend_type: str = "none" # 'pty', 'socket', 'none'

        # Helper for socket B listener
        self.server_b: Optional[socket.socket] = None
        self.pending_b_addr: Optional[str] = None
        self.pending_b_port: Optional[int] = None

        # Lock file
        self.lock_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_diag-router-router.lock')
        self.lock_fd = None

        # Clean up on exit
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))

    def acquire_lock(self) -> bool:
        """Ensures only one instance runs via file locking."""
        try:
            f = open(self.lock_file_path, 'w')
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd = f
            return True
        except Exception:
            f.close()
            return False

    def init_server_a(self) -> bool:
        """Initialize the primary listening port."""
        try:
            self.server_a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_a.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_a.bind(('127.0.0.1', self.port_a or 0))
            self.server_a.listen(5)
            self.actual_port_a = self.server_a.getsockname()[1]
            logger.info(f"Port A listening on 127.0.0.1:{self.actual_port_a}")
            return True
        except Exception as e:
            logger.error(f"Failed to bind Port A: {e}")
            return False

    def start_pty_backend(self) -> str:
        """Switches backend to a new PTY."""
        with self.lock:
            if self.active_backend or self.server_b:
                return "BUSY"
            try:
                backend = PtyBackend()
                self.active_backend = backend
                self.backend_type = "pty"
                logger.info(f"Switched backend to PTY: {backend.get_info()}")
                return backend.get_info()
            except Exception as e:
                logger.error(f"Failed to start PTY: {e}")
                return "ERR"

    def prepare_socket_backend(self, addr: str, port: int) -> bool:
        """Opens a listener for Side B."""
        with self.lock:
            # We cannot bind if a backend is active or if we are already listening on B
            if self.active_backend or self.server_b:
                return False

            try:
                self.server_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_b.bind((addr, port))
                self.server_b.listen(5)
                self.pending_b_addr = addr
                self.pending_b_port = port
                self.backend_type = "socket"

                logger.info(f"Listening for Backend connection on {addr}:{port}")
                # Start the loop that accepts B connections (one at a time)
                threading.Thread(target=self._accept_b_loop, daemon=True).start()
                return True
            except Exception as e:
                logger.error(f"Failed to bind Port B: {e}")
                return False

    def _accept_b_loop(self):
        """
        Accepts connections on Port B.
        Enforces strict single-client policy: Rejects new if one is already active.
        """
        while self.running:
            # Check safely if server_b still exists (might be closed by control command)
            with self.lock:
                listener = self.server_b

            if not listener:
                break

            try:
                conn, addr = listener.accept()
                with self.lock:
                    # STRICT CHECK: If active_backend exists, reject new connection
                    if self.active_backend is not None:
                        logger.warning(f"REJECTED Backend connection from {addr}: Backend already active.")
                        conn.close()
                        continue

                    # Otherwise, accept and promote to backend
                    self.active_backend = SocketBackend(conn, addr)
                    logger.info(f"Backend B connected: {addr}")

            except OSError:
                # Listener closed or error
                break
            except Exception as e:
                logger.error(f"Error in accept B loop: {e}")

    def close_backend(self):
        with self.lock:
            if self.active_backend:
                self.active_backend.close()
                self.active_backend = None

            # Important: Close the listener B so the loop stops
            if self.server_b:
                try:
                    self.server_b.shutdown(socket.SHUT_RDWR)
                    self.server_b.close()
                except: pass
                self.server_b = None

            self.backend_type = "none"
            self.pending_b_addr = None
            self.pending_b_port = None
            logger.info("Backend closed and listener stopped")

    def _bridge_loop(self):
        """The core multiplexing loop."""
        while self.running:
            with self.lock:
                client_a = self.client_a
                backend = self.active_backend

            if not client_a or not backend:
                time.sleep(0.1)
                continue

            try:
                fd_a = client_a.fileno()
                fd_b = backend.get_fd()

                rlist = [fd_a, fd_b]
                readable, _, exceptional = select.select(rlist, [], rlist, 0.5)

                if exceptional:
                    with self.lock:
                        if fd_a in exceptional:
                            self.client_a = None
                            logger.warning("Exceptional condition on Client A")
                        if fd_b in exceptional:
                            # Just close the backend connection; listener B remains (if applicable)
                            if self.active_backend:
                                self.active_backend.close()
                                self.active_backend = None
                    continue

                for fd in readable:
                    if fd == fd_a:
                        data = client_a.recv(8192)
                        if not data:
                            logger.info("Client A disconnected")
                            with self.lock: self.client_a = None
                            break
                        backend.write(data)

                    elif fd == fd_b:
                        data = backend.read(8192)
                        if not data:
                            logger.info("Backend disconnected")
                            # We only drop the ACTIVE connection.
                            # If server_b is listening, it will pick up the next one automatically.
                            with self.lock:
                                if self.active_backend:
                                    self.active_backend.close()
                                    self.active_backend = None
                            break
                        try:
                            client_a.sendall(data)
                        except OSError:
                            with self.lock: self.client_a = None
                            break

            except (OSError, ValueError):
                pass
            except Exception as e:
                logger.error(f"Bridge loop error: {e}")
                time.sleep(1)

    def _accept_a_loop(self):
        """Accepts connections on the primary port with strict single-client enforcement."""
        while self.running:
            try:
                conn, addr = self.server_a.accept()
                with self.lock:
                    if self.client_a is not None:
                        logger.warning(f"REJECTED Client A from {addr}: Client already connected.")
                        conn.close()
                        continue

                    logger.info(f"Client A connected: {addr}")
                    self.client_a = conn
            except OSError:
                if self.running: time.sleep(0.5)
                else: break

    def get_status(self) -> str:
        with self.lock:
            b_info = "none"
            if self.server_b:
                addr_port = self.server_b.getsockname()
                b_info = f"{addr_port[0]} {addr_port[1]}"
            elif self.active_backend:
                b_info = self.active_backend.get_info()

            lines = [
                f"PORT_A_PORT={self.actual_port_a}",
                f"PORT_A_CONNECTED={'yes' if self.client_a else 'no'}",
                f"BACKEND_TYPE={self.backend_type}",
                f"BACKEND_INFO={b_info}",
                f"BACKEND_LISTENER_ACTIVE={'yes' if self.server_b else 'no'}",
            ]
            return "\n".join(lines)

    def _control_server_loop(self):
        """Unix socket server for receiving commands."""
        if os.path.exists(self.control_path):
            os.remove(self.control_path)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.control_path)
        server.listen(5)

        while self.running:
            try:
                conn, _ = server.accept()
                with conn:
                    data = conn.recv(1024).decode().strip().split()
                    if not data: continue

                    cmd = data[0].lower()
                    resp = b"ERR\n"

                    if cmd == 'status':
                        resp = (self.get_status() + "\n").encode()
                    elif cmd == 'pty':
                        res = self.start_pty_backend()
                        if res == "BUSY": resp = b"BUSY: Close active backend first\n"
                        else: resp = (res + "\n").encode()
                    elif cmd == 'bind' and len(data) >= 3:
                        if self.prepare_socket_backend(data[1], int(data[2])):
                            resp = b"OK\n"
                        else:
                            resp = b"BUSY_OR_ERR: Make sure active backend has been closed first\n"
                    elif cmd == 'close':
                        self.close_backend()
                        resp = b"OK\n"
                    else:
                        resp = b"ERR: Unknown command\n"

                    conn.sendall(resp)
            except OSError:
                if self.running: time.sleep(0.1)
                else: break

    def start(self):
        if not self.acquire_lock():
            print("Cannot acquire lock. Is another instance running?")
            self.another_instance_running = True
            sys.exit(1)
        self.another_instance_running = False

        if not self.init_server_a():
            sys.exit(1)

        t_accept = threading.Thread(target=self._accept_a_loop, daemon=True)
        t_ctl = threading.Thread(target=self._control_server_loop, daemon=True)
        t_bridge = threading.Thread(target=self._bridge_loop, daemon=True)

        t_accept.start()
        t_ctl.start()
        t_bridge.start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False

    def cleanup(self):
        if self.another_instance_running is None or self.another_instance_running:
            return

        """Called by atexit."""
        if os.path.exists(self.control_path):
            try: os.remove(self.control_path)
            except: pass
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
            except: pass

        if not self.running: return
        self.running = False
        logger.info("Cleaning up resources...")

        self.close_backend()

        if self.client_a:
            try: self.client_a.close()
            except: pass
        if self.server_a:
            try: self.server_a.close()
            except: pass

def run_client(control_socket: str, cmd_str: str):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(control_socket)
        s.sendall(cmd_str.encode())
        print(s.recv(4096).decode(), end='')
        s.close()
    except Exception as e:
        print(f"Error communicating with daemon: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Bidirectional Socket Bridge - Routes traffic between a TCP port and a PTY or another Socket.\nThe routed backend may be switched in fly.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  Start Daemon:        %(prog)s -p 8080
  Check Status:        %(prog)s --cmd status
  Switch to PTY:       %(prog)s --cmd pty
  Switch to Socket B:  %(prog)s --cmd "bind 127.0.0.1 9090"
  Close Backend:       %(prog)s --cmd close

If no argument is passed, the ephemeral port is used for
the Socket A (the routed data).

Warning: The destination of PTY or Socket B must be closed,
         before switching to another one/reopening it.
        """
    )

    parser.add_argument('-p', '--port', type=int, required=False, help="Port for Side A (Daemon Mode)")
    parser.add_argument('--cmd', type=str, help="Command to send to the running daemon")
    parser.add_argument('-c', '--control-socket', help="Custom path for the Unix control socket")
    args = parser.parse_args()

    if args.port is not None and args.cmd is not None:
        print("Arguments -p/--port and --cmd cannot be mixed together.\n"
              "As the former is used while spawning the daemon and the latter controls already spawned daemon.")
        sys.exit(1)

    control_path = args.control_socket or os.path.join(os.path.dirname(os.path.abspath(__file__)), '_diag-router-router.sock')
    daemon_port  = 0 if not args.port else args.port

    if args.cmd:
        run_client(control_path, args.cmd)
    else:
        router = DiagRouterRouter(daemon_port, control_path)
        router.start()

if __name__ == '__main__':
    main()