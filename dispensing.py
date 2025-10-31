import serial
import json
import cv2
import subprocess 
import numpy as np 
from gpiozero import LED, OutputDevice, Buzzer 
from time import sleep, time
from datetime import datetime 
from edge_impulse_linux.image import ImageImpulseRunner 
import paho.mqtt.client as mqtt 
import ssl

led = LED(23)
buzz = Buzzer(26)

SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600 
MODEL_PATH = "/home/Shruthigna/Documents/face_recognition-linux-aarch64-v14.eim" 

MEDICATION_SCHEDULE = {
	"jayne": "19:44",
	"areebah": "13:00"
}

step_sequence_fast = [
	[1,1,0,0,],
	[0,1,1,0],
	[0,0,1,1],
	[1,0,0,1]
]

IN1 = OutputDevice(17)
IN2 = OutputDevice(27)
IN3 = OutputDevice(22)
IN4 = OutputDevice(5)

angle = 60

AWS_IOT_ENDPOINT = "a9saj11jrwuqo-ats.iot.us-east-2.amazonaws.com" 
AWS_IOT_PORT = 8883 
AWS_IOT_TOPIC = "raspi/data" 
CA_CERT_PATH = 'certs/AmazonRootCA1.pem' 
CERT_PATH = 'certs/certificate.pem.crt' 
KEY_PATH = 'certs/private.pem.key' 

current_temperature = None
current_humidity = None
mqtt_connected = None
dispensed_today = {}

def on_message(client, userdata, msg):
	print(f"Message received on {msg.topic} --- {msg.payload.decode()}")
	data = json.loads(msg.payload.decode())
	signal = data.get("action")
	
	if signal == "dispense":
		print("Dispense Command Received")
		stop_angle(60, 1)
		sleep(15)
	else:
		print("No Dispense. Medication may not be in good condition.")

def stop_angle(angle_deg, direction, rpm=50):
	steps = int(angle_deg / 360 * 510)
	step_motor(steps, direction, rpm=rpm)
	
def set_step(w1, w2, w3, w4):
	IN1.value = w1
	IN2.value = w2
	IN3.value = w3
	IN4.value = w4

def step_motor(steps, direction=1, rpm = None, delay=0.01):
	if rpm is not None:
		delay = 60 / (rpm * steps)
	for _ in range(steps):
		for step in (step_sequence_fast if direction > 0 else reversed(step_sequence_fast)):
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
		client.on_message = on_message
		client.tls_set(ca_certs=CA_CERT_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLSv1_2) 
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
		payload = { "Person": label, "Temperature": temperature, "Humidity": humidity, "Date": now.strftime("%Y-%m-%d"), "Time": now.strftime("%H-%M-%S") } 
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
	
def read_sensor_data(ser):
	if not ser:
		return None, None
		
	start_time = time()
	while time() - start_time < 5:
		if ser.in_waiting > 0:
			line = ser.readline().decode('utf-8').strip()
			if line:
				try:
					data = json.loads(line)
					temperature = data.get("temperature")
					humidity = data.get("humidity")
					print(f"Temperature: {temperature}  Humidity: {humidity}")
					return temperature, humidity
				except json.JSONDecodeError:
					pass
		sleep(0.1)
		
	return None, None
	
#def check_medication_time():
	#current_time = datetime.now().strftime("%H:%M")
	#for person, med_time in MEDICATION_SCHEDULE.items():
		#if current_time == med_time:
			#return person, med_time, datetime.now().strftime("%Y-%m-%d")
	#return None, None, None
	
def check_medication_time():
	now = datetime.now()
	for person, med_time in MEDICATION_SCHEDULE.items():
		med_hour, med_minute = map(int, med_time.split(":"))
		scheduled_time = now.replace(hour=med_hour, minute=med_minute, second=0, microsecond=0)
		
		if abs((now - scheduled_time).total_seconds()) < 60:
			return person, med_time, now.strftime("%Y-%m-%d")
	return None, None, None

def play_buzzer():
	for _ in range(2):
		buzz.on()
		sleep(2)
		buzz.off()
		sleep(2)
		
def add_dispense_record(date, person, time):
	if date not in dispensed_today:
		dispensed_today[date] = []
	dispensed_today[date].append((person,time))
	
def main():
	print("Medication Dispenser System Starting...")
	
	ser = None
	try: 
		ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
		print("Connected to Arduino")
		sleep(2)
		ser.reset_input_buffer()
	except Exception as e:
		print(f"Arduino Error : {e}")
		
	mqtt_client = setup_aws_iot()
	if not mqtt_client:
		print("Cannot run without AWS IoT. Exiting")
		#return
	
	sleep(3)
	
	with ImageImpulseRunner(MODEL_PATH) as runner:
		model_info = runner.init()
		print("Model Loaded")
		
		
		try:
			while True:
				print("\n" + "="*60)
				print("Checking Medication Schedule")
				
				person_due, person_time, person_date = check_medication_time()
			
				
				if person_due:
					
					current_date = datetime.now().strftime("%Y-%m-%d")
					already_dispensed = any  (
						person == person_due and time == person_time
						for person, time in dispensed_today.get(current_date, [])					
					)
					
					if already_dispensed:
						print(f"Person {person_due} already received medication for {person_time}")
						sleep(60)
						continue
							
					print(f"Medication Time for {person_due}")
					play_buzzer()
					
					temperature, humidity = read_sensor_data(ser)
					
					if temperature is None or humidity is None:
						temperature, humidity = 25.0, 25.0
					
					max_attempts = 5
					attempt = 0
					recognized = False
					
					while not recognized and attempt < max_attempts:
						attempt += 1
						print("Show face to camera")
						sleep(1)
						frame = capture_frame()
						
						if frame is None:
							print("Camera Failed")
							sleep(60)
							continue
							
						features, cropped = runner.get_features_from_image(frame)
						result = runner.classify(features)
						detected_person = "unknown"
						
						if isinstance(result, dict) and "result" in result:
							scores = result["result"]["classification"]
							label = max(scores, key=scores.get)
							confidence = scores[label]
							print(f"Detected: {label} with confidence {confidence}")
							
							if confidence >= 0.8 and label == person_due:
								detected_person = label
								led.on()
								recognized = True
								
								#stop_angle(60)
								
								print("Sending data to AWS Lambda")
								publish_to_aws(mqtt_client, detected_person, temperature, humidity)
								
								sleep(5)
								mqtt_client.subscribe("sensors")
								add_dispense_record(person_date, person_due, person_time)
								
								sleep(2)
								led.off()
								sleep(15)
								
							elif confidence >= 0.8 and label != person_due:
								print("Wrong person")
								led.off()
								sleep(2)
								
							else:
								print("Low confidence or unknown person")
								
					if not recognized:
						print(f"Failed to recognize person after {max_attempts}")
						print("Please use manual trigger")
						
				else:
					print("No medication due. Waiting...")
					sleep(60)
							
		except KeyboardInterrupt:
			print("Stopping")
			led.off()
			if ser:
				ser.close()
			if mqtt_client:
				mqtt_client.loop_stop()
				mqtt_client.disconnect()
					
if __name__ == "__main__":
	main()
					
					
