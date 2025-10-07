import cv2
import os
import torch
import numpy as np
import time
from twilio.rest import Client
import pygame
from PIL import Image
from ultralytics import YOLO

# loading the YOLOv5 model from a local path
model = torch.hub.load('ultralytics/yolov5', 'custom', path='trained.pt', source='github')

# using default camera
cap = cv2.VideoCapture(0)


TWILIO_ACCOUNT_SID = 'your-sid-here'     
TWILIO_AUTH_TOKEN = 'your-auth-token-here'    
TWILIO_PHONE_NUMBER = 'your-twilio-number-here' 
RECIPIENT_PHONE_NUMBER = 'your-phone-number-here'
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

pygame.mixer.init()
AUDIO_FILE = 'alert.mp3'
if not os.path.exists(AUDIO_FILE):
    print(f"Warning: {AUDIO_FILE} not found. Audio alerts disabled.")

classes = ['Drone']

rectangle_coords = [(50, 50), (250, 50), (250, 250), (50, 250)]
rectangle_drag = False
drag_corner = -1

# Mouse callback function
def mouse_event(event, x, y, flags, param):
    global rectangle_coords, rectangle_drag, drag_corner

    if event == cv2.EVENT_LBUTTONDOWN:
        # Check if the mouse click is near any of the rectangle corners
        for i, corner in enumerate(rectangle_coords):
            if abs(corner[0] - x) <= 10 and abs(corner[1] - y) <= 10:
                rectangle_drag = True
                drag_corner = i
                break

    elif event == cv2.EVENT_LBUTTONUP:
        rectangle_drag = False

    elif event == cv2.EVENT_MOUSEMOVE:
        if rectangle_drag:
            rectangle_coords[drag_corner] = (x, y)

cv2.namedWindow('frame')
cv2.setMouseCallback('frame', mouse_event)

def send_sms():
    try:
        message = client.messages.create(
            body="Alert: Enemy drone detected!",
            from_=TWILIO_PHONE_NUMBER,
            to=RECIPIENT_PHONE_NUMBER
        )
        print(f"SMS sent successfully! SID: {message.sid}")
    except Exception as e:
        print(f"SMS failed: {e}")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = None
recording = False
alert_sent = False 
alert_active= False
last_alert_time = 0

while True:
    ret, frame = cap.read()

    # Convert the frame to a PIL Image
    img = Image.fromarray(frame[...,::-1])

    results = model(img, size=640)

    drone_detected_in_area = False

    for result in results.xyxy[0]:
        x1, y1, x2, y2, conf, cls = result.tolist()
        if conf > 0.7 and classes[int(cls)] in classes:
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
            text_conf = "{:.2f}%".format(conf * 100)
            cv2.putText(frame, text_conf, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            text_coords = "({}, {})".format(int((x1 + x2) / 2), int(y2))
            cv2.putText(frame, text_coords, (int(x1), int(y2) + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            # Check if the drone intersects with or is inside the rectangle
            if rectangle_coords[0] != rectangle_coords[1]:
                if any(rectangle_coords[0][0] <= x <= rectangle_coords[2][0] and rectangle_coords[0][1] <= y <= rectangle_coords[2][1] for x, y in
                    [(x1, y1), (x1, y2), (x2, y1), (x2, y2)]) or \
                        any(rectangle_coords[0][0] <= x <= rectangle_coords[2][0] and rectangle_coords[0][1] <= y <= rectangle_coords[2][1] for x in range(int(x1), int(x2))
                            for y in range(int(y1), int(y2))):
                    drone_detected_in_area = True
                    cv2.putText(frame, "Enemy Drone Detected!!Warning!!Warning!!", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    current_time = time.time()

    if drone_detected_in_area:
        if os.path.exists(AUDIO_FILE):
            if not alert_active:
                try:
                    pygame.mixer.music.load(AUDIO_FILE)
                    pygame.mixer.music.play(-1)  # Loop indefinitely
                    alert_active = True
                    print("Playing alert sound.")
                except Exception as e:
                    print(f"Error playing sound: {e}")
        
        
        if not alert_sent and (current_time - last_alert_time) > 10:
            send_sms()
            alert_sent = True
            last_alert_time = current_time
        
        if not recording:
            writer = cv2.VideoWriter('drone_alert.mp4', fourcc, 20.0, (frame.shape[1], frame.shape[0]))
            recording = True
        if writer is not None:
            writer.write(frame)
    else:
        if alert_active:
            try:
                pygame.mixer.music.stop()
                alert_active = False
                print("Stopped alert sound.")
            except Exception as e:
                print(f"Error stopping sound: {e}")

        # reset alert flag when no drone is detected
        alert_sent = False
        if recording:
            if writer is not None:
                writer.release()
            recording = False

    for i in range(4):
        cv2.circle(frame, rectangle_coords[i], 5, (0, 255, 0), -1)
        cv2.line(frame, rectangle_coords[i], rectangle_coords[(i+1)%4], (0, 255, 0), 2)

    cv2.imshow('frame', frame)

    if cv2.waitKey(1) == ord('e'):
        break

cap.release()
if writer is not None:
    writer.release()
cv2.destroyAllWindows()