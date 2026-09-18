@echo off
setlocal
cd /d "%~dp0"
echo Helix hardware check - read only, nothing uploaded or saved.
echo.
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; 'CPU'; Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name; ''; 'System RAM in GiB'; [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1); ''; 'Windows version'; (Get-CimInstance Win32_OperatingSystem).Caption; ''; 'Display adapter(s)'; Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name; ''; 'Fixed disks: capacity and free space (GiB)'; Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,@{N='SizeGiB';E={[math]::Round($_.Size/1GB,1)}},@{N='FreeGiB';E={[math]::Round($_.FreeSpace/1GB,1)}} | Format-Table -AutoSize"
if errorlevel 1 echo Hardware query failed. Use Task Manager - Performance instead.
where nvidia-smi >nul 2>&1
if errorlevel 1 goto finish
echo NVIDIA GPU memory (MiB)
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
:finish
echo.
echo This report does not include serial numbers, account names or credentials.
echo When NVIDIA tools are unavailable, dedicated VRAM is not determined here.
pause
