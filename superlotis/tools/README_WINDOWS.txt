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

