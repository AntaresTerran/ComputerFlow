param([string]$OutputDirectory = "$PSScriptRoot/../.computerflow/validation")
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($taskDirectory) | Out-Null
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$taskCases = @{
    'volume' = 'Setze die Systemlautstärke auf neununddreißig Prozent.'
    'focus' = 'Wechsle zum ComputerFlow Testfenster Alpha.'
    'ambiguous' = 'Wechsle zum ComputerFlow Testfenster.'
    'pause' = 'Pausiere die Wiedergabe im ComputerFlow Testplayer.'
    'play' = 'Starte die Wiedergabe im ComputerFlow Testplayer.'
    'stop' = 'Abbrechen.'
    'chatgpt' = 'Wechsle zu Chat GPT.'
    'thunderbird' = 'Wechsle zu Thunderbird.'
    'editor_name' = 'Wechsle zum Editor.'
    'spotify_pause' = 'Pausiere Spotify.'
    'spotify_short_pause' = 'Spotify, Pause.'
    'wake_focus' = 'Computer, wechsle zum Editor.'
    'wake_volume' = 'Computer, setze die Lautstärke auf fünfzig Prozent.'
    'wake_joined' = 'Computer wechsle zum Editor.'
    'wake_only' = 'Computer.'
    'stop_short' = 'Stopp.'
    'stop_wake' = 'Computer, stopp.'
    'confirm' = 'Computer bestätigen.'
    'negative' = 'Heute läuft wieder ein interessantes Konzert im Radio.'
    'negative_stop' = 'Ich habe gerade einen schönen Film gesehen.'
    'speaker_a' = 'Am frühen Morgen ist das Licht im Garten besonders schön. Viele Vögel singen, und die ersten Fenster gehen auf.'
    'speaker_b' = 'Am Wochenende möchte ich mit Freunden spazieren gehen. Wir treffen uns nach dem Frühstück am Eingang zum Park.'
    'speaker_c' = 'Meine Nachbarin liest gern in der Bibliothek. Heute empfiehlt sie einen Roman über eine Reise ans Meer.'
}
try {
    $taskGerman = $taskSynth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'de-DE' } | Select-Object -First 1
    if (-not $taskGerman) { throw 'Für die deutschen Audio-Testfälle fehlt eine lokale deutsche Stimme.' }
    $taskSynth.SelectVoice($taskGerman.VoiceInfo.Name)
    foreach ($taskCase in $taskCases.GetEnumerator()) {
        $taskSynth.SetOutputToWaveFile((Join-Path $taskDirectory ($taskCase.Key + '.wav')), $taskFormat)
        $taskSynth.Speak($taskCase.Value)
        $taskSynth.SetOutputToNull()
    }
    $taskOther = $taskSynth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -ne $taskGerman.VoiceInfo.Name } | Select-Object -First 1
    if ($taskOther) {
        $taskSynth.SelectVoice($taskOther.VoiceInfo.Name)
        $taskSynth.SetOutputToWaveFile((Join-Path $taskDirectory 'speaker_other.wav'), $taskFormat)
        $taskSynth.Speak('The light in the garden is beautiful in the early morning. Birds sing and the first windows open.')
        $taskSynth.SetOutputToNull()
    }
    Write-Output "Synthetische 16-kHz-Testaufträge erzeugt: $taskDirectory"
} finally { $taskSynth.Dispose() }
