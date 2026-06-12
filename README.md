# SuperLOTISv2
Repo containing code for SuperLOTIS upgrade (SOPHIA camera, Pfeiffer Vacuum Pump and INFICON Vacuum Gauge)

## Requirements
* Python 3.14
* opcua: for the Pfeiffer Vacuum Pump
* pyserial: for the INFICON
* pylablib: for the SOPHIA camera
* paramiko: SSH session
* cyberpower: github repo for communicating with CyberPower PDU41001

## Reinstall the package
pip install -e .