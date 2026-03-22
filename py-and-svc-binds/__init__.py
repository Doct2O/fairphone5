#!/usr/bin/env python3
import ctypes
import sys
import os
import time
import datetime
import math
import threading
from typing import Optional, Callable, Dict, Any, Union

# ============================================================================
# 1. FFI SETUP & LOW-LEVEL BINDINGS
# ============================================================================

# --- Library Loading ---
try:
    _lib = ctypes.CDLL("libbinder_ndk.so")
except OSError:
    raise ImportError("libbinder_ndk.so not found. Ensure you are running on Android 10+.")

try:
    libc = ctypes.CDLL("libc.so")
except OSError:
    raise ImportError("libc.so not found.")

# --- Type Definitions ---
class AIBinder(ctypes.Structure): pass
class AParcel(ctypes.Structure): pass
class AIBinder_Class(ctypes.Structure): pass

# Callback Prototypes
_OnTransact = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.POINTER(AIBinder), ctypes.c_uint32, ctypes.POINTER(AParcel), ctypes.POINTER(AParcel))
_OnEvent = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

# Global callbacks to prevent Garbage Collection
_cb_on_transact = _OnTransact(lambda b, c, pi, po: 0)
_cb_on_create = _OnEvent(lambda u: None)
_cb_on_destroy = _OnEvent(lambda u: None)

# Memory Management for Strings
libc.malloc.restype = ctypes.c_void_p
libc.malloc.argtypes = [ctypes.c_size_t]
libc.free.argtypes = [ctypes.c_void_p]

STRING_ALLOCATOR_TYPE = ctypes.CFUNCTYPE(
    ctypes.c_bool, ctypes.c_void_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)
)

# --- Function Prototypes ---
def _proto(name, res, args):
    """Helper to define ctypes function signatures."""
    if not hasattr(_lib, name):
        raise ImportError(f"Function {name} not found in libbinder_ndk.so")
    f = getattr(_lib, name)
    f.restype = res
    f.argtypes = args
    return f

# Binder Primitives
_ndk_get_service = _proto("AServiceManager_getService", ctypes.POINTER(AIBinder), [ctypes.c_char_p])
_ndk_prepare_transaction = _proto("AIBinder_prepareTransaction", ctypes.c_int32, [ctypes.POINTER(AIBinder), ctypes.POINTER(ctypes.POINTER(AParcel))])
_ndk_transact = _proto("AIBinder_transact", ctypes.c_int32, [ctypes.POINTER(AIBinder), ctypes.c_uint32, ctypes.POINTER(ctypes.POINTER(AParcel)), ctypes.POINTER(ctypes.POINTER(AParcel)), ctypes.c_uint32])

# Parcel Primitives (Write)
_ndk_parcel_create = _proto("AParcel_create", ctypes.POINTER(AParcel), [])
_ndk_parcel_delete = _proto("AParcel_delete", None, [ctypes.POINTER(AParcel)])
_ndk_write_byte = _proto("AParcel_writeByte", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_int8])
_ndk_write_int32 = _proto("AParcel_writeInt32", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_int32])
_ndk_write_int64 = _proto("AParcel_writeInt64", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_int64])
_ndk_write_float = _proto("AParcel_writeFloat", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_float])
_ndk_write_string = _proto("AParcel_writeString", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_char_p, ctypes.c_int32])
_ndk_write_strong_binder = _proto("AParcel_writeStrongBinder", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.POINTER(AIBinder)])
_ndk_write_file_descriptor = _proto("AParcel_writeParcelFileDescriptor", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_int32])

# Parcel Primitives (Read)
_ndk_read_int32 = _proto("AParcel_readInt32", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.POINTER(ctypes.c_int32)])
_ndk_read_int64 = _proto("AParcel_readInt64", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.POINTER(ctypes.c_int64)])
_ndk_read_double = _proto("AParcel_readDouble", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.POINTER(ctypes.c_double)])
_ndk_read_string = _proto("AParcel_readString", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_void_p, STRING_ALLOCATOR_TYPE])
_ndk_read_strong_binder = _proto("AParcel_readStrongBinder", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.POINTER(ctypes.POINTER(AIBinder))])

# Data Manipulation
_ndk_get_pos = _proto("AParcel_getDataPosition", ctypes.c_int32, [ctypes.POINTER(AParcel)])
_ndk_set_pos = _proto("AParcel_setDataPosition", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.c_int32])
_ndk_get_data_size = _proto("AParcel_getDataSize", ctypes.c_int32, [ctypes.POINTER(AParcel)])
_ndk_marshal = _proto("AParcel_marshal", ctypes.c_int32, [ctypes.POINTER(AParcel), ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t, ctypes.c_size_t])

