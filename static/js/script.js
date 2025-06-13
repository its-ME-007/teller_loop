const trackingInfoBox = document.getElementById('tracking-info-id');
const standbyInfoBox = document.getElementById('standby-info-id');

const db_content =  document.getElementById('db-content-id');
const db_request = document.getElementById('db-requests-id');

const dp_container = document.getElementById('dispatch-container-id');
const history_container = document.getElementById('history-container-id');
const maintainance_container = document.getElementById('maintainance-container-id');
const cleardata_container = document.getElementById('cleardata-container-id');
const keypass_container = document.getElementById('keypass-container-id');
const keypass_ActionIcon = document.getElementById('KeypassActionIcon');


let state="standby"
function toggleTrackingInfo() {
    console.log("Check..")
    if (state=="standby") {
      trackingInfoBox.style.display = 'none'; // Show the div
      standbyInfoBox.style.display = 'flex';
    } else {
      trackingInfoBox.style.display = 'flex'; // Hide the div
      standbyInfoBox.style.display = 'none';
    }
  }
  
  document.addEventListener("DOMContentLoaded", function () {
    const buttons = document.querySelectorAll(".nav-button");
    
    buttons.forEach(button => {
        button.addEventListener("click", function () {
            buttons.forEach(btn => btn.classList.remove("active"));
            this.classList.add("active");
            toggleScreensOnClick(this.id);
        });
    });

    const abortButton = document.querySelector(".abort-button");
    abortButton.addEventListener("click", function () {
        alert("Task Aborted!");
    });

    
});

