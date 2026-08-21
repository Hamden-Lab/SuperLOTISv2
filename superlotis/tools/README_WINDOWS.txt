Required softwares:
===================
Through Microsoft Store:
- Miniconda
- Visual Studio Code
- Python Install Manager (3.14 is installed)
- WSL (default Ubuntu)
- Git
- GitHub Desktop
- Anydesk
- Picam (to run SOPHIA camera : https://www.teledynevisionsolutions.com/products/picam-sdk-amp-driver/?model=PICAM64&vertical=tvs-princeton-instruments&segment=tvs/#Downloads)

PDU configuration:
==================
username = superlotis
password = lotis@553LAB
DHCP = off
IP address = 192.168.1.101
Gateway = 192.168.1.1
DNS = 192.168.1.1

Create conda environment:
=========================
conda create -n superlotis python=3.14

superlotis computer credentials:
===========================
ssh slotis@slotis.kpno.noirlab.edu
AzTEC!SNe

superlotis admin credientials:
==============================
ssh sladm@slotis.kpno.noirlab.edu
SNe$AzTEC!

Network configuration:
======================
lyman       192.168.1.1
pfeiffer    192.168.1.100
pdu41001    192.168.1.101




PSG = pump gauge
---------------------------------------
Device: COM4
Description: USB Serial Port (COM4)
HWID: USB VID:PID=0403:6001 SER=BG01XA1ZA
VID: 1027
PID: 24577
Serial number: BG01XA1ZA
Manufacturer: FTDI
Product: None
Location: None

PCG = camera gauge
----------------------------------------
Device: COM3
Description: USB Serial Port (COM3)
HWID: USB VID:PID=0403:6001 SER=BG02MO5LA
VID: 1027
PID: 24577
Serial number: BG02MO5LA
Manufacturer: FTDI
Product: None
Location: None


Chiller
----------------------------------------
Device: COM5
Description: USB Serial Port (COM5)
HWID: USB VID:PID=0403:6001 SER=A90O3CT2A
VID: 1027
PID: 24577
Serial number: A90O3CT2A
Manufacturer: FTDI
Product: None
Location: None









Questions for Harrison:

1. Does the scheduler receives data from the clients?
For example, can the scheduler asks to the Pfeiffer pump "get turbo temperature" and then the Pfeiffer pump client server is sending back the info to the scheduler server?
Or (my guess) is that the scheduler server only sends action commands (like set this, set that) and the "get" do not exist for this communication layer. The "gets" are automatically send to the status server only.

2. Hardware: how will you attach the pump electronic box (with the 3d print) to the structure of the telescope chassis?

3. Did your code managing the saving of the FITS files disappear from the repo? I don't see it in the repo right now.
Info: 2 additional disks exist on this computer for data storage: SOPHIA_DATA (1TB) + SOPHIA_DATA2 (2TB)

2026-08-06 14:27:57,425 | ERROR | Socket exception: An existing connection was forcibly closed by the remote host (10054)


Code to test shutter.
It works great with NC + remote + cable to Pulse Input (C).

from pylablib.devices import PrincetonInstruments

cam = PrincetonInstruments.PicamCamera(SOPHIA_SN)

# SOPHIA OUT 1 follows the camera exposure
cam.set_attribute_value(
    "Output Signal",
    "Exposing"
)

cam.set_attribute_value(
    "Invert Output Signal",
    False
)

# 5 second exposure
cam.set_attribute_value(
    "Exposure Time",
    5000
)

print("Output Signal:",
      cam.get_attribute_value("Output Signal"))

print("Invert:",
      cam.get_attribute_value("Invert Output Signal"))

print("\nStarting 5 second exposure...")
print("Watch the CS45 shutter.")

data = cam.grab(
    nframes=1,
    frame_timeout=30000
)

print("Exposure complete.")
print("The shutter should now be CLOSED.")

cam.close()



C:\Users\superlotis>influxdb3 create token --admin

New token created successfully!

Token: apiv3_h6PV8kXTIJMAWsRyzJjfkq-pRNbpwlWBGFYHNpUDvF4JBP68_OF6aNKo-ypz7fYb_1qC90e4jVXBlwISr_DzKw
HTTP Requests Header: Authorization: Bearer apiv3_h6PV8kXTIJMAWsRyzJjfkq-pRNbpwlWBGFYHNpUDvF4JBP68_OF6aNKo-ypz7fYb_1qC90e4jVXBlwISr_DzKw

IMPORTANT: Store this token securely, as it will not be shown again

C:\Users\superlotis>set INFLUXDB3_AUTH_TOKEN=apiv3_h6PV8kXTIJMAWsRyzJjfkq-pRNbpwlWBGFYHNpUDvF4JBP68_OF6aNKo-ypz7fYb_1qC90e4jVXBlwISr_DzKw

C:\Users\superlotis>echo %INFLUXDB3_AUTH_TOKEN%
apiv3_h6PV8kXTIJMAWsRyzJjfkq-pRNbpwlWBGFYHNpUDvF4JBP68_OF6aNKo-ypz7fYb_1qC90e4jVXBlwISr_DzKw

C:\Users\superlotis>influxdb3 create database lyman
Database "lyman" created successfully

# Add InfluxDB3 service executables to the path
[Environment]::SetEnvironmentVariable(
    "Path",
    [Environment]::GetEnvironmentVariable("Path", "User") + ";C:\InfluxDB3",
    "User"
)

# Start the InfluxDB3 database
influxdb3

