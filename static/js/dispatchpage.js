let currentStationName = "";
let currentStationDisplay = "";
let currentStationNumber = 1;
let selectedDestination = null;
let socket = null;
let dispatchAllowed = true;
let podAvailable = false; // NEW
let isPriorityHigh = false;

function formatStationDisplay(stationName) {
  if (!stationName || stationName.length < 2) return "S1";
  //const first = stationName.charAt(0).toUpperCase();
  const first='P';
  const last = stationName.charAt(stationName.length - 1);
  return first + last;
}

document.addEventListener("DOMContentLoaded", function () {
  currentStationNumber = typeof STATION_ID !== "undefined" ? STATION_ID : 1;
  currentStationName = `station-${currentStationNumber}`;
  currentStationDisplay = formatStationDisplay(currentStationName);
  const dp_slideButton = document.getElementById("slideToDispatch");
  if (!dp_slideButton) return;
  const dpShowFromEl = document.querySelector('.dp-showstationFrom .dp-st-circle');
  if (dpShowFromEl) dpShowFromEl.textContent = currentStationDisplay;

  socket = io.connect(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  });
  let wasDisconnected = false;
  socket.on('connect', function () {
    console.log('Connected to Socket.IO server');
    if (wasDisconnected) {
    console.log('🔄 Reconnected — refreshing page...');
    location.reload(); // Full page refresh
  }
    socket.emit('join', { station_id: currentStationNumber });
    checkDispatchPermission();
    checkPodAvailability();
  });

  socket.on('disconnect', () => {
    console.log("⚠️ Socket disconnected");
    wasDisconnected = true; // Flag that we were disconnected
  });
    
  socket.on('dispatch_queued', function (data) {
    if (data.from && data.to) {
      showNotification(`Dispatch queued: From station ${data.from} to station ${data.to}`, 'success');
    }
  });

  socket.on('dispatch_failed', function (data) {
    alert('Dispatch failed: ' + data.reason);
    resetSlider();
    setTimeout(() => { dispatchAllowed = true; updateDispatchUI(); }, 1000);
  });



  socket.on('system_status_changed', function (data) {
    dispatchAllowed = !data.status;
    updateDispatchUI(data.current_dispatch);
  });

  socket.on('status', function (data) {
    console.log("Received status:", data);
    if (data.status === 'standby') {
      dispatchAllowed = true;
      updateDispatchUI();
    }
  });

  socket.on('dispatch_done', function (data) {
    dispatchAllowed = true;
    updateDispatchUI();
    showNotification(`Task ${data.task_id} completed!`, 'success');
  });

  // socket.on('pod_availability_changed', function ({ station_id, available }) {
  //   if (parseInt(station_id) === currentStationNumber) {
  //     const btn = document.getElementById("Dispatch-Btn");
  //     podAvailable = available;
  //     updateDispatchUI();
  //     if (available===true){
  //       if (!btn.classList.contains("active")) {
  //         console.log("Not in Dispatch Page");
  //         btn.click();
  //       }
  //       else{
  //         console.log("Already in Dispatch Page");
  //       }
  //     }
      
            
  //     console.log(`Pod availability updated: ${available}`);
  //   }
  // });
  
  socket.on('pod_availability_changed', function ({ station_id, available }) {
    if (parseInt(station_id) === currentStationNumber) {
      const btn = document.getElementById("Dispatch-Btn");
      console.log("Active button",getActiveButton());
      console.log("System State",state);
      podAvailable = available;
      updateDispatchUI();
      if (getActiveButton()!="Dispatch-Btn" && getActiveButton()!="Maintainance-Btn")
      { 
      if (available===true && state == "standby"){
          btn.click();
          console.log(`Pod availability updated: ${available}`);
        }
      }
      else{
      console.log("Pod Data Received but Ignored..!!"); 
    } 
    }
  });

  fetch('/api/network_architecture')
    .then(resp => resp.json())
    .then(data => {
      const stations = data.components.filter(c =>
        ["passthrough-station", "bottom-loading-station", "carrier-diverter", "carrier-diverter-with-tubing"].includes(c.type)
      );

      const destinations = stations.map(station => {
        const idStr = station.id;
        const stationNumber = parseInt(idStr.split('-').pop()) || 1;
        const displayId = formatStationDisplay(idStr);
        const name1 = idStr.replace('passthrough-', '');
        return { id: stationNumber, displayId: displayId, name: name1 };
       
      });

      const filteredDest = destinations.filter(dest => dest.name !== currentStationName);

      const destinationList = document.getElementById("dp-destinationList");
      const dp_station_name = document.getElementById("dp-to-station-name");
      const dp_station_number = document.getElementById("dp-to-station-number");
      const dp_showtostation = document.getElementById("dp-showtostation");

      if (!destinationList || !dp_station_name || !dp_station_number || !dp_showtostation) return;

      filteredDest.forEach(dest => {
        const div = document.createElement("div");
        div.classList.add("dp-destination");
        const stationNumber = parseInt(dest.name.split('-').pop());
        if (!isNaN(stationNumber) && stationNumber > 0) {
          dest.id = stationNumber;
          const div = document.createElement("div");
          div.classList.add("dp-destination");
          div.onclick = () => {
            if (!dispatchAllowed || !podAvailable) return;
            document.querySelectorAll(".dp-destination").forEach(el => el.classList.remove("active"));
            div.classList.add("active");
            dp_showtostation.textContent = dest.displayId;
            dp_showtostation.style.border = "3.5px solid #32B34B";
            dp_station_number.textContent = dest.displayId;
            dp_station_number.style.color = "#32B34B";
            dp_station_number.style.border = "2px solid #32B34B";
            dp_station_name.textContent = dest.name;
            selectedDestination = dest;
          };

          const innerDiv = document.createElement("div");
          innerDiv.classList.add("dp-content");
          const numberDiv = document.createElement("div");
          numberDiv.classList.add("dp-number");
          numberDiv.textContent = dest.displayId;
          const textSpan = document.createElement("span");
          textSpan.classList.add("dp-stationname");
          textSpan.textContent = dest.name;
          innerDiv.append(numberDiv, textSpan);
          div.appendChild(innerDiv);
          destinationList.appendChild(div);
        }
      });

      checkDispatchPermission();
    })
    .catch(err => console.error('Error loading architecture:', err));
});

