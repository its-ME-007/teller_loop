let mt_isSliding = false;
window.STATION_ID = window.STATION_ID || 1;
const mt_slideButton = document.getElementById("mt-slideToDispatch");
const mt_slideIcon = mt_slideButton.querySelector(".mt-slide-icon");

mt_slideButton.addEventListener("mousedown", startMaintenanceSlide);
mt_slideButton.addEventListener("touchstart", startMaintenanceSlide);

function startMaintenanceSlide(event) {
    mt_isSliding = true;
    let startX = event.type === "mousedown" ? event.clientX : event.touches[0].clientX;
    
    function moveMaintenanceSlide(e) {
        if (!mt_isSliding) return;
        let currentX = e.type === "mousemove" ? e.clientX : e.touches[0].clientX;
        let diff = Math.min(190, Math.max(0, currentX - startX));
        mt_slideIcon.style.left = `${5 + diff}px`;
    }

    function endMaintenanceSlide() {
        mt_isSliding = false;
        if (parseInt(mt_slideIcon.style.left) > 140) {
            mt_slideIcon.style.left = "190px";

            fetch(`/api/maintenance/selftest/${STATION_ID}`, {
                method: 'POST'
            })
            .then(res => res.json())
            .then(data => {
                console.log("Self-test triggered:", data);
            })
            .catch(err => console.error("Failed to trigger self-test:", err));

            alert("Dispatched");

            setTimeout(() => {
                mt_slideIcon.style.transition = "left 0.5s ease";
                mt_slideIcon.style.left = "5px";
                setTimeout(() => {
                    mt_slideIcon.style.transition = "";
                }, 500);
            }, 1000);
        } else {
            mt_slideIcon.style.left = "5px";
        }

        document.removeEventListener("mousemove", moveMaintenanceSlide);
        document.removeEventListener("mouseup", endMaintenanceSlide);
        document.removeEventListener("touchmove", moveMaintenanceSlide);
        document.removeEventListener("touchend", endMaintenanceSlide);
    }

    document.addEventListener("mousemove", moveMaintenanceSlide);
    document.addEventListener("mouseup", endMaintenanceSlide);
    document.addEventListener("touchmove", moveMaintenanceSlide);
    document.addEventListener("touchend", endMaintenanceSlide);
}
document.addEventListener("DOMContentLoaded", function () {
    const mt_airSlider = document.getElementById("mt-air-slider");
    const mt_airPercentage = document.getElementById("mt-air-percentage");

    mt_airSlider.addEventListener("input", function () {
        mt_airPercentage.textContent = mt_airSlider.value + "%";
    });

    // Fixed selector syntax - using comma inside the string
    document.querySelectorAll('.mt-side-button, .mt-end-button').forEach(btn => {
        btn.addEventListener('click', function () {
            const label = this.innerText.trim().toLowerCase();
            if (label === 'left' || label === 'right') {
                const dir = label === 'left' ? 'moveLeft' : 'moveRight';
                fetch(`/api/maintenance/inching/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ direction: dir })
                });
            } else if (label === 'suck' || label === 'blow') {
                const power = parseInt(document.getElementById("mt-air-slider").value);
                fetch(`/api/maintenance/airdivert/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: label, power })
                });
            } else if (label == 'stop') {
                fetch(`/api/maintenance/stop/${STATION_ID}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action:'stop'})
                });
            }
        });
    });
});