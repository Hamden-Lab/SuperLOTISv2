import serial


class TCubeChiller:
    """
    Driver for the TCUBE Edge Thermoelectric Chiller over RS-232.

    Example
    -------
    >>> chiller = TCubeChiller("/dev/ttyUSB0")
    >>> chiller.connect()
    >>> print(chiller.get_temperature())
    >>> chiller.set_setpoint(20.0)
    >>> chiller.run()
    >>> status = chiller.get_status()
    >>> chiller.disconnect()
    """

    def __init__(
        self,
        port,
        baudrate=9600,
        timeout=1.0,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits

    def connect(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
        )

    def disconnect(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    def _send(self, command):
        if not self.connected:
            raise RuntimeError("Serial port is not connected.")

        if not command.endswith("\r"):
            command += "\r"

        self.ser.reset_input_buffer()
        self.ser.write(command.encode("ascii"))
        self.ser.flush()

    def _query(self, command):
        self._send(command)
        return self.ser.readline().decode("ascii").strip()

    # ------------------------------------------------------------------
    # Basic commands
    # ------------------------------------------------------------------

    def identify(self):
        """Return identification string."""
        return self._query("IDN")

    def local(self):
        """Return control to local mode."""
        self._send("LOCAL")

    def run(self):
        """Start the chiller."""
        self._send("RUN")

    def stop(self):
        """Stop the chiller."""
        self._send("STOP")

    def restart(self):
        """Reset alarms and restart."""
        self._send("RESTART")

    # ------------------------------------------------------------------
    # Temperatures
    # ------------------------------------------------------------------

    def get_temperature(self):
        """Current coolant temperature (°C)."""
        return float(self._query("TEMP?"))

    def get_pump_temperature(self):
        """Pump temperature (°C)."""
        return float(self._query("PUMPTEMP?"))

    def get_setpoint(self):
        """Current setpoint (°C)."""
        return float(self._query("SETTEMP?"))

    def set_setpoint(self, temperature):
        """Set temperature setpoint (°C)."""
        self._send(f"SETTEMP {temperature:.1f}")

    def get_alarm_width(self):
        return float(self._query("WIDTH?"))

    def set_alarm_width(self, width):
        self._send(f"WIDTH {width:.1f}")

    def get_rtd_offset(self):
        return float(self._query("RTDOFFSET?"))

    def set_rtd_offset(self, offset):
        self._send(f"RTDOFFSET {offset:.1f}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_run_state(self):
        """Returns 'RUNNING' or 'STOPPED'."""
        return self._query("RUN?")

    def get_pwm(self):
        """Current thermoelectric PWM (%)."""
        return float(self._query("PWM?"))

    def get_status(self):
        """Status word."""
        return int(self._query("STAT1A?"))

    def get_faults(self):
        """Fault word."""
        return int(self._query("FLTS1A?"))

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def backlight_on(self):
        self._send("BLON")

    def backlight_off(self):
        self._send("BLOFF")

    # ------------------------------------------------------------------
    # Bulk read
    # ------------------------------------------------------------------

    def get_all(self):
        """
        Read all values using GETSET2.

        Returns
        -------
        dict
            {
                "temperature": float,
                "setpoint": float,
                "pump_temperature": float,
                "pwm": float,
                "fan_pwm": float,
                "tank_level_low": int,
                "status": int,
                "faults": int,
            }
        """
        self._send("GETSET2")

        # Read until ETX (0x03)
        raw = b""
        while True:
            b = self.ser.read(1)
            if not b:
                break
            if b == b"\x03":
                break
            raw += b

        fields = raw.decode("ascii").split("\r")
        fields = [f for f in fields if f]

        if len(fields) != 8:
            raise RuntimeError(
                f"Unexpected GETSET2 response ({len(fields)} fields): {fields}"
            )

        return {
            "temperature": float(fields[0]),
            "setpoint": float(fields[1]),
            "pump_temperature": float(fields[2]),
            "pwm": float(fields[3]),
            "fan_pwm": float(fields[4]),
            "tank_level_low": int(fields[5]),
            "status": int(fields[6]),
            "faults": int(fields[7]),
        }


if __name__ == '__main__':

    chiller = TCubeChiller("/dev/ttyUSB0", baudrate=9600)
    chiller.connect()

    print("Identification:", chiller.identify())
