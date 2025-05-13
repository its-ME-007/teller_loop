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
                const el = document.getElementById(key);
                console.log(value);
                if (el) {
                    el.classList.remove('green', 'gray');
                    if (key.startsWith("S")){
                        el.classList.add(value ? 'green' : 'gray');
                    }
                    if (key.startsWith("P")){
                        el.classList.add(value ? 'gray' : 'green');
                    }
                }
            });
        }
    });

    const mt_airSlider = document.getElementById("mt-air-slider");
    const mt_airPercentage = document.getElementById("mt-air-percentage");

    mt_airSlider.addEventListener("input", function () {
        mt_airPercentage.textContent = mt_airSlider.value + "%";
    });

    document.querySelectorAll('.mt-side-button').forEach(btn => {
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
                });
            } else if (label == 'stop') {
                fetch(`/api/maintenance/stop/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action:'stop'})
                });
            }
        });
    });
});

function checkMaintenancePermission() {
    fetch('/api/check_dispatch_allowed')
        .then(res => res.json())
        .then(data => {
            mt_maintenanceAllowed = data.allowed;
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
        
        if (!mt_podAvailable) {
            mt_slideButton.querySelector('span').textContent = 'Please Place Pod in the station';
        } else {
            mt_slideButton.querySelector('span').textContent = 'Slide to self-test';
        }
    } else {
        mt_slideButton.classList.remove('disabled');
        mt_slideButton.querySelector('span').textContent = 'Slide to self-test';
    }
}

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
            })
            .catch(err => {
                console.error("Failed to trigger self-test:", err);
                showNotification("Failed to trigger self-test", "error");
            });

            setTimeout(resetMaintenanceSlider, 1000);
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