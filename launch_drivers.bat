@echo on
@REM && "cd /d C:\Users\superlotis\Documents\GitHub\SuperLOTISv2\superlotis\clients\sophia"

set "superlotis=conda activate superlotis"
set "WorkDir=C:\Users\superlotis\Documents\GitHub\SuperLOTISv2\superlotis\drivers"

wt --title "Camera" --tabColor "#00ccff" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %WorkDir%\sophia && ipython -i -c "%%run sophia.py" " ^

; nt --title "PDU" --tabColor "#15ff00" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %WorkDir%\pdu41001 && ipython -i -c "%%run pdu41001.py" " ^

; nt --title "Pfeiffer" --tabColor "#ff0000" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %WorkDir%\pfeiffer && ipython -i -c "%%run pfeiffer.py" " ^

; nt --title "Gauges" --tabColor "#6f00ff" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %WorkDir%\inficon && ipython -i -c "%%run inficon.py" " ^

; nt --title "Chiller" --tabColor "#ff00b3" --suppressApplicationTitle cmd /k "%superlotis% && cd /d %WorkDir%\chiller && ipython -i -c "%%run chiller.py" "