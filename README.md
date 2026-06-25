# SuperLOTISv2
Repo containing code for SuperLOTIS upgrade (SOPHIA camera, Pfeiffer Vacuum Pump and INFICON Vacuum Gauge)

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