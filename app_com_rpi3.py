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
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Broker')

# Global variables for tracking
heartbeat_threads = {}
connected_stations = {}  # username -> ip
station_sids = {}  # username -> sid
sid_stations = {}  # sid -> username
station_heartbeats = defaultdict(float) 
HEARTBEAT_TIMEOUT = 30 
system_status = False 

# Priority Queue for dispatches
normal_queue = deque()
high_priority_queue = deque()
dispatch_in_progress = False
current_dispatch = None

# Define allowed stations (name: IP)
ALLOWED_IPS = {
    'passthrough-station-1': '192.168.90.3',
    'passthrough-station-2': '192.168.90.6',
    'passthrough-station-3': '192.168.90.8',
    'passthrough-station-4': '192.168.43.200'
}
# Map station names to their IDs for easier reference
STATION_IDS = {
    'passthrough-station-1': 1,
    'passthrough-station-2': 2,
    'passthrough-station-3': 3,
    'passthrough-station-4': 4
}

# Reverse mapping for IP to station name lookup
IP_TO_STATION = {ip: name for name, ip in ALLOWED_IPS.items()}

# MQTT Configuration
mqtt_broker_ip = "test.mosquitto.org"
mqtt_username = None
mqtt_password = None

# MQTT Topics
mqtt_topic_base = 'PTS/'
mqtt_sensor_data_topic = mqtt_topic_base + 'SENSORDATA/'
mqtt_dispatch_topic = mqtt_topic_base + 'DISPATCH/'
mqtt_status_topic = mqtt_topic_base + 'STATUS/'
mqtt_priority_topic = mqtt_topic_base + 'PRIORITY/'
mqtt_ack_topic = mqtt_topic_base + 'ACK/'
mqtt_script_topic = mqtt_topic_base + 'SCRIPT/'
mqtt_script_result_topic = mqtt_topic_base + 'SCRIPT_RESULT/'  # New topic for script results
mqtt_empty_pod_request_topic = mqtt_topic_base + 'EMPTY_POD_REQUEST/'  # New topic
mqtt_empty_pod_accepted_topic = mqtt_topic_base + 'EMPTY_POD_ACCEPTED/'


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

app.config['SYSTEM_STATUS'] = False

mqtt = Mqtt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DATABASE = 'lan_monitoring.db'

# Subscribe to MQTT topics
@mqtt.on_connect()
def handle_mqtt_connect(client, userdata, flags, rc):
    logger.info(f"Connected to MQTT broker with result code: {rc}")
    # Subscribe to all our topics
    mqtt.subscribe(mqtt_sensor_data_topic + '#', 1)
    mqtt.subscribe(mqtt_dispatch_topic + '#', 1)
    mqtt.subscribe(mqtt_status_topic + '#', 1)
    mqtt.subscribe(mqtt_priority_topic + '#', 1)
    mqtt.subscribe(mqtt_ack_topic + '#', 1)
    mqtt.subscribe(mqtt_script_topic + '#', 1)
    mqtt.subscribe(mqtt_script_result_topic + '#', 1)
    mqtt.subscribe(mqtt_empty_pod_request_topic + '#', 1)
    mqtt.subscribe(mqtt_empty_pod_accepted_topic + '#', 1)
    logger.info("Subscribed to all MQTT topics")

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
                       priority TEXT NOT NULL,
                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                       status TEXT DEFAULT 'pending',
                       execution_details TEXT
                       )''')

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

        db.execute('''CREATE TABLE IF NOT EXISTS script_executions
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       station_id TEXT NOT NULL,
                       script_name TEXT NOT NULL,
                       parameters TEXT,
                       execution_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                       status TEXT,
                       output TEXT
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
    global dispatch_in_progress
    app.config['SYSTEM_STATUS'] = True
    
    logger.info(f"Executing dispatch: from {from_id} to {to_id} with {priority} priority")
    
    # Store in database
    db = get_db()
    cursor = db.execute(
        'INSERT INTO history (sender, receiver, priority, status) VALUES (?, ?, ?, ?)',
        (from_id, to_id, priority, 'in_progress')
    )
    task_id = cursor.lastrowid
    db.commit()
    
    # Add task_id to dispatch data
    dispatch_data['task_id'] = task_id
    
    # Publish to MQTT
    dispatch_message = json.dumps({
        'task_id': task_id,
        'from': from_id,
        'to': to_id,
        'priority': priority,
        'timestamp': time.time()
    })
    mqtt.publish(f"{mqtt_dispatch_topic}{from_id}/{to_id}", dispatch_message)
    
    # Determine station names from IDs
    from_station = None
    to_station = None
    for name, station_id in STATION_IDS.items():
        if station_id == from_id:
            from_station = name
        if station_id == to_id:
            to_station = name
    
    # Send script execution commands to both stations using inching_cs.py
    if from_station and to_station:
        # Sender script parameters
        sender_params = {
            'mode': 'send',
            'destination': to_id,
            'task_id': task_id,
            'priority': priority
        }
        sender_script_msg = json.dumps({
            'script': 'inching.py',  # Changed from dispatch_handler.py
            'params': sender_params,
            'task_id': task_id
        })
        mqtt.publish(f"{mqtt_script_topic}{from_station}", sender_script_msg)
        logger.info(f"Sent inching command to sender station {from_station}")
        
        # Receiver script parameters
        receiver_params = {
            'mode': 'receive',
            'source': from_id,
            'task_id': task_id,
            'priority': priority
        }
        receiver_script_msg = json.dumps({
            'script': 'inching.py',  # Changed from dispatch_handler.py
            'params': receiver_params,
            'task_id': task_id
        })
        mqtt.publish(f"{mqtt_script_topic}{to_station}", receiver_script_msg)
        logger.info(f"Sent inching command to receiver station {to_station}")
    else:
        logger.error(f"Could not find station names for IDs: from={from_id}, to={to_id}")
    
    # Update status for all stations
    for i in range(1, 5):  # Assuming stations 1 to 4
        if i == from_id:
            status = {'status': 'sending', 'destination': to_id, 'task_id': task_id}
        elif i == to_id:
            status = {'status': 'receiving', 'source': from_id, 'task_id': task_id}
        else:
            status = {'status': 'standby'}
        
        status_message = json.dumps(status)
        mqtt.publish(f"{mqtt_status_topic}{i}", status_message)
        socketio.emit('status', status, room=str(i))

