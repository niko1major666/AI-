$ErrorActionPreference = "Continue"
$UV = "C:\Users\QWB20\.local\bin\uv.exe"
$Py = "D:\ai-skill-gap\.venv\Scripts\python.exe"
& $UV pip install --python $Py playwright
& $Py -m playwright install chromium
Write-Output "playwright install done"
