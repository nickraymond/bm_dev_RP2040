# code.py — Minimal RX test for Bristlemouth over UART (CircuitPython 9.2.0)
import time
import json
import binascii

import board
import neopixel

from bm_serial import BristlemouthSerial

# -------------------- Settings --------------------
TOPIC = "device/test"   # <-- change to whatever your BM sender will publish, e.g. "quick_release"
IDLE_BLINK_PERIOD_S = 2.0

# -------------------- LED setup -------------------
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel.brightness = 0.3
led_colors = {
    "success": (0, 255, 0),
    "error": (255, 0, 0),
    "working": (0, 0, 255),
    "transmitting": (0, 255, 255),
}

def led_flash(color_name, on_ms=60, off_ms=40, count=2):
    c = led_colors.get(color_name, (32, 32, 32))
    for _ in range(count):
        pixel[0] = c
        time.sleep(on_ms / 1000.0)
        pixel[0] = (0, 0, 0)
        time.sleep(off_ms / 1000.0)

# -------------------- Callback --------------------
def on_pub(node_id, msg_type, version, topic_len, topic, data_len, data):
    print("=== BM PUB RECEIVED ===")
    print("Node ID:    0x{:016X}".format(node_id))
    print("Type:       {}".format(msg_type))
    print("Version:    {}".format(version))
    print("Topic len:  {}".format(topic_len))
    print("Topic:      {}".format(topic))
    print("Data len:   {}".format(data_len))

    # Safe UTF-8 decode for CircuitPython (no 'errors=' kwarg)
    try:
        text = data.decode("utf-8")
    except Exception:
        # best-effort fallback
        try:
            text = str(data, "utf-8")
        except Exception:
            text = None

    # Trim common terminators if we got text
    if text is not None:
        text = text.rstrip("\x00\r\n")
        print("Data (text):", text)
    else:
        print("Data (text): <non-UTF8>")

    # Always show hex for debugging
    import binascii
    print("Data (hex):", binascii.hexlify(data).decode())

    print("=======================\n")

# -------------------- Main ------------------------
def main():
    print("Starting BM RX test…")
    print("Subscribing to topic:", TOPIC)

    # Bring up BM serial (uses board.TX/board.RX @ 115200 from bm_serial.py)
    bm = BristlemouthSerial()

    # Register our callback and send SUB frame
    bm.bristlemouth_sub(TOPIC, on_pub)

    last_blink = time.monotonic()
    pixel[0] = (0, 0, 0)  # LED off

    while True:
        # Poll the UART and dispatch any received PUBs
        bm.bristlemouth_process(0.25)

        # Tiny heartbeat so you know the loop is alive
        now = time.monotonic()
        if now - last_blink >= IDLE_BLINK_PERIOD_S:
            last_blink = now
            led_flash("working", on_ms=20, off_ms=0, count=1)

        # Keep loop light and friendly for USB REPL
        time.sleep(0.01)

# Entry
main()
