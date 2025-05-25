import numpy as np

import mediapipe as mp

from mediapipe.tasks import python

from mediapipe.tasks.python import vision

import cv2

import time

import threading



# --- Configuration ---

MARGIN = 10

ROW_SIZE = 10

FONT_SIZE = 1

FONT_THICKNESS = 1

RECT_COLOR = (255, 0, 255)

TEXT_COLOR = (0, 255, 0)

VIDEO_SOURCE = 'http://10.42.0.126:81/stream'

MODEL_PATH = 'best.tflite'

SCORE_THRESHOLD = 0.5



# --- Frame Skipping Configuration ---

PROCESS_EVERY_N_FRAMES = 2 # Giữ nguyên hoặc điều chỉnh tùy theo hiệu năng mong muốn



# --- Global variables ---

latest_frame = None

frame_lock = threading.Lock()

camera_running = True

last_successful_detections = [] # Biến mới để lưu trữ các phát hiện cuối cùng



# --- Function to capture frames from camera ---

def capture_frames():

    global latest_frame, camera_running

    cap = cv2.VideoCapture(VIDEO_SOURCE)

    if not cap.isOpened():

        print(f"Lỗi: Không thể mở luồng video từ {VIDEO_SOURCE}")

        camera_running = False

        return



    print("Đã kết nối với camera.")

    while camera_running:

        ret, frame = cap.read()

        if not ret:

            print("Lỗi: Không thể đọc khung hình từ luồng video. Đang thử kết nối lại...")

            cap.release()

            time.sleep(2)

            cap = cv2.VideoCapture(VIDEO_SOURCE)

            if not cap.isOpened():

                print(f"Lỗi: Không thể mở lại luồng video từ {VIDEO_SOURCE}")

                camera_running = False

                break

            continue

        with frame_lock:

            latest_frame = frame.copy()

    cap.release()

    print("Đã đóng luồng camera.")



# --- Main detection function ---

def run_object_detection():

    global latest_frame, camera_running, last_successful_detections



    try:

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)

        options = vision.ObjectDetectorOptions(

            base_options=base_options,

            score_threshold=SCORE_THRESHOLD,

        )

        detector = vision.ObjectDetector.create_from_options(options)

        print("Đã tạo Object Detector thành công.")

    except Exception as e:

        print(f"Lỗi khi khởi tạo Object Detector: {e}")

        return



    frame_count = 0

    processing_start_time = time.time() # Đổi tên để rõ ràng hơn

    display_fps = 0



    capture_thread = threading.Thread(target=capture_frames)

    capture_thread.daemon = True

    capture_thread.start()



    print("Đang chờ khung hình đầu tiên từ camera...")

    while latest_frame is None and camera_running:

        time.sleep(0.1)



    if not camera_running and latest_frame is None:

        print("Không thể lấy khung hình từ camera. Thoát chương trình.")

        return



    print("Bắt đầu vòng lặp xử lý chính.")

    while camera_running:

        with frame_lock:

            if latest_frame is None:

                continue

            current_frame = latest_frame.copy()



        # current_frame = cv2.flip(current_frame, 1) # Tùy chọn



        frame_count += 1

        processed_frame = current_frame.copy() # Luôn tạo bản sao để vẽ



        # Chỉ thực hiện nhận diện mỗi N khung hình

        if frame_count % PROCESS_EVERY_N_FRAMES == 0:

            temp_detections_to_draw = [] # Tạo danh sách tạm thời cho các phát hiện của khung hình này

            try:

                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=current_frame)

                detection_result = detector.detect(mp_image)



                if detection_result and detection_result.detections:

                    for detection in detection_result.detections:

                        bbox = detection.bounding_box

                        x = int(bbox.origin_x)

                        y = int(bbox.origin_y)

                        w = int(bbox.width)

                        h = int(bbox.height)



                        x = max(0, x)

                        y = max(0, y)

                        w = min(w, processed_frame.shape[1] - x)

                        h = min(h, processed_frame.shape[0] - y)



                        category = detection.categories[0]

                        category_name = category.category_name

                        probability = round(category.score, 2)

                        result_text = f"{category_name} ({probability:.2f})"



                        # Lưu thông tin cần thiết để vẽ

                        temp_detections_to_draw.append({

                            'start_point': (x, y),

                            'end_point': (x + w, y + h),

                            'result_text': result_text,

                            'text_x': x,

                            'text_y_candidate': y - MARGIN,

                            'box_bottom_y': y + h

                        })

                    last_successful_detections = temp_detections_to_draw # Cập nhật phát hiện cuối cùng



            except Exception as e:

                print(f"Lỗi trong quá trình nhận diện hoặc chuẩn bị dữ liệu: {e}")

                # Không cập nhật last_successful_detections nếu có lỗi, giữ lại kết quả cũ



        # Luôn vẽ các phát hiện cuối cùng lên khung hình (dù có xử lý ở frame này hay không)

        if last_successful_detections:

            for det_info in last_successful_detections:

                cv2.rectangle(processed_frame, det_info['start_point'], det_info['end_point'],

                              RECT_COLOR, FONT_THICKNESS + 1)



                text_y = det_info['text_y_candidate'] if det_info['text_y_candidate'] > MARGIN else det_info['box_bottom_y'] + MARGIN + ROW_SIZE

                (text_width, text_height), _ = cv2.getTextSize(det_info['result_text'], cv2.FONT_HERSHEY_PLAIN, FONT_SIZE, FONT_THICKNESS)



                # Đảm bảo text không vẽ ra ngoài lề trái/phải (cơ bản)

                text_draw_x = max(0, det_info['text_x'])

                text_draw_x = min(text_draw_x, processed_frame.shape[1] - text_width)





                cv2.rectangle(processed_frame, (text_draw_x, text_y - text_height - 4),

                              (text_draw_x + text_width, text_y + 4), (0,0,0), -1)

                cv2.putText(processed_frame, det_info['result_text'], (text_draw_x, text_y),

                            cv2.FONT_HERSHEY_PLAIN, FONT_SIZE, TEXT_COLOR, FONT_THICKNESS)





        # Tính toán và hiển thị FPS

        if frame_count % 10 == 0:

            current_time = time.time() #Sửa tên biến để tránh nhầm lẫn

            elapsed_time = current_time - processing_start_time

            if elapsed_time > 0:

                display_fps = int(10 / elapsed_time)

            processing_start_time = current_time



        cv2.putText(processed_frame, f"FPS: {display_fps}", (10, 30),

                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)



        cv2.imshow("Object Detection", processed_frame)



        if cv2.waitKey(1) & 0xFF == 27:

            print("Đã nhấn phím ESC, đang thoát...")

            camera_running = False

            break



    if capture_thread.is_alive():

        capture_thread.join()

    cv2.destroyAllWindows()

    print("Chương trình đã kết thúc.")



if __name__ == '__main__':

    run_object_detection()