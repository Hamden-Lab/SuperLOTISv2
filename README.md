# SuperLOTISv2
Repo containing code for SuperLOTIS upgrade (SOPHIA camera, Pfeiffer Vacuum Pump and INFICON Vacuum Gauge)

## Issues
- KS : SOPHIA camera does not work through the StarTech USB Hub. Probable cause(s): https://chatgpt.com/s/t_6a70db7d7ffc81919d7addffe3072537, but works through the single 15ft USB3.0 cable. Needs to buy another one I guess.

## Architecture
* Python scripts to control/command/communicate with devices directly are located in `drivers/`
* Intermediate socket-based interface are located in `clients/`
* Constants and other useful functions are located in `tools/`

## Requirements
* Miniconda + Python 3.14
* opcua: for the Pfeiffer Vacuum Pump
* pyserial: for the INFICON
* pylablib: for the SOPHIA camera
* paramiko: SSH session
* typing-extensions
* keyring
* astropy

## Create the conda environment from file
```
conda env create -f environment.yml
```
If new packages have been installed, export again the current env configuration to file:
```
conda export > environment.yml
```

## Activate the conda environment
```
conda activate superlotis
```

## Reinstall the package
```
pip install -e .
```

## TODO
- [] write a sample scheduler script to test with our local devices (pdu + pump...)
- [] testing the camera chiller driver
- [] manage the timing of the scheduler lines now, now + 30, etc.
- [X] why apache2 server installation has root access required to edit php pages ? fixed wit sladm user
- [] remember to include outlet address for all items on PDU to constants.py
- [] write a windows bat file script that create a bunch of CMD terminals for each device driver + client with colours and paths
- [] get attribute names for SOPHIA
- [] implement shutter/dark taking for SOPHIA.py
- [X] set up NTP time server for PDU in order to have correct timing for logs
- [X] timeout of pdu is only 10 minutes max before logging off (see page 63 timeout). KS extend it to 10 minutes from the default 3 minutes.
- [X] send attributes update to slotis status server
- [X] find a way to end the threads properly (both socket server and polling) 
- [X] how to keep data persistent on the scheduler socket server ?

## SLOTIS sockets architecture

- `scheduler_loader.pl` : reading the schedule scripts and sending it to the scheduler host server ran in slotis_scheduler.pl
- `slotis_scheduler.pl` : hosting all the commands that need to be executed during the observation night.
- `device_client.pl/py` : sending status information to the slotis_status_server + interpreting and transfering commands read from the slotis_scheduler (smart way = identifying FLAG + managing the execution time by comparing it with now to what is contained in the scheduler line) host server to the actual device through serial or ethernet.

## Scheduler script sample

```perl
# Specify the exact local time of execution
# as: second minute hour day_of_month month year offset_in_seconds,
# then include the command.
# e.g., "12 10 18 13 11 2004 0 SLOTIS TCS NEXTRA +183210.0" would be executed at Sat Nov 13 18:10:12 2004
# while "12 10 18 13 11 2004 21 SLOTIS TCS NEXTRA +183210.0" would be executed at Sat Nov 13 18:10:43 2004

# A negative offset is also possible.
# e.g.,  "12 10 18 13 11 2004 -3 SLOTIS TCS NEXTRA +183210.0" would be executed at Sat Nov 13 18:10:09 2004
} elsif ( $line =~ /(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*([\-|\s])(\d+)\s+(.+)/ ) {
$sec = $1;
$min = $2;
$hour = $3;
$mday = $4;               # Day of the month
$mon = $5 - 1;            # Months from Time::Local are 0 to 11, this changes the range from 1 to 12 to 0 to 11.
$year = $6;
$sign = $7;
$offset_secs = $8;
$cmd = $9;
$offset_secs = 0 - $offset_secs if $sign =~ /\-/;

$unix_timestamp = timelocal($sec, $min, $hour, $mday, $mon, $year) + $offset_secs;
```

