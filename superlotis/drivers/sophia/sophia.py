from pathlib import Path
import datetime
from astropy.io import fits
import socket
import json
from superlotis.tools.constants import SOPHIA_SN, SOPHIA_FRAME_TIMEOUT, SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT
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
            hdr['INSTRUME'] = ('SuperLOTIS telescope', 'Instrument')
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

        # Query SLOTIS status server for all variables
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(2.0)
            client.sendto(b"get all", (SLOTIS_STATUS_SERVER_IP_ADDRESS, SLOTIS_STATUS_SERVER_PORT))

            data, _ = client.recvfrom(8192)
            status = json.loads(data.decode("utf-8"))

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
    
            counter = 1
            while filename.exists():
                filename = output_dir / f"{stem}_{counter:03d}{extension}"
                counter += 1
    
            hdu = fits.PrimaryHDU(data=data, header=header)
            hdu.writeto(filename)
    
            return filename

    def take_exposure(self):
        data = self.cam.grab(nframes=1, frame_timeout=SOPHIA_FRAME_TIMEOUT)
        return data[0]

    
    def take_bias(self):
        temp_exptime = self.cam.get_attribute_value("Exposure Time")

        self.cam.set_attribute_value("Exposure Time", 0) # ms
        data = self.cam.grab(nframes=1, frame_timeout=SOPHIA_FRAME_TIMEOUT)

        self.cam.set_attribute_value("Exposure Time", temp_exptime) # ms
        return data

    def get_exptime(self):
        return self.cam.get_attribute_value("Exposure Time")

    def set_exptime(self, exptime):
        self.cam.set_attribute_value("Exposure Time", exptime)

    def get_temperature(self):
        return self.cam.get_attribute_value("Sensor Temperature Reading")
    
    def set_temperature(self, temp_c):
        self.cam.set_attribute_value("Sensor Temperature Set Point", temp_c) # C

    def get_all_attributes(self):
        # Get all attribute values of the camera (dict that can be stored as FITS headers)
        return self.cam.get_all_attribute_values()

    def open(self):
        return self.cam.open()

    def close(self):
        return self.cam.close()

    def is_open(self):
        return self.cam.is_opened()

if __name__ == "__main__":
    sophia = SOPHIA()
    print(sophia.get_all_attributes())