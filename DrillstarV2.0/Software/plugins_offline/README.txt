DrillStar offline package directory

Files:
- requirements_doc.txt: runtime packages required by the DrillStar source code.
- requirements_bundle_verified.txt: packages currently verified for offline installation from this directory.
- requirements_missing_wheels.txt: required packages that are not currently present as offline wheels.
- install_offline.ps1: installs packages from this directory.

Offline install:
PowerShell:
  .\plugins_offline\install_offline.ps1

Notes:
- The source code uses PyTorch for LSTM and Informer model nodes. Add matching torch wheels before a fully offline install of those features.
- The source code imports vtk in datascope/Modeldisplay.py. Add matching vtk wheels if the 3D model display feature is required.
- nidaqmx is the Python interface package. Real NI hardware access also requires NI drivers/runtime on the target machine.
- MySQL features require access to a MySQL server. This directory does not include the database server.
- install_offline.ps1 prefers requirements_bundle_verified.txt so it only installs packages that are currently available and verified in this directory.
