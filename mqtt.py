import serial 
import json 
import cv2 
import subprocess 
import numpy as np 
from gpiozero import LED, OutputDevice 
from time import sleep
from datetime import datetime 
from edge_impulse_linux.image import ImageImpulseRunner 
import paho.mqtt.client as mqtt 
import ssl 

led = LED(23) 
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600 
MODEL_PATH = "/home/Shruthigna/Documents/face_recognition-linux-aarch64-v14.eim" 
auth_labels = ["jayne", "areebah", "shruthigna"] # remove unknown from testing later
confidence_threshold = 0.8 
AWS_IOT_ENDPOINT = "a9saj11jrwuqo-ats.iot.us-east-2.amazonaws.com" 
AWS_IOT_PORT = 8883 
AWS_IOT_TOPIC = "raspi/data" 
CA_CERT_PATH = 'certs/AmazonRootCA1.pem' 
CERT_PATH = 'certs/certificate.pem.crt' 
KEY_PATH = 'certs/private.pem.key' 
IN1 = OutputDevice(17)
IN2 = OutputDevice(27)
IN3 = OutputDevice(22)
IN4 = OutputDevice(5)

current_temperature = None 
current_humidity = None 
mqtt_connected = False 

#step_sequence = [
	#[1,0,0,0],
	#[1,1,0,0],
	#[0,1,0,0],
	#[0,1,1,0],
	#[0,0,1,0],
	#[0,0,1,1],
	#[0,0,0,1],
	#[1,0,0,1]
#]



def set_step(w1, w2, w3, w4):
	IN1.value = w1
	IN2.value = w2
	IN3.value = w3
	IN4.value = w4

def step_motor(steps, direction=1, delay=0.01):
	for _ in range(steps):
		for step in (step_sequence if direction > 0 else reversed(step_sequence)):
			set_step(*step)
			sleep(delay)

def on_connect(client, userdata, flags, rc): 
	global mqtt_connected 
	if rc == 0: 
		print("Connected to AWS IoT Successfully") 
		mqtt_connected = True 
	else: 
		print(f"Failed to connect to AWS IoT: {rc}") 
		mqtt_connected = False 
		
def on_publish(client, userdata, mid): 
	print(f"Data published to AWS IoT: {mid}") 
	
def setup_aws_iot(): 
	try: 
		client = mqtt.Client() 
		client.on_connect = on_connect 
		client.on_publish = on_publish 
		client.tls_set( ca_certs=CA_CERT_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLSv1_2 ) 
		client.connect(AWS_IOT_ENDPOINT, AWS_IOT_PORT, 60) 
		client.loop_start() 
		return client 
	except Exception as e: 
		print(f"Error setting up AWS IoT: {e}") 
		return None 
		
def publish_to_aws(client, label, temperature, humidity): 
	if not client or not mqtt_connected: 
		print("MQTT not connected, skipping publish") 
		return 
		
	try: 
		now = datetime.now() 
		payload = { 
		"Person": label, 
		"Temperature": temperature, 
		"Humidity": humidity, 
		"Date": now.strftime("%Y-%m-%d"), 
		"Time": now.strftime("%H-%M-%S") 
		} 
		result = client.publish( AWS_IOT_TOPIC, payload=json.dumps(payload), qos=1, retain=False ) 
		if result.rc == mqtt.MQTT_ERR_SUCCESS: 
			print(f"Published: {payload}") 
		else: 
			print(f"Error publishing to AWS: {result.rc}") 
	except Exception as e: 
		print(f"Exception during publish: {e}") 
		
def capture_frame(filename="/tmp/frame.jpg"): 
	subprocess.run(["rpicam-jpeg", "-o", filename, "-t", "1000"], check=True) 
	frame = cv2.imread(filename) 
	return frame 
	
def main(): 
	global current_temperature, current_humidity 
	ser = None
	detected_label = "unknown" 
	
	try: 
		ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) 
		print("Connected to Arduino") 
		sleep(2) 
		ser.reset_input_buffer() 
	except serial.SerialException as e: 
		print(f"Arduino connection error: {e}") 
		ser = None 
		
	mqtt_client = setup_aws_iot() 
		
	if mqtt_client: 
		print("AWS IoT Client Initialized") 
		sleep(5) 
	else: 
		print("Running without AWS IoT") 
			
	with ImageImpulseRunner(MODEL_PATH) as runner: 
		model_info = runner.init() 
		labels = model_info['model_parameters']['labels'] 
		width = model_info['model_parameters']['image_input_width'] 
		height = model_info['model_parameters']['image_input_height'] 
		print(f"Model loaded, labels: {labels}, width: {width}, height: {height}") 
		
		try: 
			iteration = 0
			while True: 
				print("\n" + "="*50) 
				print(f"Iteration: {iteration}")
				
				arduino_data_received = False
				
				for _ in range(5):
					if ser and ser.in_waiting > 0: 
						line = ser.readline().decode('utf-8').strip() 
						if line: 
							try: 
								data = json.loads(line) 
								current_temperature = data.get("temperature") 
								current_humidity = data.get("humidity") 
								print(f"\nTemperature: {current_temperature}°C, Humidity: {current_humidity}%") 
								arduino_data_received = True
								break
							except json.JSONDecodeError: 
								print(f"Invalid JSON: {line}") 
								
					sleep(0.2)
					
					if not arduino_data_received:
						print("No new Arduino data received this cycle")
						
					if iteration % 2 == 0:		
						print("\nChecking face recognition...") 
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
								step_motor(512,1) 
								detected_label = label 
							else: 
								print("Unauthorized User") 
								led.off() 
								detected_label = "unknown" 
						else: 
							print("Invalid Model Output", result) 
							led.off() 
							detected_label = "unknown"
							
						if current_temperature is not None and current_humidity is not None: 
							print("Publishing to AWS")
							publish_to_aws(mqtt_client, detected_label, current_temperature, current_humidity) 
						else: 
							print("No sensor data available yet") 
							
					else:
						print("Skipping facial recognition this cycle")
						
					now = datetime.now() 
					print(f"Datetime: {now}") 
					iteration += 1
					sleep(3) 
					
		except KeyboardInterrupt: 
			print("\nExiting...") 
			led.off() 
			if ser: 
				ser.close() 
			if mqtt_client: 
				mqtt_client.loop_stop() 
				mqtt_client.disconnect() 
				
if __name__ == "__main__": 
	main() 
