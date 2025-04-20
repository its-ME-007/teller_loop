from flask import Flask, render_template, jsonify, request, abort, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_mqtt import Mqtt
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os, glob
import threading
import time
from collections import defaultdict

# Global variables for tracking
heartbeat_threads = {}
connected_stations = {}  # username -> ip
station_sids = {}  # username -> sid
sid_stations = {}  # sid -> username
station_heartbeats = defaultdict(float) 
HEARTBEAT_TIMEOUT = 30 

# MQTT Configuration
mqtt_broker_ip = "test.mosquitto.org"
mqtt_username = None
mqtt_password = None

# Define allowed stations (name: IP)
ALLOWED_IPS = {
    'passthrough-station-1': '192.168.43.87',
    'passthrough-station-2': '192.168.43.251',
    'passthrough-station-3': '192.168.43.61',
    # 'passthrough-station-4': '192.168.43.200', (Original 4th)
    'passthrough-station-4':'192.168.43.231',
}

# Mapping of RPI IP to page ID
RPI_IP_TO_PAGE_ID = {
    '192.168.43.87': 1,
    '192.168.43.251': 2,
    '192.168.43.61': 3,
    '192.168.43.200': 4,
    '192.168.43.231':5,
}

app = Flask(__name__)
CORS(app, resources={r"/": {"origins": "*"}})

# MQTT Configuration
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MQTT_BROKER_URL'] = mqtt_broker_ip
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_USERNAME'] = mqtt_username
app.config['MQTT_PASSWORD'] = mqtt_password
app.config['MQTT_KEEPALIVE'] = 64800
app.config['MQTT_TLS_ENABLED'] = False
app.config['MQTT_CLIENT_ID'] = 'rpibroker'
app.config['SECRET_KEY'] = 'secret!'

mqtt = Mqtt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DATABASE = 'lan_monitoring.db'

