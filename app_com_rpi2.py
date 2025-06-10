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

# use sensor 5 data to check the pod's status. based on it use simple if conditions to check if a dispatch can be done or not. 

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Broker')

# Suppress Werkzeug logs
# logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Global variables for tracking
connected_stations = {}  # username -> ip
station_sids = {}  # username -> sid
sid_stations = {}  # sid -> username
station_heartbeats = defaultdict(float) 
HEARTBEAT_TIMEOUT = 30 

# Priority Queue for dispatches
normal_queue = deque()
high_priority_queue = deque()
dispatch_in_progress = False
current_dispatch = None

# Map station names to their IDs for easier reference
STATION_IDS = {
    'passthrough-station-1': 1,
    'passthrough-station-2': 2,
    'passthrough-station-3': 3,
    'passthrough-station-4': 4
}

# MQTT Configuration
mqtt_broker_ip = "192.168.90.3"  # ✅ for local Mosquitto broker
mqtt_broker_port = 1883
mqtt_username = "oora"
mqtt_password = "oora"

# MQTT Topics

mqtt_topic_base = 'PTS/'
# Topics for subscribing (with wildcards)
mqtt_sensor_data_topic_sub = mqtt_topic_base + 'SENSORDATA/#'
mqtt_dispatch_topic_sub = mqtt_topic_base + 'DISPATCH/#'
mqtt_status_topic_sub = mqtt_topic_base + 'STATUS/#'

mqtt_priority_topic_sub = mqtt_topic_base + 'PRIORITY/#'
mqtt_ack_topic_sub = mqtt_topic_base + 'ACK/#'
mqtt_script_topic_sub = mqtt_topic_base + 'SCRIPT/#'
mqtt_mtn_topic_sub = mqtt_topic_base + 'MTN/#'

# Topics for publishing (without wildcards)
mqtt_sensor_data_topic_pub = mqtt_topic_base + 'SENSORDATA/'
mqtt_dispatch_topic_pub = mqtt_topic_base + 'DISPATCH/'
mqtt_status_topic_pub = mqtt_topic_base + 'STATUS/'
mqtt_status_topic_pub_1 = mqtt_topic_base + 'ACTION/'
mqtt_priority_topic_pub = mqtt_topic_base + 'PRIORITY/'
mqtt_ack_topic_pub = mqtt_topic_base + 'ACK/'
mqtt_script_topic_pub = mqtt_topic_base + 'SCRIPT/'

app = Flask(__name__)
CORS(app, resources={r"/": {"origins": "*"}})

# MQTT Configuration
# app.config['TEMPLATES_AUTO_RELOAD'] = True
# app.config['MQTT_BROKER_URL'] = mqtt_broker_ip
# app.config['MQTT_BROKER_PORT'] = 1883
# app.config['MQTT_USERNAME'] = mqtt_username
# app.config['MQTT_PASSWORD'] = mqtt_password
# app.config['MQTT_KEEPALIVE'] = 60  # Reduced from 64800 to be more reasonable
# app.config['MQTT_TLS_ENABLED'] = False
# app.config['MQTT_CLIENT_ID'] = f'rpibroker_{int(time.time())}'  # Make client ID unique
# app.config['MQTT_CLEAN_SESSION'] = True  # Ensure clean session on reconnect
# app.config['MQTT_REFRESH_TIME'] = 30  # More frequent refresh to detect connection issues
#app.config['SECRET_KEY'] = 'secret!'

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MQTT_BROKER_URL'] = mqtt_broker_ip
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_CLIENT_ID'] = f"desktop_{int(time.time())}"
app.config['MQTT_USERNAME'] = mqtt_username
app.config['MQTT_PASSWORD'] = mqtt_password
app.config['MQTT_KEEPALIVE'] = 64840
app.config['MQTT_TLS_ENABLED'] = False

app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

app.config['SYSTEM_STATUS'] = False

mqtt = Mqtt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DATABASE = 'lan_monitoring.db'

topics_to_subscribe = [
        (mqtt_sensor_data_topic_sub, 1),
        (mqtt_dispatch_topic_sub, 1),
        (mqtt_status_topic_sub, 1),
        (mqtt_priority_topic_sub, 1),
        (mqtt_ack_topic_sub, 1),
        (mqtt_script_topic_sub, 1),
        (mqtt_mtn_topic_sub, 1)
    ]
