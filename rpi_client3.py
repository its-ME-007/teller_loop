import requests
import socket
import subprocess
import time
import json
import threading
import os
import sys
import paho.mqtt.client as mqtt
from socketio import Client
import logging
import RPi.GPIO as GPIO

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rpi_client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RPiClient')

# Configuration
MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
SERVER_IP = "192.168.1.10"  # Replace with your server IP
SERVER_PORT = 5000
BASE_TOPIC = "PTS/"

# GPIO Pin Assignments for sensor reading
S1 = 23  # Carrier Sensors (Active Low)
S2 = 24
S3 = 25
S4 = 26

P1 = 4   # Position Sensors (Active Low)
P2 = 17
P3 = 27
P4 = 22

# Global variables
station_name = None
station_id = None
mqtt_client = None
sio = None
current_mode = "passthrough"

# --- Core Functions ---
def get_ip_address():
    """Get the RPi's IP address with fallback"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.warning(f"Primary IP detection failed: {e}")
        return socket.gethostbyname(socket.gethostname())

def determine_station():
    """Map IP to station name/ID (must match server's ALLOWED_IPS)"""
    ip = get_ip_address()
    ip_map = {
        '192.168.43.231': ('passthrough-station-1', '1'),
        '192.168.43.251': ('passthrough-station-2', '2'),
        '192.168.43.61': ('passthrough-station-3', '3'),
        '192.168.43.200': ('passthrough-station-4', '4')
    }
    return ip_map.get(ip, ('passthrough-station-1', '1'))  # Default fallback

def setup_gpio():
    """Initialize the GPIO pins for sensors only"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Set up input pins for sensors only
    sensor_pins = [S1, S2, S3, S4, P1, P2, P3, P4]
    for pin in sensor_pins:
        if GPIO.gpio_function(pin) != GPIO.IN:  # Only setup if not already configured
            try:
                GPIO.setup(pin, GPIO.IN)
            except Exception as e:
                logger.warning(f"Could not setup pin {pin}: {e}")

# --- MQTT Functions ---
def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        subscribe_topics()
    else:
        logger.error(f"MQTT connection failed with code {rc}")

def subscribe_topics():
    """Subscribe to all required MQTT topics"""
    topics = [
        f"{BASE_TOPIC}SCRIPT/{station_name}",
        f"{BASE_TOPIC}STATUS/{station_id}",
        f"{BASE_TOPIC}DISPATCH/#",
        f"{BASE_TOPIC}EMPTY_POD_ACCEPTED/{station_name}"
    ]
    for topic in topics:
        mqtt_client.subscribe(topic)
        logger.info(f"Subscribed to {topic}")

def handle_mqtt_message(client, userdata, msg):
    """Process incoming MQTT messages"""
    try:
        topic = msg.topic
        payload_str = msg.payload.decode()
        logger.info(f"MQTT message @ {topic}: {payload_str}")
        
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in MQTT message: {payload_str}")
            payload = {"message": payload_str}

        if f"SCRIPT/{station_name}" in topic:
            handle_script_execution(payload)
        elif f"STATUS/{station_id}" in topic:
            handle_status_update(payload)
        elif f"DISPATCH/" in topic:
            handle_dispatch_message(topic, payload)
        elif "EMPTY_POD_ACCEPTED" in topic:
            logger.info(f"Empty pod request accepted by {payload.get('provider')}")

    except Exception as e:
        logger.error(f"MQTT message error: {e}")

def handle_status_update(payload):
    """Process status updates from the server"""
    global current_mode
    status = payload.get('status')
    
    if status == 'sending':
        current_mode = 'send'
        logger.info(f"Station set to sending mode, destination: {payload.get('destination')}")
        execute_inching_command('send', payload.get('task_id'))
    elif status == 'receiving':
        current_mode = 'receive'
        logger.info(f"Station set to receiving mode, source: {payload.get('source')}")
        execute_inching_command('receive', payload.get('task_id'))
    elif status == 'standby':
        current_mode = 'passthrough'
        logger.info("Station set to passthrough mode")

def handle_dispatch_message(topic, payload):
    """Process dispatch messages"""
    parts = topic.split('/')
    if len(parts) >= 4:
        from_id = parts[2]
        to_id = parts[3]
        
        if from_id == station_id:
            logger.info(f"Dispatch command: send to station {to_id}")
            # The actual command will come through the script execution
        elif to_id == station_id:
            logger.info(f"Dispatch command: receive from station {from_id}")
            # The actual command will come through the script execution

def publish_sensor_data():
    """Read and publish current sensor values"""
    try:
        sensor_values = {
            'station_id': station_id,
            'timestamp': time.time(),
            'sensor_1': GPIO.input(S1) == GPIO.LOW,
            'sensor_2': GPIO.input(S2) == GPIO.LOW,
            'sensor_3': GPIO.input(S3) == GPIO.LOW,
            'sensor_4': GPIO.input(S4) == GPIO.LOW,
            'sensor_5': GPIO.input(P1) == GPIO.LOW,
            'sensor_6': GPIO.input(P2) == GPIO.LOW,
            'sensor_7': GPIO.input(P3) == GPIO.LOW,
            'sensor_8': GPIO.input(P4) == GPIO.LOW
        }
        
        mqtt_client.publish(
            f"{BASE_TOPIC}SENSORDATA/{station_id}",
            json.dumps(sensor_values)
        )
        
        # Also emit via SocketIO
        if sio and sio.connected:
            sio.emit('sensor_data', sensor_values)
            
        return sensor_values
    except Exception as e:
        logger.error(f"Failed to publish sensor data: {e}")
        return None

# --- Socket.IO Functions ---
def setup_socketio():
    """Initialize Socket.IO client"""
    global sio
    sio = Client()

    @sio.on('connect')
    def on_connect():
        logger.info("Connected to server via Socket.IO")
        sio.emit('join', {'username': station_name, 'ip': get_ip_address()})

    @sio.on('disconnect')
    def on_disconnect():
        logger.info("Disconnected from Socket.IO server")

    @sio.on('dispatch')
    def on_dispatch(data):
        logger.info(f"Dispatch request via Socket.IO: {data}")
        # Server will handle this and send appropriate MQTT messages

    @sio.on('empty_pod_request')
    def on_empty_pod_request(data):
        logger.info(f"Empty pod request: {data}")
        # Add logic to accept/reject based on availability
        if current_mode == 'passthrough':
            # We can provide an empty pod
            requester = data.get('requesterStation')
            sio.emit('empty_pod_request_accepted', {
                'provider': station_name,
                'requesterStation': requester,
                'timestamp': time.time()
            })

    try:
        sio.connect(f"http://{SERVER_IP}:{SERVER_PORT}")
    except Exception as e:
        logger.error(f"Socket.IO connection failed: {e}")

# --- Script Execution ---
def handle_script_execution(data):
    """Execute scripts from MQTT commands"""
    script = data.get('script')
    params = data.get('params', {})
    task_id = data.get('task_id')
    
    logger.info(f"Received script execution request: {script} with params {params}")
    
    if script == 'dispatch_handler.py':
        # We're using inching.py directly instead
        mode = params.get('mode')
        if mode == 'send':
            execute_inching_command('send', task_id)
        elif mode == 'receive':
            execute_inching_command('receive', task_id)
    else:
        # For any other script
        if not os.path.exists(script):
            logger.error(f"Script not found: {script}")
            send_script_result(script, task_id, 'failed', f"Script not found: {script}")
            return

        try:
            # Execute script
            proc = subprocess.Popen(
                [sys.executable, script, json.dumps(params)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Monitor output in background
            threading.Thread(
                target=log_script_output,
                args=(proc, script, task_id),
                daemon=True
            ).start()

        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            send_script_result(script, task_id, 'failed', str(e))

def execute_inching_command(mode, task_id):
    """Execute the inching.py script with the appropriate mode"""
    try:
        logger.info(f"Executing inching.py with mode: {mode}")
        
        # Cleanup GPIO before running inching.py
        GPIO.cleanup()
        
        params = {
            'mode': mode,
            'task_id': task_id
        }
        
        proc = subprocess.Popen(
            [sys.executable, 'inching_cs.py', json.dumps(params)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Monitor in background
        threading.Thread(
            target=monitor_inching_process,
            args=(proc, task_id, mode),
            daemon=True
        ).start()
        
        # Re-setup GPIO for sensor monitoring after inching.py starts
        time.sleep(1)  # Give inching.py time to initialize
        setup_gpio()
        
    except Exception as e:
        logger.error(f"Failed to execute inching command: {e}")
        send_script_result('inching.py', task_id, 'failed', str(e))

def monitor_inching_process(proc, task_id, mode):
    """Monitor the inching.py process execution and handle updates"""
    stdout, stderr = proc.communicate()
    
    if stdout:
        stdout_str = stdout.decode()
        logger.info(f"Inching.py stdout: {stdout_str}")
        try:
            # Try to parse the JSON output
            result = json.loads(stdout_str)
            # Process sensor updates if available
            for update in result.get('updates', []):
                # You could publish sensor data with status updates
                pass
        except json.JSONDecodeError:
            logger.warning(f"Could not parse inching.py output as JSON: {stdout_str}")
    
    if stderr:
        stderr_str = stderr.decode()
        logger.error(f"Inching.py stderr: {stderr_str}")
    
    if proc.returncode == 0:
        logger.info(f"Inching.py {mode} completed successfully for task {task_id}")
        # Notify server about completion
        send_script_result('inching.py', task_id, 'success', 'Operation completed')
        # Also notify about dispatch completion
        sio.emit('dispatch_completed', {'task_id': task_id})
    else:
        logger.error(f"Inching.py {mode} failed with return code {proc.returncode} for task {task_id}")
        send_script_result('inching.py', task_id, 'failed', f"Return code: {proc.returncode}")

def log_script_output(proc, script, task_id):
    """Capture and report script output"""
    stdout, stderr = proc.communicate()
    
    if stdout:
        logger.info(f"{script} stdout: {stdout.decode()}")
    if stderr:
        logger.error(f"{script} stderr: {stderr.decode()}")

    # Report completion
    result = 'success' if proc.returncode == 0 else 'failed'
    output = stdout.decode() if proc.returncode == 0 else stderr.decode()
    send_script_result(script, task_id, result, output)

def send_script_result(script, task_id, result, output):
    """Send script execution result via MQTT and Socket.IO"""
    result_data = {
        'station': station_name,
        'task_id': task_id,
        'script': script,
        'result': result,
        'output': output
    }
    
    # Via MQTT
    mqtt_client.publish(
        f"{BASE_TOPIC}SCRIPT_RESULT/{station_name}",
        json.dumps(result_data)
    )
    
    # Via Socket.IO
    if sio and sio.connected:
        sio.emit('script_result', result_data)

# --- Heartbeat System ---
def send_heartbeat():
    """Periodically send heartbeat signals"""
    while True:
        try:
            if mqtt_client:
                mqtt_client.publish(
                    f"{BASE_TOPIC}HEARTBEAT/{station_name}",
                    json.dumps({
                        'node': station_name,
                        'timestamp': time.time()
                    })
                )
            
            if sio and sio.connected:
                sio.emit('heartbeat', {
                    'node': station_name,
                    'timestamp': time.time()
                })
                
            time.sleep(10)  # Every 10 seconds
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            time.sleep(30)  # Longer retry on failure

# --- Empty Pod Handling ---
def request_empty_pod():
    """Initiate empty pod request"""
    if sio and sio.connected:
        sio.emit('empty_pod_request', {
            'requesterStation': station_name,
            'timestamp': time.time()
        })
        logger.info("Empty pod request sent")

# --- Main ---
def main():
    global station_name, station_id, mqtt_client

    # Initialize station identity
    station_name, station_id = determine_station()
    logger.info(f"Starting as {station_name} (ID: {station_id})")
    
    # Set up GPIO
    setup_gpio()

    # Set up MQTT
    mqtt_client = mqtt.Client(f"rpi_{station_name}_{os.getpid()}")
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = handle_mqtt_message
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")

    # Set up Socket.IO
    setup_socketio()

    # Start heartbeat thread
    threading.Thread(target=send_heartbeat, daemon=True).start()

    # Main loop - publish sensor data
    try:
        while True:
            # Read and publish sensor data
            publish_sensor_data()
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if mqtt_client:
            mqtt_client.loop_stop()
        if sio:
            sio.disconnect()
        GPIO.cleanup()

if __name__ == "__main__":
    main()