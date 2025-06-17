
if(1):
    import RPi.GPIO as GPIO
    import time
    import paho.mqtt.client as mqtt
    import json
    import threading
    import socket
    import os

        # ===== GPIO Setup =====
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    #  GPIO Pin Assignments
    PUL = 16  # Motor Clock
    DIR = 19  # Motor Direction
    ENA = 14  # Motor Enable

    S1 = 23   # Carrier Sensors (Active Low)
    S2 = 24
    S3 = 25
    S4 = 26

    P1 = 4    # Position Sensors (Active Low)
    P2 = 17
    P3 = 27
    P4 = 22

    #Limit switchs 
    LIMIT_SWITCH_LEFT = 18
    LIMIT_SWITCH_RIGHT = 21
    last_limit_trigger_time = 0
    LIMIT_WINDOW_SECONDS = 10
    limit_trigger_lock = threading.Lock()

    #other Global veriables
    loop_running = False  # Controls the loop in loop_s1_4()


    #Blow parameter 
    pump = "b"

    motor_direction = GPIO.HIGH

    #Stepper Motor Control Constants 
    STEP_DELAY = 0.0001
    STEP_COUNT = 5
    REVOLUTION_STEPS = 300
    MTN_STEP_COUNT = 100


    # MQTT Configuration 
    BROKER_IP = "192.168.90.3"
    PORT = 1883
    username="oora"
    password="oora"
    CLIENT_ID = f"station-{socket.gethostname()}-{os.getpid()}"

    # Get station name based on hostname or default to station-1
    hostname = socket.gethostname()
    # Try to determine station number from hostname (assumes hostnames like "station-1")
    # Default to 1 if not found
    try:
        STATION_NUM = int(hostname.split('-')[-1]) if '-' in hostname else 2
    except ValueError:
        STATION_NUM = 1

    STATION_NAME = f"passthrough-station-{STATION_NUM}"

    # ===== MQTT Topics =====
    mqtt_topic_base = 'PTS/'
    # Topics to subscribe to
    ACTION_TOPIC = f"{mqtt_topic_base}ACTION/{STATION_NUM}"
    SCRIPT_TOPIC = f"{mqtt_topic_base}SCRIPT/{STATION_NAME}"
    DISPATCH_TOPIC = f"{mqtt_topic_base}DISPATCH/{STATION_NUM}"
    STATUS_TOPIC = f"{mqtt_topic_base}STATUS/{STATION_NUM}"
    MTN_TOPIC = f"{mqtt_topic_base}MTN/{STATION_NUM}"
    

    # Topics to publish to
    SENSOR_DATA_TOPIC = f"{mqtt_topic_base}SENSORDATA/{STATION_NUM}"
    ACK_TOPIC = f"{mqtt_topic_base}ACK/{STATION_NUM}"
    BLOWER_TOPIC = f"{mqtt_topic_base}blower"
    ERROR_TOPIC = f"{mqtt_topic_base}ERROR/{STATION_NUM}"
    SENSOR_REQUEST_TOPIC = f"{mqtt_topic_base}SENSORDATA/REQ/{STATION_NUM}"

    # ===== System State =====
    current_task_id = None
    current_dispatch_mode = None  # 'send' or 'receive'
    system_busy = False
    sensor_data_thread = None
    sensor_data_running = False
    heartbeat_thread = None
    heartbeat_running = False

    # ===== GPIO Setup =====
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup output pins
    for pin in [PUL, DIR, ENA]:
        GPIO.setup(pin, GPIO.OUT)

    # Setup input pins
    for pin in [S1, S2, S3, S4, P1, P2, P3, P4]:
        GPIO.setup(pin, GPIO.IN)

    #Limit switchs input setup 
    GPIO.setup(LIMIT_SWITCH_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(LIMIT_SWITCH_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_UP)


    # Enable the motor
    GPIO.output(ENA, GPIO.LOW)

    # ===== MQTT Client Setup =====
    client = mqtt.Client(client_id=CLIENT_ID)
    client.username_pw_set(username,password)

# ===== Helper Functions =====
def log(message):
    """Print timestamped log message"""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def read_sensors():
    """Read all sensor values and return as dictionary"""
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

def limit_switch_triggered(channel):
    global motor_direction, last_limit_trigger_time

    current_time = time.time()
    with limit_trigger_lock:
        if current_time - last_limit_trigger_time <= LIMIT_WINDOW_SECONDS:
            log("POSITION ERROR: Limit switch triggered again within 10 seconds!")
            publish_message(ERROR_TOPIC, {
                "type": "position_error",
                "station": STATION_NAME,
                "switch": "LEFT" if channel == LIMIT_SWITCH_LEFT else "RIGHT",
                "timestamp": current_time,
                "detail": "Multiple limit switch triggers within 10 seconds"
            })

        last_limit_trigger_time = current_time

    log(f"Limit switch on GPIO {channel} triggered!")

    # Reverse motor direction
    motor_direction = GPIO.LOW if motor_direction == GPIO.HIGH else GPIO.HIGH
    log(f"Motor direction reversed to {'LOW' if motor_direction == GPIO.LOW else 'HIGH'}")


def publish_message(topic, message, qos=1, retain=False, max_retries=3):
    """Publish message to MQTT broker with retry logic"""
    if isinstance(message, dict):
        message = json.dumps(message)
    
    retries = 0
    while retries < max_retries:
        result = client.publish(topic, message, qos=qos, retain=retain)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            log(f"Published to {topic}: {message}")
            return True
        else:
            retries += 1
            log(f"Failed to publish to {topic}, attempt {retries}/{max_retries}")
            time.sleep(1)  # Wait before retrying
    
    log(f"ERROR: Failed to publish to {topic} after {max_retries} attempts")
    return False

def handle_sensor_request():
    """Respond to MQTT request for current sensor data"""
    try:
        log("handle_sensor_request() triggered by MQTT")  
        sensor_data = read_sensors()
        publish_message(SENSOR_DATA_TOPIC, sensor_data)
        log("Sensor data sent on request.")
    except Exception as e:
        log(f"Error while handling sensor data request: {e}")


def publish_sensor_data():
        """Publish sensor data to MQTT broker only when data changes"""
        global sensor_data_running
        previous_sensors = None

        while sensor_data_running:
            try:
                sensors = read_sensors()

                if sensors != previous_sensors:
                    publish_message(SENSOR_DATA_TOPIC, sensors, qos=0, retain=False)
                    previous_sensors = sensors

            except Exception as e:
                log(f"Error publishing sensor data: {e}")
            
            time.sleep(0.05)  # Small delay to avoid busy loop (adjust as needed)

def publish_heartbeat():
    """Publish heartbeat to broker to indicate the station is online"""
    global heartbeat_running
    
    while heartbeat_running:
        try:
            heartbeat_data = {
                "node": STATION_NAME,
                "status": "online",
                "timestamp": time.time()
            }
            publish_message(f"{mqtt_topic_base}HEARTBEAT/{STATION_NAME}", heartbeat_data, qos=0)

        except Exception as e:
            log(f"Error publishing heartbeat: {e}")
        time.sleep(10)  # Heartbeat every 10 seconds

def move_motor(direction, sensor_pin):
    global motor_direction
    motor_direction = direction

    """
    Move the motor in the specified direction until sensor is triggered 'count_max' times
    
    Args:
        direction: GPIO.HIGH or GPIO.LOW for direction
        stop_sensor: GPIO pin number of the sensor to check
        count_max: Number of times sensor should be triggered
        slow_extra: If True, perform extra slow movement
    """
    
    while True:
        GPIO.output(DIR, motor_direction)
        GPIO.output(DIR, motor_direction)
        GPIO.output(PUL, GPIO.HIGH)
        time.sleep(STEP_DELAY)
        GPIO.output(PUL, GPIO.LOW)
        time.sleep(STEP_DELAY)
        if GPIO.input(sensor_pin) == 0:  # Sensor active (LED off)
            break
    
    try:
        GPIO.getmode()
    except RuntimeError:
        log("GPIO mode not set. Re-initializing GPIO setup...")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
    
def send_capsule():
    """Execute sending capsule procedure"""
    global system_busy, current_task_id
    
    system_busy = True
    log("Starting SEND procedure")
    
    # Notify system that we're beginning the send procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "sending",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)
    
    # Wait for capsule at P1
    log("Waiting for capsule at P1...")
    while GPIO.input(P1) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    
    log("Capsule detected at P1")
    
    # Drop capsule
    move_motor(GPIO.LOW, S1)
    log("Capsule dropped")
    
    # Wait for capsule at P2
    while GPIO.input(P2) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule at P2")
    
    # Move to P3
    move_motor(GPIO.HIGH, S2)
    
    # Wait for capsule at P3
    while GPIO.input(P3) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule at P3, activating blower")
    
    # Activate blower
    publish_message(BLOWER_TOPIC, pump)
    
    # Notify system that sending is complete
    completion_data = {
        "type": "dispatch_completed",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "send",
            "sensors": read_sensors()
        }
    }
    #publish_message(ACK_TOPIC, completion_data)
    
    log("Send procedure complete")
    system_busy = False
    current_task_id = None

