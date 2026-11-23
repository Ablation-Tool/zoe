# Zoe Desktop App for Windows 10/11 (Zero-dependency native PowerShell + Edge App Window)
# Serves the bundled Zoe Home & Dorothy 3D Brain Observatory strictly on 127.0.0.1
# with HTTP 206 byte-range support for MP4 videos, and closes automatically when the window exits.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ObsDir = Join-Path $Root "dorothy_brain_observatory"
if (-not (Test-Path (Join-Path $ObsDir "index.html"))) {
    $ObsDir = Join-Path (Split-Path -Parent (Split-Path -Parent $Root)) "dorothy-brain-observatory"
}
$DeskDir = $Root
if (-not (Test-Path (Join-Path $DeskDir "desktop_home.html"))) {
    $DeskDir = Split-Path -Parent $Root
}

# Pick an available ephemeral loopback port
$tcp = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$tcp.Start()
$Port = $tcp.LocalEndpoint.Port
$tcp.Stop()

$Prefix = "http://127.0.0.1:$Port/"
$MimeMap = @{
    ".html" = "text/html; charset=utf-8"
    ".js"   = "application/javascript; charset=utf-8"
    ".css"  = "text/css; charset=utf-8"
    ".json" = "application/json; charset=utf-8"
    ".svg"  = "image/svg+xml"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".jpeg" = "image/jpeg"
    ".webp" = "image/webp"
    ".gif"  = "image/gif"
    ".mp4"  = "video/mp4"
    ".webm" = "video/webm"
}

$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($Prefix)
$listener.Start()

$ServerJob = Start-ThreadJob -ErrorAction SilentlyContinue -ScriptBlock { }
if ($ServerJob) { Remove-Job $ServerJob -Force -ErrorAction SilentlyContinue }

$Runspace = [runspacefactory]::CreateRunspace()
$Runspace.Open()
$PS = [powershell]::Create()
$PS.Runspace = $Runspace
[void]$PS.AddScript({
    param($listener, $DeskDir, $ObsDir, $MimeMap)
    $obsFull = [System.IO.Path]::GetFullPath($ObsDir)
    while ($listener.IsListening) {
        try {
            $ctx = $listener.GetContext()
        } catch {
            break
        }
        try {
            $rawPath = [System.Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath).TrimStart('/')
            $target = $null
            if ($rawPath -eq "" -or $rawPath -eq "desktop.html" -or $rawPath -eq "desktop_home.html") {
                $cand = Join-Path $DeskDir "desktop_home.html"
                if (Test-Path $cand) { $target = $cand } else { $target = Join-Path $obsFull "index.html" }
            } elseif ($rawPath -eq "zoe-gem.png") {
                $cand = Join-Path $DeskDir "icon.png"
                if (Test-Path $cand) { $target = $cand }
            } else {
                if ($rawPath.StartsWith("brain/")) { $rawPath = $rawPath.Substring(6) }
                if ($rawPath -eq "") { $rawPath = "index.html" }
                $cand = [System.IO.Path]::GetFullPath((Join-Path $obsFull $rawPath))
                if ($cand.StartsWith($obsFull, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path $cand -PathType Leaf)) {
                    $target = $cand
                }
            }
            if (-not $target) {
                $ctx.Response.StatusCode = 404
                $ctx.Response.Close()
                continue
            }
            $ext = [System.IO.Path]::GetExtension($target).ToLowerInvariant()
            $mime = if ($MimeMap.ContainsKey($ext)) { $MimeMap[$ext] } else { "application/octet-stream" }
            $fi = [System.IO.FileInfo]::new($target)
            $total = $fi.Length
            $start = [int64]0
            $end = [Math]::Max([int64]0, $total - 1)
            $status = 200
            $rangeHdr = $ctx.Request.Headers["Range"]
            if ($rangeHdr -and $rangeHdr.ToLowerInvariant().StartsWith("bytes=") -and $total -gt 0) {
                $spec = ($rangeHdr.Substring(6).Split(',')[0]).Trim()
                $parts = $spec.Split('-')
                if ($parts[0]) { $start = [int64]$parts[0] }
                if ($parts.Length -gt 1 -and $parts[1]) { $end = [Math]::Min($total - 1, [int64]$parts[1]) }
                if ($start -ge 0 -and $start -le $end -and $end -lt $total) { $status = 206 }
            }
            $len = if ($total -gt 0) { $end - $start + 1 } else { 0 }
            $ctx.Response.StatusCode = $status
            $ctx.Response.ContentType = $mime
            $ctx.Response.ContentLength64 = $len
            $ctx.Response.AddHeader("Accept-Ranges", "bytes")
            $ctx.Response.AddHeader("Cache-Control", "no-cache")
            if ($status -eq 206) {
                $ctx.Response.AddHeader("Content-Range", "bytes $start-$end/$total")
            }
            if ($ctx.Request.HttpMethod -ne "HEAD" -and $len -gt 0) {
                $fs = [System.IO.File]::OpenRead($target)
                try {
                    [void]$fs.Seek($start, [System.IO.SeekOrigin]::Begin)
                    $buf = New-Object byte[] 65536
                    $rem = $len
                    while ($rem -gt 0) {
                        $n = $fs.Read($buf, 0, [int][Math]::Min($buf.Length, $rem))
                        if ($n -le 0) { break }
                        $ctx.Response.OutputStream.Write($buf, 0, $n)
                        $rem -= $n
                    }
                } finally {
                    $fs.Dispose()
                }
            }
            $ctx.Response.Close()
        } catch {
            try { $ctx.Response.Close() } catch {}
        }
    }
}).AddArgument($listener).AddArgument($DeskDir).AddArgument($ObsDir).AddArgument($MimeMap)
$Async = $PS.BeginInvoke()

$EdgeCandidates = @(
    "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$AppBrowser = $EdgeCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

try {
    if ($AppBrowser) {
        $proc = Start-Process -FilePath $AppBrowser -ArgumentList "--app=$Prefix", "--window-size=1360,860" -PassThru
        $proc.WaitForExit()
    } else {
        Start-Process $Prefix
        Write-Host "Zoe Desktop running at $Prefix. Close this window to stop."
        Start-Sleep -Seconds 3600
    }
} finally {
    $listener.Stop()
    $listener.Close()
    $PS.Stop()
    $PS.Dispose()
    $Runspace.Close()
}
