// Refactored dispatchpage.js with live tracking removed, proper dispatch lifecycle handling via backend status events, and using station ID

let currentStationName = "";
let currentStationDisplay = "";
let currentStationNumber = 1;
let selectedDestination = null;
let socket = null;
let dispatchAllowed = true;
let isPriorityHigh = false;

function formatStationDisplay(stationName) {
  if (!stationName || stationName.length < 2) return "P1";
  const first = stationName.charAt(0).toUpperCase();
  const last = stationName.charAt(stationName.length - 1);
  return first + last;
}

document.addEventListener("DOMContentLoaded", function () {
  currentStationNumber = typeof STATION_ID !== "undefined" ? STATION_ID : 1;
  currentStationName = `passthrough-station-${currentStationNumber}`;
  currentStationDisplay = formatStationDisplay(currentStationName);

  const dpShowFromEl = document.querySelector('.dp-showstationFrom .dp-st-circle');
  if (dpShowFromEl) dpShowFromEl.textContent = currentStationDisplay;

  socket = io.connect(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  });

  socket.on('connect', function () {
    console.log('Connected to Socket.IO server');
    socket.emit('join', { station_id: currentStationNumber });
    checkDispatchPermission();
  });
    
  socket.on('dispatch_queued', function (data) {
    if (data.from && data.to) {
      const message = `Dispatch queued: From station ${data.from} to station ${data.to}, position ${data.position}`;
      showNotification(message, 'success');
    }
  });

  socket.on('dispatch_rejected', function (data) {
    alert('Dispatch rejected: ' + data.reason);
    resetSlider();
    setTimeout(() => { dispatchAllowed = true; updateDispatchUI(); }, 1000);
  });

  socket.on('system_status_changed', function (data) {
    dispatchAllowed = !data.status;
    updateDispatchUI();
    if (!data.status && !dispatchAllowed) {
      dispatchAllowed = true;
      updateDispatchUI();
    }
  });

  socket.on('dispatch_event', function (data) {
    if (data.from == currentStationNumber) {
      showNotification(`Dispatch from ${data.from} to ${data.to} is now being processed!`, 'success');
    }
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
        return { id: stationNumber, displayId: displayId, name: station.id };
      });

      const filteredDest = destinations.filter(dest => dest.name !== currentStationName);

      const destinationList = document.getElementById("dp-destinationList");
      const dp_station_name = document.getElementById("dp-to-station-name");
      const dp_station_number = document.getElementById("dp-to-station-number");
      const dp_showtostation = document.getElementById("dp-showtostation");

      filteredDest.forEach(dest => {
        const div = document.createElement("div");
        div.classList.add("dp-destination");
        div.onclick = () => {
          if (!dispatchAllowed) return;
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

function updateDispatchUI() {
  const slideButton = document.getElementById("slideToDispatch");
  const priorityToggle = document.getElementById("priorityToggle");
  const destinationButtons = document.querySelectorAll(".dp-destination");

  if (!dispatchAllowed) {
    slideButton.classList.add('disabled');
    priorityToggle.classList.add('disabled');
    destinationButtons.forEach(btn => btn.classList.add('disabled'));
    if (!document.querySelector('.dispatch-warning')) {
      const warn = document.createElement('div');
      warn.className = 'dispatch-warning';
      warn.textContent = 'Dispatch not available: Another dispatch is in progress';
      warn.style.color = 'red';
      document.querySelector('.dispatch-info')?.prepend(warn);
    }
  } else {
    slideButton.classList.remove('disabled');
    priorityToggle.classList.remove('disabled');
    destinationButtons.forEach(btn => btn.classList.remove('disabled'));
    document.querySelector('.dispatch-warning')?.remove();
  }
}

document.getElementById("priorityToggle").addEventListener("click", function () {
  if (!dispatchAllowed) return;
  this.classList.toggle("active");
  isPriorityHigh = this.classList.contains("active");
});

const dp_slideButton = document.getElementById("slideToDispatch");
const dp_slideIcon = dp_slideButton.querySelector(".slide-icon");
dp_slideIcon.style.left = "5px";
dp_slideIcon.style.position = "relative";
dp_slideIcon.style.zIndex = "5";
dp_slideIcon.style.cursor = "grab";

let dp_isSliding = false;
dp_slideButton.addEventListener("mousedown", startSlide);
dp_slideButton.addEventListener("touchstart", startSlide);

function startSlide(event) {
  if (!dispatchAllowed) return alert("Dispatch unavailable right now.");
  event.preventDefault();
  dp_isSliding = true;
  let startX = event.clientX || event.touches[0].clientX;
  dp_slideIcon.style.transition = "";
  dp_slideIcon.style.cursor = "grabbing";

  function moveSlide(e) {
    if (!dp_isSliding) return;
    const currentX = e.clientX || e.touches[0].clientX;
    let diff = Math.min(190, Math.max(0, currentX - startX));
    dp_slideIcon.style.left = `${5 + diff}px`;
  }

  function endSlide() {
    dp_isSliding = false;
    dp_slideIcon.style.cursor = "grab";

    if (parseInt(dp_slideIcon.style.left || "0") > 140) {
      dp_slideIcon.style.left = "190px";
      if (!dispatchAllowed || !selectedDestination || !socket) {
        resetSlider();
        return alert("Invalid dispatch state");
      }

      const priority = isPriorityHigh ? 'high' : 'low';
      const dispatchData = {
        from: currentStationNumber,
        to: selectedDestination.id,
        priority: priority
      };

      dispatchAllowed = false;
      updateDispatchUI();
      showNotification(`Dispatch from ${currentStationDisplay} to ${selectedDestination.displayId}`, 'success');
      socket.emit('dispatch', dispatchData);

      setTimeout(resetSlider, 1000);
    } else {
      resetSlider();
    }

    document.removeEventListener("mousemove", moveSlide);
    document.removeEventListener("mouseup", endSlide);
    document.removeEventListener("touchmove", moveSlide);
    document.removeEventListener("touchend", endSlide);
  }

  document.addEventListener("mousemove", moveSlide);
  document.addEventListener("mouseup", endSlide);
  document.addEventListener("touchmove", moveSlide);
  document.addEventListener("touchend", endSlide);
}

function resetSlider() {
  dp_slideIcon.style.transition = "left 0.5s ease";
  dp_slideIcon.style.left = "5px";
  setTimeout(() => { dp_slideIcon.style.transition = ""; }, 500);
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
