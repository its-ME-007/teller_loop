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


let state="standb"
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

    const acceptButton = document.querySelector(".accept");
    acceptButton.addEventListener("click", function () {
        alert("Request Accepted!");
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

  function hideallelements(){
    db_content.style.display = 'none';
    db_request.style.display = 'none';
    trackingInfoBox.style.display = 'none';
    dp_container.style.display = 'none';
    history_container.style.display = 'none';
    maintainance_container.style.display = 'none';
    cleardata_container.style.display = 'none';
    keypass_container.style.display = 'none';
    document.getElementById("kp-left-panel-cleardata-id").style.display = 'none';
    document.getElementById("kp-left-panel-maintainance-id").style.display = 'none';

    
  }

  function showdashboardpage(){
    toggleTrackingInfo()
    db_content.style.display = 'flex';
    db_request.style.display = 'flex';
  }

  function showdispatchpage(){
    dp_container.style.display = 'flex';
  }

  function showhistorypage(){
    history_container.style.display = 'flex';
  }

  function showkeypasspage(){
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
    maintainance_container.style.display = 'flex';
  }

  function showcleardatapage(){
    
    cleardata_container.style.display = 'flex';
  }

  function getActiveButton() {
    let activeButton = document.querySelector(".nav-button.active"); // Get the active button
    return activeButton ? activeButton.id : null; // Return ID if found, otherwise null
}
  function shownotifications(){

  }

