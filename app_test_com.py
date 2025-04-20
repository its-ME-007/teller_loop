from flask import Flask, render_template, jsonify, request, abort, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_cors import CORS
from flask_mqtt import Mqtt
import sqlite3
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os, glob
import threading
import time
from collections import defaultdict, deque
import random

# Global variables for tracking
heartbeat_threads = {}
connected_stations = {}  # username -> ip
station_sids = {}  # username -> sid
sid_stations = {}  # sid -> username
station_heartbeats = defaultdict(float) 
HEARTBEAT_TIMEOUT = 30 
system_status = False  # Global variable for system status

# Priority Queue for dispatches
normal_queue = deque()
high_priority_queue = deque()
dispatch_in_progress = False
current_dispatch = None

# Define allowed stations (name: IP)
ALLOWED_IPS = {
    'passthrough-station-1': '192.168.43.231',
    'passthrough-station-2': '192.168.43.189',
    'passthrough-station-3': '192.168.43.41',
    'passthrough-station-4': '192.168.43.200'
}


# MQTT Configuration
mqtt_broker_ip = "test.mosquitto.org"
'''"test.mosquitto.org     broker.hivemq.com"'''
mqtt_username = None
mqtt_password = None

# MQTT Topics
mqtt_topic_base = 'PTS/'
mqtt_sensor_data_topic = mqtt_topic_base + 'SENSORDATA/'
mqtt_dispatch_topic = mqtt_topic_base + 'DISPATCH/'
mqtt_status_topic = mqtt_topic_base + 'STATUS/'
mqtt_priority_topic = mqtt_topic_base + 'PRIORITY/'
mqtt_ack_topic = mqtt_topic_base + 'ACK/'

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
app.config['SYSTEM_STATUS'] = False  # Store system status in app config for global access

mqtt = Mqtt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DATABASE = 'lan_monitoring.db'

# Subscribe to MQTT topics
@mqtt.on_connect()
def handle_mqtt_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code: {rc}")
    # Subscribe to all our topics
    mqtt.subscribe(mqtt_sensor_data_topic, 1)
    mqtt.subscribe(mqtt_dispatch_topic, 1)
    mqtt.subscribe(mqtt_status_topic, 1)
    mqtt.subscribe(mqtt_priority_topic, 1)
    mqtt.subscribe(mqtt_ack_topic, 1)
    print("Subscribed to topics:", mqtt_sensor_data_topic, mqtt_dispatch_topic, mqtt_status_topic, mqtt_priority_topic, mqtt_ack_topic)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''CREATE TABLE IF NOT EXISTS history
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       task_id TEXT,
                       sender TEXT NOT NULL,
                       receiver TEXT NOT NULL,
                       priority TEXT NOT NULL,
                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

        db.execute('''CREATE TABLE IF NOT EXISTS sensor_data
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       station_id TEXT NOT NULL,
                       sensor_1 BOOLEAN,
                       sensor_2 BOOLEAN,
                       sensor_3 BOOLEAN,
                       sensor_4 BOOLEAN,
                       sensor_5 BOOLEAN,
                       sensor_6 BOOLEAN,
                       sensor_7 BOOLEAN,
                       sensor_8 BOOLEAN,
                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                       )''')
        
        db.commit()

def process_next_dispatch():
    global dispatch_in_progress, current_dispatch
    
    if dispatch_in_progress:
        return
    
    if high_priority_queue:
        dispatch_data = high_priority_queue.popleft()
        dispatch_in_progress = True
        current_dispatch = dispatch_data
        execute_dispatch(dispatch_data)
    elif normal_queue:
        dispatch_data = normal_queue.popleft()
        dispatch_in_progress = True
        current_dispatch = dispatch_data
        execute_dispatch(dispatch_data)

def execute_dispatch(dispatch_data):
    from_id = dispatch_data['from']
    to_id = dispatch_data['to']
    priority = dispatch_data['priority']
    
    print(f"Executing dispatch: from {from_id} to {to_id} with {priority} priority")
    
    # Store in database
    db = get_db()
    db.execute(
        'INSERT INTO history (sender, receiver, priority) VALUES (?, ?, ?)',
        (from_id, to_id, priority)
    )
    db.commit()
    
    # Publish to MQTT
    dispatch_message = json.dumps({
        'from': from_id,
        'to': to_id,
        'priority': priority,
        'timestamp': time.time()
    })
    mqtt.publish(f"{mqtt_dispatch_topic}{from_id}/{to_id}", dispatch_message)
    
    # Update status for all stations
    for i in range(1, 5):  # Assuming stations 1 to 4
        if i == from_id:
            status = {'status': 'sending', 'destination': to_id}
        elif i == to_id:
            status = {'status': 'receiving', 'source': from_id}
        else:
            status = {'status': 'standby'}
        
        status_message = json.dumps(status)
        mqtt.publish(f"{mqtt_status_topic}{i}", status_message)
        
        # Also emit via Socket.IO for browser clients
        emit('status', status, room=str(i))

