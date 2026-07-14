import os
import struct
import usb1
from adb_shell.auth.sign_pythonrsa import PythonRSASigner
from adb_shell.auth.keygen import keygen

KEY_PATH = os.path.expanduser("~/.android/adbkey")
VENDOR_ID = 0x2ca3
PRODUCT_ID = 0x1021
INTERFACE = 2
EP_OUT = 0x03
EP_IN = 0x84
TIMEOUT = 15000

A_CNXN, A_AUTH, A_OPEN, A_OKAY, A_WRTE, A_CLSE = (
    struct.unpack('<I', b'CNXN')[0], struct.unpack('<I', b'AUTH')[0],
    struct.unpack('<I', b'OPEN')[0], struct.unpack('<I', b'OKAY')[0],
    struct.unpack('<I', b'WRTE')[0], struct.unpack('<I', b'CLSE')[0],
)
AUTH_TOKEN, AUTH_SIGNATURE, AUTH_RSAPUBLICKEY = 1, 2, 3
VERSION = 0x01000000
MAXDATA = 256 * 1024

def ensure_signer():
    if not os.path.exists(KEY_PATH):
        os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
        keygen(KEY_PATH)
    return PythonRSASigner.FromRSAKeyPath(KEY_PATH)

def pack(cmd, arg0, arg1, data=b""):
    if isinstance(data, str):
        data = data.encode()
    checksum = sum(data) & 0xffffffff
    magic = cmd ^ 0xffffffff
    header = struct.pack('<6I', cmd, arg0, arg1, len(data), checksum, magic)
    return header, data

def send(h, cmd, arg0, arg1, data=b""):
    header, data = pack(cmd, arg0, arg1, data)
    n1 = h.bulkWrite(EP_OUT, header, timeout=TIMEOUT)
    n2 = h.bulkWrite(EP_OUT, data, timeout=TIMEOUT) if data else 0
    print(f"Wrote header={n1}/{len(header)} data={n2}/{len(data)}")

def recv(h):
    header = h.bulkRead(EP_IN, 24, timeout=TIMEOUT)
    cmd, arg0, arg1, data_len, checksum, magic = struct.unpack('<6I', header)
    data = h.bulkRead(EP_IN, data_len, timeout=TIMEOUT) if data_len else b""
    return cmd, arg0, arg1, bytes(data)

def open_device():
    ctx = usb1.USBContext()
    dev = ctx.getByVendorIDAndProductID(VENDOR_ID, PRODUCT_ID)
    if dev is None:
        raise RuntimeError("DJI RC2 not found")
    h = dev.open()
    try:
        h.setAutoDetachKernelDriver(True)
    except Exception:
        pass
    h.claimInterface(INTERFACE)
    # Clear any stale halt condition
    try:
        h.clearHalt(EP_OUT)
        h.clearHalt(EP_IN)
    except Exception as e:
        print("clearHalt warning:", e)
    return ctx, h

def handshake(h, signer):
    send(h, A_CNXN, VERSION, MAXDATA, b"host::pydevice\x00")
    cmd, arg0, arg1, data = recv(h)

    if cmd == A_CNXN:
        print("Connected without auth.")
        return

    if cmd != A_AUTH or arg0 != AUTH_TOKEN:
        raise RuntimeError(f"Unexpected: cmd={cmd:x} arg0={arg0}")

    print(f"Got AUTH TOKEN ({len(data)} bytes)")

    # Skip SIGNATURE entirely - RC2 doesn't respond to it.
    # Go straight to RSAPUBLICKEY, matching WebADB's flow.
    pubkey = signer.GetPublicKey()
    if isinstance(pubkey, str):
        pubkey = pubkey.encode()
    if not pubkey.endswith(b"\x00"):
        pubkey += b"\x00"

    send(h, A_AUTH, AUTH_RSAPUBLICKEY, 0, pubkey)
    cmd, arg0, arg1, data = recv(h)

    if cmd == A_CNXN:
        print("Authorized via RSAPUBLICKEY!")
        print("banner:", data)
        return

    raise RuntimeError(f"Auth failed. Response cmd={cmd:x} arg0={arg0}")

_next_local_id = [1]

def shell(h, command):
    _next_local_id[0] += 1
    local_id = _next_local_id[0]

    send(h, A_OPEN, local_id, 0, f"shell:{command}\x00")
    output = b""
    remote_id = None
    while True:
        cmd, arg0, arg1, data = recv(h)

        # Ignore packets that aren't for our stream
        if arg1 not in (0, local_id):
            continue

        if cmd == A_OKAY:
            remote_id = arg0
        elif cmd == A_WRTE:
            output += data
            send(h, A_OKAY, local_id, arg0)
        elif cmd == A_CLSE:
            send(h, A_CLSE, local_id, arg0)
            break
        else:
            break
    return output.decode(errors="replace")

if __name__ == "__main__":
    signer = ensure_signer()
    ctx, h = open_device()
    try:
        handshake(h, signer)
        print("Root shell ready. Type 'exit' to quit.\n")
        while True:
            cmd = input("rc2# ").strip()
            if cmd in ("exit", "quit"):
                break
            if not cmd:
                continue
            print(shell(h, cmd))
    finally:
        h.releaseInterface(INTERFACE)
        h.close()
        