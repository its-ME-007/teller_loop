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
    
    // Download (Placeholder Function)
    document.getElementById("download-btn").addEventListener("click", function() {
        alert("Download feature coming soon!");
    });
});
