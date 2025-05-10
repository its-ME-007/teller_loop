document.addEventListener("DOMContentLoaded", function() {
    let logs = [];

    // Fetch logs dynamically
    fetch('/get_logs')
        .then(response => response.json())
        .then(data => {
            logs = data;
            renderLogs(logs);
        });

    function renderLogs(data) {
        const tableBody = document.getElementById("log-table");
        tableBody.innerHTML = "";
        data.forEach(log => {
            let row = `<tr>
                <td>${log.task_id}</td>
                <td>${log.from}</td>
                <td>${log.to}</td>
                <td>${log.date}</td>
                <td>${log.time}</td>
            </tr>`;
            tableBody.innerHTML += row;
        });
    }

    // Sorting logic
    document.querySelectorAll("input[name='sort']").forEach(radio => {
        radio.addEventListener("change", function() {
            if (this.id === "sort-id-asc") logs.sort((a, b) => a.task_id - b.task_id);
            if (this.id === "sort-id-desc") logs.sort((a, b) => b.task_id - a.task_id);
            if (this.id === "sort-time-asc") logs.sort((a, b) => (a.time > b.time ? 1 : -1));
            if (this.id === "sort-time-desc") logs.sort((a, b) => (a.time < b.time ? 1 : -1));
            renderLogs(logs);
        });
    });

    document.getElementById("toggleSwitch").addEventListener("change", function() {
        if (this.checked) {
            console.log("Switch is ON");
        } else {
            console.log("Switch is OFF");
        }
    });
    
    // Download functionality
    document.getElementById("download-btn").addEventListener("click", function() {
        // Fetch the full history data from the server
        fetch('/api/download_history')
            .then(response => response.json())
            .then(data => {
                // Log the raw data to help with debugging
                console.log("Downloaded history data:", data);
                
                // Convert to CSV format
                const csvContent = convertToCSV(data);
                
                // Create a download link and trigger the download
                const encodedUri = encodeURI("data:text/csv;charset=utf-8," + csvContent);
                const link = document.createElement("a");
                link.setAttribute("href", encodedUri);
                link.setAttribute("download", "log_history.csv");
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            })
            .catch(error => {
                console.error("Error downloading history:", error);
            });
    });
    
    // Improved function to convert JSON to CSV
    function convertToCSV(objArray) {
        if (objArray.length === 0) return '';
        
        // Get headers from the first object
        const headers = Object.keys(objArray[0] || {}).join(',');
        
        // Create rows for each object
        const rows = objArray.map(obj => {
            return Object.keys(obj).map(key => {
                // Get the value for this key
                const value = obj[key];
                
                // Ensure value is a string and handle null/undefined values
                let stringValue = '';
                if (value !== null && value !== undefined) {
                    stringValue = String(value);
                    
                    // Replace hash symbols if they appear in date fields
                    if ((key === 'date' || key === 'time') && stringValue.includes('#')) {
                        stringValue = 'N/A'; // Replace with a more meaningful placeholder
                    }
                }
                
                // Always wrap values in quotes to handle special characters
                return `"${stringValue.replace(/"/g, '""')}"`;
            }).join(',');
        });
        
        // Combine headers and rows
        return headers + '\n' + rows.join('\n');
    }
});