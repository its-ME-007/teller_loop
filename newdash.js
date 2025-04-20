// Function to fetch live tracking info and update the dashboard
function updateLiveTracking() {
  console.log('Fetching live tracking data...');
  fetch('/api/live_tracking')
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok: ' + response.statusText);
      }
      return response.json();
    })
    .then(data => {
      console.log('Live tracking data received:', data);
      updateDashboardUI(data);
    })
    .catch(error => {
      console.error('Error fetching live tracking data:', error);
      // Still try to update UI with default standby mode on error
      updateDashboardUI({system_status: false});
    });
}

// Function to update the dashboard UI based on tracking data
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
  const dbRequest = document.getElementById('db-requests-id');
  const liveTracking = document.querySelector('.live-tracking');

  // Only update UI if we're on the dashboard page
  const dashboardBtn = document.getElementById("Dashboard-Btn");
  if (!dashboardBtn || !dashboardBtn.classList.contains("active")) {
    return;
  }

  // Update UI based on system status
  if (systemStatus === true) {
    // Active dispatch mode
    function formatFirstAndLast(word) {
      if (!word || word.length < 2) return word.toUpperCase();
      return word.charAt(0).toUpperCase() + word.charAt(word.length - 1).toUpperCase();
    }
    
    if (fromCircle) fromCircle.textContent = formatFirstAndLast(sender || '');
    if (toCircle) toCircle.textContent = formatFirstAndLast(receiver || '');
    if (taskSpan) taskSpan.textContent = 'Task ID: ' + (taskId || '');
    
    // Show tracking info, hide standby immediately
    if (standbyInfo) {
      standbyInfo.style.display = 'none';
    }
    if (trackingInfo) {
      trackingInfo.style.display = 'flex';
    }
    if (liveTracking) {
      liveTracking.style.display = 'flex';
    }
    if (dbContent) {
      dbContent.style.display = 'flex';
    }
    startArrowBlinking();
    
    // If we don't have sender/receiver info, try to fetch from history
    if ((!sender || !receiver) && systemStatus) {
      setTimeout(() => {
        fetch('/api/get_dispatch_history')
          .then(response => response.json())
          .then(history => {
            if (history && history.length > 0) {
              const latestDispatch = history[0];
              if (fromCircle) fromCircle.textContent = latestDispatch.from || '';
              if (toCircle) toCircle.textContent = latestDispatch.to || '';
              if (taskSpan) taskSpan.textContent = 'Task ID: ' + (latestDispatch.task_id || '');
            }
          })
          .catch(error => console.error('Error fetching history:', error));
      }, 2500); // Delay of 2.5 seconds
    }

    console.log('Dashboard showing active tracking mode');
  } else {
    // Standby mode
    if (fromCircle) fromCircle.textContent = '';
    if (toCircle) toCircle.textContent = '';
    if (taskSpan) taskSpan.textContent = 'Task ID: ';
    
    // Show standby info, hide tracking immediately
    if (trackingInfo) {
      trackingInfo.style.display = 'none';
    }
    if (standbyInfo) {
      standbyInfo.style.display = 'flex';
    }
    if (liveTracking) {
      liveTracking.style.display = 'flex';
      liveTracking.style.flexDirection = 'column';
      liveTracking.style.gap = '0';
    }
    if (dbContent) {
      dbContent.style.gap = '20px';
    }
    stopArrowBlinking();
    
    console.log('Dashboard showing standby mode');
  }
}
  
// Variables to hold the interval for blinking arrows
let arrowBlinkInterval;
let toggleBlink = true;
  
// Start blinking the arrows alternately every 500 ms
function startArrowBlinking() {
  const arrows = document.querySelectorAll('.arrow');
  if (arrowBlinkInterval || arrows.length === 0) return; // Already blinking or no arrows found
  
  console.log('Starting arrow blinking animation');
  
  // First make all arrows visible and green
  arrows.forEach(arrow => {
    arrow.style.opacity = 1;
    arrow.style.fill = '#32B34B';
  });
  
  arrowBlinkInterval = setInterval(() => {
    arrows.forEach((arrow, index) => {
      // Alternate opacity: even-index arrow visible when toggleBlink is true, odd-index when false
      if (toggleBlink) {
        arrow.style.opacity = (index % 2 === 0) ? 1 : 0;
      } else {
        arrow.style.opacity = (index % 2 === 0) ? 0 : 1;
      }
    });
    toggleBlink = !toggleBlink;
  }, 500);
}
  