@socketio.on('dispatch_completed')
def handle_dispatch_completed(data):
    global dispatch_in_progress, current_dispatch
    
    if dispatch_in_progress and current_dispatch:
        task_id = current_dispatch.get('task_id')
        from_id = current_dispatch['from']
        to_id = current_dispatch['to']
        
        logger.info(f"Dispatch completed: Task ID: {task_id}, from {from_id} to {to_id}")
        
        app.config['SYSTEM_STATUS'] = False
        
        # Update task status in database
        db = get_db()
        db.execute(
            'UPDATE history SET status = ? WHERE task_id = ?',
            ('completed', task_id)
        )
        db.commit()
        
        # Reset dispatch state
        dispatch_in_progress = False
        current_dispatch = None
        
        # Process next dispatch if any
        process_next_dispatch()
        
        # Update status for all stations
        for i in range(1, 5):  # Assuming stations 1 to 4
            status = {'status': 'standby'}
            status_message = json.dumps(status)
            mqtt.publish(f"{mqtt_status_topic}{i}", status_message)
            
            # Also emit via Socket.IO for browser clients
            socketio.emit('status', status, room=str(i))

@socketio.on('script_result')
def handle_script_result(data):
    station = data.get('station')
    task_id = data.get('task_id')
    script = data.get('script')
    result = data.get('result')
    
    logger.info(f"Script execution result from {station}: Task ID: {task_id}, Script: {script}, Result: {result}")
    
    # Store result in database
    db = get_db()
    db.execute(
        'INSERT INTO script_executions (station_id, script_name, parameters, status, output) VALUES (?, ?, ?, ?, ?)',
        (station, script, json.dumps(data.get('params', {})), 'completed', result)
    )
    db.commit()
    
    # Check if this is a dispatch completion notification
    if script == 'dispatch_handler.py' and result == 'success':
        # If both sender and receiver have completed, mark the dispatch as completed
        if task_id and task_id == current_dispatch.get('task_id'):
            handle_dispatch_completed({'task_id': task_id})

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
            logger.info(f"{username} with IP {ip} joined room {username}.")
        else:
            logger.warning(f"Unauthorized join attempt: {username} with IP {ip}")
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
        logger.info(f"Joined room (page ID): {page_id}")

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
    logger.info(f"Client connected: {request.sid}")

