param(
    [string]$ExePath = "G:\AI\wpf-lab\bin\Release\net10.0-windows\wpf-lab.exe",
    [string]$OutFile = "G:\AI\universal-uiux-engineering\evidence\T3.4\wpf-uia-evidence.json",
    [string]$Screenshot = "G:\AI\universal-uiux-engineering\evidence\T3.4\wpf-uia.png"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing

$proc = Start-Process -FilePath $ExePath -PassThru
Start-Sleep -Seconds 2

$root = [System.Windows.Automation.AutomationElement]::RootElement
$windowCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Window
)
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $windowCondition)
$target = $null
foreach ($w in $windows) {
    if ($w.Current.ProcessId -eq $proc.Id) { $target = $w; break }
}
if ($null -eq $target) { throw "WPF window not found for pid $($proc.Id)" }

$scriptPath = $MyInvocation.MyCommand.Path
$scriptSha = (Get-FileHash $scriptPath -Algorithm SHA256).Hash.ToLower()

function Get-Descendants($element) {
    return $element.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
}

$elements = @()
foreach ($el in Get-Descendants $target) {
    $elements += [ordered]@{
        name = $el.Current.Name
        control_type = $el.Current.ControlType.ProgrammaticName
        automation_id = $el.Current.AutomationId
        class_name = $el.Current.ClassName
        enabled = $el.Current.IsEnabled
    }
}

function Find-ByAutomationId($rootEl, $id) {
    $cond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $id)
    return $rootEl.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
}

$nameBox = Find-ByAutomationId $target "NameBox"
if ($null -eq $nameBox) { throw "NameBox not found" }
$valuePattern = $nameBox.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
$valuePattern.SetValue("DSH-WPF")

$invokeButton = Find-ByAutomationId $target "InvokeButton"
if ($null -eq $invokeButton) { throw "InvokeButton not found" }
$invoke = $invokeButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
$invoke.Invoke()
Start-Sleep -Milliseconds 500

$status = Find-ByAutomationId $target "StatusText"
$statusText = $status.Current.Name

$dialogSeen = $false
$dialogText = $null
$dialogClosed = $false
$dialogButton = Find-ByAutomationId $target "DialogButton"
if ($null -ne $dialogButton) {
    $dialogInvoke = $dialogButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $dialogInvoke.Invoke()
    Start-Sleep -Milliseconds 800
    $windows2 = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $windowCondition)
    foreach ($w in $windows2) {
        if ($w.Current.ProcessId -eq $proc.Id -and $w.Current.Name -like "*UIA Dialog Test*") {
            $dialogSeen = $true
            $texts = @()
            foreach ($el in Get-Descendants $w) {
                if ($el.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text) { $texts += $el.Current.Name }
            }
            $dialogText = ($texts -join " | ")
            $okCond = New-Object System.Windows.Automation.AndCondition(
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)),
                (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "OK"))
            )
            $ok = $w.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $okCond)
            if ($null -eq $ok) {
                $okCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, "确定")
                $ok = $w.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $okCond)
            }
            if ($null -ne $ok) {
                $ok.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
                Start-Sleep -Milliseconds 500
                $dialogClosed = ($null -eq ($root.FindFirst([System.Windows.Automation.TreeScope]::Children, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $w.Current.Name)))))
            }
        }
    }
}

$bounds = $target.Current.BoundingRectangle
$bitmap = New-Object System.Drawing.Bitmap([int]$bounds.Width, [int]$bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen([int]$bounds.X, [int]$bounds.Y, 0, 0, $bitmap.Size)
$bitmap.Save($Screenshot, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
$shotSha = (Get-FileHash $Screenshot -Algorithm SHA256).Hash.ToLower()

$result = [ordered]@{
    schema_version = "1.3.3"
    evidence_id = "EV-T3.4-WPF-UIA"
    kind = "tool_log"
    runtime_level = "NATIVE_UI_AUTOMATION"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    process = [ordered]@{ id = $proc.Id; exe = $ExePath; title = $target.Current.Name }
    framework_hint = "WPF (class names System.Windows.*)"
    elements = $elements
    actions = [ordered]@{
        set_name_box = "DSH-WPF"
        invoke_button = $true
        status_text = $statusText
        dialog_opened = $dialogSeen
        dialog_text = $dialogText
        dialog_ok_invoked = $dialogClosed
    }
    screenshot = [ordered]@{ path = $Screenshot; sha256 = $shotSha }
    generator = [ordered]@{ path = "scripts/collect_wpf_uia_evidence.ps1"; sha256 = $scriptSha }
    limitations = @(
        "UIA InvokePattern/ValuePattern only; no global physical keyboard or mouse input.",
        "Synthetic WPF lab app; not a real product UI.",
        "MessageBox OK text matched by 'OK' or Chinese '确定'; only this dialog was exercised."
    )
}
$result | ConvertTo-Json -Depth 8 | Set-Content $OutFile -Encoding UTF8
$proc.CloseMainWindow() | Out-Null
Start-Sleep -Milliseconds 500
if (-not $proc.HasExited) { $proc.Kill() }
Write-Host "wpf evidence=$OutFile elements=$($elements.Count) status=$statusText dialog=$dialogSeen ok=$dialogClosed"
