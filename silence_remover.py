#!/usr/bin/env python3
"""
Silence Remover - Remove silent parts from audio/video files, output clips.

Usage:
    SilenceRemover <input_file> [options]
    
Options:
    --threshold, -t    Silence threshold in dB (default: -40)
    --min-silence, -m  Minimum silence duration in seconds (default: 0.5)
    --buffer-start     Buffer before each clip in seconds (default: 0.1)
    --buffer-end       Buffer after each clip in seconds (default: 0.1)
    --buffer, -b       Buffer for both sides (shorthand)
"""

import os
import re
import subprocess
import sys
from pathlib import Path
import argparse


def get_bundled_path():
    """Get the path where bundled files are located."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def get_ffmpeg_path():
    """Get the path to ffmpeg binary."""
    bundled = get_bundled_path() / "ffmpeg"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"


def get_ffprobe_path():
    """Get the path to ffprobe binary."""
    bundled = get_bundled_path() / "ffprobe"
    if bundled.exists():
        return str(bundled)
    return "ffprobe"


def detect_silence(filepath, threshold, min_duration):
    """Use ffmpeg to detect silent parts."""
    cmd = [
        get_ffmpeg_path(), "-i", filepath,
        "-af", f"silencedetect=noise={threshold}dB:d={min_duration}",
        "-f", "null", "-"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        output = result.stderr
        
        silence_starts = re.findall(r"silence_start: ([\d.]+)", output)
        silence_ends = re.findall(r"silence_end: ([\d.]+)", output)
        
        ranges = []
        for i, start in enumerate(silence_starts):
            if i < len(silence_ends):
                ranges.append((float(start), float(silence_ends[i])))
            else:
                ranges.append((float(start), float('inf')))
        
        return ranges
        
    except subprocess.TimeoutExpired:
        print("Error: Timeout during silence detection")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_duration(filepath):
    """Get the duration of a media file."""
    cmd = [
        get_ffprobe_path(), "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return None


def get_non_silent_segments(silent_ranges, duration, buffer_start, buffer_end):
    """Invert silent ranges to get non-silent segments with buffers."""
    if not silent_ranges:
        return [(0, duration)]
    
    segments = []
    current_pos = 0
    
    for silence_start, silence_end in silent_ranges:
        if silence_end == float('inf'):
            silence_end = duration
        
        if silence_start > current_pos:
            seg_start = max(0, current_pos - buffer_start)
            seg_end = min(duration, silence_start + buffer_end)
            
            if seg_end - seg_start > 0.1:
                segments.append((seg_start, seg_end))
        
        current_pos = silence_end
    
    if current_pos < duration:
        seg_start = max(0, current_pos - buffer_start)
        seg_end = duration
        if seg_end - seg_start > 0.1:
            segments.append((seg_start, seg_end))
    
    if segments:
        segments = merge_segments(segments)
    
    return segments


def merge_segments(segments):
    """Merge overlapping segments."""
    if not segments:
        return []
    
    segments = sorted(segments)
    merged = [segments[0]]
    
    for start, end in segments[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    
    return merged


def extract_segment(input_file, output_file, start, end):
    """Extract a segment from the media file."""
    duration = end - start
    
    cmd = [
        get_ffmpeg_path(), "-y",
        "-ss", str(start),
        "-i", input_file,
        "-t", str(duration),
        "-c", "copy",
        output_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except:
        return False


def process_file(input_path, threshold, min_silence, buffer_start, buffer_end):
    """Process a file and extract non-silent clips."""
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return False
    
    print(f"Processing: {input_path.name}")
    print(f"Settings: threshold={threshold}dB, min_silence={min_silence}s, buffer={buffer_start}s/{buffer_end}s")
    print()
    
    # Detect silence
    print("Detecting silence...")
    silent_ranges = detect_silence(str(input_path), threshold, min_silence)
    
    if silent_ranges is None:
        return False
    
    print(f"Found {len(silent_ranges)} silent sections")
    
    # Get duration
    duration = get_duration(str(input_path))
    if duration is None:
        print("Error: Could not determine file duration")
        return False
    
    print(f"File duration: {duration:.2f}s")
    
    # Calculate segments
    segments = get_non_silent_segments(silent_ranges, duration, buffer_start, buffer_end)
    
    if not segments:
        print("No non-silent segments found!")
        return False
    
    print(f"Extracting {len(segments)} clips...")
    print()
    
    # Create output folder
    output_folder = input_path.parent / input_path.stem
    output_folder.mkdir(exist_ok=True)
    
    # Extract clips
    for i, (start, end) in enumerate(segments):
        output_file = output_folder / f"clip_{i+1:03d}{input_path.suffix}"
        clip_duration = end - start
        
        print(f"  [{i+1}/{len(segments)}] {start:.2f}s - {end:.2f}s ({clip_duration:.2f}s)")
        
        if not extract_segment(str(input_path), str(output_file), start, end):
            print(f"    Warning: Failed to extract clip {i+1}")
    
    print()
    print(f"✅ Done! {len(segments)} clips saved to: {output_folder}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Remove silent parts from audio/video files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    SilenceRemover video.mp4
    SilenceRemover podcast.mp3 -t -35 -m 1.0
    SilenceRemover lecture.mp4 --buffer 0.2
        """
    )
    
    parser.add_argument("input", help="Input audio/video file")
    parser.add_argument("-t", "--threshold", type=float, default=-40,
                        help="Silence threshold in dB (default: -40)")
    parser.add_argument("-m", "--min-silence", type=float, default=0.5,
                        help="Minimum silence duration in seconds (default: 0.5)")
    parser.add_argument("--buffer-start", type=float, default=0.1,
                        help="Buffer before each clip in seconds (default: 0.1)")
    parser.add_argument("--buffer-end", type=float, default=0.1,
                        help="Buffer after each clip in seconds (default: 0.1)")
    parser.add_argument("-b", "--buffer", type=float,
                        help="Buffer for both sides (overrides --buffer-start and --buffer-end)")
    
    args = parser.parse_args()
    
    # Handle combined buffer option
    buffer_start = args.buffer if args.buffer is not None else args.buffer_start
    buffer_end = args.buffer if args.buffer is not None else args.buffer_end
    
    # Check for ffmpeg
    try:
        subprocess.run([get_ffmpeg_path(), "-version"], capture_output=True, timeout=5)
    except:
        print("Error: FFmpeg not found!")
        print("This tool requires FFmpeg. Install it or ensure it's in your PATH.")
        sys.exit(1)
    
    # Process the file
    success = process_file(
        args.input,
        args.threshold,
        args.min_silence,
        buffer_start,
        buffer_end
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