@socketio.on('dispatch')
def handle_dispatch(data):
    from_id = int(data['from'])
    to_id = int(data['to'])
    priority = data.get('priority', 'low')
    
    logger.info(f"Dispatch request: from {from_id} to {to_id} with {priority} priority")
    
    # Create dispatch data
    dispatch_data = {
        'from': from_id,
        'to': to_id,
        'priority': priority,
        'timestamp': time.time()
    }
    
    # Add to appropriate queue
    if priority.lower() == 'high':
        high_priority_queue.append(dispatch_data)
        logger.info(f"Added to high priority queue. Queue length: {len(high_priority_queue)}")
    else:
        normal_queue.append(dispatch_data)
        logger.info(f"Added to normal queue. Queue length: {len(normal_queue)}")
    
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
    """Handle sensor data from Socket.IO connections"""
    if not data.get('station_id'):
        logger.error("Sensor data missing station_id")
        return
    
    # Convert to MQTT message format and process
    mqtt_message = json.dumps(data)
    handle_sensor_data_message(f"{mqtt_sensor_data_topic}{data['station_id']}", mqtt_message)

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
        
def handle_sensor_data_message(topic, data):
    """Process incoming sensor data from MQTT"""
    try:
        # Get station ID from topic (last segment)
        station_id = topic.split('/')[-1]
        
        try:
            sensor_data = json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON sensor data from {station_id}: {data}")
            return

        # Validate required fields
        if not isinstance(sensor_data, dict) or 'station_id' not in sensor_data:
            logger.error(f"Invalid sensor data format from {station_id}")
            return

        # Store in database
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
        
        # Forward to Socket.IO clients
        socketio.emit('sensor_update', {
            'station_id': station_id,
            'data': sensor_data
        }, room=station_id)
        
        logger.info(f"Processed sensor data from {station_id}")

    except Exception as e:
        logger.error(f"Error processing sensor data: {str(e)}")
        logger.error(f"Problematic data: {data}")

def handle_dispatch_message(topic, data):
    """Process incoming dispatch commands from MQTT"""
    try:
        # Extract route information from topic (format: PTS/DISPATCH/<from_id>/<to_id>)
        parts = topic.split('/')
        if len(parts) < 4:
            logger.error(f"Invalid dispatch topic format: {topic}")
            return

        from_id = parts[2]
        to_id = parts[3]
        
        try:
            dispatch_data = json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in dispatch message: {data}")
            return

        logger.info(f"Dispatch command received: {from_id} → {to_id}")
        
        # Forward to appropriate station rooms via Socket.IO
        socketio.emit('dispatch_command', {
            'from': from_id,
            'to': to_id,
            'data': dispatch_data
        }, room=from_id)
        
        socketio.emit('dispatch_command', {
            'from': from_id,
            'to': to_id, 
            'data': dispatch_data
        }, room=to_id)

    except Exception as e:
        logger.error(f"Error processing dispatch message: {str(e)}")
        logger.error(f"Problematic message: {data}")

def handle_status_message(topic, data):
    """Process station status updates from MQTT"""
    try:
        # Extract station ID from topic (format: PTS/STATUS/<station_id>)
        station_id = topic.split('/')[-1]
        
        try:
            status_data = json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in status message: {data}")
            return

        if 'status' not in status_data:
            logger.error(f"Missing status field in message: {data}")
            return

        logger.info(f"Status update from station {station_id}: {status_data['status']}")
        
        # Broadcast to all clients monitoring this station
        socketio.emit('station_status', {
            'station_id': station_id,
            'status': status_data
        }, room=station_id)

        # Update connected_stations tracking if this is a heartbeat
        if status_data.get('type') == 'heartbeat':
            station_name = f"passthrough-station-{station_id}"
            if station_name in connected_stations:
                station_heartbeats[station_name] = time.time()

    except Exception as e:
        logger.error(f"Error processing status message: {str(e)}")
        
def handle_priority_message(topic, data):
    """Process priority dispatch requests from MQTT"""
    try:
        # Extract route information (format: PTS/PRIORITY/<from_id>/<to_id>)
        parts = topic.split('/')
        if len(parts) < 4:
            logger.error(f"Invalid priority topic format: {topic}")
            return

        from_id = parts[2]
        to_id = parts[3]
        
        try:
            priority_data = json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in priority message: {data}")
            return

        logger.info(f"Priority request: {from_id} → {to_id} (Priority: {priority_data.get('priority')})")
        
        # Add to appropriate queue
        if priority_data.get('priority', '').lower() == 'high':
            high_priority_queue.append({
                'from': int(from_id),
                'to': int(to_id),
                'priority': 'high',
                'timestamp': time.time()
            })
        else:
            normal_queue.append({
                'from': int(from_id),
                'to': int(to_id),
                'priority': 'normal',
                'timestamp': time.time()
            })

        # Notify the requesting station
        socketio.emit('priority_ack', {
            'from': from_id,
            'to': to_id,
            'queue_position': len(high_priority_queue if priority_data.get('priority', '').lower() == 'high' else normal_queue)
        }, room=from_id)

    except Exception as e:
        logger.error(f"Error processing priority message: {str(e)}")
        