def receive_capsule():
    """Execute receiving capsule procedure"""
    global system_busy, current_task_id
    
    system_busy = True
    log("Starting RECEIVE procedure")
    
    # Notify system that we're beginning the receive procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "receiving",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)
    
    # Wait for capsule at P3
    log("Waiting for capsule at P3...")
    while GPIO.input(P3) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule detected at P3")
    publish_message(BLOWER_TOPIC, "stop")
    log("Blower OFF")
    
    # Move motor to receive position
    move_motor(GPIO.LOW, S3)
    
    # Activate blower in suction mode
    publish_message(BLOWER_TOPIC, pump)
    time.sleep(0.2)
    log("Blower SUCTION, capsule picked")
    
    # Wait for capsule at P4
    while GPIO.input(P4) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule at P4")
    
    # Turn off blower
    publish_message(BLOWER_TOPIC, "stop")
    log("Blower OFF")
    
    # Move to final position
    move_motor(GPIO.HIGH, S4)
    time.sleep(2)
    log("Capsule received")
    
    # Reset position
    move_motor(GPIO.LOW, S2)
    log("Reset complete")
    
    # Notify system that receiving is complete
    completion_data = {
        "type": "receive_completed",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "receive",
            "sensors": read_sensors()
        }
    }
    publish_message(ACK_TOPIC, completion_data)
    
    log("Receive procedure complete")
    system_busy = False
    current_task_id = None

