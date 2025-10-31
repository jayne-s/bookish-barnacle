import cv2
import subprocess
import numpy as np
from gpiozero import LED
from time import sleep
from edge_impulse_linux.image import ImageImpulseRunner

MODEL_PATH = "/home/Shruthigna/Documents/face_recognition-linux-aarch64-v13.eim"
auth_labels = ["jayne", "areebah", "shruthigna"]
confidence_threshold = 0.85
led = LED(23)

def capture_frame(filename="/tmp/frame.jpg"):
        subprocess.run(["rpicam-jpeg", "-o", filename, "-t", "1000"], check=True)
        frame = cv2.imread(filename)
        return frame

def main():
    count = 0

    with ImageImpulseRunner(MODEL_PATH) as runner:
        model_info = runner.init()
        labels = model_info['model_parameters']['labels']
        width = model_info['model_parameters']['image_input_width']
        height = model_info['model_parameters']['image_input_height']
        print(f"Model loaded, labels: {labels}, width: {width}, height: {height}")
        
        
    while count < 1:
        frame = capture_frame()
        
        if frame is None:
            print("Failed to capture frame")
            continue
        
        features, cropped = runner.get_features_from_image(frame)
        result = runner.classify(features)
        
        print("result: ", result)
        
        if isinstance(result, dict) and "result" in result and "classification" in result["result"]:
            scores = result["result"]["classification"]
            label = max(scores, key=scores.get)
            confidence = scores[label]
            print(f"Detected: {label} ({confidence:.2f})")
            
            if label in auth_labels and confidence >= confidence_threshold:
                print("Authorized Person")
                led.on()
            else:
                print("Unauthorized Person")
                led.off()
        else:
            print("invalid model output", result)
                
        sleep(2)
        count += 1


if __name__ == "__main__":
	main()
