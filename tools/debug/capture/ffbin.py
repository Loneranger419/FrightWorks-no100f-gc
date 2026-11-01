"""ffbin.ffmpeg() / ffbin.ffprobe(): full path to the tool, from PATH or a local copy (get-ffmpeg.ps1 downloads one if needed)."""
import os, shutil, subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_bin = None

def _find():
    global _bin
    if _bin is None:
        if shutil.which('ffmpeg') and shutil.which('ffprobe'):
            _bin = os.path.dirname(shutil.which('ffmpeg'))
        else:
            out = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                  os.path.join(_HERE, 'get-ffmpeg.ps1')], capture_output=True, text=True)
            if out.returncode != 0 or not out.stdout.strip():
                raise SystemExit('ffmpeg not found and get-ffmpeg.ps1 failed:\n' + out.stderr)
            _bin = out.stdout.strip().splitlines()[-1]
    return _bin

def ffmpeg():
    return os.path.join(_find(), 'ffmpeg')

def ffprobe():
    return os.path.join(_find(), 'ffprobe')