def self_capsule():
    """Execute Self test procedure"""
    global system_busy, current_task_id
    
    system_busy = True
    log("Starting SELF TEST procedure")
    
    # Notify system that we're beginning the send procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "SELF_TEST",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)
    
    # Wait for capsule at P1
    log("Waiting for capsule at P1...")
    while GPIO.input(P1) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    
    log("Capsule detected at P1")
    
    # Drop capsule
    move_motor(GPIO.LOW, S1)
    log("Capsule dropped")
    
    # Wait for capsule at P2
    while GPIO.input(P2) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule at P2")
    
    # Move to P3
    move_motor(GPIO.HIGH, S2)
    log("Capsule at p3")
    
    # Wait for capsule at P3
    while GPIO.input(P3) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule at P3, moving to recive sequence")
    move_motor(GPIO.LOW, S3)
    log("Blower on")
    # Activate blower
    publish_message(BLOWER_TOPIC, pump)
    
    # Wait for capsule at P4
    while GPIO.input(P4) == GPIO.LOW:  # Wait until sensor is triggered (LOW)
        time.sleep(0.1)
    log("Capsule at P4")
    
    # Turn off blower
    publish_message(BLOWER_TOPIC, "stop")
    log("Blower OFF")
    
    # Move to final position
    move_motor(GPIO.HIGH, S4)
    time.sleep(2)
    log("Capsule received")
    
    # Reset position
    move_motor(GPIO.LOW, S2)
    log("Reset complete")

    
    # Notify system that sending is complete
    completion_data = {
        "type": "SELF_TEST_completed",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "SELF_TEST",
            "sensors": read_sensors()
        }
    }
    publish_message(ACK_TOPIC, completion_data)
    
    log("Send procedure complete")
    system_busy = False
    current_task_id = None

# def passthrough():

#     global system_busy, current_task_id
    
#     system_busy = True
#     log("Starting passthrough procedure")

#     # Notify system that we're beginning the passthrough procedure
#     ack_data = {
#         "station": STATION_NAME,
#         "status": "passthrough",
#         "task_id": current_task_id,
#         "timestamp": time.time()
#     }
#     publish_message(ACK_TOPIC, ack_data)

#     if GPIO.input(S2) == GPIO.HIGH:

#         log("[passthrough] Starting passthrough")

#         move_motor(GPIO.LOW, S2)
#         print("[passthrough] system in passthrough state")

        

#     else:

#         print("[passthrough] system in passthrough state")

