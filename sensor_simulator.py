import time
import json
import random
import socket
import paho.mqtt.client as mqtt

# MQTT Configuration
mqtt_broker_ip = "test.mosquitto.org"
mqtt_port = 1883
mqtt_topic_base = 'PTS/'
mqtt_sensor_data_topic = mqtt_topic_base + 'SENSORDATA/'

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

def generate_sensor_data(station_id):
    """Generate random sensor data for testing"""
    return {
        'station_id': station_id,
        'sensor_1': random.choice([True, False]),
        'sensor_2': random.choice([True, False]),
        'sensor_3': random.choice([True, False]),
        'sensor_4': random.choice([True, False]),
        'sensor_5': random.choice([True, False]),
        'sensor_6': random.choice([True, False]),
        'sensor_7': random.choice([True, False]),
        'sensor_8': random.choice([True, False]),
        'timestamp': time.time()
    }

def main():
    try:
        # Get station name and ID
        station_name = get_station_name()
        station_id = station_name.split('-')[-1]  # Extract the number
        
        print(f"Starting sensor simulator for station {station_name} (ID: {station_id})")
        
        # Connect to MQTT broker
        client = mqtt.Client(f"sensor_simulator_{random.randint(1000, 9999)}")
        client.connect(mqtt_broker_ip, mqtt_port, 60)
        
        # Publish sensor data every 5 seconds
        while True:
            sensor_data = generate_sensor_data(station_id)
            data_json = json.dumps(sensor_data)
            
            # Publish to MQTT
            client.publish(f"{mqtt_sensor_data_topic}{station_id}", data_json)
            
            print(f"Published sensor data: {data_json}")
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("Sensor simulator stopped")
    except Exception as e:
        print(f"Error in sensor simulator: {e}")
    finally:
        if 'client' in locals():
            client.disconnect()

if __name__ == "__main__":
    main()