// Stop blinking and set arrows to static green
function stopArrowBlinking() {
  const arrows = document.querySelectorAll('.arrow');
  if (arrowBlinkInterval) {
    console.log('Stopping arrow blinking animation');
    clearInterval(arrowBlinkInterval);
    arrowBlinkInterval = null;
  }
  arrows.forEach(arrow => {
    arrow.style.opacity = 1;
    arrow.style.fill = '#32B34B';  // Set to static green color
  });
}
  
// Set up socket connection and event listeners
document.addEventListener('DOMContentLoaded', function() {
  console.log('Dashboard initializing...');
  
  // Set initial UI state - default to standby mode immediately
  const standbyInfo = document.getElementById('standby-info-id');
  const trackingInfo = document.getElementById('tracking-info-id');
  const dbContent = document.getElementById('db-content-id');
  
  if (standbyInfo) {
    standbyInfo.style.display = 'flex';
    standbyInfo.style.height = 'auto';
  }
  if (trackingInfo) {
    trackingInfo.style.display = 'none';
    trackingInfo.style.height = '0';
  }
  if (dbContent) {
    dbContent.style.gap = '0';
  }
  
  // Initialize empty circles and task ID right away
  const fromCircle = document.querySelector('.showstationFrom .circle');
  const toCircle = document.querySelector('.showstationTo .circle');
  const taskSpan = document.querySelector('.movement-disp .taskid');
  
  if (fromCircle) fromCircle.textContent = '';
  if (toCircle) toCircle.textContent = '';
  if (taskSpan) taskSpan.textContent = 'Task ID: ';
  
  // Set up abort button handler
  const abortButton = document.querySelector('.abort-button');
  if (abortButton) {
    abortButton.addEventListener('click', function() {
      if (confirm('Are you sure you want to abort the current dispatch?')) {
        // Get socket connection
        const socket = io.connect(window.location.origin, {
          reconnection: true,
          reconnectionDelay: 1000,
          reconnectionAttempts: 10
        });
        
        console.log('Sending abort request...');
        
        // Send the abort request
        socket.emit('dispatch_completed', { 
          type: 'dispatch_completed',
          aborted: true 
        });
        
        // Update UI immediately for better responsiveness
        if (standbyInfo) standbyInfo.style.display = 'flex';
        if (trackingInfo) trackingInfo.style.display = 'none';
        
        if (fromCircle) fromCircle.textContent = '';
        if (toCircle) toCircle.textContent = '';
        if (taskSpan) taskSpan.textContent = 'Task ID: ';
        
        stopArrowBlinking();
      }
    });
  }

  // Connect to Socket.IO with persistent connection
  const socket = io.connect(window.location.origin, {
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 10
  });
  
  socket.on('connect', function() {
    console.log('Dashboard connected to Socket.IO server');
    // Initial update on connect
    updateLiveTracking();
  });
  
  socket.on('connect_error', function(error) {
    console.error('Socket.IO connection error:', error);
  });
  
  socket.on('system_status_changed', function(data) {
    console.log('System status changed event received:', data);
    
    // Only update UI if we're on the dashboard page
    const dashboardBtn = document.getElementById("Dashboard-Btn");
    if (!dashboardBtn || !dashboardBtn.classList.contains("active")) {
      return;
    }
    
    // Provide immediate visual feedback before API call
    if (data.status === true) {
      // Immediately show tracking mode UI
      if (standbyInfo) standbyInfo.style.display = 'none';
      if (trackingInfo) trackingInfo.style.display = 'block';
      startArrowBlinking();
    } else {
      // Immediately show standby mode UI
      if (trackingInfo) trackingInfo.style.display = 'none';
      if (standbyInfo) standbyInfo.style.display = 'flex';
      stopArrowBlinking();
      
      // Clear the display fields
      if (fromCircle) fromCircle.textContent = '';
      if (toCircle) toCircle.textContent = '';
      if (taskSpan) taskSpan.textContent = 'Task ID: ';
    }
    
    // Then get the complete data from API
    updateLiveTracking();
  });
  
  socket.on('dispatch_event', function(data) {
    console.log('Dispatch event received:', data);
    // Force update on dispatch
    updateLiveTracking();
  });
  
  // Set up polling for live updates - more frequent polling (1 second)
  updateLiveTracking(); // Initial update
  setInterval(updateLiveTracking, 1000); // Check every second for changes
});
  