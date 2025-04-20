import paho.mqtt.client as mqtt
import json
import time

# --- Configuration ---
broker = "test.mosquitto.org"
port = 1883
station_id = 2  # Receiver or sender station ID
task_id = 34     # MUST match current_dispatch['task_id']

topic = f"PTS/ACK/{station_id}"
payload = {
    "type": "dispatch_completed",
    "task_id": task_id,
    "details": {
        "message": "Simulated successful delivery",
        "duration": "3 mins"
    }
}

def on_connect(client, userdata, flags, rc):
    print(f"[✓] Connected to MQTT broker with code {rc}")
    client.publish(topic, json.dumps(payload))
    print(f"[→] Published to topic {topic}")
    client.disconnect()

client = mqtt.Client()
client.on_connect = on_connect
client.connect(broker, port, 60)
client.loop_forever()
