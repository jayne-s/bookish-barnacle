import cv2
from time import sleep
from gpiozero import LED
from edge_impulse_linux.image import ImageImpulseRunner

MODEL_PATH = "model.eim"

auth_labels = ["jayne", "shruthigna", "areebah"]
confidence_threshold = 0.7

#SERVO_PIN = 18
led = LED(23)
#GPIO.setmode(GPIO.BCM)
#GPIO.setup(SERVO_PIN, GPIO.OUT)
#servo = GPIO.PWM(SERVO_PIN, 50)
#servo.start(0)
led.on()
sleep(1)
led.off()


def unlock_servo():
	print("Access Granted")
	#servo.ChangeDutyCycle(7.5)
	#time.sleep(2)
	#servo.ChangeDutyCycle(2.5)python3 -m pip install gpiozero
	#time.sleep(1)
	#servo.ChangeDutyCycle(0)
	led.on()
	
	

def deny_access():
	print("Access Denied")
	led.off()

def main():
	with ImageImpulseRunner(MODEL_PATH) as runner:
		model_info = runner.init()
		labels = model_info['model_parameters']['labels']
		print("Model loaded, labels:", labels)

		cap = cv2.VideoCapture(0)
		if not cap.isOpened():
			raise Exception("Camera not detected")
	
		print("Starting Camera")

		while True:
			ret, frame = cap.read()
			if not ret:
				print("Failed to capture frame")
				continue

			features, result = runner.classify(frame)
		
			if "classification" in result["result"]:
				scores = result["result"]["classification"]
				label = max(scores, key=scores.get)
				confidence = scores[label] * 100

				print(f"Detected: {label} ({confidence:.2f}%)")

				if label in auth_labels and confidence > confidence_threshold:
					unlock_servo()
				else:
					deny_access()

			cv2.imshow("Face Recognition", frame)
			if cv2.waitKey(1) & 0xFF == ord("q"):
				break

		cap.release()
		cv2.destroyAllWindows()
		servo.stop()
		GPIO.cleanup()

#if __name__ == "__main__":
	#main()
