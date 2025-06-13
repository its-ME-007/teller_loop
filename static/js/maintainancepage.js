let mt_isSliding = false;
window.STATION_ID = window.STATION_ID || 1;
let mt_maintenanceAllowed = true; // Flag to track if maintenance is allowed
let mt_podAvailable = false; // Flag to track pod availability

const mt_slideButton = document.getElementById("mt-slideToDispatch");
const mt_slideIcon = mt_slideButton.querySelector(".mt-slide-icon");
mt_slideIcon.style.left = "5px";
mt_slideIcon.style.position = "relative";
mt_slideIcon.style.zIndex = "5";
mt_slideIcon.style.cursor = "grab";

document.addEventListener("DOMContentLoaded", function () {
    // Initialize socket connection if not already created
    if (!window.socket) {
        window.socket = io.connect(window.location.origin, {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 10
        });
    }

    // Call functions to check system status at load
    checkMaintenancePermission();
    checkPodAvailability();

    // Socket event listeners
    socket.on('connect', function () {
        console.log('Connected to Socket.IO server');
        socket.emit('join', { station_id: STATION_ID });
        checkMaintenancePermission();
        checkPodAvailability();
    });

    socket.on('system_status_changed', function (data) {
        mt_maintenanceAllowed = !data.status;
        updateMaintenanceUI(data.current_dispatch);
    });

    socket.on('status', function (data) {
        console.log("Received status:", data);
        if (data.status === 'standby') {
            mt_maintenanceAllowed = true;
            updateMaintenanceUI();
        }
    });

    socket.on('pod_availability_changed', function ({ station_id, available }) {
        if (parseInt(station_id) === STATION_ID) {
            mt_podAvailable = available;
            updateMaintenanceUI();
            console.log(`Pod availability updated: ${available}`);
        }
    });

    socket.on('mqtt_message', function(data) {
        if (data.topic.includes("SENSORDATA")){
            console.log("SensorData", data);
            let sensordata = JSON.parse(data.data);
            Object.entries(sensordata).forEach(([key, value]) => {
                // Map sensor key to parent box ID
                const sensorToBoxMap = {
                    'S1': 'idx-status1',
                    'S2': 'idx-status3',
                    'S3': 'idx-status2',
                    'S4': 'idx-status4',
                    'P1': 'status1',
                    'P2': 'status2',
                    'P3': 'status3',
                    'P4': 'status4'
                };

                const indicatorEl = document.getElementById(key);
                const boxId = sensorToBoxMap[key];
                const boxEl = boxId ? document.getElementById(boxId) : null;

                console.log(value);

                // Update indicator color
                if (indicatorEl) {
                    indicatorEl.classList.remove('green', 'gray');
                    if (key.startsWith("S")){
                        indicatorEl.classList.add(value ? 'green' : 'gray');
                    }
                    if (key.startsWith("P")){
                        indicatorEl.classList.add(value ? 'gray' : 'green');
                    }
                }

                // Update parent box color
                if (boxEl) {
                    boxEl.classList.remove('green', 'gray');
                    // Apply coloring based on the same logic as indicators
                    if (key.startsWith("S")){
                         // For S sensors, true is green, false is gray
                        boxEl.classList.add(value ? 'green' : 'gray');
                    } else if (key.startsWith("P")){
                        // For P sensors, true is gray, false is green
                        boxEl.classList.add(value ? 'gray' : 'green');
                    }
                }
            });
        }
    });

    // Air slider functionality
    const mt_airSlider = document.getElementById("mt-air-slider");
    const mt_airPercentage = document.getElementById("mt-air-percentage");

    if (mt_airSlider && mt_airPercentage) {
        mt_airSlider.addEventListener("input", function () {
            mt_airPercentage.textContent = mt_airSlider.value + "%";
        });
    }

    // Control buttons - includes both .mt-side-button and .mt-end-button
    document.querySelectorAll('.mt-side-button, .mt-end-button').forEach(btn => {
        btn.addEventListener('click', function () {
            const label = this.innerText.trim().toLowerCase();
            if (label === 'left' || label === 'right') {
                const dir = label === 'left' ? 'moveLeft' : 'moveRight';
                fetch(`/api/maintenance/inching/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ direction: dir })
                });
            } else if (label === 'suck' || label === 'blow') {
                const power = parseInt(document.getElementById("mt-air-slider").value);
                fetch(`/api/maintenance/airdivert/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: label, power })
                }) 
                .then(response => response.json())
                .then(data => {
                    console.log(`${label} action triggered:`, data);
                    showNotification(`${label.charAt(0).toUpperCase() + label.slice(1)} action triggered`, 'success');
                })
                .catch(error => {
                    console.error(`Failed to trigger ${label} action:`, error);
                    showNotification(`Failed to trigger ${label} action`, 'error');
                });
            } else if (label == 'stop') {
                fetch(`/api/maintenance/stop/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'stop' })
                })  
                .then(response => response.json())
                .then(data => {
                    console.log('Stop action triggered:', data);
                    showNotification('Stop action triggered', 'success');
                })
                .catch(error => {
                    console.error('Failed to trigger stop action:', error);
                    showNotification('Failed to trigger stop action', 'error');
                });
            }
        });
    });

    // Initialize status box interactions
    initStatusBoxInteractions();
});
function checkMaintenancePermission() {
    fetch('/api/check_dispatch_allowed')
        .then(res => res.json())
        .then(data => {
            mt_maintenanceAllowed = data.allowed;
            updateMaintenanceUI();
        })
        .catch(err => {
            console.error('Error checking maintenance permission:', err);
            mt_maintenanceAllowed = false;
            updateMaintenanceUI();
        });
}

function checkPodAvailability() {
    fetch(`/api/check_pod_available/${STATION_ID}`)
        .then(res => res.json())
        .then(data => {
            mt_podAvailable = data.available;
            updateMaintenanceUI();
        })
        .catch(err => {
            console.error('Error checking pod availability:', err);
            mt_podAvailable = false;
            updateMaintenanceUI();
        });
}

function updateMaintenanceUI(currentDispatch = null) {
    if (!mt_maintenanceAllowed || !mt_podAvailable) {
        mt_slideButton.classList.add('disabled');
        
        // Update SVG arrow colors when disabled
        const arrows = mt_slideButton.querySelectorAll('svg path');
        arrows.forEach(arrow => {
            arrow.setAttribute('fill', 'grey');
        });
        
        if (!mt_podAvailable) {
            mt_slideButton.querySelector('span').textContent = 'Please Place Pod in the station';
        } else {
            mt_slideButton.querySelector('span').textContent = 'Slide to self-test';
        }
    } else {
        mt_slideButton.classList.remove('disabled');
        
        // Reset SVG arrow colors when enabled
        const arrows = mt_slideButton.querySelectorAll('svg path');
        arrows.forEach(arrow => {
            arrow.setAttribute('fill', '#32B34B');  // Reset to green
        });
        
        mt_slideButton.querySelector('span').textContent = 'Slide to self-test';
    }
}

// Slide button event listeners
mt_slideButton.addEventListener("mousedown", startMaintenanceSlide);
mt_slideButton.addEventListener("touchstart", startMaintenanceSlide);

function startMaintenanceSlide(event) {
    if (!mt_maintenanceAllowed || !mt_podAvailable) {
        return alert(mt_podAvailable ? "Maintenance unavailable right now." : "No pod available. Please place pod first.");
    }
    
    event.preventDefault();
    mt_isSliding = true;
    let startX = event.clientX || event.touches[0].clientX;
    mt_slideIcon.style.transition = "";
    mt_slideIcon.style.cursor = "grabbing";

    function moveMaintenanceSlide(e) {
        if (!mt_isSliding) return;
        const currentX = e.clientX || e.touches[0].clientX;
        let diff = Math.min(190, Math.max(0, currentX - startX));
        mt_slideIcon.style.left = `${5 + diff}px`;
    }

    function endMaintenanceSlide() {
        mt_isSliding = false;
        mt_slideIcon.style.cursor = "grab";

        if (parseInt(mt_slideIcon.style.left || "0") > 140) {
            mt_slideIcon.style.left = "190px";
            
            if (!mt_maintenanceAllowed || !mt_podAvailable) {
                resetMaintenanceSlider();
                return alert("Invalid maintenance state");
            }

            fetch(`/api/maintenance/selftest/${STATION_ID}`, {
                method: 'POST'
            })
            .then(res => res.json())
            .then(data => {
                console.log("Self-test triggered:", data);
                showNotification("Self-test triggered successfully", "success");
                setTimeout(resetMaintenanceSlider, 1000);
            })
            .catch(err => {
                console.error("Failed to trigger self-test:", err);
                showNotification("Failed to trigger self-test", "error");
                resetMaintenanceSlider(); // Reset immediately on error
            });
        } else {
            resetMaintenanceSlider();
        }

        document.removeEventListener("mousemove", moveMaintenanceSlide);
        document.removeEventListener("mouseup", endMaintenanceSlide);
        document.removeEventListener("touchmove", moveMaintenanceSlide);
        document.removeEventListener("touchend", endMaintenanceSlide);
    }

    document.addEventListener("mousemove", moveMaintenanceSlide);
    document.addEventListener("mouseup", endMaintenanceSlide);
    document.addEventListener("touchmove", moveMaintenanceSlide);
    document.addEventListener("touchend", endMaintenanceSlide);
}

function resetMaintenanceSlider() {
    mt_slideIcon.style.transition = "left 0.5s ease";
    mt_slideIcon.style.left = "5px";
    setTimeout(() => { mt_slideIcon.style.transition = ""; }, 500);
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.position = 'fixed';
    notification.style.bottom = '20px';
    notification.style.right = '20px';
    notification.style.padding = '10px 20px';
    notification.style.borderRadius = '5px';
    notification.style.zIndex = '1000';
  
    const colorMap = {
      success: '#32B34B',
      error: '#FF3B30',
      info: '#007AFF'
    };
    notification.style.backgroundColor = colorMap[type] || '#007AFF';
    notification.style.color = 'white';
  
    document.body.appendChild(notification);
    setTimeout(() => {
      notification.style.opacity = '0';
      notification.style.transition = 'opacity 0.5s ease';
      setTimeout(() => document.body.removeChild(notification), 500);
    }, 5000);
}

function initStatusBoxInteractions() {
    // Add ripple effect to all status boxes
    const statusBoxes = document.querySelectorAll('.mt-indx-status-box, .mt-status-box');
    
    statusBoxes.forEach(box => {
        // Add tooltip to show clickable functionality
        const tooltip = document.createElement('span');
        tooltip.className = 'status-tooltip';
        tooltip.textContent = 'Click to trigger';
        box.appendChild(tooltip);
        
        // Add click handler with ripple effect
        box.addEventListener('click', function(e) {
            // Create ripple element
            const ripple = document.createElement('span');
            ripple.className = 'ripple';
            this.appendChild(ripple);
            
            // Position the ripple
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = `${size}px`;
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            
            // Remove the ripple after animation completes
            setTimeout(() => ripple.remove(), 600);
            
            // Toggle active state
            this.classList.add('active');
            
            // Get box ID and sensor ID to determine action
            const boxId = this.id;
            const sensorId = this.querySelector('.mt-indx-indicator, .indicator').id;
            
            // Trigger the appropriate action based on the box clicked
            triggerStatusAction(boxId, sensorId);
        });
    });
}

function triggerStatusAction(boxId, sensorId) {
    // Determine the action to take based on the box ID and sensor ID
    console.log(`Button clicked: ${boxId}, Sensor: ${sensorId}`);
    
    // Map of actions based on ID prefixes
    const actions = {
        'idx-status': {
            action: 'indexing',
            S1: 'load',
            S2: 'passthrough',
            S3: 'arrive',
            S4: 'drop'
        },
        'status': {
            action: 'podsensing',
            P1: 'newpod',
            P2: 'podarrive',
            P3: 'inpassthrough',
            P4: 'inbuffer'
        }
    };
    
    // Determine action type from box ID prefix
    let actionType = null;
    let actionName = null;
    
    for (const prefix in actions) {
        if (boxId.startsWith(prefix)) {
            actionType = actions[prefix].action;
            actionName = actions[prefix][sensorId];
            break;
        }
    }
    
    if (actionType && actionName) {
        // Send the action to the server via fetch API
        fetch(`/api/maintenance/${actionType}/${STATION_ID}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: actionName })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Action triggered:', data);
            showNotification(`${actionName.charAt(0).toUpperCase() + actionName.slice(1)} action triggered`, 'success');
        })
        .catch(error => {
            console.error('Error triggering action:', error);
            showNotification('Failed to trigger action', 'error');
        })
        .finally(() => {
            // Find the status box element by its ID and remove the 'active' class
            const clickedBox = document.getElementById(boxId);
            if (clickedBox) {
                clickedBox.classList.remove('active');
            }
        });
    }
    
    // Keep the original sensor light behavior intact
    // The actual sensor light state is controlled by the MQTT messages in your existing code
}