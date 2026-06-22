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

## Reinstall the package
pip install -e .

## TODO
- [] remember to include outlet address for all items on PDU to contstants.py
- [] set up NTP time server for PDU in order to have correct timing for logs
- [] remember to modify client scripts for communications with scheduler and status servers if necessary (inficon, sophia)
- timeout of pdu is only 10 minutes max before logging off (see page 63 timeout). KS extend it to 10 minutes from the default 3 minutes.
- write a windows bat file script that create a bunch of CMD terminals for each device driver + client with colours and paths