# Class & Reference Management
_ndk_class_define = _proto("AIBinder_Class_define", ctypes.POINTER(AIBinder_Class), [ctypes.c_char_p, _OnEvent, _OnEvent, _OnTransact])
_ndk_aibinder_new = _proto("AIBinder_new", ctypes.POINTER(AIBinder), [ctypes.POINTER(AIBinder_Class), ctypes.c_void_p])
_ndk_associate_class = _proto("AIBinder_associateClass", ctypes.c_bool, [ctypes.POINTER(AIBinder), ctypes.POINTER(AIBinder_Class)])
_ndk_dec_strong = _proto("AIBinder_decStrong", None, [ctypes.POINTER(AIBinder)])
_ndk_inc_strong = _proto("AIBinder_incStrong", None, [ctypes.POINTER(AIBinder)])

# Thread Pool
_ndk_set_max_threads = _proto("ABinderProcess_setThreadPoolMaxThreadCount", ctypes.c_bool, [ctypes.c_uint32])
_ndk_start_thread_pool = _proto("ABinderProcess_startThreadPool", None, [])
_ndk_join_thread_pool = _proto("ABinderProcess_joinThreadPool", None, [])

# Ensure thread pool is active for callbacks
_ndk_set_max_threads(15)
_ndk_start_thread_pool()

# ============================================================================
# 2. HELPER UTILITIES & CALLBACKS
# ============================================================================

# --- String Allocation Helpers ---
def _android_string_allocator(string_data_ptr, length, out_ptr):
    if length < 0:
        out_ptr[0] = None
        return True
    buf = libc.malloc(length + 1)
    if not buf:
        return False
    out_ptr[0] = buf
    if string_data_ptr:
        data_receiver = ctypes.cast(string_data_ptr, ctypes.POINTER(ctypes.c_void_p))
        data_receiver[0] = buf
    return True

_allocator_callback = STRING_ALLOCATOR_TYPE(_android_string_allocator)

def _read_parcel_string(parcel_ptr):
    result_ptr = ctypes.c_void_p(0)
    status = _ndk_read_string(parcel_ptr, ctypes.addressof(result_ptr), _allocator_callback)
    if status == 0:
        if result_ptr.value is None:
            return None
        char_ptr = ctypes.cast(result_ptr, ctypes.c_char_p)
        py_string = char_ptr.value.decode('utf-8')
        libc.free(result_ptr)
        return py_string
    else:
        raise Exception(f"Failed to read string from Parcel. Status: {status}")

def _read_string8(parcel):
    """Legacy manual string reader (reads 4-byte chunks)."""
    chunk  = ctypes.c_int32()
    length = ctypes.c_int32()
    if _ndk_read_int32(parcel, ctypes.byref(length)) != 0 : raise RuntimeError("Could not read string8 length from parcel")
    ret = ""
    CHUNK_SZ_IN_BYTES = 4
    CHUNKS_TO_READ = int(math.ceil(length.value/CHUNK_SZ_IN_BYTES))
    chunkNo = 0
    while _ndk_get_pos(parcel) < _ndk_get_data_size(parcel) and chunkNo < CHUNKS_TO_READ:
        if _ndk_read_int32(parcel, ctypes.byref(chunk)) != 0 : raise RuntimeError("Could not read string8 content from parcel")
        b = chunk.value.to_bytes(4)[::-1]
        ret += b.rstrip(b'\x00').decode("utf-8")
        if b'\x00' in b:
            break
        chunkNo += 1
    return ret

def _write_string8(parcel, string: bytes):
    """Legacy manual string writer (writes 4-byte chunks). Takes bytes."""
    _ndk_write_int32(parcel, len(string))
    for s in range(0, len(string), 4):
        chunk = string[s:s+4]
        if len(chunk) < 4:
            chunk += b'\x00'*(4-len(chunk))
        chunk = chunk[::-1]
        _ndk_write_int32(parcel, chunk[0]<<24 | chunk[1]<<16 | chunk[2]<<8 | chunk[3])
    if len(string)%4 == 0:
        _ndk_write_int32(parcel, 0)

def _parcel_write_string_list(parcel, string_list):
    """Writes a list of python strings to the parcel."""
    _ndk_write_int32(parcel, len(string_list))
    for st in string_list:
        _ndk_write_string(parcel, st.encode('utf-8'), len(st))

# --- Debugging ---
def _dump_parcel(parcel_ptr, label="Parcel"):
    if not parcel_ptr:
        print(f"[{label}] Parcel is NULL")
        return
    size = _ndk_get_data_size(parcel_ptr)
    if size <= 0:
        print(f"\n=== {label} (Empty or size: {size}) ===")
        return
    buffer = (ctypes.c_uint8 * size)()
    if _ndk_marshal(parcel_ptr, buffer, 0, size) != 0:
        print(f"Failed to marshal parcel.")
        return
    print(f"\n=== {label} (size: {size}) ===")
    raw_bytes = bytes(buffer)
    COLS = 16
    for i in range(0, size, COLS):
        chunk = raw_bytes[i : i + COLS]
        hex_str = " ".join(f"{b:02X}" for b in chunk).ljust(COLS * 3 - 1)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        print(f"{i:04X}:  {hex_str}  | {ascii_str}")

