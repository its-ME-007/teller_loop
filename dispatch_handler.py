import json
import time
import random
import sys
import socket
import paho.mqtt.client as mqtt

# MQTT Configuration
mqtt_broker_ip = "test.mosquitto.org"
mqtt_port = 1883
mqtt_topic_base = 'PTS/'
mqtt_ack_topic = mqtt_topic_base + 'ACK/'
mqtt_script_topic = mqtt_topic_base + 'SCRIPT/'
mqtt_status_topic = mqtt_topic_base + 'STATUS/'

def get_station_name():
    """Get station name based on IP - for testing only"""
    ip = socket.gethostbyname(socket.gethostname())
    
    # Mapping of IPs to station names (copy from server)
    ip_to_station = {
        '192.168.43.87': 'passthrough-station-1',
        '192.168.43.251': 'passthrough-station-2',
        '192.168.43.61': 'passthrough-station-3',
        '192.168.43.200': 'passthrough-station-4'
    }
    
    # For testing, return a default station if IP not found
    return ip_to_station.get(ip, 'passthrough-station-1')

def log_message(message):
    """Print log message with timestamp"""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def handle_send_operation(params):
    """Handle sending operation"""
    task_id = params.get('task_id')
    destination = params.get('destination')
    priority = params.get('priority', 'low')
    
    log_message(f"Starting SEND operation for task {task_id} to station {destination} with {priority} priority")
    
    # Simulate sensors activating in sequence
    for i in range(1, 9):
        sensor_status = [False] * 8
        sensor_status[i-1] = True
        log_message(f"Sensor {i} activated: {sensor_status}")
        time.sleep(1)
    
    # Simulate successful completion
    success_rate = 95  # 95% success rate
    if random.randint(1, 100) <= success_rate:
        log_message(f"Send operation for task {task_id} completed successfully")
        return "success"
    else:
        log_message(f"Send operation for task {task_id} failed")
        return "failure"

def handle_receive_operation(params):
    """Handle receiving operation"""
    task_id = params.get('task_id')
    source = params.get('source')
    priority = params.get('priority', 'low')
    
    log_message(f"Starting RECEIVE operation for task {task_id} from station {source} with {priority} priority")
    
    # Simulate sensors activating in reverse sequence
    for i in range(8, 0, -1):
        sensor_status = [False] * 8
        sensor_status[i-1] = True
        log_message(f"Sensor {i} activated: {sensor_status}")
        time.sleep(1)
    
    # Simulate successful completion
    success_rate = 95  # 95% success rate
    if random.randint(1, 100) <= success_rate:
        log_message(f"Receive operation for task {task_id} completed successfully")
        return "success"
    else:
        log_message(f"Receive operation for task {task_id} failed")
        return "failure"

def main():
    if len(sys.argv) < 2:
        log_message("Error: No parameters provided")
        return
    
    # Parse parameters
    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        log_message(f"Error: Invalid JSON parameters: {sys.argv[1]}")
        return
    
    mode = params.get('mode')
    task_id = params.get('task_id')
    
    # Execute operation based on mode
    result = None
    if mode == 'send':
        result = handle_send_operation(params)
    elif mode == 'receive':
        result = handle_receive_operation(params)
    else:
        log_message(f"Error: Unknown mode: {mode}")
        result = "error"
    
    # Get station name
    station_name = get_station_name()
    station_id = station_name.split('-')[-1]  # Get the number
    
    # Send result via MQTT
    try:
        client = mqtt.Client(f"dispatch_handler_{random.randint(1000, 9999)}")
        client.connect(mqtt_broker_ip, mqtt_port, 60)
        
        # Send script execution result
        script_result = {
            'station': station_name,
            'task_id': task_id,
            'script': 'dispatch_handler.py',
            'params': params,
            'result': result,
            'timestamp': time.time()
        }
        client.publish(f"{mqtt_script_topic}{station_name}", json.dumps(script_result))
        
        # Send acknowledgment if successful
        if result == "success":
            ack_message = {
                'type': 'dispatch_completed',
                'task_id': task_id,
                'station': station_name,
                'timestamp': time.time()
            }
            client.publish(f"{mqtt_ack_topic}{station_id}", json.dumps(ack_message))
            
            # Update status to standby
            status_message = {
                'status': 'standby',
                'timestamp': time.time()
            }
            client.publish(f"{mqtt_status_topic}{station_id}", json.dumps(status_message))
        
        client.disconnect()
        log_message(f"Results published to MQTT: {result}")
    except Exception as e:
        log_message(f"MQTT publishing error: {e}")
    
    return result

if __name__ == "__main__":
    main()