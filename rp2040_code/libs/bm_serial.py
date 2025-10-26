# bm_serial.py — CircuitPython 9.x, Adafruit QT Py RP2040
# RAW RX only (incoming UART bytes are already a complete BM frame).
# TX still uses COBS framing + trailing 0x00 as per BM convention.

import board
import busio
import time


class BristlemouthSerial:
    # Message type constants (align with Pi implementation)
    BM_SERIAL_DEBUG = 0x00
    BM_SERIAL_ACK = 0x01
    BM_SERIAL_PUB = 0x02
    BM_SERIAL_SUB = 0x03
    BM_SERIAL_UNSUB = 0x04
    BM_SERIAL_LOG = 0x05
    BM_SERIAL_NET_MSG = 0x06
    BM_SERIAL_RTC_SET = 0x07
    BM_SERIAL_SELF_TEST = 0x08
    BM_SERIAL_NETWORK_INFO = 0x09
    BM_SERIAL_REBOOT_INFO = 0x0A
    BM_SERIAL_DFU_START = 0x30
    BM_SERIAL_DFU_CHUNK = 0x31
    BM_SERIAL_DFU_RESULT = 0x32
    BM_SERIAL_CFG_GET = 0x40
    BM_SERIAL_CFG_SET = 0x41
    BM_SERIAL_CFG_VALUE = 0x42
    BM_SERIAL_CFG_COMMIT = 0x43
    BM_SERIAL_CFG_STATUS_REQ = 0x44
    BM_SERIAL_CFG_STATUS_RESP = 0x45
    BM_SERIAL_CFG_DEL_REQ = 0x46
    BM_SERIAL_CFG_DEL_RESP = 0x47
    BM_SERIAL_CFG_CLEAR_REQ = 0x48
    BM_SERIAL_CFG_CLEAR_RESP = 0x49
    BM_SERIAL_DEVICE_INFO_REQ = 0x50
    BM_SERIAL_DEVICE_INFO_REPLY = 0x51
    BM_SERIAL_RESOURCE_REQ = 0x52
    BM_SERIAL_RESOURCE_REPLY = 0x53
    BM_SERIAL_NODE_ID_REQ = 0x60
    BM_SERIAL_NODE_ID_REPLY = 0x61
    BM_SERIAL_BAUD_RATE_REQ = 0x70
    BM_SERIAL_BAUD_RATE_REPLY = 0x71

    def __init__(
            self,
            uart=None,
            node_id: int = 0xC0FFEEEEF0CACC1A,
            baudrate: int = 115200,
            rx_bufsize: int = 512
    ) -> None:
        self.node_id = node_id
        self.sub_cbs = []  # callbacks: fn(node_id, type, version, topic_len, topic, data_len, data)
        self._rx_buf = bytearray(rx_bufsize)

        if uart is None:
            try:
                self.uart = busio.UART(
                    board.TX, board.RX,
                    baudrate=baudrate,
                    timeout=0.01,
                    receiver_buffer_size=rx_bufsize
                )
            except TypeError:
                self.uart = busio.UART(board.TX, board.RX, baudrate=baudrate, timeout=0.01)
        else:
            self.uart = uart

    # -------- Public API --------

    def bristlemouth_sub(self, topic: str, fn):
        """
        Register a subscription for a topic and emit a SUB frame.
        Callback signature: fn(node_id, type, version, topic_len, topic, data_len, data)
        """
        if fn not in self.sub_cbs:
            self.sub_cbs.append(fn)

        topic_b = topic.encode("utf-8")
        packet = (
                bytearray.fromhex("03000000")  # [type=0x03, 0x00, CRC(lo), CRC(hi)]
                + len(topic_b).to_bytes(2, "little")  # topic length (u16 LE)
                + topic_b
        )
        return self._uart_write(self._finalize_packet(packet))

    def spotter_tx(self, data: bytes):
        """
        Publish raw data to 'spotter/transmit-data'.
        """
        topic = b"spotter/transmit-data"
        packet = (
                self._get_pub_header()
                + len(topic).to_bytes(2, "little")
                + topic
                + b"\x01"  # version (kept from your working code)
                + data
        )
        return self._uart_write(self._finalize_packet(packet))

    def spotter_log(self, filename: str, data: str):
        """
        Publish a log line to 'spotter/fprintf'.
        """
        topic = b"spotter/fprintf"
        fn_b = filename.encode("utf-8")
        data_b = data.encode("utf-8")
        packet = (
                self._get_pub_header()
                + len(topic).to_bytes(2, "little")
                + topic
                + (b"\x00" * 8)  # reserved
                + len(fn_b).to_bytes(2, "little")
                + (len(data_b) + 1).to_bytes(2, "little")
                + fn_b
                + data_b
                + b"\n"
        )
        return self._uart_write(self._finalize_packet(packet))

    def spotter_print(self, data: str):
        """
        Print a human-readable line to the Spotter terminal (no SD write).
        Uses topic 'spotter/printf' and mirrors the same payload shape
        as spotter_log() (zero filename length + data length + newline).
        """
        topic = b"spotter/printf"
        packet = (
                self._get_pub_header()
                + len(topic).to_bytes(2, "little")
                + topic
                + (b"\x00" * 8)  # reserved
                + (0).to_bytes(2, "little")  # filename length = 0
                + (len(data) + 1).to_bytes(2, "little")  # data length (+ newline)
                + data.encode("utf-8")
                + b"\n"
        )
        return self._uart_write(self._finalize_packet(packet))

    def bristlemouth_process(self, timeout_s: float = 0.5) -> None:
        """
        Poll UART for up to timeout_s and dispatch any PUB frames to subscribed callbacks.
        RX is RAW (no COBS) — the incoming burst is a complete BM frame.
        """
        frames = self._read_burst_until_idle(timeout_s)
        for frame in frames:
            if len(frame) < 4:
                continue
            msg_type = frame[0]
            payload = frame[4:]  # after [type, reserved, crc_lo, crc_hi]
            if msg_type == self.BM_SERIAL_PUB:
                self._process_publish_message(payload)
            # Extend for other message types if needed

    # -------- Internal helpers --------

    def _uart_write(self, b: bytes) -> int:
        return self.uart.write(b)

    def _read_burst_until_idle(self, idle_timeout: float = 0.5):
        """
        RAW RX: read bytes until 'idle_timeout' of silence, return as a single frame.
        """
        start = time.monotonic()
        data = bytearray()
        while True:
            b = self.uart.read(len(self._rx_buf))  # bytes or None
            if b:
                data.extend(b)
                start = time.monotonic()
            else:
                if (time.monotonic() - start) >= idle_timeout:
                    break
                time.sleep(0.01)

        if not data:
            return []
        return [bytes(data)]

    def _process_publish_message(self, payload: bytes) -> None:
        """
        PUB payload layout (as used on your Pi):
          node_id  : u64 LE (8)
          type     : u8  (1)
          version  : u8  (1)
          topic_len: u16 LE (2)
          topic    : bytes[topic_len]
          data     : remaining bytes
        """
        if len(payload) < 12:
            return
        try:
            node_id = int.from_bytes(payload[0:8], "little")
            msg_type = payload[8]
            version = payload[9]
            topic_len = int.from_bytes(payload[10:12], "little")

            end_topic = 12 + topic_len
            if end_topic > len(payload):
                return

            topic_b = payload[12:end_topic]
            try:
                topic = topic_b.decode("utf-8")
            except Exception:
                topic = str(topic_b)

            data = payload[end_topic:]
            data_len = len(data)

            for cb in self.sub_cbs:
                try:
                    cb(node_id, msg_type, version, topic_len, topic, data_len, data)
                except Exception:
                    pass  # keep dispatcher alive

        except Exception:
            pass  # swallow malformed payloads

    def _finalize_packet(self, packet: bytearray) -> bytes:
        checksum = self._crc(0, packet)
        packet[2] = checksum & 0xFF
        packet[3] = (checksum >> 8) & 0xFF
        return self._cobs_encode(packet) + b"\x00"  # TX uses COBS + delimiter

    def _get_pub_header(self) -> bytearray:
        return (
                bytearray.fromhex("02000000")
                + self.node_id.to_bytes(8, "little")
                + bytearray.fromhex("0101")
        )

    # ---------- COBS (TX only) ----------

    def _cobs_encode(self, in_bytes: bytes) -> bytes:
        final_zero = True
        out_bytes = bytearray()
        idx = 0
        search_start_idx = 0
        for in_char in in_bytes:
            if in_char == 0:
                final_zero = True
                out_bytes.append(idx - search_start_idx + 1)
                out_bytes += in_bytes[search_start_idx:idx]
                search_start_idx = idx + 1
            else:
                if idx - search_start_idx == 0xFD:
                    final_zero = False
                    out_bytes.append(0xFF)
                    out_bytes += in_bytes[search_start_idx: idx + 1]
                    search_start_idx = idx + 1
            idx += 1
        if idx != search_start_idx or final_zero:
            out_bytes.append(idx - search_start_idx + 1)
            out_bytes += in_bytes[search_start_idx:idx]
        return bytes(out_bytes)

    # ---------- CRC ----------

    def _crc(self, seed: int, src: bytes) -> int:
        e, f = 0, 0
        for i in src:
            e = (seed ^ i) & 0xFF
            f = e ^ ((e << 4) & 0xFF)
            seed = (seed >> 8) ^ (((f << 8) & 0xFFFF) ^ ((f << 3) & 0xFFFF)) ^ (f >> 4)
        return seed
