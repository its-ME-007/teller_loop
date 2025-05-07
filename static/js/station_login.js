const pinDots = document.querySelectorAll(".kp-pin-dot");
const keypadButtons = document.querySelectorAll(".kp-key");
const showButton = document.getElementById("kp-toggle-visibility");
const pinInput = document.getElementById("pinInput");

let pin = "";
let showPin = false; // Whether to temporarily show digits

// Handle keypad button clicks
keypadButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const value = button.dataset.value;

        if (value === "back") {
            pin = pin.slice(0, -1);
        } // Inside keypadButtons.forEach where "enter" button is handled
        else if (value === "enter") {
            if (pin.length === 4) {
                pinInput.value = pin;
                document.getElementById('pinForm').submit();
            } else {
                showInvalidPin();
            }
        }
         else if (pin.length < 4) {
            pin += value;
        }

        updatePinDisplay();
    });
});

// Handle show/hide PIN button
const eyeImg = document.getElementById("eyeIcon");

showButton.addEventListener("click", () => {
    showPin = !showPin; // Toggle true/false each click
    updatePinDisplay();

    if (showPin) {
        eyeImg.src = "/static/images/seen.png"; // Show open eye
    } else {
        eyeImg.src =  "/static/images/hide.png"; // Show closed eye
    }
});

// Update visual PIN dots
function updatePinDisplay() {
    pinDots.forEach((dot, i) => {
        if (showPin && pin[i]) {
            dot.textContent = pin[i];
        } else {
            dot.textContent = pin[i] ? "●" : "○";
        }
    });
}
// Function to show "Invalid PIN" behavior
function showInvalidPin() {
    const pinText = document.getElementById("kp-pin-text");

    pinDots.forEach(dot => {
        dot.classList.add("error");    // make dots red
        dot.classList.add("shake");    // shake animation
    });

    pinText.textContent = "Invalid PIN"; // change text

    setTimeout(() => {
        pinDots.forEach(dot => {
            dot.classList.remove("error");  // remove red color
            dot.classList.remove("shake");  // stop shaking
        });

        pinText.textContent = "Please enter PIN"; // reset text
    }, 1000);}

// Shake effect on wrong entry
function shakeDots() {
    pinDots.forEach(dot => dot.classList.add("shake"));
    setTimeout(() => pinDots.forEach(dot => dot.classList.remove("shake")), 500);
}
