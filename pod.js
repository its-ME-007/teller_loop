document.addEventListener('DOMContentLoaded', function() {
    let currentStation = 'Unknown-Station';
    let currentStationDisplay = '';
    let availableStations = [];
    let activeRequest = null;
  
    // IP to Station mapping
    const ipToStation = {
        "192.168.43.231": "passthrough-station-1",
        "192.168.43.189": "passthrough-station-2", 
        "192.168.43.158": "passthrough-station-3",
        "192.168.43.200": "passthrough-station-4"
    };
  
    // Helper function to format station display
    function formatStationDisplay(stationName) {
        if (!stationName || stationName.length < 2) return stationName.toUpperCase();
        return stationName.charAt(0).toUpperCase() + stationName.charAt(stationName.length - 1).toUpperCase();
    }
  
    // Variables to hold the interval for blinking arrows
    let arrowBlinkInterval;
    let toggleBlink = true;
  
    // Fetch current station details
    function fetchCurrentStation() {
        return fetch('/api/get_client_ip')
            .then(response => response.json())
            .then(data => {
                const clientIP = data.ip;
                currentStation = ipToStation[clientIP] || "passthrough-station-1";
                currentStationDisplay = formatStationDisplay(currentStation);
                
                // Update local storage
                localStorage.setItem('stationUsername', currentStation);
                localStorage.setItem('stationDisplay', currentStationDisplay);
                
                return currentStation;
            })
            .catch(error => {
                console.error('Error fetching client IP:', error);
                return "passthrough-station-1";
            });
    }
  
    // Fetch network architecture for stations
    function fetchNetworkArchitecture() {
        return fetch('/api/network_architecture')
            .then(response => response.json())
            .then(data => {
                availableStations = data.components
                    .filter(component => 
                        component.type === "passthrough-station" || 
                        component.type === "bottom-loading-station"
                    )
                    .map(station => ({
                        id: station.id,
                        displayId: formatStationDisplay(station.id)
                    }));
                return availableStations;
            })
            .catch(error => {
                console.error('Error fetching network architecture:', error);
                return [];
            });
    }
  
    // Fetch and update live tracking info
    function updateLiveTracking() {
        console.log('Fetching live tracking data...');
        fetch('/api/live_tracking')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok: ' + response.statusText);
                }
                return response.json();
            })
            .then(data => {
                console.log('Live tracking data received:', data);
                updateDashboardUI(data);
            })
            .catch(error => {
                console.error('Error fetching live tracking data:', error);
                updateDashboardUI({system_status: false});
            });
    }
  
    // Update dashboard UI based on tracking data
    function updateDashboardUI(data) {
        const systemStatus = data.system_status;
        const sender = data.sender;
        const receiver = data.receiver;
        const taskId = data.task_id;
  
        console.log('Updating dashboard UI with system status:', systemStatus);
  
        // Get UI elements
        const standbyInfo = document.getElementById('standby-info-id');
        const trackingInfo = document.getElementById('tracking-info-id');
        const fromCircle = document.querySelector('.showstationFrom .circle');
        const toCircle = document.querySelector('.showstationTo .circle');
        const taskSpan = document.querySelector('.movement-disp .taskid');
        const dbContent = document.getElementById('db-content-id');
        const liveTracking = document.querySelector('.live-tracking');
  
        // Only update UI if we're on the dashboard page
        const dashboardBtn = document.getElementById("Dashboard-Btn");
        if (!dashboardBtn || !dashboardBtn.classList.contains("active")) {
            return;
        }
  
        if (systemStatus === true) {
            if (fromCircle) fromCircle.textContent = formatStationDisplay(sender || '');
            if (toCircle) toCircle.textContent = formatStationDisplay(receiver || '');
            if (taskSpan) taskSpan.textContent = 'Task ID: ' + (taskId || '');
            
            if (standbyInfo) standbyInfo.style.display = 'none';
            if (trackingInfo) trackingInfo.style.display = 'flex';
            if (liveTracking) liveTracking.style.display = 'flex';
            if (dbContent) dbContent.style.display = 'flex';
            
            startArrowBlinking();
            
            // Fetch history if sender/receiver info is incomplete
            if ((!sender || !receiver) && systemStatus) {
                setTimeout(() => {
                    fetch('/api/get_dispatch_history')
                        .then(response => response.json())
                        .then(history => {
                            if (history && history.length > 0) {
                                const latestDispatch = history[0];
                                if (fromCircle) fromCircle.textContent = formatStationDisplay(latestDispatch.from || '');
                                if (toCircle) toCircle.textContent = formatStationDisplay(latestDispatch.to || '');
                                if (taskSpan) taskSpan.textContent = 'Task ID: ' + (latestDispatch.task_id || '');
                            }
                        })
                        .catch(error => console.error('Error fetching history:', error));
                }, 2500);
            }
        } else {
            if (fromCircle) fromCircle.textContent = '';
            if (toCircle) toCircle.textContent = '';
            if (taskSpan) taskSpan.textContent = 'Task ID: ';
            
            if (trackingInfo) trackingInfo.style.display = 'none';
            if (standbyInfo) standbyInfo.style.display = 'flex';
            if (liveTracking) {
                liveTracking.style.display = 'flex';
                liveTracking.style.flexDirection = 'column';
                liveTracking.style.gap = '0';
            }
            if (dbContent) dbContent.style.gap = '20px';
            
            stopArrowBlinking();
        }
    }
  
    // Start blinking the arrows alternately
    function startArrowBlinking() {
        const arrows = document.querySelectorAll('.arrow');
        if (arrowBlinkInterval || arrows.length === 0) return;
        
        console.log('Starting arrow blinking animation');
        
        arrows.forEach(arrow => {
            arrow.style.opacity = 1;
            arrow.style.fill = '#32B34B';
        });
        
        arrowBlinkInterval = setInterval(() => {
            arrows.forEach((arrow, index) => {
                if (toggleBlink) {
                    arrow.style.opacity = (index % 2 === 0) ? 1 : 0;
                } else {
                    arrow.style.opacity = (index % 2 === 0) ? 0 : 1;
                }
            });
            toggleBlink = !toggleBlink;
        }, 500);
    }
  
    // Stop blinking and set arrows to static green
    function stopArrowBlinking() {
        const arrows = document.querySelectorAll('.arrow');
        if (arrowBlinkInterval) {
            console.log('Stopping arrow blinking animation');
            clearInterval(arrowBlinkInterval);
            arrowBlinkInterval = null;
        }
        arrows.forEach(arrow => {
            arrow.style.opacity = 1;
            arrow.style.fill = '#32B34B';
        });
    }
  
    // Popup helper function
    function showConfirmationPopup(message) {
        const popupDiv = document.createElement('div');
        popupDiv.style.position = 'fixed';
        popupDiv.style.top = '50%';
        popupDiv.style.left = '50%';
        popupDiv.style.transform = 'translate(-50%, -50%)';
        popupDiv.style.backgroundColor = 'white';
        popupDiv.style.border = '2px solid #32B34B';
        popupDiv.style.borderRadius = '10px';
        popupDiv.style.padding = '20px';
        popupDiv.style.zIndex = '1000';
        popupDiv.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
        popupDiv.style.textAlign = 'center';
  
        const messageP = document.createElement('p');
        messageP.textContent = message;
        messageP.style.marginBottom = '15px';
  
        const okButton = document.createElement('button');
        okButton.textContent = 'OK';
        okButton.style.backgroundColor = '#32B34B';
        okButton.style.color = 'white';
        okButton.style.border = 'none';
        okButton.style.padding = '10px 20px';
        okButton.style.borderRadius = '5px';
        okButton.style.cursor = 'pointer';
  
        okButton.addEventListener('click', () => {
            document.body.removeChild(popupDiv);
        });
  
        popupDiv.appendChild(messageP);
        popupDiv.appendChild(okButton);
        document.body.appendChild(popupDiv);
    }
  
    // Socket connection setup
    const socket = io.connect(window.location.origin, {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10
    });
  
    // Initialization
    Promise.all([fetchCurrentStation(), fetchNetworkArchitecture()])
    .then(([station, stations]) => {
        console.log('Current Station:', station);
        console.log('Available Stations:', stations);
  
        // Setup UI elements
        const sendEmptyPodButton = document.querySelector('.request-card .send-button');
        const requestedCard = document.querySelector('.requested-card');
        const reqPodStation = document.querySelector('.req-pod-station');
        const acceptButton = requestedCard.querySelector('.accept');
        const abortButton = document.querySelector('.abort-button');
  
        // Abort button handler
        if (abortButton) {
            abortButton.addEventListener('click', function() {
                if (confirm('Are you sure you want to abort the current dispatch?')) {
                    socket.emit('dispatch_completed', { 
                        type: 'dispatch_completed',
                        aborted: true 
                    });
                    
                    // Update UI immediately
                    updateDashboardUI({system_status: false});
                }
            });
        }
  
        // Send empty pod request
        sendEmptyPodButton.addEventListener('click', function() {
            const popup = document.createElement('div');
            popup.style.position = 'fixed';
            popup.style.top = '50%';
            popup.style.left = '50%';
            popup.style.transform = 'translate(-50%, -50%)';
            popup.style.backgroundColor = 'white';
            popup.style.border = '2px solid #32B34B';
            popup.style.borderRadius = '10px';
            popup.style.padding = '20px';
            popup.style.zIndex = '1000';
            popup.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
            popup.style.textAlign = 'center';
  
            const messageP = document.createElement('p');
            messageP.textContent = 'Are you sure you want to request an empty pod?';
            messageP.style.marginBottom = '15px';
  
            const confirmButton = document.createElement('button');
            confirmButton.textContent = 'Confirm';
            confirmButton.style.backgroundColor = '#32B34B';
            confirmButton.style.color = 'white';
            confirmButton.style.border = 'none';
            confirmButton.style.padding = '10px 20px';
            confirmButton.style.borderRadius = '5px';
            confirmButton.style.cursor = 'pointer';
            confirmButton.style.marginRight = '10px';
  
            const cancelButton = document.createElement('button');
            cancelButton.textContent = 'Cancel';
            cancelButton.style.backgroundColor = '#FF6B6B';
            cancelButton.style.color = 'white';
            cancelButton.style.border = 'none';
            cancelButton.style.padding = '10px 20px';
            cancelButton.style.borderRadius = '5px';
            cancelButton.style.cursor = 'pointer';
  
            cancelButton.addEventListener('click', () => {
                document.body.removeChild(popup);
            });
  
            confirmButton.addEventListener('click', () => {
                const requestId = `${currentStation}-${Date.now()}`;
                
                const requestData = {
                    requestId: requestId,
                    requesterStation: currentStation,
                    timestamp: Date.now()
                };
  
                socket.emit('request_empty_pod', requestData);
                showConfirmationPopup('Empty Pod Request Sent Successfully!');
                document.body.removeChild(popup);
            });
  
            popup.appendChild(messageP);
            popup.appendChild(confirmButton);
            popup.appendChild(cancelButton);
            document.body.appendChild(popup);
        });
  
        // Listen for empty pod requests
        socket.on('empty_pod_request', function(data) {
            if (activeRequest || data.requesterStation === currentStation) return;
  
            reqPodStation.textContent = data.requesterStation;
            requestedCard.style.display = 'flex';
            activeRequest = data;
        });
  
        // Accept button handler
        acceptButton.addEventListener('click', function() {
            if (!activeRequest) return;
  
            const acceptanceData = {
                requestId: activeRequest.requestId,
                requesterStation: activeRequest.requesterStation,
                acceptorStation: currentStation
            };
  
            socket.emit('empty_pod_request_accepted', acceptanceData);
            requestedCard.style.display = 'none';
            activeRequest = null;
            showConfirmationPopup('Empty Pod Request Accepted!');
        });
  
        // Listen for request acceptances
        socket.on('empty_pod_request_accepted', function(data) {
            if (data.requesterStation === currentStation) {
                showConfirmationPopup(`Empty Pod Request Accepted by ${data.acceptorStation}`);
            }
            requestedCard.style.display = 'none';
            activeRequest = null;
        });
  
        // Socket event listeners
        socket.on('connect', function() {
            console.log('Dashboard connected to Socket.IO server');
            updateLiveTracking();
        });
  
        socket.on('connect_error', function(error) {
            console.error('Socket.IO connection error:', error);
        });
  
        socket.on('system_status_changed', function(data) {
            const dashboardBtn = document.getElementById("Dashboard-Btn");
            if (!dashboardBtn || !dashboardBtn.classList.contains("active")) {
                return;
            }
            updateLiveTracking();
        });
  
        socket.on('dispatch_event', function(data) {
            console.log('Dispatch event received:', data);
            updateLiveTracking();
        });
  
        // Initial update and periodic polling
        updateLiveTracking();
        setInterval(updateLiveTracking, 1000);
    });
  });