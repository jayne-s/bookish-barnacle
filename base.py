import serial
import json
from gpiozero import LED
from time import sleep

led = LED(23)
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

def read_serial_data():
	try: 
		ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
		print("Connected to Arduino")
		
		sleep(2)
		
		ser.reset_input_buffer()
		
		while True:
			if ser.in_waiting > 0:
				line = ser.readline().decode('utf-8').strip()
				
				if line:
					try:
						data = json.loads(line)
						temperature = data.get("temperature")
						humidity = data.get("humidity")
						print(f"Temperature: {temperature}, Humidity: {humidity}")
						led.on()
						sleep(2)
						led.off()
						sleep(2)
					except json.JSONDecodeError:
						print("Invalid JSON")
				
				sleep(0.1)
	
	except serial.SerialException as e:
		print(f"Error: {e}")
	except KeyboardInterrupt:
		print("exiting")
		ser.close()

if __name__ == "__main__":
	read_serial_data()
