from superlotis.drivers.sophia.sophia import SOPHIA
from superlotis.drivers.pdu41001.pdu41001 import PDU41001
from superlotis.drivers.pfeiffer.pfeiffer import Pfeiffer
from superlotis.drivers.inficon.inficon import PxG55xRS485
from superlotis.drivers.chiller.chiller import TCubeChiller
from superlotis.tools.constants import PSG550_SERIAL_NUMBER, PCG550_SERIAL_NUMBER, PDU41001_IP_ADDRESS, PDU41001_USER, PDU41001_PASSWORD, CHILLER_SERIAL_NUMBER, CHILLER_SERIAL_BAUDRATE, PDU41001_NUMBER_OUTLETS
from serial.tools import list_ports

from datetime import datetime, timezone
import time
from pathlib import Path
from astropy.io import fits

# Camera
sophia = SOPHIA()

# PDU
print("STARTING PDU")
pdu = PDU41001(host=PDU41001_IP_ADDRESS, user=PDU41001_USER, password=PDU41001_PASSWORD)
pdu.connect()
pdu.get_status()

# Pumps
pfeiffer = Pfeiffer()

# Gauges
for port in list_ports.comports():
    print(port)
    if port.serial_number == PSG550_SERIAL_NUMBER:
        print(port)
        pump_gauge = PxG55xRS485(port=port.device)
        pump_gauge.connect()
    if port.serial_number == PCG550_SERIAL_NUMBER:
        camera_gauge = PxG55xRS485(port=port.device)
        camera_gauge.connect()

# Chiller
for port in list_ports.comports():
    if port.serial_number == CHILLER_SERIAL_NUMBER:
        chiller = TCubeChiller(port.device, baudrate=CHILLER_SERIAL_BAUDRATE)
        chiller.connect()

# Data acquisition
NUMBER_BIAS_FRAMES = 10
DELAY = 10

def save_image(data, header=None, output_dir="E:/", base_name="sophia_image", extension=".fits" ):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    stem = f"{date_str}_{base_name}"

    filename = output_dir / f"{stem}{extension}"

    counter = 1
    while filename.exists():
        filename = output_dir / f"{stem}_{counter:03d}{extension}"
        counter += 1

    hdu = fits.PrimaryHDU(data=data, header=header)
    hdu.writeto(filename)
    print(f"{datetime.now(timezone.utc).isoformat()} | FITS IMAGE SUCCESSFULLY SAVED IN {filename}")

    return filename

cam_temperature = -80
sophia.set_temperature(cam_temperature)

# time.sleep(30)

for exposure in range(NUMBER_BIAS_FRAMES):

    cam_status_dict = sophia.get_all_attributes()
    start_exposure_date = datetime.now(timezone.utc).isoformat()
    data = sophia.take_bias()

    hdr = fits.Header()
    hdr['DATE-OBS'] = start_exposure_date
    hdr['EXPTIME'] = cam_status_dict['Exposure Time']
    hdr['EXPTYPE'] = 'BIAS'
    hdr['CCDTEMP'] = cam_status_dict['Sensor Temperature Reading']

    vacuum_status = pfeiffer.get_status()
    vacuum_status = {'pfeiffer_' + key: vacuum_status.pop(key) for key in list(vacuum_status)}
    for key in vacuum_status:
        hdr[key] = vacuum_status[key]

    pdu_power_usage = pdu.get_power_usage()
    hdr['pdu_power_usage'] = float(pdu_power_usage['load']['device_load'].split('/')[1].replace('W', '').replace(' ', ''))

    # Report the current state of each managed outlet.
    for outlet in range(1, PDU41001_NUMBER_OUTLETS+1):
        status = pdu.get_status(
            outlet=outlet
        )[0]["status"].lower()
        hdr[f"pdu_outlet_{outlet:d}"] = status

    chiller_status = chiller.get_all()
    chiller_status = {'chiller_' + key: chiller_status.pop(key) for key in list(chiller_status)}
    for key in chiller_status:
        hdr[key] = chiller_status[key]

    pump_pressure = pump_gauge.get_pressure_real()
    camera_pressure = camera_gauge.get_pressure_real()

    hdr['PUMPRES'] = pump_pressure
    hdr['CAMPRES'] = camera_pressure

    save_image(data, header=hdr, output_dir=f"F:/{datetime.now(timezone.utc).strftime("%Y-%m-%d")}", base_name="BIAS_CAMERA_TO_OUT", extension=".fits" )
    
    time.sleep(DELAY)