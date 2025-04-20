let mt_isSliding = false;
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
            alert("Dispatched");

            // Reset the slider after 1 second
            setTimeout(() => {
                mt_slideIcon.style.transition = "left 0.5s ease"; // Add smooth transition
                mt_slideIcon.style.left = "5px";
                setTimeout(() => {
                    mt_slideIcon.style.transition = ""; // Remove transition for manual dragging
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

    // Update percentage text on slider input
    mt_airSlider.addEventListener("input", function () {
        mt_airPercentage.textContent = mt_airSlider.value + "%";
    });
});