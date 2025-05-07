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
            break;
    }

  }

  function hideallelements() {
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
    dp_container.style.display = 'flex';
  }

  function showhistorypage(){
    hideallelements();
    history_container.style.display = 'flex';
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
  }

  function showcleardatapage(){
    hideallelements();
    cleardata_container.style.display = 'flex';
  }

  function getActiveButton() {
    let activeButton = document.querySelector(".nav-button.active"); // Get the active button
    return activeButton ? activeButton.id : null; // Return ID if found, otherwise null
}
  function shownotifications(){

  }
  document.addEventListener("DOMContentLoaded", function () {
    const socket = io(); // Ensure socket is connected after DOM is ready
  
    socket.on('system_status_changed', function (data) {
      console.log("system_status_changed received:", data);
      if (data.status === false) {
        console.log("Dispatch completed. Redirecting to Dispatch Page...");
        showdispatchpage();
      }
    });
  });

  
  