#         # Notify system that passthrough is complete
#     completion_data = {
#         "type": "passthrough",
#         "station": STATION_NAME,
#         "task_id": current_task_id,
#         "status": "completed",
#         "timestamp": time.time(),
#         "details": {
#             "operation": "passthrough",
#             "sensors": read_sensors()
#         }
#     }
#     publish_message(ACK_TOPIC, completion_data)
    
#     log("Passthrough procedure complete")
#     system_busy = False
#     current_task_id = None

# ===== MQTT MTN Helper Functions =====
def move_left():
    GPIO.output(DIR, GPIO.LOW)  # Set direction

    for _ in range(MTN_STEP_COUNT):
        GPIO.output(PUL, GPIO.HIGH)
        time.sleep(0.0005)  # Small delay for step pulse
        GPIO.output(PUL, GPIO.LOW)
        time.sleep(0.0005)

def move_right():
    GPIO.output(DIR, GPIO.HIGH)  # Set direction

    for _ in range(MTN_STEP_COUNT):
        GPIO.output(PUL, GPIO.HIGH)
        time.sleep(0.0005)  # Small delay for step pulse
        GPIO.output(PUL, GPIO.LOW)
        time.sleep(0.0005)

def loop_s1_4():
    """Continuously run motor back and forth between S1 and S4 until stopped."""
    global system_busy, loop_running
    system_busy = True
    loop_running = True

    log("[loop_between_s1_s4] Starting motor loop between S1 and S4...")

    try:
        while loop_running:
            log("[loop_between_s1_s4] Moving toward S1")
            move_motor(GPIO.LOW, S1)
            time.sleep(0.5)

            if not loop_running:
                break

            log("[loop_between_s1_s4] Moving toward S4")
            move_motor(GPIO.HIGH, S4)
            time.sleep(0.5)

    except Exception as e:
        log(f"[loop_between_s1_s4] Error: {e}")

    finally:
        system_busy = False
        loop_running = False
        log("[loop_between_s1_s4] Loop stopped")

def stop_loop():
    global loop_running
    loop_running = False
    log("[stop_loop] Loop stop requested.")

def load():

    global system_busy, current_task_id
    
    system_busy = True
    log("Starting load procedure")

    # Notify system that we're beginning the load procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "load",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)

    if GPIO.input(S1) == GPIO.HIGH:

        log("[load] Starting load")

        move_motor(GPIO.LOW, S1)
        print("[load] system in load state")

        

    else:

        print("[load] system in load state")

        # Notify system that load is complete
    completion_data = {
        "type": "load",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "load",
            "sensors": read_sensors()
        }
    }
    publish_message(ACK_TOPIC, completion_data)
    
    log("load procedure complete")
    system_busy = False
    current_task_id = None

def passthrough():

    global system_busy, current_task_id
    
    system_busy = True
    log("Starting passthrough procedure")

    # Notify system that we're beginning the passthrough procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "passthrough",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)

    if GPIO.input(S2) == GPIO.HIGH:

        log("[passthrough] Starting passthrough")

        move_motor(GPIO.LOW, S2)
        print("[passthrough] system in passthrough state")

        

    else:

        print("[passthrough] system in passthrough state")

        # Notify system that passthrough is complete
    completion_data = {
        "type": "passthrough",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "passthrough",
            "sensors": read_sensors()
        }
    }
    publish_message(ACK_TOPIC, completion_data)
    
    log("Passthrough procedure complete")
    system_busy = False
    current_task_id = None

def arrive():

    global system_busy, current_task_id
    
    system_busy = True
    log("Starting arrive procedure")

    # Notify system that we're beginning the arrive procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "arrive",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)

    if GPIO.input(S3) == GPIO.HIGH:

        log("[arrive] Starting arrive")

        move_motor(GPIO.HIGH, S3)
        print("[arrive] system in arrive state")

        

    else:

        print("[arrive] system in arrive state")

        # Notify system that arrive is complete
    completion_data = {
        "type": "arrive",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "arrive",
            "sensors": read_sensors()
        }
    }
    publish_message(ACK_TOPIC, completion_data)
    
    log("arrive procedure complete")
    system_busy = False
    current_task_id = None

