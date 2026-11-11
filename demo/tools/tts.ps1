# Generates one narration WAV per storyboard segment with a built-in Windows voice (offline, no external service).
param([string]$Storyboard = "$PSScriptRoot\storyboard.json", [string]$OutDir = "$PSScriptRoot\work\voice")

Add-Type -AssemblyName System.Speech
$sb = Get-Content -Raw -Encoding UTF8 $Storyboard | ConvertFrom-Json
New-Item -ItemType Directory -Force $OutDir | Out-Null

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice($sb.voice)
$synth.Rate = [int]$sb.rate
$synth.Volume = 100
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(44100, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)

foreach ($seg in $sb.segments) {
    $path = Join-Path $OutDir ($seg.id + ".wav")
    $synth.SetOutputToWaveFile($path, $format)
    $synth.Speak([string]$seg.say)
    $synth.SetOutputToNull()
    Write-Output ("voiced " + $seg.id)
}
$synth.Dispose()