# --- Generic Cleanups ---
def _safe_dec_strong(binder):
    if binder: _ndk_dec_strong(binder)

def _safe_parcel_delete(parcel):
    if parcel: _ndk_parcel_delete(parcel)

# --- Global C Callback Placeholders ---
# These are kept alive to prevent GC.
_cb_on_create = _OnEvent(lambda u: None)
_cb_on_destroy = _OnEvent(lambda u: None)
_cb_on_transact_stub = _OnTransact(lambda b, c, pi, po: 0)


# ============================================================================
# 3. CORE LOGIC: ATTRIBUTION & BINDERS
# ============================================================================

def _write_attribution_source(parcel, package_name, write_presence=True):
    if write_presence and _ndk_write_int32(parcel, 1) != 0:
        raise RuntimeError("Failed to write presence bit")

    start_pos = _ndk_get_pos(parcel)
    _ndk_write_int32(parcel, 0)  # Size placeholder
    _ndk_write_int32(parcel, -1) # pid
    _ndk_write_int32(parcel, -1) # uid
    _ndk_write_int32(parcel, 0)  # device_id

    b_pkg = package_name.encode('utf-8')
    _ndk_write_string(parcel, b_pkg, len(b_pkg))
    _ndk_write_string(parcel, None, -1) # attribution_tag (null)
    _ndk_write_strong_binder(parcel, None) # token (null)
    _ndk_write_int32(parcel, -1) # renounced_permissions (null)
    _ndk_write_int32(parcel, 0)  # next (empty)

    end_pos = _ndk_get_pos(parcel)
    _ndk_set_pos(parcel, start_pos)
    _ndk_write_int32(parcel, end_pos - start_pos)
    _ndk_set_pos(parcel, end_pos)

def _extract_binders(parcel):
    ret = []
    data_size = _ndk_get_data_size(parcel)
    original_pos = _ndk_get_pos(parcel)

    # Heuristic scan for binders
    for n in range(original_pos, data_size, 4):
        _ndk_set_pos(parcel, n)
        probe_pos = _ndk_get_pos(parcel)
        probe = ctypes.c_int32()

        # If we can't read from current pointer as int32, the data underneath is likely in parcel's
        # object list, check if that's a binder.
        if _ndk_read_int32(parcel, ctypes.byref(probe)) != 0:
            _ndk_set_pos(parcel, probe_pos)
            binder = ctypes.POINTER(AIBinder)()
            if _ndk_read_strong_binder(parcel, ctypes.byref(binder)) != 0:
                continue
            ret.append(binder)
        # Magic checks (73622A85 / 73682A85 are often used in FlatBinder objects)
        elif probe.value in [0x73622A85, 0x73682A85] and n%8 == 0:
            _ndk_set_pos(parcel, probe_pos)
            binder = ctypes.POINTER(AIBinder)()
            if _ndk_read_strong_binder(parcel, ctypes.byref(binder)) != 0:
                continue
            ret.append(binder)

    _ndk_set_pos(parcel, original_pos) # restore
    return tuple(ret)

# ============================================================================
# 4. SYSTEM FEATURES: TORCH, POWER, DISPLAY
# ============================================================================

