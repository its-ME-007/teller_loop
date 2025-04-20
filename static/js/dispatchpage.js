// Mapping of allowed IP addresses to station names
const ipToStation = {
  "192.168.90.8": "passthrough-station-1",
  "192.168.90.3": "passthrough-station-2",
  "192.168.90.6": "passthrough-station-3",
  "192.168.43.200": "passthrough-station-4"
};

let currentStationName = ""; // Will be set dynamically
let currentStationDisplay = ""; // Formatted station display (first and last char capitalized)
let currentStationNumber = 1; // Default station number
let selectedDestination = null; // Track the selected destination
let socket = null; // Socket.io connection
let dispatchAllowed = true; // Track if dispatching is allowed

// Helper function to format station display (first and last char capitalized)
function formatStationDisplay(stationName) {
  if (!stationName || stationName.length < 2) return "P1";
  
  const first = stationName.charAt(0).toUpperCase();
  const last = stationName.charAt(stationName.length - 1);
  return first + last;
}

// Initialize socket connection
document.addEventListener('DOMContentLoaded', function() {
  // Connect to Socket.IO server
  socket = io.connect(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  });
  
  socket.on('connect', function() {
    console.log('Connected to Socket.IO server');
    checkDispatchPermission();
  });
  
  socket.on('dispatch_queued', function(data) {
    console.log('Dispatch queued:', data);
    // Show clear feedback that the dispatch was queued successfully
    if (data.from && data.to) {
      const message = `Dispatch queued: From station ${data.from} to station ${data.to}, position ${data.position}`;
      // Create a notification element
      showNotification(message, 'success');
    }
  });
  
  socket.on('status', function(data) {
    console.log('Status update:', data);
  });
  
  socket.on('dispatch_rejected', function(data) {
    console.error('Dispatch rejected:', data);
    alert('Dispatch rejected: ' + data.reason);
    resetSlider();
    
    // Re-enable dispatch in case the UI got stuck
    setTimeout(() => {
      dispatchAllowed = true;
      updateDispatchUI();
    }, 1000);
  });
  
  socket.on('system_status_changed', function(data) {
    console.log('System status changed event received:', data);
    dispatchAllowed = !data.status;
    updateDispatchUI();
    
    // If status became false after our dispatch, it might have completed
    if (!data.status && !dispatchAllowed) {
      console.log('System status changed to standby');
      
      // Re-enable dispatch controls
      dispatchAllowed = true;
      updateDispatchUI();
    }
  });
  
  // Listen for dispatch_event which confirms dispatch was processed
  socket.on('dispatch_event', function(data) {
    console.log('Dispatch event confirmation received:', data);
    
    // Only process if this is about our station
    if (data.from == currentStationNumber) {
      showNotification(`Dispatch from ${data.from} to ${data.to} is now being processed!`, 'success');
    }
  });
});

// Function to check if dispatch is currently allowed
function checkDispatchPermission() {
  fetch('/api/check_dispatch_allowed')
    .then(response => response.json())
    .then(data => {
      console.log('Dispatch permission check:', data);
      dispatchAllowed = data.allowed;
      updateDispatchUI();
    })
    .catch(error => {
      console.error('Error checking dispatch permission:', error);
    });
}

// Function to update UI based on dispatch permission
function updateDispatchUI() {
  const slideButton = document.getElementById("slideToDispatch");
  const priorityToggle = document.getElementById("priorityToggle");
  const destinationButtons = document.querySelectorAll(".dp-destination");
  
  if (!dispatchAllowed) {
    // Add disabled class to elements
    slideButton.classList.add('disabled');
    priorityToggle.classList.add('disabled');
    destinationButtons.forEach(btn => btn.classList.add('disabled'));
    
    // Add temporary info message
    if (!document.querySelector('.dispatch-warning')) {
      const warningDiv = document.createElement('div');
      warningDiv.className = 'dispatch-warning';
      warningDiv.style.color = 'red';
      warningDiv.style.textAlign = 'center';
      warningDiv.style.padding = '10px';
      warningDiv.textContent = 'Dispatch not available: Another dispatch is in progress';
      const dispatchInfo = document.querySelector('.dispatch-info');
      if (dispatchInfo) {
        dispatchInfo.prepend(warningDiv);
      }
    }
  } else {
    // Remove disabled class from elements
    slideButton.classList.remove('disabled');
    priorityToggle.classList.remove('disabled');
    destinationButtons.forEach(btn => btn.classList.remove('disabled'));
    
    // Remove warning message if exists
    const warningDiv = document.querySelector('.dispatch-warning');
    if (warningDiv) {
      warningDiv.remove();
    }
  }
}

