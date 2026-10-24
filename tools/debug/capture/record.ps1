# Record the running game's client area (window capture of the swapchain is black, so grab the desktop region).
# record.ps1 -Out <file.mp4> [-Seconds 5] [-Toggle]   -Toggle creates Play\fogstat.txt for the duration (FOGSTAT/FOGCOV probes)
param([Parameter(Mandatory)][string]$Out, [int]$Seconds = 5, [switch]$Toggle)
$root = Resolve-Path "$PSScriptRoot\..\..\.."
$ffBin = & (Join-Path $PSScriptRoot 'get-ffmpeg.ps1')   # PATH, else tools\debug\local\ffmpeg (downloaded once)
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class FogRecWin {
  [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Rt, B; }
  [StructLayout(LayoutKind.Sequential)] public struct P { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref P p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
'@ -ErrorAction SilentlyContinue
$g = Get-Process 'Scooby-Doo Refrightened' -ErrorAction Stop | Select-Object -First 1
$h = $g.MainWindowHandle
[FogRecWin]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 500
$r = New-Object FogRecWin+R; [FogRecWin]::GetClientRect($h, [ref]$r) | Out-Null
$p = New-Object FogRecWin+P; [FogRecWin]::ClientToScreen($h, [ref]$p) | Out-Null
$flag = Join-Path $root 'Play\fogstat.txt'
if ($Toggle) { Remove-Item $flag -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 300; New-Item $flag -ItemType File -Force | Out-Null }
& (Join-Path $ffBin 'ffmpeg.exe') -hide_banner -loglevel error -y -f gdigrab -framerate 60 -offset_x $p.X -offset_y $p.Y `
  -video_size "$($r.Rt)x$($r.B)" -t $Seconds -i desktop -c:v libx264 -preset ultrafast -qp 10 $Out
if ($Toggle) { Remove-Item $flag -ErrorAction SilentlyContinue }
"recorded $Out ($($r.Rt)x$($r.B))"