"""
This one here is just left as a reference of how to reach the ContentProvider and Settings.
I WON'T UPDATE THE CODE OF THIS FUNCTION.
As it turns out this is so highly unstable, it managed to break the hw-event-binder.py script
couple of times after update, EVEN within the same Android and LineageOS versions. And this is not even
the worst aspect of that. It seems that LineageOS does some silent patchwork on the IActivityManager.aidl
during the build, and I am unable to track the proper METHOD_ID for getContentProviderExternal() easily due this.
I'd need to download the sources every time the bump happens and probably, at least start the build
(mind you, complete LineageOS build takes about 8h). So it is no go for me, like this.
"""
def is_torch_on_highly_unstable_unmantained(package_name: str = "com.termux"):
    # https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r4/core/java/android/app/IActivityManager.aidl
    CLASS_NAME = "android.app.IActivityManager"
    METHOD_ID = 136 # getContentProviderExternal

    service = None
    client_token = None
    data = None
    reply = None
    settings_provider_binder = None
    settings_provider_binder_ok = False
    connection_binder = None
    provider_data = None
    provider_reply = None
    settings_name = "settings"

    try:
        service = _ndk_get_service(b"activity")
        if not service: raise ConnectionError("Could not find activity service")

        activity_class = _ndk_class_define(CLASS_NAME.encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact_stub)
        if not _ndk_associate_class(service, activity_class): raise RuntimeError("Failed to associate class")

        data = ctypes.POINTER(AParcel)()
        _ndk_prepare_transaction(service, ctypes.byref(data))

        tag = f"{package_name}.settings.tag"
        _ndk_write_string(data, settings_name.encode('utf-8'), len(settings_name)) # Name
        _ndk_write_int32(data, 0) # userId
        _ndk_write_strong_binder(data, None) # Token
        _ndk_write_string(data, tag.encode('utf-8'), len(tag)) # tag

        reply_ptr = ctypes.POINTER(AParcel)()
        if _ndk_transact(service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply_ptr), 0) != 0:
            raise RuntimeError("Binder transaction failed")
        reply = reply_ptr

        _ndk_set_pos(reply, 0)
        exc_code = ctypes.c_int32()
        _ndk_read_int32(reply, ctypes.byref(exc_code))
        if exc_code.value != 0:
            print(f"Service returned exception: {exc_code.value}")
        else:
            settings_provider_binder_ok = True
        binders = _extract_binders(reply)
        if len(binders) != 1: raise RuntimeError(f"Expected exactly one binder in returned Parcel, instead of {len(binders)}")
        settings_provider_binder, = binders

        provider_class = _ndk_class_define("android.content.IContentProvider".encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact_stub)
        if not _ndk_associate_class(settings_provider_binder, provider_class): raise RuntimeError("Failed to associate provider class")

        provider_data = ctypes.POINTER(AParcel)()
        _ndk_prepare_transaction(settings_provider_binder, ctypes.byref(provider_data))

        _write_attribution_source(provider_data, package_name, write_presence=False)
        _ndk_write_string(provider_data, b"settings", 8)
        _ndk_write_string(provider_data, b"GET_secure", 10)
        _ndk_write_string(provider_data, b"flashlight_enabled", 18)
        _ndk_write_int32(provider_data, 0)

        provider_reply_ptr = ctypes.POINTER(AParcel)()
        # As per: https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-16.0.0_r4/core/java/android/content/IContentProvider.java
        # CALL_TRANSACTION = IBinder.FIRST_CALL_TRANSACTION + 20; # 21.
        if _ndk_transact(settings_provider_binder, 21, ctypes.byref(provider_data), ctypes.byref(provider_reply_ptr), 0) != 0:
            raise RuntimeError("Provider transaction failed")
        provider_reply = provider_reply_ptr

        _ndk_set_pos(provider_reply, 0)
        _ndk_read_int32(provider_reply, ctypes.byref(exc_code))
        if exc_code.value != 0: raise RuntimeError(f"Service returned exception: {exc_code.value}")

        hdr = ctypes.c_int32()
        _ndk_read_int32(provider_reply, ctypes.byref(hdr))
        _ndk_read_int32(provider_reply, ctypes.byref(hdr))
        _ndk_read_int32(provider_reply, ctypes.byref(hdr))
        if _read_parcel_string(provider_reply) != "value":
            raise RuntimeError(f"Expected key 'value' in returned bundle")
        _ndk_read_int32(provider_reply, ctypes.byref(hdr))
        val = _read_parcel_string(provider_reply)

        if val == '0': return False
        elif val == '1': return True
        else: raise RuntimeError(f"Unexpected value: {val}")

    finally:
        _safe_parcel_delete(provider_reply)
        _safe_parcel_delete(provider_data)
        _safe_dec_strong(connection_binder)
        if settings_provider_binder_ok:
            METHOD_ID = METHOD_ID + 2 # removeContentProviderExternalAsUser, relative, as it is most likely to move whole group on Interface change
            cleanup_data = ctypes.POINTER(AParcel)()
            _ndk_prepare_transaction(service, ctypes.byref(cleanup_data))
            _ndk_write_string(cleanup_data, settings_name.encode('utf-8'), len(settings_name)) # Name
            _ndk_write_strong_binder(cleanup_data, None) # Token
            _ndk_write_int32(cleanup_data, 0) # UserId
            clean_up_reply = ctypes.POINTER(AParcel)()
            # Clean up the resources allocated in the previous call of getContentProviderExternal
            if _ndk_transact(service, METHOD_ID, ctypes.byref(cleanup_data), ctypes.byref(clean_up_reply), 0) != 0:
                print("!!!! Clean-up after binder transaction failed!")
            _safe_parcel_delete(clean_up_reply)
            _safe_parcel_delete(cleanup_data)
        _safe_dec_strong(settings_provider_binder)
        _safe_parcel_delete(reply)
        _safe_parcel_delete(data)
        _safe_dec_strong(service)

