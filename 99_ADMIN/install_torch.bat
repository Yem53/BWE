@echo off
"C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe" -m pip install --no-cache-dir torch==2.9.0 > "H:\BWE\99_ADMIN\torch_install.log" 2>&1
echo exit=%ERRORLEVEL% >> "H:\BWE\99_ADMIN\torch_install.log"