```bash
#Observing schedule for 230518
now -1 SLOTIS SICAM cooler on
now 0 SLOTIS TCS 4 MOVSTOW
now 1 SLOTIS TCS 4 DISEPOCH 2000.0
0 31 19 18 05 2023 -20 SLOTIS TCS 0 ELAZ 85.00 180.00
0 31 19 18 05 2023 -10 SLOTIS TCS 0 TRKON
0 31 19 18 05 2023 0 SLOTIS FILTER position 1
0 31 19 18 05 2023 1 SLOTIS SICAM object Flat_B
0 31 19 18 05 2023 41 SLOTIS SICAM setexp 2000
0 31 19 18 05 2023 44 SLOTIS SICAM expose
0 31 19 18 05 2023 67 SLOTIS SICAM wfits /home/slotis/data/230518/flat001.fits
0 31 19 18 05 2023 88 SLOTIS TCS 0 stepra 100
0 31 19 18 05 2023 98 SLOTIS SICAM setexp 3000
0 31 19 18 05 2023 101 SLOTIS SICAM expose
0 31 19 18 05 2023 125 SLOTIS SICAM wfits /home/slotis/data/230518/flat002.fits
0 31 19 18 05 2023 146 SLOTIS TCS 0 stepra 100
0 31 19 18 05 2023 156 SLOTIS SICAM setexp 3000
0 31 19 18 05 2023 159 SLOTIS SICAM expose
0 31 19 18 05 2023 183 SLOTIS SICAM wfits /home/slotis/data/230518/flat003.fits
0 31 19 18 05 2023 204 SLOTIS TCS 0 stepra 100
0 31 19 18 05 2023 214 SLOTIS SICAM setexp 4000
0 31 19 18 05 2023 217 SLOTIS SICAM expose
0 31 19 18 05 2023 242 SLOTIS SICAM wfits /home/slotis/data/230518/flat004.fits
0 31 19 18 05 2023 263 SLOTIS TCS 0 stepra 100
0 31 19 18 05 2023 273 SLOTIS SICAM setexp 5000
0 31 19 18 05 2023 276 SLOTIS SICAM expose
0 31 19 18 05 2023 302 SLOTIS SICAM wfits /home/slotis/data/230518/flat005.fits
0 31 19 18 05 2023 323 SLOTIS TCS 0 stepra 100
0 31 19 18 05 2023 333 SLOTIS FILTER position 2
0 31 19 18 05 2023 334 SLOTIS SICAM object Flat_V
0 31 19 18 05 2023 374 SLOTIS SICAM setexp 3000
0 31 19 18 05 2023 377 SLOTIS SICAM expose
```


### SOPHIA get all attributes response

```python
Dictionary('ADC Analog Gain': High
'ADC Bit Depth': 16
'ADC Quality': Low Noise
'ADC Speed': 1.0
'Active Bottom Margin': 3
'Active Height': 2048
'Active Left Margin': 50
'Active Right Margin': 50
'Active Shutter': None
'Active Top Margin': 2
'Active Width': 2048
'CCD Characteristics': Back Illuminated & U.V. Enhanced & Multi-Port
'Clean Cycle Count': 1
'Clean Cycle Height': 2048
'Clean Serial Register': True
'Clean Until Trigger': True
'Cooling Fan Status': On
'Correct Pixel Bias': True
'Disable Cooling Fan': False
'Disable Data Formatting': False
'Exact Readout Count Maximum': 1000000000000
'Exposure Time': 100.0
'External Shutter Status': Not Connected
'External Shutter Type': Vincent CS45
'Frame Rate Calculation': 0.22867631860928136
'Frame Size': 8388608
'Frame Stride': 8388608
'Frame Tracking Bit Depth': 64
'Frames per Readout': 1
'Gap Height': 0.0
'Gap Width': 0.0
'Internal Shutter Status': Not Connected
'Internal Shutter Type': Vincent CS45
'Invert Output Signal': False
'Invert Output Signal-2': False
'Kinetics Window Height': 10
'Online Readout Rate Calculation': 0.23402798440173528
'Orientation': Normal
'Output Signal': Exposing
'Output Signal-2': Reading Out
'Pixel Bit Depth': 16
'Pixel Format': Monochrome 16-bit
'Pixel Height': 13.5
'Pixel Width': 13.5
'ROIs': [CPicamRoi(x=0, width=2048, x_binning=1, y=0, height=2048, y_binning=1)]
'Readout Control Mode': Full Frame
'Readout Count': 1
'Readout Orientation': Normal
'Readout Port Count': 1
'Readout Rate Calculation': 0.22867631860928136
'Readout Stride': 8388608
'Readout Time Calculation': 4272.99326
'Sensor Active Bottom Margin': 3
'Sensor Active Extended Height': 0
'Sensor Active Height': 2048
'Sensor Active Left Margin': 50
'Sensor Active Right Margin': 50
'Sensor Active Top Margin': 2
'Sensor Active Width': 2048
'Sensor Masked Bottom Margin': 0
'Sensor Masked Height': 0
'Sensor Masked Top Margin': 0
'Sensor Secondary Active Height': 0
'Sensor Secondary Masked Height': 0
'Sensor Temperature Reading': 19.0
'Sensor Temperature Set Point': 25.0
'Sensor Temperature Status': Unlocked
'Sensor Type': CCD
'Shutter Closing Delay': 0.0
'Shutter Delay Resolution': 1000.0
'Shutter Opening Delay': 0.0
'Shutter Timing Mode': Normal
'Time Stamp Bit Depth': 64
'Time Stamp Resolution': 10000000
'Time Stamps': None
'Track Frames': False
'Trigger Determination': Rising Edge
'Trigger Response': No Response
'Vertical Shift Rate': 12.0)
```


### Populate the headers of FITS images taken by SOPHIA from the status server

INSTRUMENT = 'SuperLOTIS telescope'
CCDNAME = 'Princeton Instruments E2V'
CCDTEMP
CCDTARGETTEMP
CHILLERTEMP
PUMP_PRESSURE
CAM_PRESSURE
VACUUM_VALVE
PDU_OUT1...
EXPTIME
DATE-OBS
MJD
FILTER
MOUNTRA
MOUNTDEC
MOUNTHA
MOUNTALT
MOUNTAZ
OBJECT
AIRMASS
WEATHER_...
CCDGAIN
BINNING
SHUTTER_STATUS
IMTYPE : light, dark, bias, flat...

+ all the attributes from SOPHIA with cam.get_all_attribute_values()