def drop():

    global system_busy, current_task_id
    
    system_busy = True
    log("Starting drop procedure")

    # Notify system that we're beginning the drop procedure
    ack_data = {
        "station": STATION_NAME,
        "status": "drop",
        "task_id": current_task_id,
        "timestamp": time.time()
    }
    publish_message(ACK_TOPIC, ack_data)

    if GPIO.input(S4) == GPIO.HIGH:

        log("[drop] Starting drop")

        move_motor(GPIO.HIGH, S4)
        print("[drop] system in drop state")

        

    else:

        print("[drop] system in drop state")

        # Notify system that drop is complete
    completion_data = {
        "type": "drop",
        "station": STATION_NAME,
        "task_id": current_task_id,
        "status": "completed",
        "timestamp": time.time(),
        "details": {
            "operation": "drop",
            "sensors": read_sensors()
        }
    }
    publish_message(ACK_TOPIC, completion_data)
    
    log("drop procedure complete")
    system_busy = False
    current_task_id = None

def blow():
    log(f"[blow] blower activated")
    publish_message(BLOWER_TOPIC, "b")

def suck():
    log(f"[suck] suction activated")
    publish_message(BLOWER_TOPIC, "s")

def stop():
    log(f"[stop blower] stoping the pump")
    publish_message(BLOWER_TOPIC, "stop")
    
