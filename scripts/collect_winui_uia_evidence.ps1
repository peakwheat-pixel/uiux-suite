param(
    [string]$OutFile = "G:\AI\universal-uiux-engineering\evidence\T3.4\winui-uia-evidence.json"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$tmp = Join-Path $env:TEMP "uiux-winui-blank.txt"
Set-Content -Path $tmp -Value "" -NoNewline
$proc = Start-Process -FilePath "notepad.exe" -ArgumentList @($tmp) -PassThru
Start-Sleep -Seconds 2
$root = [System.Windows.Automation.AutomationElement]::RootElement
$wc = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Window)
$target = $null
foreach ($w in $root.FindAll([System.Windows.Automation.TreeScope]::Children, $wc)) {
    if ($w.Current.Name -like "*uiux-winui-blank*") { $target = $w; break }
}
if ($null -eq $target) { throw "Notepad window not found" }

$desc = $target.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$elements = @()
$classes = @()
foreach ($el in $desc) {
    $elements += [ordered]@{
        name = $el.Current.Name
        control_type = $el.Current.ControlType.ProgrammaticName
        class_name = $el.Current.ClassName
        automation_id = $el.Current.AutomationId
    }
    if ($el.Current.ClassName -like "Microsoft.UI.Xaml*") { $classes += $el.Current.ClassName }
}

$docCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Document)
$doc = $target.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $docCond)
$setValueSupported = $false
$readBack = $null
if ($null -ne $doc) {
    try {
        $vp = $doc.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $vp.SetValue("DSH WinUI UIA action")
        $readBack = $vp.Current.Value
        $setValueSupported = $true
    } catch {
        try {
            $tp = $doc.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern)
            $readBack = $tp.DocumentRange.GetText(-1)
        } catch { }
    }
}

$closed = $false
try {
    $wp = $target.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern)
    $wp.Close()
    Start-Sleep -Milliseconds 800
    $saveDialog = $null
    foreach ($w in $root.FindAll([System.Windows.Automation.TreeScope]::Children, $wc)) {
        if ($w.Current.ProcessId -eq $proc.Id -and $w.Current.Name -notlike "*Notepad*" -and $w.Current.Name -notlike "*记事本*") { $saveDialog = $w }
    }
    if ($null -ne $saveDialog) {
        foreach ($name in @("不保存", "Don't save", "否")) {
            $bc = New-Object System.Windows.Automation.AndCondition(
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)),
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $name))
            )
            $b = $saveDialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $bc)
            if ($null -ne $b) { $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); break }
        }
    }
    Start-Sleep -Milliseconds 500
    $closed = $proc.HasExited
} catch { }

$result = [ordered]@{
    schema_version = "1.3.3"
    evidence_id = "EV-T3.4-WINUI-UIA"
    kind = "tool_log"
    runtime_level = "NATIVE_UI_AUTOMATION"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    process = [ordered]@{ id = $proc.Id; exe = "notepad.exe"; title = $target.Current.Name }
    framework_hint = if ($classes.Count -gt 0) { "WinUI 3 (Microsoft.UI.Xaml.Controls.*)" } else { "classic or unknown" }
    xaml_classes = ($classes | Select-Object -Unique)
    elements = $elements
    actions = [ordered]@{
        document_found = ($null -ne $doc)
        value_pattern_set = $setValueSupported
        read_back = $readBack
        window_closed = $closed
    }
    generator = [ordered]@{ path = "scripts/collect_winui_uia_evidence.ps1"; sha256 = (Get-FileHash $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash.ToLower() }
    limitations = @(
        "Blank Notepad window; no file opened or saved.",
        "UIA ValuePattern/TextPattern only; no global physical keyboard input.",
        "WinUI build internals may vary with Windows updates."
    )
}
$result | ConvertTo-Json -Depth 8 | Set-Content $OutFile -Encoding UTF8
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
Write-Host "winui evidence=$OutFile doc=$($null -ne $doc) set=$setValueSupported read=[$readBack] closed=$closed"
