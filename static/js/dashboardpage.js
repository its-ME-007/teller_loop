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

  function updateDashboardUI(data) {
    const systemStatus = data.system_status;
    const sender = data.sender;
    const receiver = data.receiver;
    const taskId = data.task_id;

    const standbyInfo = document.getElementById('standby-info-id');
    const trackingInfo = document.getElementById('tracking-info-id');
    const fromCircle = document.querySelector('.showstationFrom .circle');
    const toCircle = document.querySelector('.showstationTo .circle');
    const taskSpan = document.querySelector('.movement-disp .taskid');
    const dbContent = document.getElementById('db-content-id');
    const liveTracking = document.querySelector('.live-tracking');

    const dashboardBtn = document.getElementById("Dashboard-Btn");
    if (!dashboardBtn || !dashboardBtn.classList.contains("active")) return;

    if (systemStatus === true) {
      function formatFirstAndLast(word) {
        if (!word || word.length < 2) return word.toUpperCase();
        return word.charAt(0).toUpperCase() + word.charAt(word.length - 1).toUpperCase();
      }

      if (fromCircle) fromCircle.textContent = formatFirstAndLast(sender || '');
      if (toCircle) toCircle.textContent = formatFirstAndLast(receiver || '');
      if (taskSpan) taskSpan.textContent = 'Task ID: ' + (taskId || '');

      if (standbyInfo) standbyInfo.style.display = 'none';
      if (trackingInfo) trackingInfo.style.display = 'flex';
      if (liveTracking) liveTracking.style.display = 'flex';
      if (dbContent) dbContent.style.display = 'flex';

      startArrowBlinking();

      if ((!sender || !receiver) && systemStatus) {
        setTimeout(() => {
          fetch('/api/get_dispatch_history')
            .then(response => response.json())
            .then(history => {
              if (history && history.length > 0) {
                const latestDispatch = history[0];
                if (fromCircle) fromCircle.textContent = formatFirstAndLast(latestDispatch.from || '');
                if (toCircle) toCircle.textContent = formatFirstAndLast(latestDispatch.to || '');
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
    const acceptButton = requestedCard.querySelector('.accept');
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
        requesterStation: currentStation,
        timestamp: Date.now()
      };
      socket.emit('request_empty_pod', requestData);
      showConfirmationPopup('Empty Pod Request Sent Successfully!');
    });

    socket.on('empty_pod_request', function (data) {
      if (activeRequest || data.requesterStation === currentStation) return;
      reqPodStation.textContent = formatStationDisplay(data.requesterStation);
      requestedCard.style.display = 'flex';
      activeRequest = data;
    });

    acceptButton.addEventListener('click', function () {
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

    socket.on('empty_pod_request_accepted', function (data) {
      if (data.requesterStation === currentStation) {
        showConfirmationPopup(`Empty Pod Request Accepted by ${data.acceptorStation}`);
      }
      requestedCard.style.display = 'none';
      activeRequest = null;
    });

    socket.on('connect', function () {
      console.log('Dashboard connected to Socket.IO server');
    });

    socket.on('connect_error', function (error) {
      console.error('Socket.IO connection error:', error);
    });

    socket.on('system_status_changed', function (data) {
      const dashboardBtn = document.getElementById("Dashboard-Btn");
      if (!dashboardBtn || !dashboardBtn.classList.contains("active")) return;
      updateDashboardUI(data);
    });

    socket.on('dispatch_event', function (data) {
      console.log('Dispatch event received:', data);
      updateDashboardUI(data);
    });
  });
});
