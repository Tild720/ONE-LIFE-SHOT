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
    ('"{0}"' -f $projectFile), '-dx11', '-corelimit=2', '-nosplash', '-NoLiveCoding', '-windowed', '-ResX=640', '-ResY=360',
    '-ModelContextProtocolStartServer', '-log=LowLoadEditor.log',
    '-ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreads=64,NumUnusedShaderCompilingThreadsDuringGame=64,ShaderCompilerCoreCountThreshold=128,PercentageUnusedShaderCompilingThreads=100',
    '-ExecCmds="t.MaxFPS 10,sg.ViewDistanceQuality 0,sg.AntiAliasingQuality 0,sg.ShadowQuality 0,sg.GlobalIlluminationQuality 0,sg.ReflectionQuality 0,sg.PostProcessQuality 0,sg.TextureQuality 0,sg.EffectsQuality 0,sg.FoliageQuality 0,sg.ShadingQuality 0,r.ScreenPercentage 20,r.Streaming.PoolSize 128"'
)
if ($EditorAutomation) {
    $launchArguments += ('-ExecutePythonScript="{0}"' -f (Join-Path $PSScriptRoot 'Editor-Queue.py'))
}
$editorProcess = Start-Process -FilePath $editorPath -ArgumentList $launchArguments -WindowStyle Hidden -PassThru
try { $editorProcess.PriorityClass = 'BelowNormal' } catch { Write-Warning 'Could not lower process priority.' }
try { $editorProcess.ProcessorAffinity = [intptr]3 } catch { Write-Warning 'Could not limit the editor to two logical CPUs.' }
Write-Output ('Started one low-load DX11 editor. PID: {0}' -f $editorProcess.Id)
