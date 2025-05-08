// Refactored dashboardpage.js to use station ID from backend instead of IP mapping

document.addEventListener('DOMContentLoaded', function() {
  let currentStation = 'Unknown-Station';
  let currentStationDisplay = '';
  let availableStations = [];
  let activeRequest = null;

  // Helper function to format station display
  function formatStationDisplay(stationName) {
    if (!stationName || stationName.length < 2) return stationName.toUpperCase();
    return stationName.charAt(0).toUpperCase() + stationName.charAt(stationName.length - 1).toUpperCase();
  }

  let arrowBlinkInterval;
  let toggleBlink = true;

  function fetchCurrentStation() {
    if (typeof STATION_ID !== 'undefined') {
      currentStation = `passthrough-station-${STATION_ID}`;
      currentStationDisplay = formatStationDisplay(currentStation);
      localStorage.setItem('stationUsername', currentStation);
      localStorage.setItem('stationDisplay', currentStationDisplay);
      return Promise.resolve(currentStation);
    } else {
      console.warn('STATION_ID not defined. Falling back to passthrough-station-1');
      currentStation = 'passthrough-station-1';
      currentStationDisplay = formatStationDisplay(currentStation);
      return Promise.resolve(currentStation);
    }
  }

  function fetchNetworkArchitecture() {
    return fetch('/api/network_architecture')
      .then(response => response.json())
      .then(data => {
        availableStations = data.components
          .filter(component => component.type === "passthrough-station" || component.type === "bottom-loading-station")
          .map(station => ({ id: station.id, displayId: formatStationDisplay(station.id) }));
        return availableStations;
      })
      .catch(error => {
        console.error('Error fetching network architecture:', error);
        return [];
      });
  }

  

  function startArrowBlinking() {
    const arrows = document.querySelectorAll('.arrow');
    if (arrowBlinkInterval || arrows.length === 0) return;

    arrows.forEach(arrow => {
      arrow.style.opacity = 1;
      arrow.style.fill = '#32B34B';
    });

    arrowBlinkInterval = setInterval(() => {
      arrows.forEach((arrow, index) => {
        arrow.style.opacity = (index % 2 === (toggleBlink ? 0 : 1)) ? 1 : 0;
      });
      toggleBlink = !toggleBlink;
    }, 500);
  }

  function stopArrowBlinking() {
    const arrows = document.querySelectorAll('.arrow');
    if (arrowBlinkInterval) {
      clearInterval(arrowBlinkInterval);
      arrowBlinkInterval = null;
    }
    arrows.forEach(arrow => {
      arrow.style.opacity = 1;
      arrow.style.fill = '#32B34B';
    });
  }

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
    messageP.style.color = 'black';
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
  

    const socket = io.connect(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  });

  Promise.all([fetchCurrentStation(), fetchNetworkArchitecture()]).then(([station, stations]) => {
    const sendEmptyPodButton = document.querySelector('.request-card .send-button');
    const requestedCard = document.querySelector('.requested-card');
    const reqPodStation = document.querySelector('.req-pod-station');
    const abortButton = document.querySelector('.abort-button');

    if (abortButton) {
      abortButton.addEventListener('click', function () {
        if (confirm('Are you sure you want to abort the current dispatch?')) {
          socket.emit('dispatch_completed', {
            type: 'dispatch_completed',
            aborted: true
          });
          updateDashboardUI({ system_status: false });
        }
      });
    }

    sendEmptyPodButton.addEventListener('click', function () {
      const requestId = `${currentStation}-${Date.now()}`;
      const requestData = {
        requestId: requestId,
        requesterStation:currentStation,
        timestamp: Date.now()
      };
     socket.emit('request_empty_pod', requestData);
      showConfirmationPopup('Empty Pod Request Sent Successfully!');
    });

    socket.on('empty_pod_request', function(data) {
      const fromStation = data.requesterStation;
      const stationNumber = fromStation.split('-').pop(); // gets '1' from 'passthrough-station-1'
    
      const requestCircle = document.querySelector('.req-pod-station');
      if (requestCircle) {
        requestCircle.textContent = stationNumber;
        console.log(`Empty pod request received from: Station ${stationNumber}`);
      } else {
        console.warn("Could not find .req-pod-station element!");
      }
      activeRequest = data;
      if (typeof showdashboardpage === 'function') {
        console.log("🔁 Redirecting to dashboard due to new pod request...");
        showdashboardpage();
      }
    });
    const acceptButton = document.querySelector(".accept");

if (acceptButton) {
  console.log("✅ Accept button found after Promise, adding listener.");

  acceptButton.addEventListener('click', function () {
    if (!activeRequest) return; // Check if request is there

    const acceptanceData = {
      requestId: activeRequest.requestId,
      requesterStation: activeRequest.requesterStation,
      acceptorStation: currentStation
    };

    socket.emit('empty_pod_request_accepted', acceptanceData); // Emit event to server

    const requestCircle = document.querySelector('.req-pod-station');
    if (requestCircle) {
      requestCircle.textContent = '';  // 🔥 Clear the circle on Accept
    }

    activeRequest = null; // Clear own active request

    showConfirmationPopup('✅ Empty Pod Request Accepted!');
    if (typeof showdispatchpage === 'function') {
      showdispatchpage();
    
      setTimeout(() => {
          if (typeof setDispatchCircles === 'function') {
            setDispatchCircles(acceptanceData.requesterStation, acceptanceData.acceptorStation);
          }
        }, 200);
        
      
    }
    
  });
} else {
  console.log("❌ Accept button NOT found after Promise!");
}

  //NEW FUCNTION FOR OTEHR STATIOSN REQUEST CARD
  socket.on('empty_pod_request_accepted', function (data) {
    const requestCircle = document.querySelector('.req-pod-station');
    if (requestCircle) {
      requestCircle.textContent = ''; // 🔥 Clear the circle on all stations
    }
  
    activeRequest = null; // 🔥 Reset activeRequest on all stations
  
    if (data.requesterStation === currentStation) {
      showConfirmationPopup(`✅ Your Request was Accepted by ${data.acceptorStation}`);
    }
  });
  
    
    socket.on('station_dispatch_started', function(data) {
      console.log("Dispatch triggered by station", data.from);
      if (typeof showdashboardpage === 'function') showdashboardpage();
      const abortButton = document.querySelector('.abort-button');
      
    });
    
    socket.on('connect', function () {
      console.log('Dashboard connected to Socket.IO server');
    });
    

    socket.on('connect_error', function (error) {
      console.error('Socket.IO connection error:', error);
    });

    socket.on('system_status_changed', function (data) {
      console.log("🛰️ System status changed:", data);
    
      // ✅ Always switch to Dashboard if dispatch starts
      if (data.status === true && typeof showdashboardpage === 'function') {
        console.log("🚨 Dispatch started. Switching to Dashboard...");
        showdashboardpage();
      }
    
      // Update the UI regardless of whether we switched
      if (typeof updateDashboardUI === 'function') {
        updateDashboardUI(data);
      }
    });
    

    socket.on('dispatch_event', function (data) {
      console.log('Dispatch event received:', data);
      updateDashboardUI(data);
    
    });
  });
});
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
  console.log("Upadting dahsboard UI with system status:",systemStatus,"sender",sender,"reciever",receiver,"taskid",taskId);
  // Only update UI if we're on the dashboard page
  const dashboardBtn = document.getElementById("Dashboard-Btn");
 // if (!dashboardBtn || !dashboardBtn.classList.contains("active")) {
 //   console.log("INISIDE !DASHBOARD");
  //  return;
  //}

  if (systemStatus === true) {
    console.log("INSIDE systemStatus is true");
    // Active dispatch mode      
    if (fromCircle) fromCircle.textContent = (sender || '');
    if (toCircle) toCircle.textContent = (receiver || '');
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
              if (fromCircle) fromCircle.textContent = (latestDispatch.from || '');
              if (toCircle) toCircle.textContent = (latestDispatch.to || '');
              if (taskSpan) taskSpan.textContent = 'Task ID: ' + (latestDispatch.task_id || '');
            }
          })
          .catch(error => console.error('Error fetching history:', error));
      }, 2500);
    }
  } else {
    // Standby mode
    console.log("INSIDE STANDBY MODE");
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






