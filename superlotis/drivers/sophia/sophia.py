import pylablib as pll
pll.par["devices/dlls/picam"] = r"C:\Program Files\Princeton Instruments\PICam\Runtime"
from pylablib.devices import PrincetonInstruments
from superlotis.tools.constants import SOPHIA_SN, SOPHIA_FRAME_TIMEOUT

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

    def take_exposure(self):
        data = self.cam.grab(nframes=1, frame_timeout=SOPHIA_FRAME_TIMEOUT)
        return data[0]

    def save_image(self, data, header):
        pass
    
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