"""
This maybe is not super clean way to do this, but at least it is reliable.

Btw. Did you know that the settings binary underneath calls `cmd` binary?
For below call, it would look like so:
`cmd settings get secure flashlight_enabled`

Sadly, I cannot replicate this call using libbinder_ndk.so, as it internally checks
whether we are calling user or system method codes on the service and cmd uses
SHELL_COMMAND_TRANSACTION code, which is regarded as a system one :(
"""
import subprocess
def is_torch_on():
    command = ["/system/bin/settings", "get", "secure", "flashlight_enabled"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    status = result.stdout.strip()

    if status == "1":
        return True
    return False

def set_torch_mode(turn_on: bool, camera_id: str = "0", package_name: str = "com.termux"):
    CLASS_NAME = "android.hardware.ICameraService"
    METHOD_ID = 16 # setTorchMode

    service = None
    client_token = getattr(set_torch_mode, "client_token", None)
    data = None
    reply = None

    try:
        service = _ndk_get_service(b"media.camera")
        if not service: raise ConnectionError("Could not find media.camera service")

        cam_class = _ndk_class_define(CLASS_NAME.encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact_stub)
        if not _ndk_associate_class(service, cam_class): raise RuntimeError("Failed to associate class")

        if not client_token:
            tok_class = _ndk_class_define(f"{package_name}.client_token".encode(), _cb_on_create, _cb_on_destroy, _cb_on_transact_stub)
            client_token = _ndk_aibinder_new(tok_class, None)
            setattr(set_torch_mode, "client_token", client_token)

        data = ctypes.POINTER(AParcel)()
        _ndk_prepare_transaction(service, ctypes.byref(data))

        b_cid = camera_id.encode('utf-8')
        _ndk_write_string(data, b_cid, len(b_cid))
        _ndk_write_int32(data, 1 if turn_on else 0)
        _ndk_write_strong_binder(data, client_token)
        _write_attribution_source(data, package_name)
        _ndk_write_int32(data, 0)

        reply_ptr = ctypes.POINTER(AParcel)()
        if _ndk_transact(service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply_ptr), 0) != 0:
            raise RuntimeError("Binder transaction failed")
        reply = reply_ptr

        _ndk_set_pos(reply, 0)
        exc_code = ctypes.c_int32()
        _ndk_read_int32(reply, ctypes.byref(exc_code))
        if exc_code.value != 0: raise RuntimeError(f"Service exception: {exc_code.value}")

        return True

    finally:
        _safe_parcel_delete(reply)
        _safe_parcel_delete(data)
        _safe_dec_strong(service)

def is_display_off():
    CLASS_NAME = "android.os.IPowerManager"
    METHOD_ID = 21 # isInteractive
    service = None
    data = None
    reply = None
    try:
        service = _ndk_get_service(b"power")
        if not service: raise ConnectionError("Could not find power service")

        cam_class = _ndk_class_define(CLASS_NAME.encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact_stub)
        _ndk_associate_class(service, cam_class)

        data = ctypes.POINTER(AParcel)()
        _ndk_prepare_transaction(service, ctypes.byref(data))

        reply_ptr = ctypes.POINTER(AParcel)()
        _ndk_transact(service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply_ptr), 0)
        reply = reply_ptr

        _ndk_set_pos(reply, 0)
        exc_code = ctypes.c_int32()
        _ndk_read_int32(reply, ctypes.byref(exc_code))
        if exc_code.value != 0: raise RuntimeError(f"Service exception: {exc_code.value}")

        is_interactive = ctypes.c_int32()
        _ndk_read_int32(reply, ctypes.byref(is_interactive))
        return is_interactive.value == 0
    finally:
        _safe_parcel_delete(reply)
        _safe_parcel_delete(data)
        _safe_dec_strong(service)

def is_keyguard_active():
    CLASS_NAME = "android.view.IWindowManager"
    METHOD_ID = 30 # isKeyguardLocked
    service = None
    data = None
    reply = None
    try:
        service = _ndk_get_service(b"window")
        if not service: raise ConnectionError("Could not find window service")

        cam_class = _ndk_class_define(CLASS_NAME.encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact_stub)
        _ndk_associate_class(service, cam_class)

        data = ctypes.POINTER(AParcel)()
        _ndk_prepare_transaction(service, ctypes.byref(data))

        reply_ptr = ctypes.POINTER(AParcel)()
        _ndk_transact(service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply_ptr), 0)
        reply = reply_ptr

        _ndk_set_pos(reply, 0)
        exc_code = ctypes.c_int32()
        _ndk_read_int32(reply, ctypes.byref(exc_code))
        if exc_code.value != 0: raise RuntimeError(f"Service exception: {exc_code.value}")

        is_locked = ctypes.c_int32()
        _ndk_read_int32(reply, ctypes.byref(is_locked))
        return is_locked.value != 0
    finally:
        _safe_parcel_delete(reply)
        _safe_parcel_delete(data)
        _safe_dec_strong(service)

PARTIAL_WAKE_LOCK = 1

# Wake Lock Callback Stub
def _wake_lock_cb(binder, code, data_in, data_out):
    return True
_cb_wake_lock = _OnTransact(_wake_lock_cb)

