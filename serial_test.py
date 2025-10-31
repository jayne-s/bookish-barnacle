import serial  
import json  
import cv2  
import subprocess  
import numpy as np  
from gpiozero import LED  
from time import sleep  
from datetime import datetime
from edge_impulse_linux.image import ImageImpulseRunner  

led = LED(23)  
SERIAL_PORT = '/dev/ttyACM0'  
BAUD_RATE = 9600  
MODEL_PATH = "/home/Shruthigna/Documents/face_recognition-linux-aarch64-v13.eim"  
auth_labels = ["jayne", "areebah", "shruthigna"]  
confidence_threshold = 0.8  

def capture_frame(filename="/tmp/frame.jpg"):  
	subprocess.run(["rpicam-jpeg", "-o", filename, "-t", "1000"], check=True) 
	frame = cv2.imread(filename)  
	return frame  

 
def main():  
	try: 
		ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) 
		print("Connected to Arduino") 
		sleep(2) 
		ser.reset_input_buffer() 
	except serial.SerialException as e: 
		print(f"Arduino connection error: {e}") 
		ser = None 
		
	
	with ImageImpulseRunner(MODEL_PATH) as runner:
		model_info = runner.init() 
		labels = model_info['model_parameters']['labels'] 
		width = model_info['model_parameters']['image_input_width'] 
		height = model_info['model_parameters']['image_input_height'] 
		print(f"Model loaded, labels: {labels}, width: {width}, height: {height}") 
		
		try: 
			while True:
				if ser and ser.in_waiting > 0: 
					line = ser.readline().decode('utf-8').strip() 
					if line: 
						try: 
							data = json.loads(line) 
							temperature = data.get("temperature") 
							humidity = data.get("humidity") 
							print(f"\n Temperature: {temperature}°C, Humidity: {humidity}%") 
						except json.JSONDecodeError: 
							print(f"Invalid JSON: {line}") 
							
				print("\n Checking face recognition...") 
				frame = capture_frame() 
				if frame is None: 
					print("Failed to capture frame") 
					sleep(2) 
					continue 
				
				features, cropped = runner.get_features_from_image(frame) 
				result = runner.classify(features) 
				
				if isinstance(result, dict) and "result" in result and "classification" in result["result"]: 
					scores = result["result"]["classification"] 
					label = max(scores, key=scores.get) 
					confidence = scores[label] 
					print(f"Detected: {label} (confidence: {confidence:.2%})") 
					
					if label in auth_labels and confidence >= confidence_threshold: 
						print("Authorized User") 
						led.on() 
					else: 
						print("Unauthorized User") 
						led.off() 
				else: 
					print("Invalid Model Output", result) 
					sleep(2) 
					
				sleep(5)
				date = datetime.now().date()
				time = datetime.now().time()
				print(f"DateTime: {date} {time}")
				
					
		except KeyboardInterrupt: 
			print("\n\nExiting...") 
			led.off() 
			if ser: 
				ser.close() 
				
if __name__ == "__main__": 
	main() 
