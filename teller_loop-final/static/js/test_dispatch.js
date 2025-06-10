// Mapping of allowed IP addresses to station names
const ipToStation = {
  "192.168.43.87": "passthrough-station-1",
  "192.168.43.251": "passthrough-station-2",
  "192.168.43.61": "passthrough-station-3",
  "192.168.43.200": "passthrough-station-4"
};

let currentStationName = ""; // Will be set dynamically
let selectedDestination = null;
let socket = null;

// Initialize Socket.IO connection
function initializeSocket(pageId) {
  // Connect to Socket.IO server
  socket = io();

  // Join the room for this page
  socket.emit('join', pageId);

  // Listen for status updates
  socket.on('status', function(data) {
    console.log('Status update received:', data);
    // Update UI based on status if needed
    if (data.status === 'sending') {
      console.log(`Sending to station ${data.destination}`);
    } else if (data.status === 'receiving') {
      console.log(`Receiving from station ${data.source}`);
    } else if (data.status === 'standby') {
      console.log('Station is on standby');
    }
  });

  // Listen for dispatch queue updates
  socket.on('dispatch_queued', function(data) {
    console.log(`Dispatch queued: from ${data.from} to ${data.to}, position ${data.position}`);
    alert(`Dispatch queued! Position in queue: ${data.position}`);
  });

  console.log('Socket.IO initialized and connected');
}

// First, get the client IP and determine the current station name
fetch('/api/get_client_ip')
  .then(response => response.json())
  .then(data => {
    const clientIP = data.ip;
    currentStationName = ipToStation[clientIP] || "passthrough-station-1"; // Default to station 1 if IP not found
    
    // Extract station number from the name
    const stationNumber = currentStationName.split('-').pop();
    
    const dpShowFromEl = document.querySelector('.dp-showstationFrom .dp-st-circle');
    if (dpShowFromEl) {
      // Set the first letter capitalized and the station number
      dpShowFromEl.textContent = currentStationName[0].toUpperCase() + stationNumber;
    }
    
    // Initialize Socket.IO with the station number as the page ID
    initializeSocket(stationNumber);
        
    // Now fetch the network architecture to build the destination list
    return fetch('/api/network_architecture');
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return response.json();
  })
  .then(data => {
    // Filter for only the stations from the components
    const stations = data.components.filter(component =>
      component.type === "passthrough-station" ||
      component.type === "bottom-loading-station" ||
      component.type === "carrier-diverter-with-tubing" ||
      component.type === "carrier-diverter"
    );

    // Create the destinations array using each station's id as both id and name
    const destinations = stations.map(station => {
      const idStr = station.id;
      const stationNumber = idStr.split('-').pop();
      // Create a custom id by capitalizing the first letter and appending the station number
      const customId = idStr[0].toUpperCase() + stationNumber;
      
      return {
        id: customId,
        name: station.id,
        stationNumber: stationNumber
      };
    });

    // Filter out the current station from the destination list
    const filteredDestinations = destinations.filter(dest => dest.name !== currentStationName);
    
    // Populate the destination list (destination buttons)
    const destinationList = document.getElementById("dp-destinationList");
    const dp_station_name = document.getElementById("dp-to-station-name");
    const dp_station_number = document.getElementById("dp-to-station-number");
    const dp_showtostation = document.getElementById("dp-showtostation");
    
    filteredDestinations.forEach(dest => {
      let div = document.createElement("div");
      div.classList.add("dp-destination");

      // Create a wrapper for number and text
      let innerDiv = document.createElement("div");
      innerDiv.classList.add("dp-content");

      // Create number div
      let numberDiv = document.createElement("div");
      numberDiv.classList.add("dp-number");
      numberDiv.textContent = dest.id;

      // Create text span
      let textSpan = document.createElement("span");
      textSpan.classList.add("dp-stationname");
      textSpan.textContent = dest.name;

      // Append number and text to the inner div
      innerDiv.appendChild(numberDiv);
      innerDiv.appendChild(textSpan);

      // Append inner div to main button div
      div.appendChild(innerDiv);

      div.onclick = function() {
        document.querySelectorAll(".dp-destination").forEach(el => el.classList.remove("active"));
        div.classList.add("active");
        dp_showtostation.style.border = "3.5px solid #32B34B";
        dp_station_number.style.border = "2px solid #32B34B";
        dp_station_number.style.color = "#32B34B";
        dp_showtostation.textContent = dest.id;
        dp_station_number.textContent = dest.id;
        dp_station_name.textContent = dest.name;
        
        // Store selected destination
        selectedDestination = {
          id: dest.stationNumber,
          name: dest.name
        };
      };

      destinationList.appendChild(div);
    });
  })
  .catch(error => console.error('Error fetching network architecture or client IP:', error));

// Priority toggle handler
let isPriorityHigh = false;
document.getElementById("priorityToggle").addEventListener("click", function() {
  this.classList.toggle("active");
  isPriorityHigh = this.classList.contains("active");
});

// Function to send dispatch request
function sendDispatchRequest() {
  if (!socket || !selectedDestination) {
    alert("Please select a destination first!");
    return false;
  }
  
  // Extract source station number from currentStationName
  const sourceNumber = parseInt(currentStationName.split('-').pop());
  const destinationNumber = parseInt(selectedDestination.id);
  
  // Prepare dispatch data
  const dispatchData = {
    from: sourceNumber,
    to: destinationNumber,
    priority: isPriorityHigh ? 'high' : 'low'
  };
  
  console.log("Sending dispatch request:", dispatchData);
  
  // Send dispatch request via Socket.IO
  socket.emit('dispatch', dispatchData);
  
  return true;
}

// Slide-to-Dispatch Button Code
let isSliding = false;
const slideButton = document.getElementById("slideToDispatch");
const slideIcon = slideButton.querySelector(".slide-icon");

slideButton.addEventListener("mousedown", startSlide);
slideButton.addEventListener("touchstart", startSlide);

function startSlide(event) {
  isSliding = true;
  let startX = event.type === "mousedown" ? event.clientX : event.touches[0].clientX;
  
  function moveSlide(e) {
    if (!isSliding) return;
    let currentX = e.type === "mousemove" ? e.clientX : e.touches[0].clientX;
    let diff = Math.min(190, Math.max(0, currentX - startX));
    slideIcon.style.left = `${5 + diff}px`;
  }

  function endSlide() {
    isSliding = false;
    if (parseInt(slideIcon.style.left) > 140) {
      slideIcon.style.left = "190px";
      setTimeout(() => {
        // Send dispatch request
        if (sendDispatchRequest()) {
          alert("Dispatch request sent!");
        }

        // Smoothly reset slider after a 1-second delay
        slideIcon.style.transition = "left 0.5s ease";
        slideIcon.style.left = "5px";
        setTimeout(() => {
          slideIcon.style.transition = "";
        }, 500);
      }, 1000);
    } else {
      // Smoothly reset slider even if threshold isn't met
      slideIcon.style.transition = "left 0.5s ease";
      slideIcon.style.left = "5px";
      setTimeout(() => {
        slideIcon.style.transition = "";
      }, 500);
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