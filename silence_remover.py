#!/usr/bin/env python3
"""
Silence Remover - GUI app to remove silent parts from audio/video files.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def get_bundled_path():
    """Get the path where bundled files are located."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def get_ffmpeg_path():
    """Get the path to ffmpeg binary."""
    bundled = get_bundled_path() / "ffmpeg.exe"
    if bundled.exists():
        return str(bundled)
    bundled = get_bundled_path() / "ffmpeg"
    if bundled.exists():
        return str(bundled)
    return "ffmpeg"


def get_ffprobe_path():
    """Get the path to ffprobe binary."""
    bundled = get_bundled_path() / "ffprobe.exe"
    if bundled.exists():
        return str(bundled)
    bundled = get_bundled_path() / "ffprobe"
    if bundled.exists():
        return str(bundled)
    return "ffprobe"


class SilenceRemoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Silence Remover")
        self.root.geometry("550x450")
        self.root.resizable(True, True)
        
        self.selected_file = None
        self.processing = False
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.file_label = ttk.Label(file_frame, text="No file selected", wraplength=400)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.browse_btn = ttk.Button(file_frame, text="Browse...", command=self.browse_file)
        self.browse_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Silence threshold
        thresh_frame = ttk.Frame(settings_frame)
        thresh_frame.pack(fill=tk.X, pady=3)
        ttk.Label(thresh_frame, text="Silence threshold (dB):").pack(side=tk.LEFT)
        self.threshold_var = tk.StringVar(value="-40")
        self.threshold_entry = ttk.Entry(thresh_frame, textvariable=self.threshold_var, width=10)
        self.threshold_entry.pack(side=tk.RIGHT)
        ttk.Label(thresh_frame, text="(lower = quieter sounds count as silence)", foreground="gray").pack(side=tk.RIGHT, padx=(0, 10))
        
        # Minimum silence duration to split
        min_silence_frame = ttk.Frame(settings_frame)
        min_silence_frame.pack(fill=tk.X, pady=3)
        ttk.Label(min_silence_frame, text="Min silence to split (sec):").pack(side=tk.LEFT)
        self.min_silence_var = tk.StringVar(value="1.0")
        self.min_silence_entry = ttk.Entry(min_silence_frame, textvariable=self.min_silence_var, width=10)
        self.min_silence_entry.pack(side=tk.RIGHT)
        ttk.Label(min_silence_frame, text="(shorter gaps merged)", foreground="gray").pack(side=tk.RIGHT, padx=(0, 10))
        
        # Minimum clip length
        min_clip_frame = ttk.Frame(settings_frame)
        min_clip_frame.pack(fill=tk.X, pady=3)
        ttk.Label(min_clip_frame, text="Min clip length (sec):").pack(side=tk.LEFT)
        self.min_clip_var = tk.StringVar(value="1.0")
        self.min_clip_entry = ttk.Entry(min_clip_frame, textvariable=self.min_clip_var, width=10)
        self.min_clip_entry.pack(side=tk.RIGHT)
        ttk.Label(min_clip_frame, text="(shorter clips skipped)", foreground="gray").pack(side=tk.RIGHT, padx=(0, 10))
        
        # Buffer slider
        buffer_frame = ttk.Frame(settings_frame)
        buffer_frame.pack(fill=tk.X, pady=(10, 3))
        ttk.Label(buffer_frame, text="Buffer (padding around clips):").pack(side=tk.LEFT)
        self.buffer_label = ttk.Label(buffer_frame, text="0.10 sec")
        self.buffer_label.pack(side=tk.RIGHT)
        
        self.buffer_var = tk.DoubleVar(value=0.1)
        self.buffer_slider = ttk.Scale(
            settings_frame, 
            from_=0, 
            to=1.0, 
            variable=self.buffer_var,
            orient=tk.HORIZONTAL,
            command=self.on_buffer_change
        )
        self.buffer_slider.pack(fill=tk.X, pady=(0, 5))
        
        # Process button
        self.process_btn = ttk.Button(main_frame, text="🎬 Remove Silence", command=self.start_processing)
        self.process_btn.pack(pady=15)
        
        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.status_label = ttk.Label(main_frame, text="Ready", foreground="gray")
        self.status_label.pack()
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.log_text = tk.Text(log_frame, height=8, state=tk.DISABLED, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def on_buffer_change(self, value):
        self.buffer_label.config(text=f"{float(value):.2f} sec")
    
    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def set_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def browse_file(self):
        filetypes = [
            ("Media files", "*.mp4 *.mkv *.avi *.mov *.mp3 *.wav *.flac *.m4a *.webm *.ogg"),
            ("Video files", "*.mp4 *.mkv *.avi *.mov *.webm"),
            ("Audio files", "*.mp3 *.wav *.flac *.m4a *.ogg"),
            ("All files", "*.*")
        ]
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            self.selected_file = filepath
            # Show just filename, not full path
            self.file_label.config(text=os.path.basename(filepath))
            self.log(f"Selected: {filepath}")
    
    def start_processing(self):
        if self.processing:
            return
        
        if not self.selected_file:
            messagebox.showerror("Error", "Please select a file first.")
            return
        
        if not os.path.exists(self.selected_file):
            messagebox.showerror("Error", "Selected file no longer exists.")
            return
        
        # Validate inputs
        try:
            threshold = float(self.threshold_var.get())
            min_silence = float(self.min_silence_var.get())
            min_clip = float(self.min_clip_var.get())
            buffer_time = self.buffer_var.get()
        except ValueError:
            messagebox.showerror("Error", "Invalid numeric values in settings.")
            return
        
        self.processing = True
        self.process_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        
        thread = threading.Thread(
            target=self.process_file,
            args=(threshold, min_silence, min_clip, buffer_time, buffer_time)
        )
        thread.start()
    
    def process_file(self, threshold, min_silence, min_clip, buffer_start, buffer_end):
        try:
            self.set_status("Detecting silence...")
            self.log("Analyzing audio for silence...")
            self.progress_var.set(10)
            
            silent_ranges = self.detect_silence(self.selected_file, threshold, min_silence)
            
            if silent_ranges is None:
                self.log("Error detecting silence.")
                self.set_status("Error")
                return
            
            self.log(f"Found {len(silent_ranges)} silent sections")
            self.progress_var.set(30)
            
            duration = self.get_duration(self.selected_file)
            if duration is None:
                self.log("Error getting file duration.")
                self.set_status("Error")
                return
            
            self.log(f"File duration: {duration:.2f}s")
            
            segments = self.get_non_silent_segments(silent_ranges, duration, buffer_start, buffer_end)
            
            # Filter out clips that are too short
            original_count = len(segments)
            segments = [(s, e) for s, e in segments if (e - s) >= min_clip]
            skipped = original_count - len(segments)
            if skipped > 0:
                self.log(f"Skipped {skipped} clips shorter than {min_clip}s")
            
            if not segments:
                self.log("No non-silent segments found!")
                self.set_status("No clips to extract")
                messagebox.showinfo("Done", "No non-silent segments found in the file.")
                return
            
            self.set_status(f"Extracting {len(segments)} clips...")
            self.log(f"Extracting {len(segments)} clips...")
            self.progress_var.set(40)
            
            input_path = Path(self.selected_file)
            output_folder = input_path.parent / input_path.stem
            output_folder.mkdir(exist_ok=True)
            
            self.log(f"Output: {output_folder}")
            
            for i, (start, end) in enumerate(segments):
                progress = 40 + (55 * (i + 1) / len(segments))
                self.progress_var.set(progress)
                self.set_status(f"Extracting clip {i+1}/{len(segments)}...")
                
                output_file = output_folder / f"clip_{i+1:03d}{input_path.suffix}"
                
                if not self.extract_segment(self.selected_file, str(output_file), start, end):
                    self.log(f"Warning: Failed to extract clip {i+1}")
            
            self.progress_var.set(100)
            self.set_status("Done!")
            self.log(f"✓ Saved {len(segments)} clips to {output_folder}")
            
            # Open folder
            self.root.after(0, lambda: self.open_folder(output_folder))
            messagebox.showinfo("Success", f"Extracted {len(segments)} clips to:\n{output_folder}")
            
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.set_status("Error")
        finally:
            self.processing = False
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
    
    def detect_silence(self, filepath, threshold, min_duration):
        cmd = [
            get_ffmpeg_path(), "-i", filepath,
            "-af", f"silencedetect=noise={threshold}dB:d={min_duration}",
            "-f", "null", "-"
        ]
        
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
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
            self.log("Timeout during silence detection")
            return None
        except Exception as e:
            self.log(f"FFmpeg error: {e}")
            return None
    
    def get_duration(self, filepath):
        cmd = [
            get_ffprobe_path(), "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath
        ]
        
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return float(result.stdout.strip())
        except:
            return None
    
    def get_non_silent_segments(self, silent_ranges, duration, buffer_start, buffer_end):
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
            segments = self.merge_segments(segments)
        
        return segments
    
    def merge_segments(self, segments):
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
    
    def extract_segment(self, input_file, output_file, start, end):
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
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            return result.returncode == 0
        except:
            return False
    
    def open_folder(self, folder_path):
        import platform
        try:
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
        except:
            pass


def main():
    # Check for ffmpeg
    try:
        subprocess.run(
            [get_ffmpeg_path(), "-version"], 
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
    except:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", "FFmpeg not found!")
        sys.exit(1)
    
    root = tk.Tk()
    app = SilenceRemoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