for topic, qos in topics_to_subscribe:
        mqtt.subscribe(topic, qos)

#mqtt.subscribe(topics_to_subscribe)
# Subscribe to MQTT topics
@mqtt.on_connect()
def handle_mqtt_connect(client, userdata, flags, rc):
    logger.info(f"Connected to MQTT broker with result code: {rc}")
    # Subscribe using the subscription topics (with wildcards)
    topics_to_subscribe = [
        (mqtt_sensor_data_topic_sub, 1),
        (mqtt_dispatch_topic_sub, 1),
        (mqtt_status_topic_sub, 1),
        (mqtt_priority_topic_sub, 1),
        (mqtt_ack_topic_sub, 1),
        (mqtt_script_topic_sub, 1)
    ]
    for topic, qos in topics_to_subscribe:
        mqtt.subscribe(topic, qos)
    #mqtt.subscribe(topics_to_subscribe)
    logger.info(f"Subscribed to topics: {', '.join(t[0] for t in topics_to_subscribe)}")

@mqtt.on_disconnect()
def handle_disconnect(client, userdata, rc):
    logger.info(f"[MQTT] Disconnected from broker with result code: {rc}")
    if rc == 0:
        logger.info("Disconnected gracefully.")
    else:
        logger.info("Unexpected disconnect! Possible causes:")
        logger.info("- Broker rejected the connection (bad credentials, client ID conflict, etc.)")
        logger.info("- Network error")
        logger.info("- Callback crashed")

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
                       station_id TEXT NOT NULL UNIQUE,
                       S1 BOOLEAN,
                       S2 BOOLEAN,
                       S3 BOOLEAN,
                       S4 BOOLEAN,
                       P1 BOOLEAN,
                       P2 BOOLEAN,
                       P3 BOOLEAN,
                       P4 BOOLEAN,
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
    
    db = get_db()
    cursor = db.execute(
        'INSERT INTO history (sender, receiver, priority, status) VALUES (?, ?, ?, ?)',
        (from_id, to_id, priority, 'in_progress')
    )
    task_id = cursor.lastrowid
    db.commit()
    
    dispatch_data['task_id'] = task_id
    
    dispatch_message = json.dumps({
        'task_id': task_id,
        'from': from_id,
        'to': to_id,
        'priority': priority,
        'timestamp': time.time()
    })
    
    mqtt.publish(f"{mqtt_dispatch_topic_pub}/{to_id}", dispatch_message)
    
    # Determine station names from IDs
    from_station = None
    to_station = None
    for name, station_id in STATION_IDS.items():
        if station_id == from_id:
            from_station = name
        if station_id == to_id:
            to_station = name
    
    # Send script execution commands to both stations
    if from_station and to_station:
        # Sender script parameters - using inching_cs.py now
        sender_params = {
            'mode': 'send',
            'task_id': task_id
        }
        sender_script_msg = json.dumps({
            'script': 'Tellerloop_sw.py',  # Changed from dispatch_handler.py
            'params': sender_params,
            'task_id': task_id
        })
        mqtt.publish(f"{mqtt_script_topic_pub}{from_station}", sender_script_msg)
        logger.info(f"Sent script execution command to sender station {from_station}")
        
        # Receiver script parameters
        receiver_params = {
            'mode': 'receive',
            'task_id': task_id
        }
        receiver_script_msg = json.dumps({
            'script': 'Tellerloop_sw.py',  # Changed from dispatch_handler.py
            'params': receiver_params,
            'task_id': task_id
        })
        mqtt.publish(f"{mqtt_script_topic_pub}{to_station}", receiver_script_msg)
        logger.info(f"Sent script execution command to receiver station {to_station}")
    else:
        logger.error(f"Could not find station names for IDs: from={from_id}, to={to_id}")
    
    socketio.emit('system_status_changed', {
        'status': True,
        'current_dispatch': {
            'from': from_id,
            'to': to_id,
            'priority': priority
        }
    })
    for i in range(1, 5):  # Assuming stations 1 to 4
        if i == from_id:
            status = {'status': 'sending', 'destination': to_id, 'task_id': task_id}
            msg = {'action':'dispatch'}
        elif i == to_id:
            msg = {'action':'receive'}
            status = {'status': 'receiving', 'source': from_id, 'task_id': task_id}
        else:
            msg = {'action':'passthrough'}
            status = {'status': 'standby'}
        
        status_message = json.dumps(msg)
        mqtt.publish(f"{mqtt_status_topic_pub_1}{i}", status_message)
 
        socketio.emit('status', status, room=str(i))

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    try:
        data = message.payload.decode()
        topic = message.topic
        print(f"MQTT message received: {topic} -> {data}")
        logger.info(f"MQTT message received: {topic} -> {data}")
        
        # Handle different types of messages based on topic
        if topic.startswith('PTS/SENSORDATA/'):
            # Get station ID from topic
            station_id = topic.split('/')[-1]
            # Forward to Socket.IO clients
            socketio.emit('mqtt_message', {'topic': topic, 'data': data}, room=str(station_id))
            
            # Store to database if it's valid JSON
            try:
                sensor_data = json.loads(data)
                if isinstance(sensor_data, dict):
                    db = get_db()
                    #mapped_data = map_sensor_data(sensor_data)
                    mapped_data = sensor_data
                    db.execute(
                        '''
                        INSERT INTO sensor_data 
                        (station_id, S1, S2, S3, S4, P1, P2, P3, P4) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(station_id) DO UPDATE SET
                            S1 = excluded.S1,
                            S2 = excluded.S2,
                            S3 = excluded.S3,
                            S4 = excluded.S4,
                            P1 = excluded.P1,
                            P2 = excluded.P2,
                            P3 = excluded.P3,
                            P4 = excluded.P4,
                            timestamp = CURRENT_TIMESTAMP
                        ''',
                        (
                            station_id,
                            mapped_data.get('S1', False),
                            mapped_data.get('S2', False),
                            mapped_data.get('S3', False),
                            mapped_data.get('S4', False),
                            mapped_data.get('P1', False),
                            mapped_data.get('P2', False),
                            mapped_data.get('P3', False),
                            mapped_data.get('P4', False)
                        )
                    )
                    db.commit()
                    #mapped_data = map_sensor_data(sensor_data)
                    sensor_5 = mapped_data.get('P1', False)
                    logger.info(f"Emitting Pod Availability: {not sensor_5} for station {station_id}")
                    socketio.emit('pod_availability_changed', {
                    'station_id': station_id,
                    'available': not sensor_5
                    }, room=str(station_id))

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON format in sensor data: {data}")
                
        elif topic.startswith('PTS/DISPATCH/'):
            parts = topic.split('/')
            if len(parts) >= 4:
                from_id = parts[2]
                to_id = parts[3]
                socketio.emit('dispatch_event', {'from': from_id, 'to': to_id, 'data': data})
                logger.info(f"Dispatch from {from_id} to {to_id}: {data}")
                
        elif topic.startswith('PTS/STATUS/'):
            station_id = topic.split('/')[-1]
            socketio.emit('station_status', {'station': station_id, 'data': data}, room=str(station_id))
            logger.info(f"Status update for station {station_id}: {data}")
                
        elif topic.startswith('PTS/PRIORITY/'):
            parts = topic.split('/')
            if len(parts) >= 4:
                from_id = parts[2]
                to_id = parts[3]
                if not is_pod_available(from_id):
                    logger.warning(f"Priority dispatch aborted: No pod available at station {from_id}")
                    return
                logger.info(f"Priority request from {from_id} to {to_id}: {data}")
                
        elif topic.startswith('PTS/ACK/'):
            station_id = topic.split('/')[-1]
            logger.info(f"Acknowledgment for station {station_id}: {data}")
            
            try:
                ack_data = json.loads(data)
                if ack_data.get('type') == 'receive_completed':
                    handle_dispatch_completed(ack_data)
                elif ack_data.get('type') == 'receive_completed':
                    logger.info(f"Receiver ACK received for Task {ack_data.get('task_id')}")
                    socketio.emit('receiver_ack_completed', ack_data)  # 🔥 NEW EMIT to frontend
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON format in acknowledgment: {data}")
                
    except Exception as e:
        logger.error(f"MQTT message processing error: {e}")

