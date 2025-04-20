        let cd_isSliding = false;
        const cd_slideButton = document.getElementById("cd-slideToDispatch");
        const cd_slideIcon = cd_slideButton.querySelector(".cd-slide-icon");

        cd_slideButton.addEventListener("mousedown", cd_startSlide);
        cd_slideButton.addEventListener("touchstart", cd_startSlide);

        function cd_startSlide(event) {
            cd_isSliding = true;
            let startX = event.type === "mousedown" ? event.clientX : event.touches[0].clientX;
            
            function moveSlide(e) {
                if (!cd_isSliding) return;
                let currentX = e.type === "mousemove" ? e.clientX : e.touches[0].clientX;
                let diff = Math.min(190, Math.max(0, currentX - startX));

                cd_slideIcon.style.left = `${5 + diff}px`;
            }

            function endSlide() {
                cd_isSliding = false;
                if (parseInt(cd_slideIcon.style.left) > 140) {
                    cd_slideIcon.style.left = "190px";
                    alert("Data Cleared!");

                    // Reset the slider after 1 second
                    setTimeout(() => {
                        cd_slideIcon.style.transition = "left 0.5s ease"; // Add smooth transition
                        cd_slideIcon.style.left = "5px";
                        setTimeout(() => {
                            cd_slideIcon.style.transition = ""; // Remove transition for manual dragging
                        }, 500);
                    }, 1000);
                } else {
                    cd_slideIcon.style.left = "5px";
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