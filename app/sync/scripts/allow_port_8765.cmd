@echo off
echo Adding Windows Firewall rule for PlayerDBSync (TCP 8765, inbound)...
netsh advfirewall firewall add rule name="PlayerDBSync_8765" dir=in action=allow protocol=TCP localport=8765
pause
