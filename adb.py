"""
Custom ADB client for DJI RC2 - forces RSAPUBLICKEY auth response
instead of SIGNATURE, matching what WebADB does.

Install first:
    pip install adb-shell[usb]
    (on Windows you'll also need the WinUSB driver bound to the ADB
     interface - use Zadig if `adb devices` shows the device but this
     script can't find it)
"""

import os
from adb_shell.adb_message import AdbMessage, unpack
from adb_shell.constants import (
    CNXN, AUTH, OPEN, OKAY, WRTE, CLSE,
    AUTH_TOKEN, AUTH_SIGNATURE, AUTH_RSAPUBLICKEY,
    VERSION, MAX_ADB_DATA,
)
from adb_shell.transport.usb_transport import UsbTransport
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.auth.keygen import keygen

KEY_PATH = os.path.expanduser("~/.android/adbkey")

def ensure_keys():
    if not os.path.exists(KEY_PATH):
        os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
        keygen(KEY_PATH)
    return PythonRSASigner.FromRSAKeyPath(KEY_PATH)

def find_transport():
    transport = UsbTransport.find_adb(serial=None)
    if transport is None:
        raise RuntimeError("No ADB-capable USB device found. "
                            "Check Zadig/WinUSB driver binding on Windows.")
    transport.connect()
    return transport

def send(transport, cmd, arg0, arg1, data=b""):
    transport.bulk_write(AdbMessage(cmd, arg0, arg1, data).pack() +
                          (data if not isinstance(data, bytes) else data))

def read_msg(transport):
    header = transport.bulk_read(24)
    cmd, arg0, arg1, data_len, checksum, magic = unpack(header)
    data = transport.bulk_read(data_len) if data_len else b""
    return cmd, arg0, arg1, data

def handshake(transport, signer, banner=b"host::pydevice"):
    # 1. CNXN
    send(transport, CNXN, VERSION, MAX_ADB_DATA, banner + b"\x00")

    cmd, arg0, arg1, data = read_msg(transport)

    if cmd == CNXN:
        print("Connected without auth needed.")
        return True

    if cmd != AUTH or arg0 != AUTH_TOKEN:
        raise RuntimeError(f"Unexpected response: {cmd}")

    token = data

    # 2. Skip SIGNATURE entirely - send RSAPUBLICKEY straight away
    #    (this is the actual fix - stock adb tries SIGNATURE first,
    #    which the RC2 seems to choke on)
    pubkey = signer.GetPublicKey().encode() if isinstance(signer.GetPublicKey(), str) else signer.GetPublicKey()
    if not pubkey.endswith(b"\x00"):
        pubkey += b"\x00"

    send(transport, AUTH, AUTH_RSAPUBLICKEY, 0, pubkey)

    cmd, arg0, arg1, data = read_msg(transport)

    if cmd == CNXN:
        print("Authorized via RSAPUBLICKEY. Check RC2 screen if a popup appears.")
        return True

    raise RuntimeError(f"Auth failed, device responded: {cmd}")

def shell(transport, command):
    """Very minimal OPEN/WRTE/OKAY shell exec - single command, no interactivity."""
    local_id = 1
    send(transport, OPEN, local_id, 0, f"shell:{command}\x00".encode())

    output = b""
    remote_id = None
    while True:
        cmd, arg0, arg1, data = read_msg(transport)
        if cmd == OKAY:
            remote_id = arg0
        elif cmd == WRTE:
            output += data
            send(transport, OKAY, local_id, arg0)
        elif cmd == CLSE:
            send(transport, CLSE, local_id, arg0 if arg0 else 0)
            break
    return output.decode(errors="replace")

if __name__ == "__main__":
    signer = ensure_keys()
    t = find_transport()
    try:
        handshake(t, signer)
        print("--- Testing shell ---")
        print(shell(t, "getprop ro.build.version.release"))
    finally:
        t.close()