def handle_ack_message(topic, data):
    """Process acknowledgment messages from MQTT"""
    try:
        # Extract station ID from topic (format: PTS/ACK/<station_id>)
        station_id = topic.split('/')[-1]
        
        try:
            ack_data = json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in ack message: {data}")
            return

        logger.info(f"Acknowledgment from station {station_id}: {ack_data.get('type', 'unknown')}")
        
        # Handle different acknowledgment types
        ack_type = ack_data.get('type')
        if ack_type == 'dispatch_received':
            socketio.emit('dispatch_ack', {
                'station_id': station_id,
                'task_id': ack_data.get('task_id')
            }, room=ack_data.get('from_station'))
            
        elif ack_type == 'empty_pod_received':
            socketio.emit('empty_pod_ack', {
                'provider': station_id,
                'requester': ack_data.get('requester')
            }, broadcast=True)

    except Exception as e:
        logger.error(f"Error processing ack message: {str(e)}")

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    try:
        data = message.payload.decode()
        topic = message.topic
        logger.info(f"MQTT message received: {topic} -> {data}")
        
        # Handle different types of messages based on topic
        if topic.startswith(mqtt_sensor_data_topic):
            handle_sensor_data_message(topic, data)
        elif topic.startswith(mqtt_dispatch_topic):
            handle_dispatch_message(topic, data)
        elif topic.startswith(mqtt_status_topic):
            handle_status_message(topic, data)
        elif topic.startswith(mqtt_priority_topic):
            handle_priority_message(topic, data)
        elif topic.startswith(mqtt_ack_topic):
            handle_ack_message(topic, data)
        elif topic.startswith(mqtt_script_result_topic):
            handle_script_result_message(topic, data)
        elif topic.startswith(mqtt_empty_pod_request_topic):
            handle_empty_pod_request(topic, data)
        elif topic.startswith(mqtt_empty_pod_accepted_topic):
            handle_empty_pod_accepted(topic, data)
            
    except Exception as e:
        logger.error(f"MQTT message processing error: {e}") 

def handle_script_result_message(topic, data):
    """Handle script execution results from stations"""
    try:
        result_data = json.loads(data)
        station = topic.split('/')[-1]
        logger.info(f"Script result from {station}: {result_data}")
        
        # Store result in database
        db = get_db()
        db.execute(
            'INSERT INTO script_executions (station_id, script_name, parameters, status, output) VALUES (?, ?, ?, ?, ?)',
            (station, result_data.get('script'), 
             json.dumps(result_data.get('params', {})),
             result_data.get('result', 'unknown'),
             result_data.get('output', ''))
        )
        db.commit()
        
        # Check if this is a dispatch completion notification
        if result_data.get('script') == 'inching.py' and result_data.get('result') == 'success':
            task_id = result_data.get('task_id')
            if task_id and task_id == current_dispatch.get('task_id'):
                handle_dispatch_completed({'task_id': task_id})
                
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in script result: {data}")

def handle_empty_pod_request(topic, data):
    """Handle empty pod requests"""
    try:
        request_data = json.loads(data)
        requester = request_data.get('requesterStation')
        logger.info(f"Empty pod request from {requester}")
        
        # Broadcast to all stations via Socket.IO
        socketio.emit('empty_pod_request', request_data, broadcast=True)
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in empty pod request: {data}")

def handle_empty_pod_accepted(topic, data):
    """Handle empty pod acceptance"""
    try:
        accept_data = json.loads(data)
        logger.info(f"Empty pod request accepted: {accept_data}")
        
        # Broadcast to all stations via Socket.IO
        socketio.emit('empty_pod_request_accepted', accept_data, broadcast=True)
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in empty pod acceptance: {data}")

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
                            S1 BOOLEAN NOT NULL,
                            S2 BOOLEAN NOT NULL,
                            S3 BOOLEAN NOT NULL,
                            S4 BOOLEAN NOT NULL,
                            P1 BOOLEAN NOT NULL,
                            P2 BOOLEAN NOT NULL,
                            P3 BOOLEAN NOT NULL,
                            P4 BOOLEAN NOT NULL
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

@app.route('/api/get_sensor_data/<station_id>')
def get_sensor_data(station_id):
    """API endpoint to retrieve historical sensor data"""
    db = get_db()
    rows = db.execute(
        'SELECT * FROM sensor_data WHERE station_id = ? ORDER BY timestamp DESC LIMIT 100',
        (station_id,)
    ).fetchall()
    
    return jsonify([
        {**dict(row), 'timestamp': row['timestamp']}  # Convert SQLite Row to dict
        for row in rows
    ])
    
