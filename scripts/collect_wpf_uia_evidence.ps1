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
foreach ($w in $windows) { if ($w.Current.ProcessId -eq $proc.Id) { $target = $w; break } }
if ($null -eq $target) { throw "WPF window not found for pid $($proc.Id)" }

function Get-Descendants($element) {
    return $element.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
}
function Find-ByAutomationId($rootEl, $id) {
    $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, $id)
    return $rootEl.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
}
function Find-ByNameAndType($rootEl, $name, $type) {
    $c1 = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $name)
    $c2 = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, $type)
    $cond = New-Object System.Windows.Automation.AndCondition($c1, $c2)
    return $rootEl.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)
}

$elements = @()
foreach ($el in Get-Descendants $target) {
    $elements += [ordered]@{
        name = $el.Current.Name
        control_type = $el.Current.ControlType.ProgrammaticName
        automation_id = $el.Current.AutomationId
        class_name = $el.Current.ClassName
    }
}

$nameBox = Find-ByAutomationId $target "NameBox"
if ($null -eq $nameBox) { throw "NameBox not found" }
$nameBox.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue("DSH-WPF")

$invokeButton = Find-ByAutomationId $target "InvokeButton"
if ($null -eq $invokeButton) { throw "InvokeButton not found" }
$invokeButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Start-Sleep -Milliseconds 500
$statusText = (Find-ByAutomationId $target "StatusText").Current.Name

$dialogButton = Find-ByAutomationId $target "DialogButton"
if ($null -eq $dialogButton) { throw "DialogButton not found" }
$dialogButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
Start-Sleep -Seconds 1

$dialogTextEl = Find-ByNameAndType $target "Native dialog from WPF" ([System.Windows.Automation.ControlType]::Text)
$dialogSeen = ($null -ne $dialogTextEl)
$dialogText = if ($dialogSeen) { $dialogTextEl.Current.Name } else { $null }
$okButton = $null
if ($dialogSeen) {
    $okButton = Find-ByNameAndType $target "确定" ([System.Windows.Automation.ControlType]::Button)
    if ($null -eq $okButton) { $okButton = Find-ByNameAndType $target "OK" ([System.Windows.Automation.ControlType]::Button) }
}
$okInvoked = $false
if ($null -ne $okButton) {
    $okButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Start-Sleep -Milliseconds 500
    $okInvoked = $true
}
$dialogClosed = ($null -eq (Find-ByNameAndType $target "Native dialog from WPF" ([System.Windows.Automation.ControlType]::Text)))

$fileMenu = Find-ByNameAndType $target "File" ([System.Windows.Automation.ControlType]::MenuItem)
$menuExpanded = $false
$menuCloseFound = $false
if ($null -ne $fileMenu) {
    try {
        $fileMenu.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
        Start-Sleep -Milliseconds 300
        $menuExpanded = $true
    } catch { }
    $closeItem = Find-ByNameAndType $target "Close" ([System.Windows.Automation.ControlType]::MenuItem)
    $menuCloseFound = ($null -ne $closeItem)
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
        dialog_ok_invoked = $okInvoked
        dialog_closed = $dialogClosed
        menu_file_expanded = $menuExpanded
        menu_close_item_found = $menuCloseFound
    }
    screenshot = [ordered]@{ path = $Screenshot; sha256 = $shotSha }
    generator = [ordered]@{ path = "scripts/collect_wpf_uia_evidence.ps1"; sha256 = (Get-FileHash $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash.ToLower() }
    limitations = @(
        "UIA InvokePattern/ValuePattern/ExpandCollapsePattern only; no global physical keyboard or mouse input.",
        "Synthetic WPF lab app; not a real product UI.",
        "MessageBox is a child element in the UIA tree; OK text matched by Chinese '确定' or 'OK'.",
        "Screenshot may be blank under background composition; UIA tree is the primary evidence."
    )
}
$result | ConvertTo-Json -Depth 8 | Set-Content $OutFile -Encoding UTF8
$proc.CloseMainWindow() | Out-Null
Start-Sleep -Milliseconds 500
if (-not $proc.HasExited) { $proc.Kill() }
Write-Host "wpf evidence=$OutFile elements=$($elements.Count) status=$statusText dialog=$dialogSeen ok=$okInvoked closed=$dialogClosed menu=$menuExpanded closeItem=$menuCloseFound"
