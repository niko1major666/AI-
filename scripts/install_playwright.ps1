$ErrorActionPreference = "Continue"
$UV = "C:\Users\QWB20\.local\bin\uv.exe"
$Py = "D:\ai-skill-gap\.venv\Scripts\python.exe"
& $UV pip install --python $Py playwright `
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple `
    --extra-index-url https://pypi.org/simple
& $Py -m playwright install chromium
Write-Output "playwright install done"
