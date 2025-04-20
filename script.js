const trackingInfoBox = document.getElementById('tracking-info-id');
const standbyInfoBox = document.getElementById('standby-info-id');

const db_content =  document.getElementById('db-content-id');
const db_request = document.getElementById('db-requests-id');

const dp_container = document.getElementById('dispatch-container-id');

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
            //showdispatchpage();
            console.log("History Page");
            break;
        case "Maintainance-Btn":
            hideallelements();
            //showdispatchpage();
            console.log("Maintainance Page");
            break;
        case "ClearData-Btn":
            hideallelements();
            //showdispatchpage();
            console.log("ClearData Page");
            break;
        case "ScreenLock-Btn":
            hideallelements();
            //showdispatchpage();
            console.log("ScreenLock Page");
            break;
    }

  }

  function hideallelements(){
    db_content.style.display = 'none';
    db_request.style.display = 'none';
    trackingInfoBox.style.display = 'none';
    dp_container.style.display = 'none';
  }

  function showdashboardpage(){
    toggleTrackingInfo()
    db_content.style.display = 'flex';
    db_request.style.display = 'flex';
  }

  function showdispatchpage(){
    dp_container.style.display = 'flex';
  }