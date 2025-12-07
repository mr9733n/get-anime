@echo off
echo Removing Windows Firewall rule PlayerDBSync_8765 ...
netsh advfirewall firewall delete rule name="PlayerDBSync_8765"
pause
