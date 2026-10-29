🚀PyExplorer is a lightweight and intuitive remote file explorer specifically designed for Raspberry Pi. Built with Python and PyQt6, it allows you to manage your remote files as if they were on your local machine.

🌟 Features
Device Management: Save multiple Raspberry Pi connections with aliases, IP addresses, and credentials.

Secure Connection: Uses SSH/SFTP protocol for safe data transfer.

Sidebar Navigation: Quickly switch between your saved devices.

File Operations:

Double-click to Open: Open remote files directly with your PC's default applications.

Upload/Download: Easy file transfer between your PC and Raspberry Pi.

Delete: Manage remote storage directly from the UI.

Context Menu: Right-click support for all major file operations.

Secure by default: SSH host keys are verified against a persistent known_hosts (TOFU), and passwords are stored in the OS keyring (with encrypted-file fallback, written with 0600 permissions) instead of plain text.

🛠️ Requirements
To run PyExplorer, you need Python installed on your system along with the following libraries:

Bash
pip install -r requirements.txt
🚀 How to Use
Clone the repository (or download the code).

Run the application:

Bash
python src/main.py
Add a device: Enter a Name, IP, Username, and Password, then click Save.

Connect: Select a device from the sidebar and hit Connect.

👤 Author
Enrico Martini - Lead Developer

GitHub: enkas79

📝 Version
Current Version: 1.7.1

📄 License
This project is licensed under the MIT License.