class WakeLock:
    """
    RAII Wrapper for Android WakeLock.
    Guarantees the system lock is released and binders are dereferenced
    when the object is garbage collected.
    """
    def __init__(self, service, lock_binder, package_name, level):
        self.service = service
        self.lock_binder = lock_binder
        self.package_name = package_name
        self.level = level
        self._released = False

    def _release_wake_lock_internal(self):
        data = None
        reply = None
        METHOD_ID = 3 # releaseWakeLock
        try:
            data_ptr = ctypes.POINTER(AParcel)()
            _ndk_prepare_transaction(self.service, ctypes.byref(data_ptr))
            data = data_ptr
            _ndk_write_strong_binder(data, self.lock_binder)
            _ndk_write_int32(data, self.level)

            reply_ptr = ctypes.POINTER(AParcel)()
            _ndk_transact(self.service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply_ptr), 0)
            reply = reply_ptr
        finally:
            _safe_parcel_delete(data)
            _safe_parcel_delete(reply)
            _safe_dec_strong(self.lock_binder)
            _safe_dec_strong(self.service)

    def release(self):
        if not self._released and self.lock_binder:
            self._release_wake_lock_internal()
            self._released = True
            self.lock_binder = None # Internal logic handles decStrong

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def __del__(self):
        self.release()

def acquire_wake_lock(package_name="com.termux", level=PARTIAL_WAKE_LOCK) -> Optional[WakeLock]:
    METHOD_ID = 1 # acquireWakeLock
    CLASS_NAME = 'android.os.IPowerManager'

    service = _ndk_get_service(b"power")
    if not service:
        raise ConnectionError("Could not find power service")

    power_class = _ndk_class_define(CLASS_NAME.encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact)
    if not _ndk_associate_class(service, power_class):
        raise RuntimeError("Failed to associate class with power_service")

    data = None
    reply = None
    try:
        # Define IWakeLockCallback class
        wl_cb_class = _ndk_class_define(b"android.os.IWakeLockCallback", _cb_on_create, _cb_on_destroy, _cb_on_transact)
        if not wl_cb_class:
            raise RuntimeError("Could not create class for interface: android.os.IWakeLockCallback")
        wakeloc_binder = _ndk_aibinder_new(wl_cb_class, None)
        if not wakeloc_binder:
            raise RuntimeError("Could not create callback binder.")

        data_ptr = ctypes.POINTER(AParcel)()
        _ndk_prepare_transaction(service, ctypes.byref(data_ptr))
        data = data_ptr

        tag = f"{package_name}.wakelock"
        _ndk_write_strong_binder(data, wakeloc_binder)
        _ndk_write_int32(data, level)
        _ndk_write_string(data, tag.encode(), len(tag))
        _ndk_write_string(data, package_name.encode(), len(package_name))
        _ndk_write_int32(data, 0) # No WorkSource
        _ndk_write_string(data, tag.encode(), len(tag)) # historyTag
        _ndk_write_int32(data, 0) # displayId
        _ndk_write_strong_binder(data, wakeloc_binder)

        reply_ptr = ctypes.POINTER(AParcel)()
        status = _ndk_transact(service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply_ptr), 0)
        reply = reply_ptr

        if status == 0:
            return WakeLock(service, wakeloc_binder, package_name, level)

        return None
    except Exception:
        _safe_dec_strong(service)
        raise
    finally:
        _safe_parcel_delete(data)
        _safe_parcel_delete(reply)

# ============================================================================
# 5. LOCATION SERVICES
# ============================================================================

def _write_location_request(data):
    #     public void writeToParcel(@NonNull Parcel parcel, int flags) {
    #     parcel.writeString(mProvider);
    #     parcel.writeLong(mIntervalMillis);
    #     parcel.writeInt(mQuality);
    #     parcel.writeLong(mExpireAtRealtimeMillis);
    #     parcel.writeLong(mDurationMillis);
    #     parcel.writeInt(mMaxUpdates);
    #     parcel.writeLong(mMinUpdateIntervalMillis);
    #     parcel.writeFloat(mMinUpdateDistanceMeters);
    #     parcel.writeLong(mMaxUpdateDelayMillis);
    #     parcel.writeBoolean(mHideFromAppOps);
    #     parcel.writeBoolean(mAdasGnssBypass);
    #     parcel.writeBoolean(mBypass);
    #     parcel.writeBoolean(mLowPower);
    #     parcel.writeTypedObject(mWorkSource, 0);
    # }
    _ndk_write_int32(data, 1) # presence of the object

    GPS_PROVIDER = "gps"
    _ndk_write_string(data, GPS_PROVIDER.encode('utf-8'), len(GPS_PROVIDER)) # mProvider
    _ndk_write_int64(data, 5000)  # mIntervalMillis
    _ndk_write_int32(data, 0x00000064) # mQuality = QUALITY_HIGH_ACCURACY
    # 4. mExpireAtRealtimeMillis (Long)
    # Using a large value or Long.MAX_VALUE equivalent
    _ndk_write_int64(data, 0x7FFFFFFFFFFFFFFF)
    # 5. mDurationMillis (Long)
    _ndk_write_int64(data, 0x7FFFFFFFFFFFFFFF)
    # 6. mMaxUpdates (Int)
    # Using Integer.MAX_VALUE for "no limit"
    _ndk_write_int32(data, 0x7FFFFFFF)
    # 7. mMinUpdateIntervalMillis (Long)
    _ndk_write_int64(data, 0)
    # 8. mMinUpdateDistanceMeters (Float)
    _ndk_write_float(data, 0.0)
    # 9. mMaxUpdateDelayMillis (Long)
    _ndk_write_int64(data, 0)
    # 10. mHideFromAppOps (Boolean -> Int32)
    _ndk_write_int32(data, 0) # False
    # 11. mAdasGnssBypass (Boolean -> Int32)
    _ndk_write_int32(data, 0) # False
    # 12. mBypass (Boolean -> Int32)
    _ndk_write_int32(data, 0) # False
    # 13. mLowPower (Boolean -> Int32)
    _ndk_write_int32(data, 0) # False

    # 14. mWorkSource (TypedObject)
    # First, write a 0 or 1 to indicate if the WorkSource object is present.
    _ndk_write_int32(data, 1)

    _ndk_write_int32(data, 0)  # mNum
    _ndk_write_int32(data, -1) # mUids
    _ndk_write_int32(data, -1) # mNames
    _ndk_write_int32(data, -1) # mChains

