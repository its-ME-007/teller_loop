import requests
import socket
import subprocess
import time
import webbrowser
import json
import threading
import os
import sys
import paho.mqtt.client as mqtt
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RPiClient')

# MQTT Configuration
mqtt_broker_ip = "test.mosquitto.org"
mqtt_port = 1883
mqtt_topic_base = 'PTS/'
mqtt_script_topic = mqtt_topic_base + 'SCRIPT/'
mqtt_status_topic = mqtt_topic_base + 'STATUS/'
mqtt_sensor_data_topic = mqtt_topic_base + 'SENSORDATA/'

# Global variables
station_name = None
station_id = None
mqtt_client = None

def get_ip_address():
    """Get the IP address of the Raspberry Pi"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"Error getting IP address: {e}")
        # Fallback method using hostname
        return socket.gethostbyname(socket.gethostname())

def determine_station_name():
    """Determine station name based on IP address"""
    ip = get_ip_address()
    
    # Map IPs to station names (keep in sync with server)
    ip_to_station = {
        '192.168.43.87': 'passthrough-station-1',
        '192.168.43.251': 'passthrough-station-2',
        '192.168.43.61': 'passthrough-station-3',
        '192.168.43.200': 'passthrough-station-4'
    }
    
    name = ip_to_station.get(ip)
    if name:
        return name, name.split('-')[-1]  # Return name and ID number
    else:
        # For testing: use a default if IP not recognized
        logger.warning(f"IP {ip} not recognized, using default station name")
        return 'passthrough-station-1', '1'

def fetch_page_url(server_address):
    """Fetch the URL for this Raspberry Pi from the server"""
    try:
        url = f"http://{server_address}/get_page_url"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            logger.error(f"Error: Server returned status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to server: {e}")
        return None

def display_url_info(url_info):
    """Display URL information in the terminal"""
    print("\n" + "="*50)
    print("RASPBERRY PI URL INFORMATION")
    print("="*50)
    print(f"IP Address: {url_info['ip']}")
    print(f"Page ID:    {url_info['page_id']}")
    print(f"URL:        {url_info['url']}")
    print("="*50)
    print("To open this URL in your browser, press 'o'")
    print("To exit, press 'q'")
    print("="*50 + "\n")

def start_sensor_simulator():
    """Start the sensor simulator in a separate process"""
    logger.info("Starting sensor simulator...")
    try:
        # Check if sensor_simulator.py exists in the same directory
        if os.path.exists("sensor_simulator.py"):
            subprocess.Popen([sys.executable, "sensor_simulator.py"], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
            logger.info("Sensor simulator started")
        else:
            logger.error("sensor_simulator.py not found in current directory")
    except Exception as e:
        logger.error(f"Error starting sensor simulator: {e}")

def handle_mqtt_message(client, userdata, message):
    """Handle incoming MQTT messages"""
    try:
        payload = message.payload.decode()
        topic = message.topic
        logger.info(f"MQTT message received: {topic}")
        
        # Handle script execution requests
        if topic.startswith(f"{mqtt_script_topic}{station_name}"):
            try:
                data = json.loads(payload)
                script_name = data.get('script')
                params = data.get('params', {})
                task_id = data.get('task_id')
                
                logger.info(f"Script execution request: {script_name}, Task ID: {task_id}")
                
                # Check if script exists
                if not os.path.exists(script_name):
                    logger.error(f"Script not found: {script_name}")
                    return
                
                # Execute script with parameters
                params_json = json.dumps(params)
                process = subprocess.Popen(
                    [sys.executable, script_name, params_json],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Log the execution
                logger.info(f"Executing script: {script_name} with params: {params_json}")
                
                # Monitor script output in a separate thread
                def monitor_output():
                    stdout, stderr = process.communicate()
                    if stdout:
                        logger.info(f"Script output: {stdout.decode()}")
                    if stderr:
                        logger.error(f"Script error: {stderr.decode()}")
                    
                    # Report completion back to MQTT
                    result_message = {
                        'station': station_name,
                        'task_id': task_id,
                        'script': script_name,
                        'result': 'completed',
                        'timestamp': time.time()
                    }
                    client.publish(f"{mqtt_script_topic}{station_name}/result", json.dumps(result_message))
                
                threading.Thread(target=monitor_output).start()
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in MQTT message: {payload}")
            except Exception as e:
                logger.error(f"Error processing script execution: {e}")
        
        # Handle status update requests
        elif topic.startswith(f"{mqtt_status_topic}{station_id}"):
            try:
                status_data = json.loads(payload)
                status = status_data.get('status')
                logger.info(f"Station status update: {status}")
                
                if status == 'sending':
                    logger.info(f"Starting send operation to station {status_data.get('destination')}")
                elif status == 'receiving':
                    logger.info(f"Starting receive operation from station {status_data.get('source')}")
                elif status == 'standby':
                    logger.info("Station status: Standby")
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in status message: {payload}")
                
    except Exception as e:
        logger.error(f"Error in MQTT message handler: {e}")

def setup_mqtt():
    """Set up MQTT client and subscriptions"""
    global mqtt_client
    
    client_id = f"rpi_client_{station_name}_{int(time.time())}"
    mqtt_client = mqtt.Client(client_id)
    mqtt_client.on_message = handle_mqtt_message
    
    try:
        # Connect to MQTT broker
        mqtt_client.connect(mqtt_broker_ip, mqtt_port, 60)
        
        # Subscribe to relevant topics
        mqtt_client.subscribe(f"{mqtt_script_topic}{station_name}")
        mqtt_client.subscribe(f"{mqtt_status_topic}{station_id}")
        
        # Start MQTT loop in a background thread
        mqtt_client.loop_start()
        
        logger.info(f"Connected to MQTT broker {mqtt_broker_ip}:{mqtt_port}")
        logger.info(f"Subscribed to topics: {mqtt_script_topic}{station_name}, {mqtt_status_topic}{station_id}")
        
        # Announce ourselves
        status_message = {
            'station': station_name,
            'status': 'online',
            'ip': get_ip_address(),
            'timestamp': time.time()
        }
        mqtt_client.publish(f"{mqtt_status_topic}{station_id}", json.dumps(status_message))
        
    except Exception as e:
        logger.error(f"Error setting up MQTT: {e}")
        return False
    
    return True

def main():
    global station_name, station_id
    
    logger.info("Starting Raspberry Pi client...")
    
    # Determine station name and ID based on IP
    station_name, station_id = determine_station_name()
    logger.info(f"Station identified as: {station_name} (ID: {station_id})")
    
    # Set up MQTT
    if not setup_mqtt():
        logger.error("Failed to set up MQTT. Some features may not work.")
    
    # Start sensor simulator
    start_sensor_simulator()
    
    SERVER_ADDRESS = "192.168.1.10:5000"  
    
    logger.info("Fetching URL information for this Raspberry Pi...")
    
    url_info = fetch_page_url(SERVER_ADDRESS)
    
    if url_info and url_info.get('status') == 'success':
        display_url_info(url_info)
        
        # Wait for user input
        while True:
            user_input = input("Enter 'o' to open URL, 's' for status, or 'q' to quit: ").lower()
            if user_input == 'o':
                logger.info(f"Opening URL: {url_info['url']}")
                # Try to open in browser
                try:
                    webbrowser.open(url_info['url'])
                except Exception as e:
                    logger.error(f"Could not open browser automatically: {e}")
                    # Fallback for Raspberry Pi terminal
                    try:
                        subprocess.run(['xdg-open', url_info['url']], check=True)
                    except Exception as e2:
                        logger.error(f"Could not open using xdg-open: {e2}")
                        print(f"Please manually open: {url_info['url']}")
            elif user_input == 's':
                # Display current status
                ip = get_ip_address()
                print("\n" + "="*50)
                print("RASPBERRY PI STATUS")
                print("="*50)
                print(f"Station Name: {station_name}")
                print(f"Station ID:   {station_id}")
                print(f"IP Address:   {ip}")
                print(f"MQTT Broker:  {mqtt_broker_ip}:{mqtt_port}")
                print("="*50 + "\n")
            elif user_input == 'q':
                logger.info("Exiting program.")
                # Clean up MQTT connection
                if mqtt_client:
                    # Send offline status
                    status_message = {
                        'station': station_name,
                        'status': 'offline',
                        'timestamp': time.time()
                    }
                    mqtt_client.publish(f"{mqtt_status_topic}{station_id}", json.dumps(status_message))
                    
                    # Disconnect from MQTT
                    mqtt_client.loop_stop()
                    mqtt_client.disconnect()
                break
    else:
        logger.error("Failed to get URL information. Please check:")
        print("1. Is the server running?")
        print("2. Is this Raspberry Pi's IP address registered in the server's mapping?")
        print("3. Can this Raspberry Pi connect to the server?")
        print(f"Current IP address: {get_ip_address()}")
        print(f"Server address: {SERVER_ADDRESS}")

if __name__ == "__main__":
    main()