@socketio.on('dispatch_completed')
def handle_dispatch_completed(data):
    global dispatch_in_progress, current_dispatch
    
    if dispatch_in_progress and current_dispatch:
        task_id = data.get('task_id') or current_dispatch.get('task_id')
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
        
        # Add execution details if available
        execution_details = data.get('details')
        if execution_details:
            db.execute(
                'UPDATE history SET execution_details = ? WHERE task_id = ?',
                (json.dumps(execution_details), task_id)
            )
            db.commit()
        
                # Notify UI to re-enable dispatch
        socketio.emit('system_status_changed', {
            'status': False,
            'current_dispatch': None
        })
        # Reset dispatch state
        dispatch_in_progress = False
        current_dispatch = None
        
        # Process next dispatch if any
        process_next_dispatch()
        
        # Update status for all stations
        for i in range(1, 5):  # Assuming stations 1 to 4
            status = {'status': 'standby'}
            status_message = json.dumps(status)
            mqtt.publish(f"{mqtt_status_topic_pub}{i}", status_message)
            
            socketio.emit('status', status, room=str(i))
            
def map_sensor_data(data):
    if 'S1' in data: 
        return {
            'sensor_1': data.get('S1', False),
            'sensor_2': data.get('S2', False),
            'sensor_3': data.get('S3', False),
            'sensor_4': data.get('S4', False),
            'sensor_5': data.get('P1', False),
            'sensor_6': data.get('P2', False),
            'sensor_7': data.get('P3', False),
            'sensor_8': data.get('P4', False)
        }
    return data

