import tkinter as tk
import cv2
import requests
from PIL import Image, ImageTk
import threading
import time
import os
import numpy as np
from io import BytesIO

class ESP32CamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32-CAM Stream")

        self.capture_folder = "captures"
        if not os.path.exists(self.capture_folder):
            os.makedirs(self.capture_folder)

        self.status_label = tk.Label(self.root, text="Trạng thái: Đang kết nối...", fg="blue")
        self.status_label.pack(pady=5)

        self.video_frame = tk.Label(self.root, width=640, height=480, bg="gray")
        self.video_frame.pack(padx=10, pady=10)
        self.video_frame.pack_forget()  # Ẩn video_frame lúc ban đầu**

        self.settings_frame = tk.Frame(self.root)
        self.settings_frame.pack(pady=5)

        tk.Label(self.settings_frame, text="Địa chỉ IP:").grid(row=0, column=0, padx=5, sticky="e")
        self.ip_input = tk.Entry(self.settings_frame)
        self.ip_input.grid(row=0, column=1, padx=5)
        self.ip_input.insert(0, "192.168.8.160") # Giá trị mặc định

        tk.Label(self.settings_frame, text="Giây chụp tự động:").grid(row=0, column=2, padx=5, sticky="e")
        self.interval_spinbox = tk.Spinbox(self.settings_frame, from_=1, to=60, width=5)
        self.interval_spinbox.grid(row=0, column=3, padx=5)
        self.interval_spinbox.delete(0,"end")
        self.interval_spinbox.insert(0, "2") # Giá trị mặc định

        self.apply_settings_button = tk.Button(self.settings_frame, text="Áp dụng", command=self.apply_settings)
        self.apply_settings_button.grid(row=0, column=4, padx=5)

        self.controls_frame = tk.Frame(self.root)
        self.controls_frame.pack(pady=10)

        self.auto_capture_button = tk.Button(self.controls_frame, text="Bật Chụp Tự Động",
                                                command=self.toggle_auto_capture, width=15)
        self.auto_capture_button.grid(row=0, column=0, padx=5)

        self.manual_capture_button = tk.Button(self.controls_frame, text="Chụp Thủ Công",
                                                 command=self.manual_capture, width=15)
        self.manual_capture_button.grid(row=0, column=1, padx=5)

        self.reconnect_button = tk.Button(self.controls_frame, text="Kết nối lại",
                                                command=self.reconnect, width=15)
        self.reconnect_button.grid(row=0, column=2, padx=5)

        self.quality_frame = tk.Frame(self.root)
        self.quality_frame.pack(pady=5)

        tk.Label(self.quality_frame, text="Chất lượng ảnh:").grid(row=0, column=0, padx=5)
        quality_options = ["QVGA", "VGA", "SVGA", "XGA", "HD", "SXGA", "UXGA"]
        self.quality_var = tk.StringVar(value="QVGA")
        self.quality_menu = tk.OptionMenu(self.quality_frame, self.quality_var, *quality_options)
        self.quality_menu.grid(row=0, column=1, padx=5)

        self.apply_quality_button = tk.Button(self.quality_frame, text="Áp dụng",
                                                 command=self.set_quality, width=10)
        self.apply_quality_button.grid(row=0, column=2, padx=5)

        self.auto_capture = False
        self.is_streaming = False
        self.last_auto_capture = 0
        self.current_frame = None
        self.auto_capture_interval = 2 # Giá trị mặc định, sẽ được cập nhật từ spinbox
        self.base_url = "" # Sẽ được cập nhật trong apply_settings
        self.stream_url = ""
        self.capture_url = ""
        self.status_url = ""

        self.apply_settings() # Gọi apply_settings ban đầu để thiết lập URL từ giá trị mặc định trong Entry

    def apply_settings(self):
        ip_address = self.ip_input.get()
        interval_str = self.interval_spinbox.get()
        try:
            interval = int(interval_str)
            if 1 <= interval <= 60:
                self.auto_capture_interval = interval
            else:
                self.status_label.config(text="Giây chụp tự động phải từ 1-60.", fg="red")
                return
        except ValueError:
            self.status_label.config(text="Giây chụp tự động không hợp lệ.", fg="red")
            return

        self.base_url = f"http://{ip_address}"
        self.stream_url = f"{self.base_url}:81/stream"
        self.capture_url = f"{self.base_url}/capture"
        self.status_url = f"{self.base_url}/status"

        self.status_label.config(text=f"Đã đặt IP thành {ip_address} và giây chụp tự động thành {interval} giây.", fg="green")
        self.reconnect() # Tự động kết nối lại sau khi áp dụng cài đặt IP


    def toggle_auto_capture(self):
        self.auto_capture = not self.auto_capture
        if self.auto_capture:
            self.auto_capture_button.config(text="Tắt Chụp Tự Động")
            self.last_auto_capture = time.time()
        else:
            self.auto_capture_button.config(text="Bật Chụp Tự Động")

    def set_quality(self):
        quality = self.quality_var.get()
        size_map = {
            "QVGA": 8,
            "VGA": 10,
            "SVGA": 11,
            "XGA": 12,
            "HD": 13,
            "SXGA": 14,
            "UXGA": 15
        }

        if quality in size_map:
            try:
                requests.get(f"{self.base_url}/control?var=framesize&val={size_map[quality]}")
                self.status_label.config(text=f"Đã thay đổi chất lượng sang {quality}", fg="green")
            except Exception as e:
                self.status_label.config(text=f"Lỗi cài đặt chất lượng: {e}", fg="red")

    def manual_capture(self):
        try:
            response = requests.get(self.capture_url, timeout=3)
            if response.status_code == 200:
                image_data = response.content
                filename = os.path.join(self.capture_folder, f"manual_capture_{int(time.time())}.jpg")

                with open(filename, 'wb') as f:
                    f.write(image_data)

                self.status_label.config(text=f"Đã chụp ảnh và lưu vào {filename}", fg="green")
                print(f"Đã chụp ảnh và lưu vào {filename}")
                return

        except Exception as e:
            print(f"Không thể sử dụng URL capture: {e}")

        if self.current_frame is not None:
            filename = os.path.join(self.capture_folder, f"manual_capture_{int(time.time())}.jpg")
            cv2.imwrite(filename, self.current_frame)
            self.status_label.config(text=f"Đã chụp ảnh và lưu vào {filename}", fg="green")
            print(f"Đã chụp ảnh và lưu vào {filename}")
        else:
            self.status_label.config(text="Không thể chụp - Không có frame", fg="red")

    def reconnect(self):
        self.stop_stream()
        self.status_label.config(text="Đang kết nối lại...", fg="blue")
        self.root.update()
        time.sleep(1)
        self.start()

    def test_connection(self):
        try:
            response = requests.get(self.base_url, timeout=2)
            if response.status_code == 200:
                self.status_label.config(text="Kết nối thành công đến ESP32-CAM", fg="green")
                return True
            else:
                self.status_label.config(text=f"Không thể kết nối, mã lỗi: {response.status_code}", fg="red")
                return False
        except requests.exceptions.RequestException as e:
            self.status_label.config(text=f"Lỗi kết nối: {e}", fg="red")
            return False

    def process_mjpeg_stream(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            r = requests.get(self.stream_url, stream=True, headers=headers)

            if r.status_code != 200:
                self.status_label.config(text=f"Không thể kết nối stream, mã lỗi: {r.status_code}", fg="red")
                return

            bytes_data = bytes()
            for chunk in r.iter_content(chunk_size=1024):
                if not self.is_streaming:
                    break

                bytes_data += chunk
                a = bytes_data.find(b'\xff\xd8')
                b = bytes_data.find(b'\xff\xd9')

                if a != -1 and b != -1 and a < b:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]

                    try:
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            self.current_frame = frame

                            current_time = time.time()
                            if self.auto_capture and (current_time - self.last_auto_capture >= self.auto_capture_interval):
                                filename = os.path.join(self.capture_folder, f"auto_capture_{int(current_time)}.jpg")
                                cv2.imwrite(filename, frame)
                                print(f"Đã tự động chụp và lưu vào {filename}")
                                self.last_auto_capture = current_time

                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            img = ImageTk.PhotoImage(image=img)

                            self.video_frame.img = img
                            self.video_frame.config(image=img)
                            self.root.update_idletasks()
                    except Exception as e:
                        print(f"Lỗi xử lý frame: {e}")

        except Exception as e:
            self.status_label.config(text=f"Lỗi stream: {e}", fg="red")
            print(f"Lỗi stream: {e}")

    def start_stream(self):
        if not self.test_connection():
            return

        self.video_frame.pack() # Hiện video_frame trước khi stream**
        self.status_label.config(text="Đang streaming...", fg="green")
        self.process_mjpeg_stream()

    def stop_stream(self):
        self.is_streaming = False
        self.video_frame.pack_forget() # Ẩn video_frame khi dừng stream (hoặc kết nối lại)**

    def start(self):
        self.is_streaming = True
        streaming_thread = threading.Thread(target=self.start_stream)
        streaming_thread.daemon = True
        streaming_thread.start()

    def on_close(self):
        self.stop_stream()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ESP32CamApp(root)

    root.minsize(680, 600)

    app.start()

    root.protocol("WM_DELETE_WINDOW", app.on_close)

    root.mainloop()