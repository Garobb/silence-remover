#!/bin/bash
# Build the silence remover as a standalone executable with bundled ffmpeg

set -e
cd "$(dirname "$0")"

echo "=== Silence Remover Builder ==="

# Find ffmpeg and ffprobe
FFMPEG_PATH=$(which ffmpeg)
FFPROBE_PATH=$(which ffprobe)

if [ -z "$FFMPEG_PATH" ] || [ -z "$FFPROBE_PATH" ]; then
    echo "Error: ffmpeg and ffprobe must be installed"
    echo "Install with: brew install ffmpeg"
    exit 1
fi

echo "Found ffmpeg: $FFMPEG_PATH"
echo "Found ffprobe: $FFPROBE_PATH"

# Install pyinstaller if needed
pip install pyinstaller --quiet

# Clean previous builds
rm -rf build dist *.spec

# Build the app with bundled ffmpeg
echo "Building standalone app..."
pyinstaller \
    --onefile \
    --windowed \
    --name "SilenceRemover" \
    --add-binary "$FFMPEG_PATH:." \
    --add-binary "$FFPROBE_PATH:." \
    silence_remover.py

echo ""
echo "✅ Build complete!"
echo ""
echo "Executable: $(pwd)/dist/SilenceRemover"
ls -lh dist/
