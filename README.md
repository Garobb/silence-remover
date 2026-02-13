# Silence Remover

A simple GUI tool to remove silent parts from audio/video files.

## Features

- Select any audio or video file
- Automatically detects and removes silent sections
- Outputs individual clips to a folder (same name as the file)
- Configurable settings:
  - **Silence threshold (dB)**: How quiet is "silent"? Default -40dB
  - **Min silence duration**: How long must silence last to be cut? Default 0.5s
  - **Buffer before/after**: Padding to keep around each clip (prevents cutting words)

## Requirements

- **FFmpeg** must be installed and in your PATH
  - macOS: `brew install ffmpeg`
  - Windows: Download from https://ffmpeg.org/download.html
  - Linux: `apt install ffmpeg` or equivalent

## Running

### From source
```bash
python silence_remover.py
```

### Build standalone executable
```bash
./build.sh
# or on Windows:
pip install pyinstaller
pyinstaller --onefile --windowed --name "SilenceRemover" silence_remover.py
```

The executable will be in the `dist/` folder.

## How it works

1. Uses FFmpeg's `silencedetect` filter to find silent sections
2. Inverts those to get the non-silent segments
3. Extracts each segment using FFmpeg's stream copy (fast, no re-encoding)
4. Saves clips as `clip_001`, `clip_002`, etc. in a new folder

## Output

Given a file `/path/to/video.mp4`, clips are saved to:
```
/path/to/video/
├── clip_001.mp4
├── clip_002.mp4
├── clip_003.mp4
└── ...
```