function toggleScreensOnClick(buttonid) {
    // If leaving maintenance page, log logout
    if (document.getElementById('maintainance-container-id').style.display === 'flex') {
        console.log("Logged out of :Maintenance page");
    }
    if (
      document.getElementById('maintainance-container-id')?.style.display === 'flex' &&  // user is currently in maintenance
      buttonid !== "Maintainance-Btn" &&                                                 // clicked a different button
      typeof socket !== 'undefined' &&
      window.STATION_ID
    ) {
      socket.emit('maintenance_exited', { station_id: window.STATION_ID });
    }



    console.log("Check..",buttonid)
    switch (buttonid){
        case "Dispatch-Btn":
            hideallelements();
            showdispatchpage();
            console.log("Dispatch Page");
            break;
        case "Dashboard-Btn":
            hideallelements();
            showdashboardpage();
            console.log("DashBoard Page");
            break;
        case "History-Btn":
            hideallelements();
            showhistorypage();
            console.log("History Page");
            break;
        case "Maintainance-Btn":
            hideallelements();
            showkeypasspage();
            console.log("Maintainance Page");
            break;
        case "ClearData-Btn":
            hideallelements();
            showkeypasspage();
            console.log("ClearData Page");
            break;
        case "ScreenLock-Btn":
            hideallelements();
            shownotifications();
            console.log("ScreenLock Page");
            window.location.href = "/"; // Redirect to the root route
            break;
    }

  }

  function hideallelements() {
    if (maintainance_container && maintainance_container.style.display !== 'none') {
      if (typeof socket !== 'undefined' && window.STATION_ID) {
        console.log(" Sending maintenance_exited");
        socket.emit('maintenance_exited', { station_id: window.STATION_ID });
      }
    }

    // Do NOT hide dashboard elements — they are toggled in showdashboardpage
    if (db_content) db_content.style.display = 'none';
    if (db_request) db_request.style.display = 'none';
    if (trackingInfoBox) trackingInfoBox.style.display = 'none';
    if (dp_container) dp_container.style.display = 'none';
    if (history_container) history_container.style.display = 'none';
    if (maintainance_container) maintainance_container.style.display = 'none';
    if (cleardata_container) cleardata_container.style.display = 'none';
    if (keypass_container) keypass_container.style.display = 'none';
  
    // Clear left panel additions if any
    const clearLeftPanel = document.getElementById("kp-left-panel-cleardata-id");
    if (clearLeftPanel) clearLeftPanel.style.display = 'none';
  
    const maintainLeftPanel = document.getElementById("kp-left-panel-maintainance-id");
    if (maintainLeftPanel) maintainLeftPanel.style.display = 'none';
  }
  

  window.showdashboardpage = function () {
    hideallelements();
    db_content.style.display = 'flex';
    db_request.style.display = 'flex';
    setActiveNav("Dashboard");
  
    fetch('/api/live_tracking')
      .then(response => response.json())
      .then(data => {
        console.log("Live Tracking Data:", data);
        state = data.system_status === true ? "active" : "standby";
        toggleTrackingInfo();
        if (typeof updateDashboardUI === 'function') updateDashboardUI(data);
      })
      .catch(error => console.error("Error fetching live tracking:", error));
  };

  function showdispatchpage(){
    hideallelements();
    
    if (window.STATION_ID !== 0) {
      checkDispatchPermission();
      checkPodAvailability();
  }
    dp_container.style.display = 'flex';
    setActiveNav("Dispatch");
  }

  function showhistorypage(){
    hideallelements();
    if (history_container) {
      history_container.style.display = 'block';  // Changed from 'flex' to 'block'
      console.log("History container displayed:", history_container.style.display);
  } else {
      console.error("History container not found");
  }setActiveNav("History");
  }

  function showkeypasspage(){
    hideallelements();
    if (getActiveButton()=="Maintainance-Btn"){
      document.getElementById("kp-left-panel-maintainance-id").style.display = 'flex';
      keypass_container.style.display = 'flex';
     }
    if (getActiveButton()=="ClearData-Btn"){
      document.getElementById("kp-left-panel-cleardata-id").style.display = 'flex';
      keypass_container.style.display = 'flex';
     }
  }
  
  function showmaintainancepage(){
    hideallelements();
    maintainance_container.style.display = 'flex';
    setActiveNav("Maintainance");
    if (typeof socket !== 'undefined' && window.STATION_ID) {
      console.log("Sending maintenance_enetred");
    socket.emit('maintenance_entered', { station_id: window.STATION_ID });
  }
  }

  function showcleardatapage(){
    hideallelements();
    cleardata_container.style.display = 'flex';
    setActiveNav("Clear Data");
  }

  function getActiveButton() {
    let activeButton = document.querySelector(".nav-button.active"); // Get the active button
    return activeButton ? activeButton.id : null; // Return ID if found, otherwise null
}
  function shownotifications(){

  }
  document.addEventListener("DOMContentLoaded", function () {
    const socket = io(); // Ensure socket is connected after DOM is ready

    let wasDisconnected = false;
  socket.on('notify_maintenance_entered', function(data) {
  if (data.station_id !== window.STATION_ID) {  //  don't alert self
    alert(`Station ${data.station_id} has entered Maintenance Mode`);
  }
});


socket.on('notify_maintenance_exited', function(data) {
  if (data.station_id !== window.STATION_ID) {  // don't alert self
    alert(`Station ${data.station_id} has exited Maintenance Mode`);
  }
});


  socket.on('disconnect', () => {
    console.warn("⚠️ Socket disconnected");
    wasDisconnected = true; // Flag that we were disconnected
  });

  socket.on('connect', () => {
    console.log("✅ Socket connected");
    if (wasDisconnected) {
      // Reconnected after a disconnection
      console.log("🔄 Reconnected — refreshing page...");
      location.reload(); // Refresh the page
    }
  });
  
    socket.on('receiver_ack_completed', function (data) {
      console.log("✅ Receiver ACK received:", data);
      showdispatchpage();  // ✅ Redirect to dispatch page only after receiver ACK
    });
  });
  window.setDispatchCircles = function (requesterStation, acceptorStation) {
    const fromEl = document.querySelector('.dp-showstationFrom .dp-st-circle'); // LEFT
    const toEl = document.getElementById('dp-showtostation');                   // RIGHT
    const stationNumberEl = document.getElementById('dp-to-station-number');
    const stationNameEl = document.getElementById('dp-to-station-name');
  
    const formatDisplay = (station) => {
      if (!station) return '';
      return 'P' + station.split('-').pop();
    };
  
    const sender = formatDisplay(acceptorStation);     // this station
    const receiver = formatDisplay(requesterStation);  // requested one
  
    const receiverNumber = parseInt(requesterStation.split('-').pop());
  
    // ✅ VISUAL UPDATE
    if (fromEl) fromEl.textContent = sender;
    if (toEl) {
      toEl.textContent = receiver;
      toEl.style.setProperty("border", "3.5px solid #32B34B", "important");
    }
  
    if (stationNumberEl) {
      stationNumberEl.textContent = receiver;
      stationNumberEl.style.color = "#32B34B";
      stationNumberEl.style.border = "2px solid #32B34B";
    }
  
    if (stationNameEl) stationNameEl.textContent = requesterStation;
  
    // ✅ FUNCTIONAL UPDATE: make dispatch work
    if (typeof selectedDestination !== 'undefined') {
      selectedDestination = {
        id: receiverNumber,
        displayId: receiver,
        name: requesterStation
      };
      console.log("✅ selectedDestination set:", selectedDestination);
    } else {
      console.warn("❌ selectedDestination not defined globally.");
    }
  
    console.log(`✅ Dispatch Circles updated: ${sender} → ${receiver}`);
  };
  function setActiveNav(pageName) {
    const buttons = document.querySelectorAll('.nav-button');
    buttons.forEach(btn => btn.classList.remove('active'));
  
    const targetBtn = document.getElementById(`${pageName}-Btn`);
    if (targetBtn) {
      targetBtn.classList.add('active');
    }
  }

  
  
  
  
  
  

  
  