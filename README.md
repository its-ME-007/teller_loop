# 🚀 Teller Loop - Intelligent Pneumatic Dispatch System

A smart, network-driven **pneumatic tube dispatch system** designed for **medicinal transport** within a facility. This system allows for efficient, real-time dispatch of medicine containers (pods) between stations using a software-controlled loop, integrating Flask, MQTT, WebSockets, and Socket.IO.

---

## 🏥 Use Case

This Teller Loop is engineered to automate and streamline the **movement of medicinal items** from one department or room to another, minimizing human involvement and improving reliability in clinical environments.

---

## 👨‍💻 Project Details

- **Domain:** Smart Transportation Systems / Healthcare Automation  
- **Technology Stack:**  
  - 🔧 Python (Flask, Socket.IO, MQTT, SQLAlchemy)  
  - 💻 Frontend: HTML, CSS, Vanilla JS  
  - 📡 Communication: MQTT (for tube control), WebSockets (real-time UI)  
  - 🧠 Architecture: Modular station-based dispatch, real-time control  
- **Routing:** ID-based endpoint routing instead of IP-based to support modular expansion

---

## 👩‍🎓 Developed By

A department-level initiative from the **Department of Computer Science and Engineering, RV College of Engineering (RVCE)**.

### 💡 Software Team (4th Semester CSE):
| Name               | GitHub Profile                               |
|--------------------|----------------------------------------------|
| Anirudh R. Kulkarni | [@its-ME-007](https://github.com/its-ME-007) |
| Anish               | [@anish41338](https://github.com/anish41338) |

---

## 📦 Features

- 🧪 **Live Dispatch Monitoring**  
- 📊 **Real-Time Dispatch Requests** via MQTT  
- 🛰️ **WebSocket Integration** for status & alerts  
- 🧠 **Intelligent Queue Management**  
- 🚨 **Abort & Acknowledge Dispatch**  
- 🧼 **ID-Based Routing** for multi-station scalability  
- 🔐 Role-free, UI-driven interface for ease of use

---

## 🛠️ Running the Project

### Prerequisites
- Python 3.10+
- Mosquitto MQTT broker
- Install dependencies:

```bash
pip install -r requirements.txt
```

### Launch the Server
```bash
python app_com_rpi2.py
```

### Access in Browser
```bash
http://<your-ip>:5000/1  # Where 1 is the station ID
```

---

## 🧪 Dev Notes

- Live tracking has been removed in favor of simple state-based toggling.
- Station-specific pages work on dynamic `<int:page_id>` routes.
- Every station gets its own WebSocket room and MQTT channel for separation.

---

## 📄 License

This is an academic project under the guidance of RVCE's Computer Science Department. For any collaborations or contributions, please contact the student team or faculty directly.

---
