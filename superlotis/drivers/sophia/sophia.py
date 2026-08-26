from pathlib import Path
from datetime import datetime
from astropy.io import fits
import socket
from superlotis.tools.utilities import parse_status_response
from superlotis.tools.constants import SOPHIA_SN, SOPHIA_FRAME_TIMEOUT, SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT, TCP_BUFFER_SIZE
import pylablib as pll
pll.par["devices/dlls/picam"] = r"C:\Program Files\Princeton Instruments\PICam\Runtime"
from pylablib.devices import PrincetonInstruments


class SOPHIA(object):
    """
    Class to control SOPHIA camera through pylablib package.
    Requires to install official picam drivers.
    Links:
        - https://github.com/AlexShkarin/pyLabLib/tree/main/pylablib/devices/PrincetonInstruments
        - https://pylablib.readthedocs.io/en/stable/devices/Picam.html
        - https://pylablib.readthedocs.io/en/stable/.apidoc/pylablib.devices.PrincetonInstruments.html
    """
    
    def __init__(self):
        self.cam = PrincetonInstruments.PicamCamera(SOPHIA_SN)
        print("CONNECTED TO SOPHIA CAMERA")

    def header_populator(self):
        """
        Query the SLOTIS status server with "get all" and build an
        astropy `Header` populated with returned status variables and
        common camera fields.

        Returns
        -------
        astropy.io.fits.Header
        """

        hdr = fits.Header()

        # Basic instrument/static fields
        try:
            hdr['INSTRUMENT'] = ('SuperLOTIS telescope', 'Instrument')
            hdr['CCDNAME'] = ('Princeton Instruments E2V', 'CCD name')
        except Exception:
            pass

        # Timestamp of header creation
        try:
            hdr['DATE-OBS'] = datetime.datetime.utcnow().isoformat()
        except Exception:
            pass

        # Add camera-specific dynamic fields if available
        try:
            exptime = self.get_exptime()
            hdr['EXPTIME'] = (exptime, 'Exposure time (s)')
        except Exception:
            pass

        try:
            ctemp = self.get_temperature()
            hdr['CCDTEMP'] = (ctemp, 'CCD sensor temperature (C)')
        except Exception:
            pass

        # NOTE: KS: bad practice, you can't have code relating to some external capabilities in the driver code.
        # The driver code should ONLY contain control/command operations with the camera.
        # Query SLOTIS status server for all variables.
        # This following block should go in the client code.
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT))
            msg = "get all"
            sock.sendall(msg.encode("utf-8"))

            chunks = []

            while True:
                try:
                    data = sock.recv(TCP_BUFFER_SIZE)

                    if not data:
                        break

                    chunks.append(data)

                    if b"\n.EOF" in data or data.endswith(b".EOF\n"):
                        break

                except socket.timeout:
                    break

            data = b"".join(chunks)

            status = parse_status_response(data)

            # Populate header with returned status keys using HIERARCH for long names
            for key, val in status.items():
                safe_key = key.upper().replace(' ', '_')
                # FITS standard limits keyword length to 8 chars; use HIERARCH prefix for longer names
                if len(safe_key) > 8:
                    hkey = f"HIERARCH {safe_key}"
                else:
                    hkey = safe_key

                try:
                    hdr[hkey] = val
                    hdr.comments[hkey] = f"status: {key}"
                except Exception:
                    # Fallback to string representation for unsupported values
                    hdr[hkey] = str(val)
                    hdr.comments[hkey] = f"status: {key}"

        except Exception:
            # If status server query fails, return header with whatever we have
            pass

        return hdr

    def save_image(self, data, header=None, output_dir="E:/", base_name="sophia_image", extension=".fits" ):
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
    
            date_str = datetime.now().strftime("%Y%m%d")
            stem = f"{base_name}_{date_str}"
    
            filename = output_dir / f"{stem}{extension}"

            # print here to see; go take another image and inspect this print in the terminal, it also showed nothing but zeroes there
            # print(data[:10])
    
            counter = 1
            while filename.exists():
                filename = output_dir / f"{stem}_{counter:03d}{extension}"
                counter += 1
    
            hdu = fits.PrimaryHDU(data=data, header=header)
            hdu.writeto(filename)
    
            return filename
    
    def take_bias(self):

        self.configure_dark_shutter()

        old_exptime = self.cam.get_attribute_value("Exposure Time")

        self.cam.set_attribute_value("Exposure Time", 0) # ms
        data = self.cam.grab(nframes=1, frame_timeout=SOPHIA_FRAME_TIMEOUT)

        self.cam.set_attribute_value("Exposure Time", old_exptime) # ms
        return data[0]

    def get_exptime(self):
        return self.cam.get_attribute_value("Exposure Time")

    def set_exptime(self, exptime):
        self.cam.set_attribute_value("Exposure Time", exptime)

    def get_temperature(self):
        return self.cam.get_attribute_value("Sensor Temperature Reading")
    
    def set_temperature(self, temp_c):
        # NOTE: keep the get picture in order for the temperature setpoint to take effect (magic)
        self.cam.set_attribute_value("Sensor Temperature Set Point", temp_c) # C

        temp_exptime = self.cam.get_attribute_value("Exposure Time")
        self.cam.set_attribute_value("Exposure Time", 0) # ms
        _ = self.cam.grab(nframes=1, frame_timeout=SOPHIA_FRAME_TIMEOUT)
        self.cam.set_attribute_value("Exposure Time", temp_exptime)

    def get_target_temperature(self):
        return self.cam.get_attribute_value("Sensor Temperature Set Point")

    def get_all_attributes(self):
        # Get all attribute values of the camera (dict that can be stored as FITS headers)
        return self.cam.get_all_attribute_values()

    def open(self):
        return self.cam.open()

    def close(self):
        return self.cam.close()

    def is_open(self):
        return self.cam.is_opened()

    def take_exposure(self, exptime):
        """
        Take a light frame with the CS45 shutter open.

        Parameters
        ----------
        exptime : float
            Exposure time in milliseconds.

        Returns
        -------
        numpy.ndarray
            Light image.
        """
        self.configure_science_shutter()

        self.cam.set_attribute_value(
            "Exposure Time",
            exptime
        )

        data = self.cam.grab(
            nframes=1,
            frame_timeout=SOPHIA_FRAME_TIMEOUT
        )

        return data[0]

    def take_dark(self, exptime):
        """
        Take a dark frame with the CS45 shutter closed.

        The SOPHIA-XO Trigger Out 1 is connected to the VCM-D1
        Pulse Input. For a dark exposure, OUT 1 is forced LOW
        so that the normally-closed CS45 shutter remains closed
        while the CCD integrates.

        Parameters
        ----------
        exptime : float
            Exposure time in milliseconds.

        Returns
        -------
        numpy.ndarray
            Dark image.
        """
        self.configure_dark_shutter()

        if exptime:
            self.cam.set_attribute_value(
            "Exposure Time",
            exptime
        )

        data = self.cam.grab(
            nframes=1,
            frame_timeout=SOPHIA_FRAME_TIMEOUT
        )

        return data[0]

    def configure_science_shutter(self):
        """
        Configure SOPHIA OUT 1 for normal science exposures.

        OUT 1 follows the camera exposure:
            exposure start -> HIGH
            exposure end   -> LOW

        Connected to VCM-D1 Pulse Input, this opens the CS45
        for the duration of the exposure.
        """

        self.cam.set_attribute_value(
            "Output Signal",
            "Exposing"
        )

        self.cam.set_attribute_value(
            "Invert Output Signal",
            False
        )


    def configure_dark_shutter(self):
        """
        Configure SOPHIA OUT 1 so that the CS45 remains closed.

        The CS45/VCM-D1 is configured N.C. (normally closed).

        Always High + inverted produces a continuously LOW
        physical output, so no pulse is sent to the VCM-D1
        Pulse Input.
        """

        self.cam.set_attribute_value(
            "Output Signal",
            "Always High"
        )

        self.cam.set_attribute_value(
            "Invert Output Signal",
            True
        )




if __name__ == "__main__":
    sophia = SOPHIA()
    print(sophia.get_all_attributes())