@app.route('/get_logs')
def get_logs():
    try:
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
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({'error': 'Failed to retrieve logs'}), 500

def drop_all_tables():
    try:
        conn = sqlite3.connect(DATABASE)
        cur = conn.cursor()
        
        # Retrieve the list of all user-defined tables in the database
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
        
        for table in tables:
            table_name = table[0]
            # Skip SQLite's internal tables (e.g., sqlite_sequence)
            if table_name.startswith('sqlite_'):
                logger.info(f"Skipping internal table: {table_name}")
                continue
            logger.info(f"Dropping table: {table_name}")
            cur.execute(f"DROP TABLE IF EXISTS '{table_name}'")
        
        conn.commit()
        conn.close()
        
        logger.info("All user-defined tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        raise

@app.route('/api/clear_history', methods=['DELETE'])
def clear_history():
    try:
        # Drop all existing tables
        drop_all_tables()
        
        # Reinitialize the database
        init_db()
        
        # Find the latest network architecture JSON
        directory = os.path.dirname(__file__)
        json_files = glob.glob(os.path.join(directory, "network_architecture*.json"))
        
        if not json_files:
            logger.warning("No network architecture files found")
            return jsonify({'error': 'No architecture files found'}), 404
        
        # Get the most recently modified JSON file
        latest_file = max(json_files, key=os.path.getmtime)
        
        # Load the JSON data
        with open(latest_file, 'r') as json_file:
            data = json.load(json_file)
        
        logger.info(f"Loaded network architecture from {latest_file}")
        logger.info(f"Loaded JSON data keys: {data.keys()}")
        
        # Process components from the JSON file
        components = data.get('components', [])
        logger.info(f"Found {len(components)} components in JSON file")
        
        db = get_db()
        
        for component in components:
            comp_type = component.get('type')
            comp_id = component.get('id')
            
            logger.info(f"Processing component: type={comp_type}, id={comp_id}")
            
            # Create tables only for specific component types
            if comp_type in ['passthrough-station', 'bottom-loading-station']:
                if comp_id:
                    table_name = f"component_{comp_id}"
                    logger.info(f"Creating table for component: {table_name}")
                    
                    db.execute(f'''
                        CREATE TABLE IF NOT EXISTS "{table_name}" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            S1 BOOLEAN NOT NULL,
                            S2 BOOLEAN NOT NULL,
                            S3 BOOLEAN NOT NULL,
                            S4 BOOLEAN NOT NULL,
                            P1 BOOLEAN NOT NULL,
                            P2 BOOLEAN NOT NULL,
                            P3 BOOLEAN NOT NULL,
                            P4 BOOLEAN NOT NULL
                        )
                    ''')
                else:
                    logger.warning("Skipping component due to missing id")
            else:
                logger.info(f"Skipping component type: {comp_type}")
        
        db.commit()
        logger.info("Component tables creation committed")
        
        return jsonify({
            'status': 'success', 
            'message': 'History cleared and reinitialized.',
            'components_processed': len(components)
        }), 200
    
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return jsonify({
            'status': 'error', 
            'message': f'Failed to clear history: {str(e)}'
        }), 500

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
        logger.error(f"Error fetching live tracking data: {e}")
        return jsonify({
            'system_status': app.config['SYSTEM_STATUS'],
            'sender': None,
            'receiver': None,
            'task_id': None
        })

@app.route('/api/get_current_station', methods=['GET'])
def get_current_station():
    user_ip = request.remote_addr
   
    # Use the existing ALLOWED_IPS dictionary for mapping
    station = IP_TO_STATION.get(user_ip, 'Unknown')
    return jsonify({
        'station': station,
        'ip': user_ip
    })

# SocketIO events for empty pod requests
@socketio.on('request_empty_pod')
def handle_empty_pod_request(data):
    # Broadcast empty pod request to all other stations
    requester_station = data.get('requesterStation', 'Unknown')
    emit('empty_pod_request', data, broadcast=True, include_self=False)

    request_message = json.dumps(data)
    mqtt.publish(f"{mqtt_topic_base}EMPTY_POD_REQUEST/{requester_station}", request_message)

    logger.info(f"Empty pod request from {requester_station}")

@socketio.on('empty_pod_request_accepted')
def handle_empty_pod_request_accepted(data):
    # Broadcast acceptance to all stations
    emit('empty_pod_request_accepted', data, broadcast=True)

    acceptance_message = json.dumps(data)
    mqtt.publish(f"{mqtt_topic_base}EMPTY_POD_ACCEPTED/{data.get('requesterStation', 'Unknown')}", acceptance_message)
    logger.info(f"Empty pod request accepted: {data}")

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)  