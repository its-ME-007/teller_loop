import RPi.GPIO as GPIO
import time
import json
import sys

# GPIO Pin Assignments
PUL = 16  # Motor Clock
DIR = 19  # Motor Direction
ENA = 14  # Motor Enable

S1 = 23  # Carrier Sensors (Active Low)
S2 = 24
S3 = 25
S4 = 26

P1 = 4   # Position Sensors (Active Low)
P2 = 17
P3 = 27
P4 = 22
RELAY_PIN = 8
# Stepper Motor Control Constants
STEP_DELAY = 0.0005  # Adjust step delay for speed
STEP_COUNT = 5       # Steps per loop iteration
REVOLUTION_STEPS = 300  # Adjust based on motor steps per revolution

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Configure GPIOs
for pin in [PUL, DIR, ENA, RELAY_PIN]:
    GPIO.setup(pin, GPIO.OUT)

for pin in [S1, S2, S3, S4, P1, P2, P3, P4]:
    GPIO.setup(pin, GPIO.IN)

# Enable Motor
GPIO.output(ENA, GPIO.LOW)

def move_motor(direction, stop_sensor, count_max, slow_extra=False):
    GPIO.output(DIR, direction)
    count = 0
   
    while count < count_max:
        if GPIO.input(stop_sensor) == GPIO.LOW:
            count += 1
            if count == 1:
                print("First sensor trigger - Continuing rotation for 1 revolution at half speed")
                for _ in range(REVOLUTION_STEPS):  # 1 revolution
                    GPIO.output(PUL, GPIO.HIGH)
                    time.sleep(STEP_DELAY * 4)  # Half speed
                    GPIO.output(PUL, GPIO.LOW)
                    time.sleep(STEP_DELAY * 4)
                print("Returning back to sensor position at half speed")
                GPIO.output(DIR, not direction)
                while GPIO.input(stop_sensor) == GPIO.HIGH:
                    for _ in range(STEP_COUNT):
                        GPIO.output(PUL, GPIO.HIGH)
                        time.sleep(STEP_DELAY * 4)  # Half speed on return
                        GPIO.output(PUL, GPIO.LOW)
                        time.sleep(STEP_DELAY * 4)
                GPIO.output(DIR, direction)  # Restore original direction
            
            if count == 2 and slow_extra:  # Additional Backward motion
                print("Extra backward motion at even slower speed")
                GPIO.output(DIR, not direction)
                for _ in range(REVOLUTION_STEPS // 2):  # Half revolution
                    GPIO.output(PUL, GPIO.HIGH)
                    time.sleep(STEP_DELAY * 4)  # Slower speed
                    GPIO.output(PUL, GPIO.LOW)
                    time.sleep(STEP_DELAY * 4)
                GPIO.output(DIR, direction)  # Restore original direction
            
        for _ in range(STEP_COUNT):
            GPIO.output(PUL, GPIO.HIGH)
            time.sleep(STEP_DELAY)
            GPIO.output(PUL, GPIO.LOW)
            time.sleep(STEP_DELAY)

def send_capsule():
    print("Send process started")
    status_updates = []
    
    status_updates.append({"status": "sending", "message": "Send process started", "sensors": get_sensor_status()})
    
    while GPIO.input(P1) == GPIO.LOW:
        pass
    status_updates.append({"status": "sending", "message": "Capsule detected at P1", "sensors": get_sensor_status()})
    print("Capsule detected at P1")
    
    move_motor(GPIO.LOW, S1, 2)
    status_updates.append({"status": "sending", "message": "Capsule dropped at target position", "sensors": get_sensor_status()})
    print("Capsule dropped at target position")
    
    while GPIO.input(P1) == GPIO.HIGH or GPIO.input(P2) == GPIO.LOW:
        pass
    status_updates.append({"status": "sending", "message": "Capsule moved to P2 position", "sensors": get_sensor_status()})
    print("Capsule moved to P2 position")
    
    move_motor(GPIO.HIGH, S2, 3, slow_extra=True)
    while GPIO.input(P3) == GPIO.LOW:
        pass
    move_motor(GPIO.LOW, S3, 2)
    status_updates.append({"status": "sending", "message": "Relay ON", "sensors": get_sensor_status()})
    print("Relay ON")
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    while GPIO.input(P4) == GPIO.LOW:
        pass
    move_motor(GPIO.HIGH, S4, 3, slow_extra=True)
    GPIO.output(RELAY_PIN, GPIO.LOW)
    status_updates.append({"status": "sending", "message": "Relay OFF", "sensors": get_sensor_status()})
    print("Relay OFF")
    
    time.sleep(5)
    status_updates.append({"status": "sending", "message": "Package sent", "sensors": get_sensor_status()})
    print("Package sent")
    status_updates.append({"status": "standby", "message": "System reset to pass-through state", "sensors": get_sensor_status()})
    print("System reset to pass-through state")
    
    return {"status": "success", "updates": status_updates}

def receive_capsule():
    print("Receive process started")
    status_updates = []
    
    status_updates.append({"status": "receiving", "message": "Receive process started", "sensors": get_sensor_status()})
    
    while GPIO.input(P3) == GPIO.LOW:
        pass
    status_updates.append({"status": "receiving", "message": "Package detected at P3", "sensors": get_sensor_status()})
    
    move_motor(GPIO.LOW, S3, 3)
    status_updates.append({"status": "receiving", "message": "SUCTION HIGH - Capsule Picked", "sensors": get_sensor_status()})
    print("SUCTION HIGH - Capsule Picked")
    
    while GPIO.input(P4) == GPIO.LOW:
        pass
    
    move_motor(GPIO.HIGH, S4, 3, slow_extra=True)
    status_updates.append({"status": "receiving", "message": "Moving capsule to final position", "sensors": get_sensor_status()})
    
    time.sleep(2)
    status_updates.append({"status": "receiving", "message": "Package received", "sensors": get_sensor_status()})
    print("Package received")
    move_motor(GPIO.LOW, S2, 1)
    status_updates.append({"status": "standby", "message": "System reset to pass-through state", "sensors": get_sensor_status()})
    print("System reset to pass-through state")
    
    return {"status": "success", "updates": status_updates}

def get_sensor_status():
    """Get the current status of all sensors"""
    return {
        "S1": GPIO.input(S1) == GPIO.LOW,
        "S2": GPIO.input(S2) == GPIO.LOW,
        "S3": GPIO.input(S3) == GPIO.LOW,
        "S4": GPIO.input(S4) == GPIO.LOW,
        "P1": GPIO.input(P1) == GPIO.LOW,
        "P2": GPIO.input(P2) == GPIO.LOW,
        "P3": GPIO.input(P3) == GPIO.LOW,
        "P4": GPIO.input(P4) == GPIO.LOW
    }

def main():
    # Process command line arguments
    try:
        if len(sys.argv) < 2:
            print("No parameters provided")
            return {"status": "error", "message": "No parameters provided"}
        
        params = json.loads(sys.argv[1])
        mode = params.get('mode', '')
        
        if mode == 'send':
            result = send_capsule()
            print(json.dumps(result))
            return result
        elif mode == 'receive':
            result = receive_capsule()
            print(json.dumps(result))
            return result
        elif mode == 'passthrough':
            print("Station is in pass-through mode")
            return {"status": "success", "message": "Station is in pass-through mode"}
        else:
            print(f"Unknown mode: {mode}")
            return {"status": "error", "message": f"Unknown mode: {mode}"}
            
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}
    finally:
        # Always disable the motor when exiting
        GPIO.output(ENA, GPIO.HIGH)

if __name__ == "__main__":
    try:
        result = main()
        sys.exit(0 if result and result.get("status") == "success" else 1)
    finally:
        GPIO.output(ENA, GPIO.HIGH)  # Disable motor
        GPIO.cleanup()