# MQTT topic subscription
mqtt_topic1 = 'PTS/SENSORDATA/#'
mqtt.subscribe(mqtt_topic1, 1)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS history
                      (task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       sender TEXT NOT NULL,
                       receiver TEXT NOT NULL,
                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                       )''')
        
        db.commit()

@socketio.on('join')
def handle_join(data):
    if isinstance(data, dict) and 'username' in data:
        # This is for the station connection flow
        username = data['username']
        ip = data['ip']
        sid = request.sid

        # Check if the station is allowed
        if username in ALLOWED_IPS and ALLOWED_IPS[username] == ip:
            # Place the station into its own room (room name same as username)
            join_room(username)
            print(f"{username} with IP {ip} joined room {username}.")
        else:
            print(f"Unauthorized join attempt: {username} with IP {ip}")
            disconnect()
            return

        # Store station connection data
        connected_stations[username] = ip
        station_sids[username] = sid
        sid_stations[sid] = username

        # Send the updated station list to all clients
        emit('update_connected_stations', list(connected_stations.keys()), broadcast=True)
        emit('station_joined', {'node': username, 'ip': ip}, broadcast=True)
    else:
        # This is for the page_id join flow from code 1
        page_id = data
        join_room(str(page_id))
        print(f"Joined room: {page_id}")

@socketio.on('hello_packet')
def handle_hello_packet(data):
    sender = data['node']
    if sender in connected_stations:
        # Broadcast hello packet to all other stations
        emit('hello_packet', data, broadcast=True, include_self=False)

@socketio.on('hello_ack')
def handle_hello_ack(data):
    sender = data['sender']
    receiver = data['receiver']
    if sender in connected_stations and receiver in connected_stations:
        # Forward acknowledgment to the specific receiver (using room targeting)
        receiver_sid = station_sids.get(receiver)
        if receiver_sid:
            emit('hello_ack', data, room=receiver_sid)

@socketio.on('heartbeat')
def handle_heartbeat(data):
    username = data['node']
    timestamp = data['timestamp']
    if username in connected_stations:
        station_heartbeats[username] = timestamp
        # Broadcast heartbeat to all other stations
        emit('heartbeat', data, broadcast=True, include_self=False)

@socketio.on('dispatch')
def handle_dispatch(data):
    from_id = data['from']
    to_id = data['to']
    print(f"Dispatching from {from_id} to {to_id}")
    for i in range(1, 5):  # Assuming pages 1 to 4
        if i == from_id:
            emit('status', {'message': f'Sending to {to_id}'}, room=str(i))
        elif i == to_id:
            emit('status', {'message': f'Receiving from {from_id}'}, room=str(i))
        else:
            emit('status', {'message': 'Standby'}, room=str(i))

def cleanup_inactive_stations():
    current_time = time.time()
    inactive_threshold = 15  # seconds
    for username, last_heartbeat in list(station_heartbeats.items()):
        if current_time - last_heartbeat > inactive_threshold:
            sid = station_sids.get(username)
            if sid:
                leave_room(username)
                del sid_stations[sid]
                del station_sids[username]
            del connected_stations[username]
            del station_heartbeats[username]
            emit('station_left', {'node': username}, broadcast=True)
            emit('update_connected_stations', list(connected_stations.keys()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    username = sid_stations.get(sid)
    if username:
        # Leave the room associated with this station
        leave_room(username)
        # Clean up tracking data
        if username in connected_stations:
            del connected_stations[username]
        if username in station_sids:
            del station_sids[username]
        if sid in sid_stations:
            del sid_stations[sid]
        if username in station_heartbeats:
            del station_heartbeats[username]
        # Notify clients about disconnection
        emit('station_left', {'node': username}, broadcast=True)
        emit('update_connected_stations', list(connected_stations.keys()), broadcast=True)
    else:
        print("Client disconnected")

@socketio.on('connect')
def handle_connect():
    print("Client connected")

logs = [
    {"task_id": 5266, "from": 5, "to": 6, "date": "25/1/25", "time": "4:15"},
    {"task_id": 6519, "from": 8, "to": 6, "date": "14/1/25", "time": "21:15"},
    {"task_id": 5652, "from": 1, "to": 2, "date": "31/12/24", "time": "-"},
    {"task_id": 5266, "from": 5, "to": 9, "date": "12/12/24", "time": "23:22"},
    {"task_id": 6519, "from": 3, "to": 6, "date": "15/8/24", "time": "-"},
    {"task_id": 5652, "from": 5, "to": 6, "date": "16/8/24", "time": "15:15"}
]

@app.route('/')
def home():
    return render_template('Tellerloop.html')  # Load the Tellerloop page

@app.route('/<int:page_id>', methods=['GET', 'POST'])
def handle_page(page_id):
    return render_template('Tellerloop.html', page_id=page_id)

@app.route('/api/get_client_ip')
def get_client_ip():
    return jsonify({'ip': request.remote_addr})

@app.route('/api/check_ip', methods=['GET'])
def check_ip():
    user_ip = request.remote_addr
    # Check if the client IP is one of the allowed IPs (values in ALLOWED_IPS)
    is_allowed = user_ip in ALLOWED_IPS.values()
    return jsonify({'is_allowed': is_allowed})

@app.route('/api/network_architecture')
def get_network_architecture():
    try:
        directory = os.path.dirname(__file__)
        json_files = glob.glob(os.path.join(directory, "network_architecture*.json"))
        
        if not json_files:
            return jsonify({'error': 'No architecture files found'}), 404
        
        latest_file = max(json_files, key=os.path.getmtime)
        with open(latest_file, 'r') as json_file:
            data = json.load(json_file)
         # Debug: Check keys present in the JSON file
        print("Loaded JSON data keys:", data.keys())
        
        # Process the components from the JSON file
        components = data.get('components', [])
        print(f"Found {len(components)} components in JSON file.")
        db = get_db()
        
        for component in components:
            comp_type = component.get('type')  # Use the correct key for type
            comp_id = component.get('id')        # Use the correct key for id
            print(f"Component details: type={comp_type}, id={comp_id}")
            
            if comp_type in ['passthrough-station', 'bottom-loading-station']:
                if comp_id:
                    table_name = f"component_{comp_id}"
                    print(f"Creating table for component id: {comp_id}, table name: {table_name}")
                    db.execute(f'''
                        CREATE TABLE IF NOT EXISTS "{table_name}" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            positional_sensor_1 BOOLEAN NOT NULL,
                            positional_sensor_2 BOOLEAN NOT NULL,
                            positional_sensor_3 BOOLEAN NOT NULL,
                            positional_sensor_4 BOOLEAN NOT NULL,
                            positional_sensor_5 BOOLEAN NOT NULL,
                            positional_sensor_6 BOOLEAN NOT NULL,
                            positional_sensor_7 BOOLEAN NOT NULL,
                            positional_sensor_8 BOOLEAN NOT NULL
                        )
                    ''')
                else:
                    print("Skipping component due to missing id.")
            else:
                print("Skipping component due to type mismatch.")
        db.commit()
        print("Component tables creation committed.")
        
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Network architecture file not found'}), 404
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format in network architecture file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_logs')
def get_logs():
    return jsonify(logs)

@app.route('/get_page_url')
def get_page_url():
    # for getting client IP address
    client_ip = request.remote_addr
    
    # Look up for the page ID for the IP corresponding...
    page_id = RPI_IP_TO_PAGE_ID.get(client_ip)
    
    if page_id is None:
        return jsonify({'status': 'error', 'message': 'Unknown Raspberry Pi IP address'}), 404
    
    # Get server host for constructing full URL
    server_host = request.host.split(':')[0]  # Remove port if present
    server_port = request.host.split(':')[1] if ':' in request.host else '5000'
    
    # Construct the URL for this Raspberry Pi
    url = f"http://{server_host}:{server_port}/{page_id}"
    
    return jsonify({
        'status': 'success',
        'page_id': page_id,
        'url': url,
        'ip': client_ip
    })

@mqtt.on_connect()
def handle_mqtt_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    mqtt.subscribe(mqtt_topic1, 1)

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    try:
        data = message.payload.decode()
        topic = message.topic
        if topic.startswith('PTS/SENSORDATA/'):
            page_id = topic.split('/')[-1]
            socketio.emit('mqtt_message', {'data': data}, room=str(page_id))
    except Exception as e:
        print(f"MQTT message error: {e}")

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)  # Allow access from other devices