@socketio.on('join')
def handle_join(data):

    sid = request.sid

    if isinstance(data, dict) and 'station_id' in data:
        station_id = int(data['station_id'])

        # Create a unique room name as string
        join_room(str(station_id))
        logger.info(f"Station {station_id} joined room {station_id}.")

        # Store connection mappings
        connected_stations[station_id] = sid
        station_sids[station_id] = sid
        sid_stations[sid] = station_id

        # Notify others
        emit('update_connected_stations', list(connected_stations.keys()), broadcast=True)
        emit('station_joined', {'station_id': station_id}, broadcast=True)

        # Publish to MQTT
        status_message = json.dumps({
            'station_id': station_id,
            'status': 'online',
            'timestamp': time.time()
        })
        mqtt.publish(f"{mqtt_status_topic_pub}{station_id}", status_message)

    else:
        # Handle fallback: maybe this was a page (dashboard client)
        page_id = str(data)
        join_room(page_id)
        logger.info(f"Joined room (page ID): {page_id}")

    if dispatch_in_progress and current_dispatch:
        emit('system_status_changed', {
            'status': True,
            'current_dispatch': current_dispatch
        }, room=sid)

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
        mqtt.publish(f"{mqtt_ack_topic_pub}{receiver}", ack_message)

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
    # Convert station names to IDs if needed
    from_station = data.get('from')
    to_station = data.get('to')
    
    # Handle both station names and IDs
    if isinstance(from_station, str) and from_station.startswith('passthrough-station-'):
        from_id = int(from_station.split('-')[-1])
    else:
        from_id = int(from_station)
        
    if isinstance(to_station, str) and to_station.startswith('passthrough-station-'):
        to_id = int(to_station.split('-')[-1])
    else:
        to_id = int(to_station)

    
    priority = data.get('priority', 'low')
    
    logger.info(f"Dispatch request: from {from_id} to {to_id} with {priority} priority")
    
    # CHECK SENSOR-5 before dispatch
    if not is_pod_available(from_id):
        logger.warning(f"Dispatch aborted: No pod available at station {from_id}")
        emit('dispatch_failed', {
            'reason': f"No pod available at station {from_id}. Dispatch aborted."
        }, room=request.sid)
        return

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
    mqtt.publish(f"{mqtt_topic_base}PRIORITY/{from_id}/{to_id}", dispatch_request)
    
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
        logger.error("No station ID provided in sensor data")
        return
    
    try:
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
        
        # Publish to MQTT using publish topic (no wildcards)
        try:
            sensor_message = json.dumps(data)
            mqtt.publish(f"{mqtt_sensor_data_topic_pub}{station_id}", sensor_message)
            logger.info(f"Published sensor data for station {station_id}")
        except Exception as mqtt_error:
            logger.error(f"MQTT publishing error for station {station_id}: {str(mqtt_error)}")
            # Continue execution - don't let MQTT errors stop the rest of the function
        
        logger.info(f"Sensor data received from station {station_id}: {data}")
        
    except Exception as e:
        logger.error(f"Error processing sensor data for station {station_id}: {str(e)}")
        db.rollback()

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
            mqtt.publish(f"{mqtt_status_topic_pub}{station_num}", status_message)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")
    sid = request.sid
    station_id = sid_stations.get(sid)

    if station_id:
        leave_room(str(station_id))
        connected_stations.pop(station_id, None)
        station_sids.pop(station_id, None)
        sid_stations.pop(sid, None)

        emit('station_left', {'station_id': station_id}, broadcast=True)
        emit('update_connected_stations', list(connected_stations.keys()), broadcast=True)

        status_message = json.dumps({
            'station_id': station_id,
            'status': 'offline',
            'timestamp': time.time()
        })
        mqtt.publish(f"{mqtt_status_topic_pub}{station_id}", status_message)