@socketio.on('dispatch_completed')
def handle_dispatch_completed(data):
    global dispatch_in_progress, current_dispatch, system_status
    
    if dispatch_in_progress and current_dispatch:
        from_id = current_dispatch['from']
        to_id = current_dispatch['to']
        
        print(f"Dispatch completed: from {from_id} to {to_id}")
        
        # Reset dispatch state and system status
        dispatch_in_progress = False
        current_dispatch = None
        system_status = False
        app.config['SYSTEM_STATUS'] = False
        
        # Notify all clients about the status change
        print(f"Broadcasting system_status_changed event with status=False")
        socketio.emit('system_status_changed', {'status': False}, include_self=True)
        
        # Process next dispatch if any
        process_next_dispatch()
        
        # Update status for all stations
        for i in range(1, 5):  # Assuming stations 1 to 4
            status = {'status': 'standby'}
            status_message = json.dumps(status)
            mqtt.publish(f"{mqtt_status_topic}{i}", status_message)
            
            # Also emit via Socket.IO for browser clients
            emit('status', status, room=str(i))
    elif data.get('aborted'):
        # Handle manual abort
        print("Dispatch aborted manually")

        # Update the last entry in the history table to set task_id to "Aborted"
        db = get_db()
        last_entry = db.execute('SELECT * FROM history ORDER BY timestamp DESC LIMIT 1').fetchone()
        
        if last_entry:
            # Update the task_id of the last entry
            db.execute('UPDATE history SET task_id = ? WHERE id = ?', ("Aborted", last_entry['id']))
            db.commit()
            print(f"Updated task_id of the last entry to 'Aborted': {last_entry['id']}")

        dispatch_in_progress = False
        current_dispatch = None
        system_status = False
        app.config['SYSTEM_STATUS'] = False
        
        # Notify all clients about the status change
        print(f"Broadcasting system_status_changed event with status=False for abort")
        socketio.emit('system_status_changed', {'status': False}, include_self=True)

@socketio.on('join')
def handle_join(data):
    # Handle both formats of join data
    if isinstance(data, dict) and 'username' in data:
        # Original station join format
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
        
        # Publish station online status to MQTT
        status_message = json.dumps({
            'station': username,
            'status': 'online',
            'ip': ip,
            'timestamp': time.time()
        })
        mqtt.publish(f"{mqtt_status_topic}{username.split('-')[-1]}", status_message)
    else:
        # New page_id based join format
        page_id = str(data)
        join_room(page_id)
        print(f"Joined room (page ID): {page_id}")

@socketio.on('hello_packet')
def handle_hello_packet(data):
    sender = data['node']
    if sender in connected_stations:
        # Broadcast hello packet to all other stations
        emit('hello_packet', data, broadcast=True, include_self=False)
        
        # Also publish to MQTT
        hello_message = json.dumps(data)
        mqtt.publish(f"{mqtt_topic_base}HELLO/{sender}", hello_message)

@socketio.on('hello_ack')
def handle_hello_ack(data):
    sender = data['sender']
    receiver = data['receiver']
    if sender in connected_stations and receiver in connected_stations:
        # Forward acknowledgment to the specific receiver (using room targeting)
        receiver_sid = station_sids.get(receiver)
        if receiver_sid:
            emit('hello_ack', data, room=receiver_sid)
            
        # Also publish to MQTT
        ack_message = json.dumps(data)
        mqtt.publish(f"{mqtt_ack_topic}{receiver}", ack_message)

