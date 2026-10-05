param([switch]$EditorAutomation)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectFile = Join-Path $projectRoot 'One_life_Shot/One_life_Shot.uproject'
$engineVersion = (Get-Content -Raw -LiteralPath $projectFile | ConvertFrom-Json).EngineAssociation
$launcherFile = Join-Path $env:ProgramData 'Epic/UnrealEngineLauncher/LauncherInstalled.dat'
$installation = if (Test-Path -LiteralPath $launcherFile) {
    (Get-Content -Raw -LiteralPath $launcherFile | ConvertFrom-Json).InstallationList |
        Where-Object { $_.ArtifactId -eq ('UE_' + $engineVersion) } | Select-Object -First 1
}
$engineRoot = if ($installation) { $installation.InstallLocation } else { Join-Path 'C:/Program Files/Epic Games' ('UE_' + $engineVersion) }
$editorPath = Join-Path $engineRoot 'Engine/Binaries/Win64/UnrealEditor.exe'
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw 'Unreal Editor is already running. Close it before starting another instance.'
}
if (!(Test-Path -LiteralPath $editorPath) -or !(Test-Path -LiteralPath $projectFile)) {
    throw 'Unreal Editor or project file was not found.'
}
$launchArguments = @(
    ('"{0}"' -f $projectFile), '-dx11', '-nosplash', '-NoLiveCoding', '-nosound',
    '-ModelContextProtocolStartServer', '-log=LowLoadEditor.log',
    '-ExecCmds="t.MaxFPS 20,sg.ViewDistanceQuality 0,sg.AntiAliasingQuality 0,sg.ShadowQuality 0,sg.GlobalIlluminationQuality 0,sg.ReflectionQuality 0,sg.PostProcessQuality 0,sg.TextureQuality 0,sg.EffectsQuality 0,sg.FoliageQuality 0,sg.ShadingQuality 0,r.ScreenPercentage 40,r.Streaming.PoolSize 192"'
)
if ($EditorAutomation) {
    $launchArguments += ('-ExecutePythonScript="{0}"' -f (Join-Path $PSScriptRoot 'Editor-Queue.py'))
}
$editorProcess = Start-Process -FilePath $editorPath -ArgumentList $launchArguments -WindowStyle Hidden -PassThru
try { $editorProcess.PriorityClass = 'BelowNormal' } catch { Write-Warning 'Could not lower process priority.' }
Write-Output ('Started one low-load DX11 editor. PID: {0}' -f $editorProcess.Id)
