import serial
import struct
from superlotis.tools.constants import PCG550_SERIAL_PORT, PSG550_SERIAL_PORT

class PxG55xRS485:
    """
    Driver for INFICON PCG550/552/554 and PSG550/552/554 RS485 interface.
    https://www.inficon.com/en/products/vacuum-gauge-and-controller/pcg55x
    """

    DEVICE_ID_MASTER = 0x00

    CMD_READ_REQ = 0x01
    CMD_READ_RESP = 0x02
    CMD_WRITE_REQ = 0x03
    CMD_WRITE_RESP = 0x04

    def __init__(
        self,
        port,
        baudrate=57600,
        address=1,
        timeout=5.0,
    ):
        self.address = address

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )

    def close(self):
        self.ser.close()

    # ------------------------------------------------------------------
    # CRC16 (same algorithm as in the documentation)
    # ------------------------------------------------------------------

    @staticmethod
    def crc16(data: bytes) -> int:
        crc = 0xFFFF

        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0x8408
                else:
                    crc >>= 1

        return crc & 0xFFFF

    @classmethod
    def append_crc(cls, payload: bytes) -> bytes:
        crc = cls.crc16(payload)
        return payload + struct.pack("<H", crc)

    @classmethod
    def verify_crc(cls, frame: bytes):
        if len(frame) < 2:
            return False

        expected = struct.unpack("<H", frame[-2:])[0]
        actual = cls.crc16(frame[:-2])
        return expected == actual

    # ------------------------------------------------------------------
    # Low-level communication
    # ------------------------------------------------------------------

    def _send_old(self, frame: bytes):
        self.ser.reset_input_buffer()
        self.ser.write(frame)

    def _send(self, frame):
        print("TX:", frame.hex(" "))
        self.ser.reset_input_buffer()
        self.ser.write(frame)

    def _read_frame(self):
        # Read first 4-byte header
        header = self.ser.read(4)
        if len(header) != 4:
            raise TimeoutError("Timeout waiting for response header.")

        msg_len = header[3]

        # msg_len counts Cmd + PID + Reserved + Data
        remaining = msg_len + 2  # + CRC16
        body = self.ser.read(remaining)

        if len(body) != remaining:
            raise TimeoutError("Incomplete response.")

        frame = header + body

        if not self.verify_crc(frame):
            raise IOError("CRC check failed.")

        return frame

    # ------------------------------------------------------------------
    # Generic read/write
    # ------------------------------------------------------------------

    def read_pid(self, pid):
        payload = bytearray()

        payload.append(self.address)
        payload.append(self.DEVICE_ID_MASTER)
        payload.append(0x00)        # Ack
        payload.append(5)           # Cmd+PID+Reserved = 1+2+2

        payload.append(self.CMD_READ_REQ)
        payload.extend(struct.pack(">H", pid))
        payload.extend(b"\x00\x00")

        frame = self.append_crc(bytes(payload))

        self._send(frame)

        response = self._read_frame()

        cmd = response[4]
        if cmd != self.CMD_READ_RESP:
            raise IOError("Unexpected response command.")

        pid_returned = struct.unpack(">H", response[5:7])[0]
        if pid_returned != pid:
            raise IOError("Returned PID mismatch.")

        data = response[9:-2]

        return data

    def write_pid(self, pid, data: bytes):
        payload = bytearray()

        payload.append(self.address)
        payload.append(self.DEVICE_ID_MASTER)
        payload.append(0x00)

        msg_length = 5 + len(data)
        payload.append(msg_length)

        payload.append(self.CMD_WRITE_REQ)
        payload.extend(struct.pack(">H", pid))
        payload.extend(b"\x00\x00")
        payload.extend(data)

        frame = self.append_crc(bytes(payload))

        self._send(frame)

        response = self._read_frame()

        if response[4] != self.CMD_WRITE_RESP:
            raise IOError("Write failed.")

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def get_pressure_real(self):
        """
        Read PID 222 (Real32 pressure).

        Returns:
            float : pressure in currently configured units.
        """
        data = self.read_pid(222)
        return struct.unpack(">f", data)[0]

    def get_pressure_fixed(self):
        """
        Read PID 221 (Fixs32en20 integer pressure).

        Returns pressure converted to float.
        """
        data = self.read_pid(221)
        raw = struct.unpack(">i", data)[0]
        return raw / (2 ** 20)

    def get_serial_number(self):
        data = self.read_pid(207)
        return struct.unpack(">I", data)[0]

    def get_product_name(self):
        data = self.read_pid(208)
        return data.decode("ascii").rstrip("\x00")

    def set_pressure_unit(self, unit):
        """
        PID 224

        unit:
            0 = mbar
            1 = Torr
            2 = Pascal
            3 = micron
            4 = Counts
        """
        self.write_pid(224, bytes([unit]))

if __name__ == "__main__":
    gauge = PxG55xRS485(port=PSG550_SERIAL_PORT)
    # print("Serial number:", gauge.get_serial_number())
    # print("Product name:", gauge.get_product_name())
    # print("Pressure (real):", gauge.get_pressure_real())
    # print("Pressure (fixed):", gauge.get_pressure_fixed())