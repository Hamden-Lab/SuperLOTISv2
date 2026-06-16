# SuperLOTISv2
Repo containing code for SuperLOTIS upgrade (SOPHIA camera, Pfeiffer Vacuum Pump and INFICON Vacuum Gauge)

## Architecture
* Python scripts to control/command/communicate with devices directly are located in `drivers/`
* Intermediate socket-based interface are located in `clients/`
* Constants and other useful functions are located in `tools/`

## Requirements
* Python 3.14
* opcua: for the Pfeiffer Vacuum Pump
* pyserial: for the INFICON
* pylablib: for the SOPHIA camera
* paramiko: SSH session
* cyberpower: github repo for communicating with CyberPower PDU41001

## Reinstall the package
pip install -e .

## ToDo
* Remember to include PDU IP address and port to constants.py
* remember to include outlet address for all items on PDU to contstants.py