const pinDots = document.querySelectorAll(".kp-pin-dot");
const keypadButtons = document.querySelectorAll(".kp-key");
//const statusMessage = document.getElementById("kp-pindisptext");
const showButton = document.getElementById("kp-toggle-visibility");

const validPin = "1234";
let pin = "";
let showPin = false; // Track whether to show numbers

keypadButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const value = button.dataset.value;

        if (value === "back") {
            pin = pin.slice(0, -1);
        } else if (value === "enter") {
            if (pin === validPin) {
                
                if (getActiveButton()=="Dispatch-Btn"){
                    console.log("Log In to:",getActiveButton())
                    hideallelements();
                    showdispatchpage();
                }
                if (getActiveButton()=="Maintainance-Btn"){
                    console.log("Log In to:",getActiveButton())
                     if (typeof socket !== 'undefined' && window.STATION_ID) {
                        socket.emit('maintenance_entered', { station_id: window.STATION_ID });
                    }
                    hideallelements();
                    showmaintainancepage();
                }
                if (getActiveButton()=="ClearData-Btn"){
                    console.log("Log In to:",getActiveButton())
                    hideallelements();
                    showcleardatapage();
                }

                //statusMessage.text = "✔ PIN Correct";
                //statusMessage.style.color = "green";
            } else {
                //statusMessage.text = "✖ Incorrect PIN";
                //statusMessage.style.color = "red";
                pinDots.forEach(dot => dot.classList.add("shake"));
                setTimeout(() => pinDots.forEach(dot => dot.classList.remove("shake")), 500);
            }

            // Reset PIN after a delay
            setTimeout(() => {
                pin = "";
                updatePinDisplay();
            }, 500);
        } else if (pin.length < 4) {
            pin += value;
        }

        updatePinDisplay();
    });
});

// Show button logic
showButton.addEventListener("click", () => {
    showPin = true;
    updatePinDisplay();

    // Hide numbers again after 2 seconds
    setTimeout(() => {
        showPin = false;
        updatePinDisplay();
    }, 1000);
});

// Function to update PIN display
function updatePinDisplay() {
    pinDots.forEach((dot, i) => {
        if (showPin && pin[i]) {
            dot.textContent = pin[i]; // Show number when toggled
        } else {
            dot.textContent = pin[i] ? "●" : "○"; // Hide number
        }
    });
}