# -- Global Callback Registry for Location --
# We use a global registry to map the static C callback to Python methods.
_active_location_listeners: Union[Callable[[ctypes.POINTER(AParcel)], None]] = set()
_active_location_listeners_lock = threading.Lock()

def _static_location_callback(binder, code, data_in, data_out):
    global _active_location_listeners
    global _active_location_listeners_lock
    """Static entry point for location callbacks."""
    with _active_location_listeners_lock:
        if code == 1 and _active_location_listeners: # void onLocation(in @nullable Location location)
            for alm in _active_location_listeners:
                alm.internal_handler(data_in)
            _active_location_listeners.clear()
    return True

_cb_on_transact_location = _OnTransact(_static_location_callback)

class AsyncLocationManager:
    """
    Asynchronous wrapper for Android Location Service via Binder NDK.
    Allows registering a python callback for updates.
    """
    def __init__(self):
        self.service = None
        self.callback_binder = None
        self.is_listening = False
        self.internal_handler = None

        # Initialize Binders once
        self.service = _ndk_get_service(b"location")
        if not self.service:
            raise ConnectionError("Location service not found")
        CLASS_NAME = "android.location.ILocationManager"
        loc_class = _ndk_class_define(CLASS_NAME.encode('utf-8'), _cb_on_create, _cb_on_destroy, _cb_on_transact)
        if not _ndk_associate_class(self.service, loc_class):
            raise RuntimeError("Failed to associate class 'android.location.ILocationManager' with service")

        loc_cb_class = _ndk_class_define(f"android.location.ILocationCallback".encode(),
                                     _cb_on_create, _cb_on_destroy, _cb_on_transact_location)
        if not loc_cb_class:
            raise RuntimeError("Could not create class for interface: android.location.ILocationCallback")
        self.callback_binder = _ndk_aibinder_new(loc_cb_class, None)
        if not self.callback_binder:
            raise RuntimeError("Could not create callback binder.")

    def get_location_async(self, callback_func: Callable[[Dict[str, Any]], None], provider="gps", package_name="com.termux"):
        """
        Starts listening for location updates.
        callback_func receives a dict with keys: provider, time, lat, lng.
        """
        global _active_location_listeners
        global _active_location_listeners_lock
        METHOD_ID = 2 # getCurrentLocation

        with _active_location_listeners_lock:
            # 1. Define internal handler to parse Parcel -> Dict
            def internal_handler(data_in):
                notNull = ctypes.c_int32()
                _ndk_read_int32(data_in, ctypes.byref(notNull))

                if notNull.value not in [0, -1]:
                    HAS_ELAPSED_REALTIME_UNCERTAINTY_MASK = 1 << 8
                    tmpInt32 = ctypes.c_int32()
                    tmpInt64 = ctypes.c_int64()
                    tmpDouble = ctypes.c_double()

                    p_provider = _read_string8(data_in)
                    _ndk_read_int32(data_in, ctypes.byref(tmpInt32)) ; fieldMask = tmpInt32.value
                    _ndk_read_int64(data_in, ctypes.byref(tmpInt64)) ; timeMs = tmpInt64.value
                    _ndk_read_int64(data_in, ctypes.byref(tmpInt64)) # mElapsedRealtimeNs
                    if fieldMask & HAS_ELAPSED_REALTIME_UNCERTAINTY_MASK:
                        _ndk_read_double(data_in, ctypes.byref(tmpDouble))

                    _ndk_read_double(data_in, ctypes.byref(tmpDouble)) ; lng = tmpDouble.value
                    _ndk_read_double(data_in, ctypes.byref(tmpDouble)) ; lat = tmpDouble.value

                    result = {
                        "provider": p_provider,
                        "time_ms": timeMs,
                        "latitude": lat,
                        "longitude": lng,
                        "datetime": datetime.datetime.fromtimestamp(timeMs/1000)
                    }
                    callback_func(result)
                else:
                    # Callback MUST be called to release locks/events
                    callback_func({})
            self.internal_handler = internal_handler
            if self in _active_location_listeners:
                return
            else:
                _active_location_listeners.add(self)
                if len(_active_location_listeners) > 1: # The set wasn't empty, the GPS request has been made from other instance
                    return

        # 3. Send Request (Using initialized binders)
        data = None
        reply = None
        try:
            data = ctypes.POINTER(AParcel)()
            status = _ndk_prepare_transaction(self.service, ctypes.byref(data))
            if status != 0:
                raise RuntimeError(f"Prepare transaction failed: {status}")

            _ndk_write_string(data, provider.encode("utf-8"), len(provider)) # provider
            _write_location_request(data) # request
            _ndk_write_strong_binder(data, self.callback_binder) # callback
            _ndk_write_string(data, package_name.encode("utf-8"), len(package_name))  # packageName
            _ndk_write_string(data, None, -1) # attribution tag
            LISTENER_ID=f"{package_name}.loc.listener"
            _ndk_write_string(data, LISTENER_ID.encode("utf-8"), len(LISTENER_ID)) # listener ID

            # 6. Execute transaction
            reply = ctypes.POINTER(AParcel)()
            status = _ndk_transact(self.service, METHOD_ID, ctypes.byref(data), ctypes.byref(reply), 0)
            if status != 0:
                raise RuntimeError(f"Binder transaction failed with status: {status}")

            # 7. Check service response
            _ndk_set_pos(reply, 0)
            exc_code = ctypes.c_int32()
            _ndk_read_int32(reply, ctypes.byref(exc_code))

            if exc_code.value != 0:
                raise RuntimeError(f"Service exception code: {exc_code.value}")
        finally:
            _safe_parcel_delete(data)
            _safe_parcel_delete(reply)

    def __del__(self):
        """Cleanup binders when the object is destroyed."""
        global _active_location_listeners
        global _active_location_listeners_lock
        with _active_location_listeners_lock:
            if self in _active_location_listeners:
                _active_location_listeners.remove(self)
        _safe_dec_strong(self.callback_binder)
        self.callback_binder = None
        _safe_dec_strong(self.service)
        self.service = None

