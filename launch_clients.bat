@echo on
@REM Last two need to be removed before working with the telescope

set "superlotis=conda activate superlotis"
set "ClientsDir=C:\Users\superlotis\Documents\GitHub\SuperLOTISv2\superlotis\clients"
set "RootDir=C:\Users\superlotis\Documents\GitHub\SuperLOTISv2"

wt --title "Camera" --tabColor "#00ccff" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %ClientsDir%\sophia && ipython -i -c "%%run sophia_client.py" " ^

; nt --title "PDU" --tabColor "#15ff00" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %ClientsDir%\pdu41001 && ipython -i -c "%%run pdu41001_client.py" " ^

; nt --title "Pfeiffer" --tabColor "#ff0000" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %ClientsDir%\pfeiffer && ipython -i -c "%%run pfeiffer_client.py" " ^

; nt --title "Gauges" --tabColor "#fbff00" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %ClientsDir%\inficon && ipython -i -c "%%run inficon_client.py" " ^

; nt --title "Chiller" --tabColor "#9900ff" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %ClientsDir%\chiller && ipython -i -c "%%run chiller_client.py" " ^

; nt --title "test_scheduler" --tabColor "#000000" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %RootDir% && ipython -i -c "%%run scheduler_emulator.py" " ^

; nt --title "test_status" --tabColor "#000000" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %RootDir% && ipython -i -c "%%run status_server_emulator.py" " ^

; nt --title "test_client" --tabColor "#000000" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %RootDir% && ipython -i -c "%%run client_sample_for_status_server.py" " 

