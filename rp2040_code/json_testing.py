# code.py — LED + Config via TAP routing only (no duplicate handlers)
import time, json, os, binascii
import board, neopixel
from bm_serial import BristlemouthSerial
from bm_store import ensure_dir, read_json, write_json_atomic

# -------------------- Topics --------------------
LED_TOPIC        = "device/led"
CFG_GET_TOPIC    = "device/config/get"
CFG_SET_TOPIC    = "device/config/set"

# -------------------- Files & defaults -----------
CONFIG_DIR        = "/config"
SYSTEM_JSON_PATH  = "/config/system.json"
SYSTEM_DEFAULTS = {
    "sd_high_hz": 25,
    "sd_low_hz": 1,
    "tx_high_hz": 1,
    "tx_low_hz": 0.2,
    "imu_enabled": True,
}

# -------------------- LED setup -------------------
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel.brightness = 0.3
led_colors = {
    "success": (0, 255, 0),
    "error": (255, 0, 0),
    "working": (0, 0, 255),
    "transmitting": (0, 255, 255),
    "white": (255, 255, 255),
    "off": (0, 0, 0),
}
latched_color = led_colors["off"]

def led_set(color):
    global latched_color
    pixel[0] = color
    latched_color = color

def led_flash_transient(color, on_ms=60, off_ms=40, count=2):
    restore = latched_color
    for _ in range(max(1, int(count))):
        pixel[0] = color; time.sleep(on_ms/1000.0)
        pixel[0] = restore; time.sleep(off_ms/1000.0)

# -------------------- Debugging ---------------------
DEBUG_REPL = True
def dbg(*a):
    if DEBUG_REPL:
        print(*a)

def same_topic(rx: str, expect: str) -> bool:
    # tolerate trailing NULs, spaces, CR/LF weirdness
    if rx is None:
        return False
    rx_clean = rx.rstrip("\x00 \r\n")
    return rx_clean == expect

# -------------------- Helpers ---------------------
def safe_text(b):
    try: return b.decode("utf-8")
    except Exception:
        try: return str(b, "utf-8")
        except Exception: return None

def ack(bm: BristlemouthSerial, msg: str):
    dbg("[ACK]", msg)               # REPL confirmation
    try:
        bm.spotter_print(msg)       # what your BM console shows
    except Exception:
        pass


def fs_is_rw():
    p = "/.rw_test.tmp"
    try:
        with open(p, "w") as f: f.write("x")
        os.remove(p)
        return True
    except Exception:
        return False

# -------------------- Handlers (called from TAP) --
def handle_led(bm, payload_text):
    if payload_text is None:
        ack(bm, "LED ERR: non-UTF8"); return
    if '"off"' in payload_text:
        led_set(led_colors["off"]); ack(bm, "LED ACK: off"); return
    if '"on"' in payload_text:
        led_set(led_colors["white"]); ack(bm, "LED ACK: on white"); return
    # simple blink feedback
    for _ in range(3):
        pixel[0] = led_colors["working"]; time.sleep(0.1)
        pixel[0] = latched_color; time.sleep(0.05)
    ack(bm, "LED ACK: blinked")

def handle_cfg_get(bm):
    try:
        cfg = read_json(SYSTEM_JSON_PATH, SYSTEM_DEFAULTS)
        # was: json.dumps(cfg, separators=(",", ":"), sort_keys=True)
        pretty = json.dumps(cfg)
        dbg("CFG GET ->", pretty)
        ack(bm, "CFG: " + pretty)
    except Exception as e:
        dbg("CFG GET ERROR:", e)
        ack(bm, "CFG ERR: read failed")


def handle_cfg_set(bm, payload_text, fs_rw):
    if payload_text is None:
        ack(bm, "CFG ERR: non-UTF8"); return
    try:
        incoming = json.loads(payload_text.strip().rstrip("\x00\r\n"))
    except Exception as e:
        dbg("CFG SET JSON ERROR:", e, "payload:", payload_text)
        ack(bm, "CFG ERR: bad JSON"); return

    cfg = read_json(SYSTEM_JSON_PATH, SYSTEM_DEFAULTS)
    for k in SYSTEM_DEFAULTS.keys():
        if k in incoming:
            cfg[k] = incoming[k]

    if not fs_rw:
        ack(bm, "CFG ERR: FS is read-only (host-edit mode)"); return

    ok = write_json_atomic(SYSTEM_JSON_PATH, cfg)
    if ok:
        # was: json.dumps(cfg, separators=(",", ":"), sort_keys=True)
        pretty = dumps_sorted(cfg)
        dbg("CFG SET ->", pretty)
        ack(bm, "CFG SAVED: " + pretty)
    else:
        ack(bm, "CFG ERR: write failed")

def dumps_sorted(d: dict) -> str:
    # Manual key order; avoids unsupported json kwargs
    keys = list(d.keys())
    keys.sort()
    parts = []
    for k in keys:
        parts.append('"%s": %s' % (k, json.dumps(d[k])))
    return "{" + ", ".join(parts) + "}"



# -------------------- TAP router ------------------
def tap_router(node_id, msg_type, version, topic_len, topic, data_len, data):
    # Always show what we got (helps diagnose)
    text = safe_text(data)
    short = (text[:100] + "…") if (text and len(text) > 100) else (text or "")
    dbg(f"[RX] topic={topic!r} ({data_len}B) payload={short!r}")
    dbg(f"[ROUTER] eq_get={topic == CFG_GET_TOPIC}, eq_set={topic == CFG_SET_TOPIC}")
    dbg(f"same_get={same_topic(topic, CFG_GET_TOPIC)}, same_set={same_topic(topic, CFG_SET_TOPIC)}")
    if same_topic(topic, LED_TOPIC):
        handle_led(bm, text)
        return

    if same_topic(topic, CFG_GET_TOPIC):
        # ACK immediately so you see it on the BM console, even if anything below fails
        ack(bm, "CFG GET SEEN")
        handle_cfg_get(bm)
        return

    if same_topic(topic, CFG_SET_TOPIC):
        # ACK immediately so you see it on the BM console
        ack(bm, "CFG SET SEEN")
        handle_cfg_set(bm, text, FS_RW)
        return



# -------------------- Main ------------------------
bm = None
FS_RW = False

def main():
    global bm, FS_RW
    print("Starting BM LED + Config (TAP-routed)…")
    FS_RW = fs_is_rw()
    print("[MODE]", "Device-write (RW)" if FS_RW else "Host-edit (RO)")

    if FS_RW:
        ensure_dir(CONFIG_DIR)
        cur = read_json(SYSTEM_JSON_PATH, SYSTEM_DEFAULTS)
        write_json_atomic(SYSTEM_JSON_PATH, cur)
        try: print("[boot] ls /config ->", os.listdir("/config"))
        except Exception as e: print("[boot] ls /config ERROR:", e)

    bm = BristlemouthSerial()
    # Send SUB frames so the network forwards these topics to us
    bm.bristlemouth_sub(LED_TOPIC, lambda *a, **k: None)       # no-op
    bm.bristlemouth_sub(CFG_GET_TOPIC, lambda *a, **k: None)   # no-op
    bm.bristlemouth_sub(CFG_SET_TOPIC, lambda *a, **k: None)   # no-op

    # Single TAP: the router
    try:
        bm.bristlemouth_tap(tap_router)
    except Exception:
        pass

    last = time.monotonic()
    led_set(led_colors["off"])

    while True:
        bm.bristlemouth_process(0.25)
        now = time.monotonic()
        if now - last > 2.0:
            last = now
            led_flash_transient(led_colors["working"], 15, 0, 1)
        time.sleep(0.01)

main()