logs = [
    {"task_id": 5266, "from": 5, "to": 6, "date": "25/1/25", "time": "4:15"},
    {"task_id": 6519, "from": 8, "to": 6, "date": "14/1/25", "time": "21:15"},
    {"task_id": 5652, "from": 1, "to": 2, "date": "31/12/24", "time": "-"},
    {"task_id": 5266, "from": 5, "to": 9, "date": "12/12/24", "time": "23:22"},
    {"task_id": 6519, "from": 3, "to": 6, "date": "15/8/24", "time": "-"},
    {"task_id": 5652, "from": 5, "to": 6, "date": "16/8/24", "time": "15:15"}
]

def is_pod_available(station_id):
    """
    Returns True if pod is available, False otherwise.
    Sensor 5 = False => Pod available
    Sensor 5 = True => Pod not available
    """
    try:
        db = get_db()
        row = db.execute(
            '''SELECT P1 FROM sensor_data 
               WHERE station_id = ? 
            ''',
            (station_id,)
        ).fetchone()
        if row:
            return not bool(row[0])
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking pod availability for station {station_id}: {e}")
        return False


@app.route('/')
def home():
    return render_template('home.html')  # Load the Tellerloop page
station_passwords = {
    0: "0000",
    1: "1111",
    2: "2222",
    3: "3333",
    4: "4444"
}

@app.route('/<int:page_id>', methods=['GET', 'POST'])
def handle_page(page_id):
    if page_id not in station_passwords:
        return render_template('404.html'), 404

    if request.method == 'POST':
        entered_pin = request.form.get('pin')
        correct_pin = station_passwords[page_id]

        if entered_pin == correct_pin:
            return render_template('Tellerloop.html', page_id=page_id)
        else:
            return render_template('station_login.html', page_id=page_id, error="Incorrect PIN")

    return render_template('station_login.html', page_id=page_id)


