param(
  [string]$InputDir = 'assets',
  [string]$Output = 'ocr-text.json'
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

function Wait-Async($Operation, [type]$ResultType) {
  $method = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.IsGenericMethodDefinition -and
    $_.GetGenericArguments().Count -eq 1 -and
    $_.GetParameters().Count -eq 1
  })[0]
  $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
  $task.Wait()
  return $task.Result
}

function Read-OcrResult([string]$ImagePath, $Engine) {
  $fullPath = (Resolve-Path -LiteralPath $ImagePath).Path
  $file = Wait-Async ([Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)) ([Windows.Storage.StorageFile])
  $stream = Wait-Async ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
  $decoder = Wait-Async ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Wait-Async ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $result = Wait-Async ($Engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  return [pscustomobject]@{
    text = $result.Text
    lines = @($result.Lines | ForEach-Object { $_.Text })
  }
}

$language = [Windows.Globalization.Language]::new('de-DE')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) {
  throw 'Keine deutsche OCR-Engine verfügbar.'
}

$items = @()
Get-ChildItem -LiteralPath $InputDir -File | Sort-Object Name | ForEach-Object {
  Write-Host "OCR $($_.Name)"
  $ocr = Read-OcrResult $_.FullName $engine
  $items += [pscustomobject]@{
    file = $_.FullName
    name = $_.Name
    text = $ocr.text
    lines = $ocr.lines
  }
}

$items | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Output -Encoding UTF8