function checkDispatchPermission() {
  fetch('/api/check_dispatch_allowed')
    .then(res => res.json())
    .then(data => {
      dispatchAllowed = data.allowed;
      updateDispatchUI();
    });
}

function checkPodAvailability() {
  fetch(`/api/check_pod_available/${currentStationNumber}`)
    .then(res => res.json())
    .then(data => {
      podAvailable = data.available;
      updateDispatchUI();
    })
    .catch(err => {
      console.error('Error checking pod availability:', err);
      podAvailable = false;
      updateDispatchUI();
    });
}

function updateDispatchUI(currentDispatch = null) {
  const slideButton = document.getElementById("slideToDispatch");
  const priorityToggle = document.getElementById("priorityToggle");
  const destinationButtons = document.querySelectorAll(".dp-destination");
  if (!slideButton) return;

  if (!dispatchAllowed || !podAvailable) {
    slideButton.classList.add('disabled');
    if (priorityToggle) priorityToggle.classList.add('disabled');
    destinationButtons.forEach(btn => btn.classList.add('disabled'));
    if (!podAvailable) {
      slideButton.querySelector('span').textContent = 'Please Place Pod in the station';
    } else {
      slideButton.querySelector('span').textContent = 'Slide to dispatch';
    }
  } else {
    slideButton.classList.remove('disabled');
    if (priorityToggle) priorityToggle.classList.remove('disabled');
    destinationButtons.forEach(btn => btn.classList.remove('disabled'));
    slideButton.querySelector('span').textContent = 'Slide to dispatch';
  }
}

const priorityToggle = document.getElementById("priorityToggle");
if (priorityToggle) {
  priorityToggle.addEventListener("click", function () {
    if (!dispatchAllowed || !podAvailable) return;
    this.classList.toggle("active");
    isPriorityHigh = this.classList.contains("active");
  });
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
