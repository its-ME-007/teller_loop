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
    
    // Download functionality - only for station 0
    const downloadBtn = document.getElementById("download-btn");
    if (downloadBtn) {
        downloadBtn.addEventListener("click", function() {
            console.log("Download button clicked");
            console.log("STATION_ID:", window.STATION_ID);
            
            // Check if jsPDF is available
            if (typeof window.jspdf === 'undefined') {
                console.error("jsPDF library not loaded");
                alert("PDF generation library not loaded. Please refresh the page.");
                return;
            }

            try {
                // Create new PDF document
                const { jsPDF } = window.jspdf;
                const doc = new jsPDF();

                // Add title
                doc.setFontSize(16);
                doc.text("Teller Loop History Report", 14, 15);
                
                // Add date
                doc.setFontSize(10);
                const currentDate = new Date().toLocaleDateString();
                doc.text(`Generated on: ${currentDate}`, 14, 22);

                // Prepare table data
                const tableData = logs.map(log => [
                    log.task_id,
                    log.from,
                    log.to,
                    log.date,
                    log.time
                ]);

                // Add table using autoTable plugin
                doc.autoTable({
                    head: [['Task ID', 'From', 'To', 'Date', 'Time']],
                    body: tableData,
                    startY: 30,
                    theme: 'grid',
                    styles: {
                        fontSize: 8,
                        cellPadding: 2
                    },
                    headStyles: {
                        fillColor: [50, 50, 50],
                        textColor: 255
                    }
                });

                // Save the PDF
                doc.save(`teller_loop_history_${new Date().toISOString().split('T')[0]}.pdf`);
                console.log("PDF generated successfully");
            } catch (error) {
                console.error("Error generating PDF:", error);
                alert("Error generating PDF. Please check console for details.");
            }
        });
    }
});
