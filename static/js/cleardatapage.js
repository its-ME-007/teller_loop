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
                    if (parseInt(cd_slideIcon.style.left) > 140) {
                        cd_slideIcon.style.left = "190px";
                        
                            // Show popup
                            document.getElementById("cd-popup").style.display = "flex";

                            // Only one checkbox logic
                            const checkboxes = document.querySelectorAll('input[name="cd-clear-option"]');
                            checkboxes.forEach(cb => {
                                cb.onclick = () => {
                                    checkboxes.forEach(c => {
                                        if (c !== cb) c.checked = false;
                                    });
                                };
                            });

                            // Cancel/Back button
                            document.getElementById("cd-popup-cancel").onclick = () => {
                                document.getElementById("cd-popup").style.display = "none";
                            };

                            // OK button
                            document.getElementById("cd-popup-ok").onclick = () => {
                                let selected = null;
                                let selectedText = "";
                                
                                checkboxes.forEach(cb => {
                                    if (cb.checked) {
                                        selected = cb.value;
                                        // Get the label text
                                        selectedText = cb.parentElement.textContent.trim();
                                    }
                                });

                                if (!selected) {
                                    alert("Please select a time range.");
                                    return;
                                }

                                document.getElementById("cd-popup").style.display = "none";
                                
                                // Show success alert with selected option
                                let apiEndpoint = '';
                            if (selected === '60') {
                                apiEndpoint = '/api/clear_history_60';
                            } else if (selected === '30') {
                                apiEndpoint = '/api/clear_history_30';
                            } else if (selected === 'all') {
                                apiEndpoint = '/api/clear_history';
                            }

                            // Make API call to clear data
                            fetch(apiEndpoint, {
                                method: 'DELETE',
                                headers: {
                                    'Content-Type': 'application/json',
                                }
                            })
                            .then(response => response.json())
                            .then(data => {
                                    if (data.status === 'success') {
                                        console.log('Clear operation successful:', data);
                                
                                        // ✅ Force a page reload to reflect changes in the UI
                                        location.reload();
                                    } else {
                                        alert(`Failed to clear data: ${data.message}`);
                                        console.error('Clear operation failed:', data);
                                    }
                                })

                            .catch(error => {
                                alert(`Error clearing data: ${error.message}`);
                                console.error('Error:', error);
                            });
                            
                        };
                    } else {
                        cd_slideIcon.style.left = "5px";
                    }


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
