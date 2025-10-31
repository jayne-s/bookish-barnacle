from gpiozero import OutputDevice
from time import sleep


IN1 = OutputDevice(17)
IN2 = OutputDevice(27)
IN3 = OutputDevice(22)
IN4 = OutputDevice(5)

angle = 60

step_sequence = [
	[1,0,0,0],
	[1,1,0,0],
	[0,1,0,0],
	[0,1,1,0],
	[0,0,1,0],
	[0,0,1,1],
	[0,0,0,1],
	[1,0,0,1]
]

step_sequence_fast = [
	[1,1,0,0,],
	[0,1,1,0],
	[0,0,1,1],
	[1,0,0,1]
]

def stop_angle(angle_deg, direction=1, rpm=50):
	steps = int(angle_deg / 360 * 510)
	step_motor(steps, direction, rpm=rpm)
	#step_motor(510, rpm=10)

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
			
try:
	stop_angle(60)
except KeyboardInterrupt:
	print("Program stopped")