#purely for testing, remove in deployment
@app.route('/api/set_sensor_status/<station_id>/<sensor_5_status>', methods=['POST'])
def set_sensor_status(station_id, sensor_5_status):
    try:
        db = get_db()
        sensor_5_value = True if sensor_5_status.lower() == 'true' else False
        db.execute(
            '''INSERT INTO sensor_data 
               (station_id, sensor_1, sensor_2, sensor_3, sensor_4, 
                sensor_5, sensor_6, sensor_7, sensor_8)
               VALUES (?, 0, 0, 0, 0, ?, 0, 0, 0)''',
            (station_id, sensor_5_value)
        )
        db.commit()

        socketio.emit('pod_availability_changed', {
            'station_id': station_id,
            'available': not sensor_5_value
        }, room=str(station_id))

        return jsonify({'message': f'Sensor-5 status updated for station {station_id}', 'sensor_5': sensor_5_value}), 200
    except Exception as e:
        logger.error(f"Error setting sensor status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/check_pod_available/<station_id>')
def check_pod_available(station_id):
    return jsonify({'available': is_pod_available(station_id)})

# can be kept on a separate file
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
        logger.debug(f"Loaded JSON data keys: {data.keys()}")
        
        # Process the components from the JSON file
        components = data.get('components', [])
        logger.debug(f"Found {len(components)} components in JSON file.")
        db = get_db()
        
        for component in components:
            comp_type = component.get('type')  # Use the correct key for type
            comp_id = component.get('id')      # Use the correct key for id
            logger.debug(f"Component details: type={comp_type}, id={comp_id}")
            
            if comp_type in ['passthrough-station', 'bottom-loading-station']:
                if comp_id:
                    table_name = f"component_{comp_id}"
                    logger.debug(f"Creating table for component id: {comp_id}, table name: {table_name}")
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
                    logger.debug("Skipping component due to missing id.")
            else:
                logger.debug("Skipping component due to type mismatch.")
        db.commit()
        logger.debug("Component tables creation committed.")
        
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({'error': 'Network architecture file not found'}), 404
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format in network architecture file'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/live_tracking')
def get_live_tracking():
    try:
        db = get_db()
        # Get the most recent entry from history table
        latest_entry = db.execute(
            'SELECT * FROM history ORDER BY timestamp DESC LIMIT 1'
        ).fetchone()
       
        if (latest_entry):
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
        drop_all_tables()
        
        init_db()
        
        directory = os.path.dirname(__file__)
        json_files = glob.glob(os.path.join(directory, "network_architecture*.json"))
        
        if not json_files:
            logger.warning("No network architecture files found")
            return jsonify({'error': 'No architecture files found'}), 404
        
        latest_file = max(json_files, key=os.path.getmtime)
        
        with open(latest_file, 'r') as json_file:
            data = json.load(json_file)
        
        logger.info(f"Loaded network architecture from {latest_file}")
        logger.info(f"Loaded JSON data keys: {data.keys()}")
        
        components = data.get('components', [])
        logger.info(f"Found {len(components)} components in JSON file")
        
        db = get_db()
        
        for component in components:
            comp_type = component.get('type')
            comp_id = component.get('id')
            
            logger.info(f"Processing component: type={comp_type}, id={comp_id}")
            
            if comp_type in ['passthrough-station', 'bottom-loading-station']:
                if comp_id:
                    table_name = f"component_{comp_id}"
                    logger.info(f"Creating table for component: {table_name}")
                    
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

@app.route('/api/maintenance/selftest/<int:station_id>', methods=['POST'])
def maintenance_self_test(station_id):
    mqtt.publish(f"PTS/MTN/{station_id}", json.dumps({"action": "self_test"}))
    return jsonify({"status": "sent", "action": "self_test"}), 200

@app.route('/api/maintenance/inching/<int:station_id>', methods=['POST'])
def maintenance_inching(station_id):
    direction = request.json.get('direction')
    if direction not in ['moveLeft', 'moveRight']:
        return jsonify({"error": "Invalid direction"}), 400
    mqtt.publish(f"PTS/MTN/{station_id}", json.dumps({"action": direction}))
    return jsonify({"status": "sent", "action": direction}), 200

@app.route('/api/maintenance/airdivert/<int:station_id>', methods=['POST'])
def maintenance_air_divert(station_id):
    action = request.json.get('action')
    power = request.json.get('power')
    if action not in ['suck', 'blow'] or not isinstance(power, int):
        return jsonify({"error": "Invalid request"}), 400
    mqtt.publish(f"PTS/MTN/{station_id}", json.dumps({"action": action, "power": power}))
    return jsonify({"status": "sent", "action": action, "power": power}), 200

@app.route('/api/maintenance/stop/<int:station_id>', methods=['POST'])
def maintenance_stop(station_id):
    mqtt.publish(f"PTS/MTN/{station_id}", json.dumps({"action": "stop"}))
    return jsonify({"status": "sent", "action": "stop"}), 200

