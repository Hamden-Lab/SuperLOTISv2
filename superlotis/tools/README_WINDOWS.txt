Through Microsoft Store:
- Visual Studio Code
- Python Install Manager (3.14 is installed)
- WSL (default Ubuntu)
- Git
- GitHub Desktop

C:\Users\superlotis>python --version
Python 3.14.6

C:\Users\superlotis>wsl.exe --install Ubuntu

TODO:
- Download code repository using git through SSH keys: https://gist.github.com/praneeth-katuri/c9e92bafb43c56849a130f26afab8d92

Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

Install the latest PowerShell for new features and improvements! https://aka.ms/PSWindows

PS C:\WINDOWS\system32> ssh-keygen -t ed25519 -C "your_email@example.com"

PS C:\WINDOWS\system32> Get-Service ssh-agent | Set-Service -StartupType Automatic
PS C:\WINDOWS\system32> Start-Service ssh-agent
PS C:\WINDOWS\system32> Get-Service ssh-agent

Status   Name               DisplayName
------   ----               -----------
Running  ssh-agent          OpenSSH Authentication Agent


PS C:\WINDOWS\system32> ssh-add C:\Users\superlotis\.ssh\id_ed25519
Identity added: C:\Users\superlotis\.ssh\id_ed25519 (sophia_computer)
PS C:\WINDOWS\system32> Set-Service -Name ssh-agent -StartupType Automatic
PS C:\WINDOWS\system32> Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
PS C:\WINDOWS\system32>

superlotis computer: 192.168.1.1

PDU configuration:
username : superlotis
psswd : lotis@553LAB
DHCP = off
IP address = 192.168.1.101
Gateway = 192.168.1.1
DNS = 192.168.1.1

pip install paramiko ipython typing-extensions pylablib pyserial keyring


conda create -n superlotis python=3.14

https://catherineh.github.io/programming/2016/06/07/mimicking-udev-rules-with-pyserial



ssh slotis@slotis.kpno.noirlab.edu
AzTEC!SNe



Each device client script is checking the "scheduler host server" and looking for its FLAG (e.g., for example SLOTIS FILTER for the filter wheel).
Then, it checks the key time contained in the scheduler command row and compares it the current time.

- scheduler_loader.pl : reading the schedule scripts and sending it to the scheduler host server ran in slotis_scheduler.pl
- slotis_scheduler.pl : hosting all the commands that need to be executed during the observation night.
- device_client.pl/py : sending status information to the slotis_status_server + interpreting and transfering commands read from the slotis_scheduler (smart way = identifying FLAG + managing the execution time by comparing it with now to what is contained in the scheduler line) host server to the actual device through serial or ethernet.