import sys
import subprocess
import itertools
import time
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QMimeData, QThread, pyqtSignal

class ConversionThread(QThread):
    status = pyqtSignal(str)
    eta = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal()
    
    def __init__(self, input_file):
        super().__init__()
        self.input_file = input_file
    
    def get_video_duration(self):
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", self.input_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            return float(result.stdout.strip())
        except Exception:
            return None
    
    def run(self):
        output_file = self.input_file.rsplit(".", 1)[0] + ".mp4"
        total_duration = self.get_video_duration()
        
        process = subprocess.Popen(
            ["ffmpeg", "-i", self.input_file, "-c:v", "copy", "-c:a", "aac", output_file, "-progress", "pipe:1", "-nostats"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        self.status.emit("Starting conversion...")
        start_time = time.time()
        
        for line in process.stdout:
            if "out_time_ms=" in line:
                try:
                    time_ms = int(line.strip().split("=")[-1])
                    current_time = time_ms / 1_000_000
                    if total_duration:
                        elapsed_time = time.time() - start_time
                        estimated_total_time = elapsed_time / (current_time / total_duration)
                        remaining_time = max(0, estimated_total_time - elapsed_time)
                        eta_text = f"ETA: {int(remaining_time)}s"
                        self.status.emit(f"Processing {current_time:.1f}s / {total_duration:.1f}s ...")
                        self.eta.emit(eta_text)
                except ValueError:
                    continue
        
        process.wait()
        if process.returncode == 0:
            self.status.emit("Finalizing conversion...")
            self.eta.emit("")
            self.finished.emit(output_file)
        else:
            self.status.emit("Error during conversion.")
            self.eta.emit("")
            self.error.emit()

class SpinnerThread(QThread):
    spinner_update = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.spinner = itertools.cycle(['|', '/', '-', '\\'])
    
    def run(self):
        while self.running:
            self.spinner_update.emit(next(self.spinner))
            self.msleep(75)
    
    def stop(self):
        self.running = False

class VideoConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Video Converter")
        self.setGeometry(100, 100, 400, 200)
        self.setAcceptDrops(True)
        
        self.label = QLabel("Drag and drop a video file here", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.eta_label = QLabel("", self)
        self.eta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label = QLabel("", self)
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.eta_label)
        layout.addWidget(self.spinner_label)
        self.setLayout(layout)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.convert_to_mp4(file_path)
    
    def convert_to_mp4(self, input_file):
        self.label.setText("Initializing conversion...")
        
        self.spinner_thread = SpinnerThread()
        self.spinner_thread.spinner_update.connect(self.update_spinner)
        self.spinner_thread.start()
        
        self.thread = ConversionThread(input_file)
        self.thread.status.connect(self.label.setText)
        self.thread.eta.connect(self.eta_label.setText)
        self.thread.finished.connect(self.on_conversion_complete)
        self.thread.error.connect(self.on_conversion_error)
        self.thread.start()
    
    def update_spinner(self, symbol):
        self.spinner_label.setText(symbol)
    
    def on_conversion_complete(self, output_file):
        self.spinner_thread.stop()
        self.spinner_label.setText("")
        self.eta_label.setText("")
        self.label.setText(f"Conversion complete! Saved as: {output_file}")
    
    def on_conversion_error(self):
        self.spinner_thread.stop()
        self.spinner_label.setText("")
        self.eta_label.setText("")
        self.label.setText("Error during conversion.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    converter = VideoConverter()
    converter.show()
    sys.exit(app.exec())