@socketio.on('heartbeat')
def handle_heartbeat(data):
    username = data['node']
    timestamp = data['timestamp']
    if username in connected_stations:
        station_heartbeats[username] = timestamp
        # Broadcast heartbeat to all other stations
        emit('heartbeat', data, broadcast=True, include_self=False)
        
        # Also publish to MQTT for logging
        heartbeat_message = json.dumps(data)
        mqtt.publish(f"{mqtt_topic_base}HEARTBEAT/{username}", heartbeat_message)

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('dispatch')
def handle_dispatch(data):
    global system_status
    # Check if system is already dispatching
    if app.config['SYSTEM_STATUS']:
        emit('dispatch_rejected', {
            'reason': 'System is already dispatching. Please wait until the current dispatch completes.'
        })
        return
    
    from_id = data['from']
    to_id = data['to']
    # from_id = int(data['from']) working one
    # to_id = int(data['to'])
    priority = data['priority']
    
    print(f"Dispatch request: from {from_id} to {to_id} with {priority} priority")
    
    # Generate task_id in format: random6digit/MM/YYYY
    random_id = random.randint(100000, 999999)  # Generate a 6-digit number
    current_month_year = datetime.now().strftime("%m/%Y")  # Format MM/YYYY
    task_id = f"{random_id}/{current_month_year}"

    # Create dispatch data
    dispatch_data = {
        'task_id': task_id,
        'from': from_id,
        'to': to_id,
        'priority': priority,
        'timestamp': time.time()
    }

    # Insert into history table
    db = get_db()
    db.execute(
        '''INSERT INTO history (task_id, sender, receiver, priority, timestamp)
           VALUES (?, ?, ?, ?, ?)''',
        (task_id, from_id, to_id, priority, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    
    # Add to appropriate queue
    if priority.lower() == 'high':
        high_priority_queue.append(dispatch_data)
        print(f"Added to high priority queue. Queue length: {len(high_priority_queue)}")
    else:
        normal_queue.append(dispatch_data)
        print(f"Added to normal queue. Queue length: {len(normal_queue)}")
    
    # Set system status to true when dispatch is initiated
    system_status = True
    app.config['SYSTEM_STATUS'] = True
    
    # Notify all clients about the dispatch status
    print(f"Broadcasting system_status_changed event with status=True")
    socketio.emit('system_status_changed', {'status': True}, include_self=True)
    
    # Publish to MQTT
    dispatch_request = json.dumps(dispatch_data)
    mqtt.publish(f"{mqtt_priority_topic}{from_id}/{to_id}", dispatch_request)
    
    # Process next dispatch if none is in progress
    if not dispatch_in_progress:
        process_next_dispatch()
    else:
        # Inform the client that the dispatch is queued
        emit('dispatch_queued', {
            'from': from_id,
            'to': to_id,
            'position': len(high_priority_queue) if priority.lower() == 'high' else len(normal_queue)
        }, room=str(from_id))

@socketio.on('sensor_data')
def handle_sensor_data(data):
    station_id = data.get('station_id')
    
    if not station_id:
        print("Error: No station ID provided in sensor data")
        return
    
    # Store sensor data in database
    db = get_db()
    db.execute(
        '''INSERT INTO sensor_data 
           (station_id, sensor_1, sensor_2, sensor_3, sensor_4, 
            sensor_5, sensor_6, sensor_7, sensor_8) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            station_id,
            data.get('sensor_1', False),
            data.get('sensor_2', False),
            data.get('sensor_3', False),
            data.get('sensor_4', False),
            data.get('sensor_5', False),
            data.get('sensor_6', False),
            data.get('sensor_7', False),
            data.get('sensor_8', False)
        )
    )
    db.commit()
    
    # Publish to MQTT
    sensor_message = json.dumps(data)
    mqtt.publish(f"{mqtt_sensor_data_topic}{station_id}", sensor_message)
    
    # Log to console
    print(f"Sensor data received from station {station_id}: {data}")

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
            
            # Publish station offline status to MQTT
            status_message = json.dumps({
                'station': username,
                'status': 'offline',
                'timestamp': time.time()
            })
            station_num = username.split('-')[-1]
            mqtt.publish(f"{mqtt_status_topic}{station_num}", status_message)

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")
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
        
        # Publish station offline status to MQTT
        status_message = json.dumps({
            'station': username,
            'status': 'offline',
            'timestamp': time.time()
        })
        station_num = username.split('-')[-1]
        mqtt.publish(f"{mqtt_status_topic}{station_num}", status_message)

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    try:
        data = message.payload.decode()
        topic = message.topic
        print(f"MQTT message received: {topic} -> {data}")
        
        # Handle different types of messages based on topic
        if topic.startswith('PTS/SENSORDATA/'):
            # Get station ID from topic
            station_id = topic.split('/')[-1]
            # For Socket.IO clients
            socketio.emit('mqtt_message', {'topic': topic, 'data': data}, room=str(station_id))
            
            # Log to console for debugging
            print(f"Sensor data from station {station_id}: {data}")
            
            # Store to database if it's valid JSON
            try:
                sensor_data = json.loads(data)
                if isinstance(sensor_data, dict):
                    db = get_db()
                    db.execute(
                        '''INSERT INTO sensor_data 
                           (station_id, sensor_1, sensor_2, sensor_3, sensor_4, 
                            sensor_5, sensor_6, sensor_7, sensor_8) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            station_id,
                            sensor_data.get('sensor_1', False),
                            sensor_data.get('sensor_2', False),
                            sensor_data.get('sensor_3', False),
                            sensor_data.get('sensor_4', False),
                            sensor_data.get('sensor_5', False),
                            sensor_data.get('sensor_6', False),
                            sensor_data.get('sensor_7', False),
                            sensor_data.get('sensor_8', False)
                        )
                    )
                    db.commit()
            except json.JSONDecodeError:
                print(f"Invalid JSON format in sensor data: {data}")
                
        elif topic.startswith('PTS/DISPATCH/'):
            # Extract from and to IDs from topic
            parts = topic.split('/')
            if len(parts) >= 4:
                from_id = parts[2]
                to_id = parts[3]
                
                # Forward to SocketIO clients
                socketio.emit('dispatch_event', {'from': from_id, 'to': to_id, 'data': data})
                
                # Log the dispatch
                print(f"Dispatch from {from_id} to {to_id}: {data}")
                
        elif topic.startswith('PTS/STATUS/'):
            # Extract station ID from topic
            station_id = topic.split('/')[-1]
            
            # Forward to SocketIO clients
            socketio.emit('station_status', {'station': station_id, 'data': data}, room=str(station_id))
            
            # Log the status update
            print(f"Status update for station {station_id}: {data}")
            
        elif topic.startswith('PTS/PRIORITY/'):
            # Extract from and to IDs from topic
            parts = topic.split('/')
            if len(parts) >= 4:
                from_id = parts[2]
                to_id = parts[3]
                
                # Log the priority update
                print(f"Priority request from {from_id} to {to_id}: {data}")
                
        elif topic.startswith('PTS/ACK/'):
            # Extract station ID from topic
            station_id = topic.split('/')[-1]
            
            # Log the acknowledgment
            print(f"Acknowledgment for station {station_id}: {data}")
            
            # Check if this is a dispatch completion acknowledgment
            try:
                ack_data = json.loads(data)
                if ack_data.get('type') == 'dispatch_completed':
                    handle_dispatch_completed(ack_data)
            except json.JSONDecodeError:
                print(f"Invalid JSON format in acknowledgment: {data}")
                
    except Exception as e:
        print(f"MQTT message processing error: {e}")

# Generate random sensor data for testing
def generate_random_sensor_data(station_id):
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

# Test function to publish random sensor data
def test_publish_sensor_data():
    for i in range(1, 5):  # Stations 1-4
        station_id = str(i)
        sensor_data = generate_random_sensor_data(station_id)
        data_json = json.dumps(sensor_data)
        mqtt.publish(f"{mqtt_sensor_data_topic}{station_id}", data_json)
        print(f"Published test sensor data for station {station_id}: {data_json}")

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
            comp_id = component.get('id')      # Use the correct key for id
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
    db = get_db()
    rows = db.execute(
        'SELECT * FROM history ORDER BY timestamp DESC'
    ).fetchall()
    
    # Convert to list of dictionaries
    result = []
    for row in rows:
        result.append({
            'task_id': row['task_id'],
            'from': row['sender'],
            'to': row['receiver'],
            'priority': row['priority'],
            'date': datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%y'),
            'time': datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        })
    
    return jsonify(result)

def drop_all_tables():
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    
    # Retrieve the list of all user-defined tables in the database
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    
    for table in tables:
        table_name = table[0]
        # Skip SQLite's internal tables (e.g., sqlite_sequence)
        if table_name.startswith('sqlite_'):
            print(f"Skipping internal table: {table_name}")
            continue
        print(f"Dropping table: {table_name}")
        cur.execute(f"DROP TABLE IF EXISTS '{table_name}'")
    
    conn.commit()
    conn.close()

@app.route('/api/clear_history', methods=['DELETE'])
def clear_history():
    drop_all_tables()
    init_db()
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
        comp_id = component.get('id')      # Use the correct key for id
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
    return jsonify({'status': 'success', 'message': 'History cleared and reinitialized.'}), 200

@app.route('/api/get_sensor_data/<station_id>')
def get_sensor_data(station_id):
    db = get_db()
    rows = db.execute(
        'SELECT * FROM sensor_data WHERE station_id = ? ORDER BY timestamp DESC LIMIT 50',
        (station_id,)
    ).fetchall()
    
    # Convert to list of dictionaries
    result = []
    for row in rows:
        result.append({
            'id': row['id'],
            'station_id': row['station_id'],
            'sensor_1': bool(row['sensor_1']),
            'sensor_2': bool(row['sensor_2']),
            'sensor_3': bool(row['sensor_3']),
            'sensor_4': bool(row['sensor_4']),
            'sensor_5': bool(row['sensor_5']),
            'sensor_6': bool(row['sensor_6']),
            'sensor_7': bool(row['sensor_7']),
            'sensor_8': bool(row['sensor_8']),
            'timestamp': row['timestamp']
        })
    
    return jsonify(result)

@app.route('/api/get_dispatch_history')
def get_dispatch_history():
    db = get_db()
    rows = db.execute(
        'SELECT * FROM history ORDER BY timestamp DESC LIMIT 100'
    ).fetchall()
    
    # Convert to list of dictionaries
    result = []
    for row in rows:
        result.append({
            'task_id': row['task_id'],
            'from': row['sender'],
            'to': row['receiver'],
            'priority': row['priority'],
            'date': datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%y'),
            'time': datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        })
    
    return jsonify(result)

@app.route('/api/test_sensor_data')
def test_sensor_data_endpoint():
    test_publish_sensor_data()
    return jsonify({'status': 'Test sensor data published'})

@app.route('/api/check_dispatch_allowed')
def check_dispatch_allowed():
    return jsonify({
        'allowed': not app.config['SYSTEM_STATUS'],
        'reason': 'System is already dispatching' if app.config['SYSTEM_STATUS'] else None
    })

@app.route('/api/live_tracking')
def get_live_tracking():
    try:
        db = get_db()
        # Get the most recent entry from history table
        latest_entry = db.execute(
            'SELECT * FROM history ORDER BY timestamp DESC LIMIT 1'
        ).fetchone()
        
        if latest_entry:
            return jsonify({
                'system_status': app.config['SYSTEM_STATUS'],
                'sender': latest_entry['sender'],
                'receiver': latest_entry['receiver'],
                'task_id': latest_entry['task_id']
            })
        else:
            return jsonify({
                'system_status': app.config['SYSTEM_STATUS'],
                'sender': None,
                'receiver': None,
                'task_id': None
            })
    except Exception as e:
        print(f"Error fetching live tracking data: {e}")
        return jsonify({
            'system_status': app.config['SYSTEM_STATUS'],
            'sender': None,
            'receiver': None,
            'task_id': None
        })
        
#Routes for doing the requestionf of the empty pods..
@socketio.on('request_empty_pod')
def handle_empty_pod_request(data):
    # Broadcast empty pod request to all other stations
    emit('empty_pod_request', data, broadcast=True, include_self=False)
    
    # Optional: Log the request or publish to MQTT
    request_message = json.dumps(data)
    mqtt.publish(f"{mqtt_topic_base}EMPTY_POD_REQUEST/{data['requesterStation']}", request_message)

@socketio.on('empty_pod_request_accepted')
def handle_empty_pod_request_accepted(data):
    # Broadcast acceptance to all stations
    emit('empty_pod_request_accepted', data, broadcast=True)
    
    # Optional: Log or publish to MQTT
    acceptance_message = json.dumps(data)
    mqtt.publish(f"{mqtt_topic_base}EMPTY_POD_ACCEPTED/{data['requesterStation']}", acceptance_message)

@app.route('/api/get_current_station', methods=['GET'])
def get_current_station():
    user_ip = request.remote_addr
    
    # Mapping of IPs to station names
    ip_to_station = {
        '192.168.43.231': 'passthrough-station-1',
        '192.168.43.189': 'passthrough-station-2',
        '192.168.43.41': 'passthrough-station-3',
        '192.168.43.200': 'passthrough-station-4'
    }
    
    station = ip_to_station.get(user_ip, 'Unknown')
    return jsonify({
        'station': station,
        'ip': user_ip
    })

# Testing without rpi, the communication part

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)  # Allow access from other devices