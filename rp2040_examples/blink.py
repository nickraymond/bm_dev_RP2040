# code.py — command demo over Bristlemouth (RAW RX), QT Py RP2040, CircuitPython 9.2.0
import time
import json
import binascii
import board
import neopixel
from bm_serial import BristlemouthSerial

# -------------------- Settings --------------------
LED_TOPIC = "device/led"   # BM -> MCU command topic
ACK_PRINT = True           # live bus message (spotter/printf)
ACK_LOG   = True           # write to Spotter SD log (spotter/fprintf)
ACK_LOG_FILE = "led_cmd.log"

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

# Latched LED state (what should persist after transient flashes)
latched_color = led_colors["off"]

def led_set(color):
    global latched_color
    pixel[0] = color
    latched_color = color

def led_flash_transient(color, on_ms=60, off_ms=40, count=2):
    """Flash without changing the latched state; restore at end."""
    global latched_color
    restore = latched_color
    for _ in range(max(1, int(count))):
        pixel[0] = color
        time.sleep(on_ms / 1000.0)
        pixel[0] = restore
        time.sleep(off_ms / 1000.0)

def led_blink_then_restore(color, on_ms=250, off_ms=250, count=5):
    """Blink for 'count' cycles, then restore latched state."""
    global latched_color
    restore = latched_color
    for _ in range(max(1, int(count))):
        pixel[0] = color
        time.sleep(on_ms / 1000.0)
        pixel[0] = restore
        time.sleep(off_ms / 1000.0)

# -------------------- Helpers ---------------------
def safe_decode_text(b: bytes):
    try:
        return b.decode("utf-8")
    except Exception:
        try:
            return str(b, "utf-8")
        except Exception:
            return None

def ack(bm: BristlemouthSerial, msg: str):
    # Live visibility
    if ACK_PRINT:
        try:
            bm.spotter_print(msg)
        except Exception:
            pass
    # SD log on Spotter
    if ACK_LOG:
        try:
            bm.spotter_log(ACK_LOG_FILE, msg)
        except Exception:
            pass

def parse_led_command(js: dict):
    """
    JSON:
      {"led":"blink","period_ms":500,"count":5,"color":"success"}
      {"led":"on","color":"white"}
      {"led":"off"}
    Optional: duty (0..1) for blink (default 0.5)
    """
    cmd = (js.get("led") or "").lower()
    color_name = (js.get("color") or "success").lower()
    color = led_colors.get(color_name, led_colors["success"])

    if cmd == "blink":
        period_ms = int(js.get("period_ms", 500))
        duty = float(js.get("duty", 0.5))
        duty = 0.0 if duty < 0 else (1.0 if duty > 1.0 else duty)
        on_ms = max(1, int(period_ms * duty))
        off_ms = max(0, period_ms - on_ms)
        count = int(js.get("count", 5))
        return ("blink", color, on_ms, off_ms, count, color_name)

    if cmd == "on":
        return ("on", color, 0, 0, 0, color_name)

    if cmd == "off":
        return ("off", led_colors["off"], 0, 0, 0, "off")

    return ("unknown", color, 0, 0, 0, color_name)

# -------------------- BM callback -----------------
def on_pub(node_id, msg_type, version, topic_len, topic, data_len, data):
    # Visual nudge for RX (transient)
    led_flash_transient(led_colors["transmitting"], on_ms=30, off_ms=20, count=2)

    # REPL debug
    print("=== BM PUB RECEIVED ===")
    print("Node ID:    0x{:016X}".format(node_id))
    print("Type:       {}".format(msg_type))
    print("Version:    {}".format(version))
    print("Topic:      {}".format(topic))
    print("Data len:   {}".format(data_len))

    text = safe_decode_text(data)
    if text is None:
        print("Data (text): <non-UTF8>")
    else:
        text = text.rstrip("\x00\r\n")
        print("Data (text):", text)
    print("Data (hex):", binascii.hexlify(data).decode())
    print("=======================")

    if text is None:
        ack(bm_instance, "LED ERR: non-UTF8 payload on {}".format(topic))
        return

    try:
        js = json.loads(text)
    except Exception:
        ack(bm_instance, "LED ERR: invalid JSON: '{}'".format(text))
        return

    mode, color, on_ms, off_ms, count, color_name = parse_led_command(js)

    if mode == "blink":
        msg = "LED ACK: blink color={} on_ms={} off_ms={} count={}".format(
            color_name, on_ms, off_ms, count
        )
        print(msg); ack(bm_instance, msg)
        led_blink_then_restore(color, on_ms=on_ms, off_ms=off_ms, count=count)
        return

    if mode == "on":
        msg = "LED ACK: on color={}".format(color_name)
        print(msg); ack(bm_instance, msg)
        led_set(color)
        return

    if mode == "off":
        msg = "LED ACK: off"
        print(msg); ack(bm_instance, msg)
        led_set(led_colors["off"])
        return

    msg = "LED ERR: unknown command '{}'".format(js.get("led"))
    print(msg); ack(bm_instance, msg)

# -------------------- Main ------------------------
bm_instance = None

def main():
    global bm_instance
    print("Starting BM LED demo…")
    print("Subscribing to:", LED_TOPIC)

    bm_instance = BristlemouthSerial()   # RAW-RX bm_serial handles receive as a single frame
    bm_instance.bristlemouth_sub(LED_TOPIC, on_pub)

    last_heartbeat = time.monotonic()
    led_set(led_colors["off"])  # start off

    while True:
        bm_instance.bristlemouth_process(0.25)

        # Non-destructive heartbeat every 2s (brief blue flash, then restore)
        now = time.monotonic()
        if now - last_heartbeat > 2.0:
            last_heartbeat = now
            led_flash_transient(led_colors["working"], on_ms=15, off_ms=0, count=1)

        time.sleep(0.01)

main()