// First, get the client IP and determine the current station name
fetch('/api/get_client_ip')
  .then(response => response.json())
  .then(data => {
    const clientIP = data.ip;
    currentStationName = ipToStation[clientIP] || "passthrough-station-1"; // Default to station 1 if IP not found
    
    // Format station display (first and last char capitalized)
    currentStationDisplay = formatStationDisplay(currentStationName);
    
    // Extract station number from the name (e.g., "passthrough-station-1" -> 1)
    currentStationNumber = parseInt(currentStationName.split('-').pop()) || 1;

    const dpShowFromEl = document.querySelector('.dp-showstationFrom .dp-st-circle');
    if (dpShowFromEl) {
      dpShowFromEl.textContent = currentStationDisplay;
    }
        
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
      // Extract station number or use a default
      let stationNumber;
      if (idStr.includes('-')) {
        stationNumber = parseInt(idStr.split('-').pop()) || 1;
      } else {
        stationNumber = 1;
      }
      
      // Format station display for first and last character
      const displayId = formatStationDisplay(idStr);
      
      return {
        id: stationNumber,
        displayId: displayId,
        name: station.id
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
      numberDiv.textContent = dest.displayId;

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
        if (!dispatchAllowed) return;
        
        document.querySelectorAll(".dp-destination").forEach(el => el.classList.remove("active"));
        div.classList.add("active");
        dp_showtostation.style.border = "3.5px solid #32B34B";
        dp_station_number.style.border = "2px solid #32B34B";
        dp_station_number.style.color = "#32B34B";
        dp_showtostation.textContent = dest.displayId;
        dp_station_number.textContent = dest.displayId;
        dp_station_name.textContent = dest.name;
        
        // Store the selected destination
        selectedDestination = dest;
      };

      destinationList.appendChild(div);
    });
    
    // Check dispatch permission after loading destinations
    checkDispatchPermission();
  })
  .catch(error => console.error('Error fetching network architecture or client IP:', error));

// Priority toggle handler
let isPriorityHigh = false;
document.getElementById("priorityToggle").addEventListener("click", function() {
  if (!dispatchAllowed) return;
  
  this.classList.toggle("active");
  isPriorityHigh = this.classList.contains("active");
});

// Slide-to-Dispatch Button Code
let dp_isSliding = false;
const dp_slideButton = document.getElementById("slideToDispatch");
const dp_slideIcon = dp_slideButton.querySelector(".slide-icon");

// Set initial position explicitly
dp_slideIcon.style.left = "5px";

// Apply styling for better visibility during sliding
dp_slideIcon.style.position = "relative";
dp_slideIcon.style.zIndex = "5";
dp_slideIcon.style.cursor = "grab";

dp_slideButton.addEventListener("mousedown", function(event) {
  if (!dispatchAllowed) {
    alert("Dispatch is not available. Another dispatch is currently in progress.");
    return;
  }
  startSlide(event);
});

dp_slideButton.addEventListener("touchstart", function(event) {
  if (!dispatchAllowed) {
    alert("Dispatch is not available. Another dispatch is currently in progress.");
    return;
  }
  startSlide(event);
});

function resetSlider() {
  dp_slideIcon.style.transition = "left 0.5s ease";
  dp_slideIcon.style.left = "5px";
  setTimeout(() => {
    dp_slideIcon.style.transition = "";
  }, 500);
}

