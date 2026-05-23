$ErrorActionPreference = 'Stop'

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $Root

function Invoke-Step {
  param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
  )

  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Import-Schritt fehlgeschlagen: $FilePath $($Arguments -join ' ')"
  }
}

$UserSite = python -m site --user-site
if ($UserSite -and (Test-Path -LiteralPath $UserSite)) {
  if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$UserSite;$env:PYTHONPATH"
  } else {
    $env:PYTHONPATH = $UserSite
  }
}

Write-Host ''
Write-Host '=== Quellenbilder extrahieren ==='
Invoke-Step -FilePath python -Arguments @('tools/extract_source_images.py')

Write-Host ''
Write-Host '=== Loesungsdaten extrahieren ==='
Invoke-Step -FilePath python -Arguments @('tools/extract_source_answers.py')

Write-Host ''
Write-Host '=== OCR fuer Quellenbilder ==='
Invoke-Step -FilePath powershell -Arguments @('-ExecutionPolicy', 'Bypass', '-File', 'tools/ocr-assets.ps1', '-InputDir', 'assets', '-Output', 'ocr-extra.json')

Write-Host ''
Write-Host '=== Fragen importieren ==='
Invoke-Step -FilePath python -Arguments @('tools/import_questions.py')

Write-Host ''
Write-Host 'Neuimport abgeschlossen.'