@app.route('/api/maintenance/indexing/<int:station_id>', methods=['POST'])
def maintenance_indexing(station_id):
    action = request.json.get('action')
    if not action:
        return jsonify({"error": "Action not provided"}), 400
    mqtt.publish(f"PTS/MTN/{station_id}", json.dumps({"action": action}))
    logger.info(f"Indexing action received for station {station_id}: {action}")
    return jsonify({"status": "sent", "action": action}), 200

@app.route('/api/maintenance/podsensing/<int:station_id>', methods=['POST'])
def maintenance_podsensing(station_id):
    action = request.json.get('action')
    if not action:
        return jsonify({"error": "Action not provided"}), 400
    mqtt.publish(f"PTS/MTN/{station_id}", json.dumps({"action": action}))
    logger.info(f"Pod sensing action received for station {station_id}: {action}")
    return jsonify({"status": "sent", "action": action}), 200

@app.route('/api/get_current_station/<int:station_id>', methods=['GET'])
def get_current_station_by_id(station_id):
    return jsonify({'station_id': station_id})

@app.route('/api/download_history', methods=['GET'])
def download_history():  # Removed the station_id parameter as it's not used in the function
    db = get_db()
    rows = db.execute(
        'SELECT * FROM history ORDER BY timestamp DESC'
    ).fetchall()

    result = []
    for row in rows:
        try:
            # Parse the timestamp safely
            date_str = ''
            time_str = ''
            if row['timestamp']:
                try:
                    date_obj = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
                    date_str = date_obj.strftime('%d/%m/%y')
                    time_str = date_obj.strftime('%H:%M')
                except ValueError:
                    # If timestamp is in a different format, try another common format
                    try:
                        date_obj = datetime.strptime(row['timestamp'], '%Y-%m-%dT%H:%M:%S')
                        date_str = date_obj.strftime('%d/%m/%y')
                        time_str = date_obj.strftime('%H:%M')
                    except ValueError:
                        # If still can't parse, use raw value
                        date_str = str(row['timestamp']).split(' ')[0] if ' ' in str(row['timestamp']) else str(row['timestamp'])
                        time_str = str(row['timestamp']).split(' ')[1] if ' ' in str(row['timestamp']) else ''
            
            result.append({
                'task_id': row['task_id'],
                'from': row['sender'],
                'to': row['receiver'],
                'priority': row['priority'],
                'date': date_str,
                'time': time_str
            })
        except Exception as e:
            # Log the error but continue processing other rows
            logger.error(f"Error processing row {row['task_id']}: {str(e)}")
            # Add the row with error indication
            result.append({
                'task_id': row['task_id'],
                'from': row['sender'],
                'to': row['receiver'],
                'priority': row['priority'],
                'date': 'error',
                'time': 'error'
            })
    
    return jsonify(result)

@socketio.on('request_empty_pod')
def handle_empty_pod_request(data):
    requester_station = data.get('requesterStation', 'Unknown')

    # MQTT publish
    request_message = json.dumps(data)
    mqtt.publish(f"{mqtt_topic_base}EMPTY_POD_REQUEST/{requester_station}", request_message)

    # Broadcast to all connected clients (except sender)
    emit('empty_pod_request', data, broadcast=True, include_self=False)

    logger.info(f"Empty pod request from {requester_station}")


@socketio.on('empty_pod_request_accepted')
def handle_empty_pod_request_accepted(data):
    emit('empty_pod_request_accepted', data, broadcast=True)
    acceptance_message = json.dumps(data)
    mqtt.publish(f"{mqtt_topic_base}EMPTY_POD_ACCEPTED/{data.get('requesterStation', 'Unknown')}", acceptance_message)
    logger.info(f"Empty pod request accepted: {data}")
    start_dispatch_message = json.dumps({
        "type": "start_dispatch",
        "request_id": data.get('requestId'),
        "from": data.get('acceptorStation'),
        "to": data.get('requesterStation')
    })
    mqtt.publish(f"{mqtt_topic_base}START_DISPATCH/{data.get('acceptorStation', 'Unknown')}", start_dispatch_message)
    logger.info(f" Start dispatch published to {data.get('acceptorStation')}: {start_dispatch_message}")
    
if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=80, debug=True)