function startSlide(event) {
  event.preventDefault(); // Prevent default dragging behavior
  dp_isSliding = true;
  let startX = event.type === "mousedown" ? event.clientX : event.touches[0].clientX;
  
  // Remove any transition for smooth dragging
  dp_slideIcon.style.transition = "";
  
  // Change cursor while dragging
  dp_slideIcon.style.cursor = "grabbing";
  
  function moveSlide(e) {
    if (!dp_isSliding) return;
    let currentX = e.type === "mousemove" ? e.clientX : e.touches[0].clientX;
    let diff = Math.min(190, Math.max(0, currentX - startX));
    dp_slideIcon.style.left = `${5 + diff}px`;
  }

  function endSlide() {
    dp_isSliding = false;
    dp_slideIcon.style.cursor = "grab";
    
    if (parseInt(dp_slideIcon.style.left || "0") > 140) {
      // Complete slide animation
      dp_slideIcon.style.transition = "left 0.3s ease";
      dp_slideIcon.style.left = "190px";
      
      // Check if dispatch is still allowed
      if (!dispatchAllowed) {
        alert("Sorry, another dispatch was initiated while you were sliding. Please try again later.");
        resetSlider();
        return;
      }
      
      // Check if we have a valid destination selected
      if (selectedDestination && socket) {
        // Get the priority value
        const priority = isPriorityHigh ? 'high' : 'low';
        
        // Prepare the dispatch data
        const dispatchData = {
          from: currentStationName,
          to: selectedDestination.name,
          priority: priority
        };
        
        console.log("Sending dispatch:", dispatchData);
        
        // Update UI immediately to prevent multiple dispatches
        dispatchAllowed = false;
        updateDispatchUI();
        
        try {
          // Show custom notification instead of alert
          showNotification(`Dispatch from ${currentStationDisplay} to ${selectedDestination.displayId}`, 'success');
          
          // Emit the dispatch event
          socket.emit('dispatch', dispatchData);
          console.log("Dispatch event emitted successfully");
          
          // Force update system status for immediate feedback
          setTimeout(() => {
            // This will trigger a UI update in case the socket event is delayed
            fetch('/api/live_tracking')
              .then(response => response.json())
              .then(data => {
                console.log('Immediate tracking update after dispatch:', data);
                // Switch to dashboard view after successful dispatch
                const dashboardBtn = document.getElementById("Dashboard-Btn");
                if (dashboardBtn) {
                  dashboardBtn.click();
                }
              });
          }, 200);
        } catch (error) {
          console.error("Error sending dispatch:", error);
          showNotification("Error sending dispatch. Please try again.", 'error');
          dispatchAllowed = true;
          updateDispatchUI();
        }
        
        // Reset slider after 1 second
        setTimeout(() => {
          resetSlider();
        }, 1000);
      } else {
        showNotification("Please select a destination before dispatching.", 'error');
        resetSlider();
      }
    } else {
      // Smoothly reset slider even if threshold isn't met
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

// Function to show temporary notification
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  notification.style.position = 'fixed';
  notification.style.bottom = '20px';
  notification.style.right = '20px';
  notification.style.padding = '10px 20px';
  notification.style.borderRadius = '5px';
  notification.style.zIndex = '1000';
  
  // Set colors based on type
  if (type === 'success') {
    notification.style.backgroundColor = '#32B34B';
    notification.style.color = 'white';
  } else if (type === 'error') {
    notification.style.backgroundColor = '#FF3B30';
    notification.style.color = 'white';
  } else {
    notification.style.backgroundColor = '#007AFF';
    notification.style.color = 'white';
  }
  
  // Add to document
  document.body.appendChild(notification);
  
  // Remove after 5 seconds
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transition = 'opacity 0.5s ease';
    setTimeout(() => {
      document.body.removeChild(notification);
    }, 500);
  }, 5000);
}