def get_location(loc_provider: str = "gps", package_name: str = "com.termux", timeout: Optional[Union[float, int]] = None) -> Optional[Dict]:
    """
    Synchronous wrapper to get a single location update.
    Blocks until a location is received or timeout occurs.

    :param timeout: Time in seconds to wait for location. If None, waits indefinitely.
    """
    if not hasattr(get_location, 'manager'):
        setattr(get_location, 'manager',  AsyncLocationManager())

    result_container = {}
    event = threading.Event()
    def cb(data):
        result_container.update(data)
        event.set()

    manager = getattr(get_location, 'manager')
    manager.get_location_async(cb, package_name=package_name, provider=loc_provider)
    # threading.Event.wait(None) blocks indefinitely,
    # wait(number) blocks for that many seconds.
    signaled = event.wait(timeout)
    if signaled:
        return result_container
    else:
        return None

# ============================================================================
# 6. MAIN EXECUTION (DEMO)
# ============================================================================

if __name__ == "__main__":
    print(f"PID: {os.getpid()}")

    # --- Torch / System Check ---
    print("\n--- System Status ---")
    if os.getuid() == 0:
        print("Keyguard active: ", is_keyguard_active())
        print("Display off:     ", is_display_off())
        print("Torch enabled:   ", is_torch_on())
    else:
        print("!WARN: Cannot test is_keyguard_active(), is_display_off() and is_torch_on() binders, must be run as a root!")

    print("\n--- Torch Toggle ---")
    print("Turning torch ON...")
    set_torch_mode(True)
    print("Sleep for 1s...")
    time.sleep(1)
    if os.getuid() == 0:
        print("Torch state now: ", is_torch_on())
    print("Turning torch OFF...")
    set_torch_mode(False)

    # --- Location Sync Check ---
    print("\n--- Synchronous Location Check (may wait) ---")
    with acquire_wake_lock() as lock:
        print("Wakelock acquired for location.")
        if os.getuid() != 0:
            try:
                # Example: wait for 10 seconds. Pass None to wait indefinitely.
                loc = get_location(timeout=10)
                if loc is None:
                    print("Location timed out.")
                else:
                    if loc:
                        print(f"Location received:")
                        print(f"  Provider: {loc['provider']}")
                        print(f"  Time:     {loc['datetime']}")
                        print(f"  Lat/Lng:  {loc['latitude']}, {loc['longitude']}")
                    else:
                        print("Could not determine the location.")

            except Exception as e:
                print(f"Location Error: {e}")
        else:
            print("!WARN: Cannot test location binders, must NOT be run as a root!")
    print("Wakelock released.")
    print("\nDone.")