# ===== MQTT Callback Functions =====
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log(f"Connected to MQTT broker {BROKER_IP} as {STATION_NAME}")
        
        # Subscribe to relevant topics
        client.subscribe(ACTION_TOPIC)
        client.subscribe(SCRIPT_TOPIC)
        client.subscribe(DISPATCH_TOPIC)
        client.subscribe(STATUS_TOPIC)
        client.subscribe(MTN_TOPIC)
        client.subscribe(SENSOR_REQUEST_TOPIC)


        log(f"Subscribed to topics: {ACTION_TOPIC}, {SCRIPT_TOPIC}, {DISPATCH_TOPIC}, {STATUS_TOPIC}, {MTN_TOPIC}")
        
        # Publish station online status
        online_status = {
            "station": STATION_NAME,
            "status": "online",
            "ip": socket.gethostbyname(socket.gethostname()),
            "timestamp": time.time()
        }
        publish_message(STATUS_TOPIC, online_status)
        
        # Start sensor data reporting thread
        global sensor_data_thread, sensor_data_running
        sensor_data_running = True
        sensor_data_thread = threading.Thread(target=publish_sensor_data, daemon=True)
        sensor_data_thread.daemon = True
        sensor_data_thread.start()
        
        # Start heartbeat thread
        global heartbeat_thread, heartbeat_running
        heartbeat_running = True
        heartbeat_thread = threading.Thread(target=publish_heartbeat, daemon=True)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()

        def reset_limit_counters():
            """Periodically reset limit switch trigger counters to avoid false positives."""
            global limit_switch_left_count, limit_switch_right_count
            while True:
                time.sleep(LIMIT_RESET_INTERVAL)
                with limit_counter_lock:
                    if limit_switch_left_count > 0 or limit_switch_right_count > 0:
                        log(f"Resetting limit switch counters: Left={limit_switch_left_count}, Right={limit_switch_right_count}")
                    limit_switch_left_count = 0
                    limit_switch_right_count = 0

    else:
        log(f"Connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    log(f"Disconnected (code {rc})")
    
    # Stop sensor data reporting
    global sensor_data_running, heartbeat_running
    sensor_data_running = False
    heartbeat_running = False
    
    # Attempt to reconnect
    while rc != 0:
        log("Attempting to reconnect...")
        try:
            rc = client.reconnect()
        except Exception as e:
            log(f"Reconnection failed: {e}")
            time.sleep(2)

def on_message(client, userdata, message):
    """Handle incoming MQTT messages"""
    topic = message.topic
    try:
        payload = message.payload.decode('utf-8')
        log(f"Received message on {topic}: {payload}")
        
        # Handle different message types based on topic
        if topic == ACTION_TOPIC:
            handle_action_message(payload)
        elif topic == SCRIPT_TOPIC:
            handle_script_message(payload)
        elif topic == DISPATCH_TOPIC:
            handle_dispatch_message(payload)
        elif topic == STATUS_TOPIC:
            handle_status_message(payload)
        elif topic == SENSOR_REQUEST_TOPIC:
            handle_sensor_request()

        else:
            log(f"Unhandled topic: {topic}")
    
    except Exception as e:
        log(f"Error processing message: {e}")

def handle_action_message(payload):
    global system_busy, current_dispatch_mode

    try:
        data = json.loads(payload)
        action = data.get('action')

        if action == "getdata":
            handle_sensor_request()
            return

        if system_busy:
            log(f"System busy, ignoring action: {action}")
            return

        if action == "dispatch":
            current_dispatch_mode = "send"
            motor_thread = threading.Thread(target=send_capsule, daemon=True)
            motor_thread.start()
        elif action == "receive":
            current_dispatch_mode = "receive"
            motor_thread = threading.Thread(target=receive_capsule, daemon=True)
            motor_thread.start()

        else:
            log(f"Unknown action: {action}")
    
    except json.JSONDecodeError:
        # Try legacy format (simple string command)
        if payload == "send":
            current_dispatch_mode = "send"
            motor_thread = threading.Thread(target=send_capsule, daemon=True)
            motor_thread.start()
        elif payload == "receive":
            current_dispatch_mode = "receive"
            motor_thread = threading.Thread(target=receive_capsule, daemon=True)
            motor_thread.start()
        else:
            log(f"Unknown command: {payload}")

def handle_mtn_message(payload):
    global system_busy, current_dispatch_mode
    
    try:
        data = json.loads(payload)
        action = data.get('action')

        if action == "stop":
            current_dispatch_mode = "stop_loop"
            motor_thread = threading.Thread(target=stop_loop, daemon=True)
            motor_thread.start()
        
        if system_busy:
            log(f"System busy, ignoring action: {action}")
            return
        
        if action == "self_test":
            current_dispatch_mode = "self_capsule"
            motor_thread = threading.Thread(target=self_capsule, daemon=True)
            motor_thread.start()
        elif action == "moveLeft":
            current_dispatch_mode = "moveLeft"
            motor_thread = threading.Thread(target=move_left, daemon=True)
            motor_thread.start()
        elif action == "moveRight":
            current_dispatch_mode = "moveRight"
            motor_thread = threading.Thread(target=move_right, daemon=True)
            motor_thread.start()
        elif action == "loop":
            current_dispatch_mode = "loop"
            motor_thread = threading.Thread(target=loop_s1_4, daemon=True)
            loop_running = True
            motor_thread.start()
        elif action == "stop":
            current_dispatch_mode = "stop_loop"
            motor_thread = threading.Thread(target=stop_loop, daemon=True)
            motor_thread.start()

        elif action == "load":
            current_dispatch_mode = "load"
            motor_thread = threading.Thread(target=load, daemon=True)
            motor_thread.start()
        
        elif action == "passthrough":
            current_dispatch_mode = "passthrough"
            motor_thread = threading.Thread(target=passthrough, daemon=True)
            motor_thread.start()

        elif action == "arrive":
            current_dispatch_mode = "arrive"
            motor_thread = threading.Thread(target=arrive, daemon=True)
            motor_thread.start()

        elif action == "drop":
            current_dispatch_mode = "drop"
            motor_thread = threading.Thread(target=drop, daemon=True)
            motor_thread.start()

        elif action == "blow":
            blow()
        
        elif action == "suck":
            suck()

        elif action == "stop_blower":
            stop()

        else:
            log(f"Unknown action: {action}")
    
    except json.JSONDecodeError:
        # Try legacy format (simple string command)
        if payload == "self_test":
            current_dispatch_mode = "self_test"
            motor_thread = threading.Thread(target=self_capsule, daemon=True)
            motor_thread.start()
        elif payload == "moveLeft":
            current_dispatch_mode = "moveLeft"
            motor_thread = threading.Thread(target=move_left, daemon=True)
            motor_thread.start()
        elif payload == "moveRight":
            current_dispatch_mode = "moveRight"
            motor_thread = threading.Thread(target=move_right, daemon=True)
            motor_thread.start()
        elif payload == "loop":
            current_dispatch_mode = "loop"
            motor_thread = threading.Thread(target=loop_s1_4, daemon=True)
            motor_thread.start()
        elif payload == "stop":
            current_dispatch_mode = "stop_loop"
            motor_thread = threading.Thread(target=stop_loop, daemon=True)
            motor_thread.start()

        elif action == "stop_blower":
            stop()
                
        elif action == "load":
            current_dispatch_mode = "load"
            motor_thread = threading.Thread(target=load, daemon=True)
            motor_thread.start()
        
        elif action == "passthrough":
            current_dispatch_mode = "passthrough"
            motor_thread = threading.Thread(target=passthrough, daemon=True)
            motor_thread.start()

        elif action == "arrive":
            current_dispatch_mode = "arrive"
            motor_thread = threading.Thread(target=arrive, daemon=True)
            motor_thread.start()

        elif action == "drop":
            current_dispatch_mode = "drop"
            motor_thread = threading.Thread(target=drop, daemon=True)
            motor_thread.start()
        
        elif action == "blow":
            blow()
        
        elif action == "suck":
            suck()
            

        else:
            log(f"Unknown command: {payload}")

def handle_script_message(payload):
    """Handle script execution commands"""
    global current_task_id, system_busy
    
    if system_busy:
        log("System busy, ignoring script execution")
        return
    
    try:
        data = json.loads(payload)
        script_name = data.get('script')
        params = data.get('params', {})
        current_task_id = data.get('task_id')
        
        log(f"Script execution request: {script_name} with params: {params}")
        
        # In this case, we're handling the script execution inline
        # rather than launching external scripts
        if script_name == 'master_v3.py':
            mode = params.get('mode')
            
            if mode == 'send':
                log("Executing send mode")
                motor_thread = threading.Thread(target=send_capsule, daemon=True)
                motor_thread.start()
            elif mode == 'receive':
                log("Executing receive mode")
                motor_thread = threading.Thread(target=receive_capsule, daemon=True)
                motor_thread.start()
            else:
                log(f"Unknown mode: {mode}")
        else:
            log(f"Unknown script: {script_name}")
    
    except json.JSONDecodeError:
        log(f"Invalid JSON format in script message: {payload}")

def handle_dispatch_message(payload):
    """Handle dispatch requests"""
    global current_task_id, system_busy
    
    if system_busy:
        log("System busy, ignoring dispatch message")
        return
    
    try:
        data = json.loads(payload)
        current_task_id = data.get('task_id')
        from_id = data.get('from')
        to_id = data.get('to')
        
        log(f"Dispatch request: Task {current_task_id} from {from_id} to {to_id}")
        
        # Determine if this station is the sender or receiver
        if from_id == STATION_NUM:
            log("This station is the sender")
            motor_thread = threading.Thread(target=send_capsule, daemon=True)
            motor_thread.start()
        elif to_id == STATION_NUM:
            log("This station is the receiver")
            motor_thread = threading.Thread(target=receive_capsule, daemon=True)
            motor_thread.start()
        else:
            log("This station is not involved in this dispatch")
    
    except json.JSONDecodeError:
        log(f"Invalid JSON format in dispatch message: {payload}")

def handle_status_message(payload):
    """Handle system status updates"""
    try:
        data = json.loads(payload)
        status = data.get('status')
        
        log(f"System status update: {status}")
        
        # Update internal state based on status
        if status == 'standby':
            global system_busy
            system_busy = False
    
    except json.JSONDecodeError:
        log(f"Invalid JSON format in status message: {payload}")

#limit interepts 
GPIO.add_event_detect(LIMIT_SWITCH_LEFT, GPIO.FALLING, callback=limit_switch_triggered, bouncetime=200)
GPIO.add_event_detect(LIMIT_SWITCH_RIGHT, GPIO.FALLING, callback=limit_switch_triggered, bouncetime=200)


# ===== Main Function =====
def main():
    # Set up MQTT callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Set up last will message for when the station disconnects unexpectedly
    last_will = json.dumps({
        "station": STATION_NAME,
        "status": "offline",
        "timestamp": time.time()
    })
    client.will_set(STATUS_TOPIC, last_will, qos=1, retain=True)
    
    # Connect to MQTT broker
    try:
        client.connect(BROKER_IP, PORT, keepalive=60)
    except Exception as e:
        log(f"Failed to connect to broker: {e}")
        return
    
    log(f"Started {STATION_NAME} on {socket.gethostbyname(socket.gethostname())}")
    log("Waiting for commands...")
    
    # Start the MQTT loop
    client.loop_forever()

# ===== Entry Point =====
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user. Shutting down...")
    finally:
        # Clean up GPIO
        GPIO.output(ENA, GPIO.HIGH)  # Disable motor
        GPIO.cleanup()
        
        # Stop threads
        sensor_data_running = False
        heartbeat_running = False
        
        # Disconnect from MQTT broker
        if client.is_connected():
            client.disconnect()
