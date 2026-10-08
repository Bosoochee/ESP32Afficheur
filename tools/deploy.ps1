# Copie le contenu de src/ à la racine de la carte, puis la redémarre.
# Usage : .\tools\deploy.ps1 [-Port COM5]
param([string]$Port = "auto")
$ErrorActionPreference = "Stop"

Push-Location (Join-Path $PSScriptRoot "..\src")
try {
    # py_compile laisse des __pycache__ que "cp -r lib" copierait sur la carte
    Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
    mpremote connect $Port fs cp -r lib board.py secrets.py tempo.py main.py : + reset
} finally {
    Pop-Location
}
