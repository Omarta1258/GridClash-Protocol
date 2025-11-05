import socket
import struct
import time
import tkinter as tk
from tkinter import ttk
import threading
import queue

serverName = 'localhost'
serverPort = 12000
HEADER_FORMAT = '!4s B B I I Q H'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

class GridClashClient:
    def __init__(self, root):
        self.root = root
        self.root.title("GridClash - Client")
        self.root.geometry("800x900")
        self.root.configure(bg="#1a1a2e")
        
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.player_id = None
        self.grid_size = 10
        self.cells = {}
        self.cell_owners = {}
        self.message_queue = queue.Queue()
        self.running = True
        
        # Delta encoding state
        self.last_acknowledged_snapshot = 0
        self.current_snapshot_id = 0
        self.sequence_number = 0
        
        # Player colors (1-4)
        self.colors = {
            1: "#3498db",  # Blue
            2: "#e74c3c",  # Red
            3: "#2ecc71",  # Green
            4: "#f39c12",  # Orange
            'empty': "#34495e"
        }
        
        self.setup_ui()
        self.connect_to_server()
        
        # Start network thread
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()
        
        # Start UI update loop
        self.update_ui()
        
    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="GridClash", font=("Arial", 32, "bold"),
                        bg="#1a1a2e", fg="#00d4ff")
        title.pack(pady=20)
        
        # Player info
        self.info_frame = tk.Frame(self.root, bg="#1a1a2e")
        self.info_frame.pack(pady=10)
        
        self.player_label = tk.Label(self.info_frame, text="Connecting...",
                                     font=("Arial", 14), bg="#1a1a2e", fg="#ffffff")
        self.player_label.pack()
        
        # Stats info
        self.stats_label = tk.Label(self.info_frame, text="Snapshot: 0 | Seq: 0",
                                    font=("Arial", 10), bg="#1a1a2e", fg="#aaaaaa")
        self.stats_label.pack()
        
        # Grid frame
        grid_frame = tk.Frame(self.root, bg="#0f0f1e", bd=5, relief=tk.RAISED)
        grid_frame.pack(pady=20, padx=50)
        
        # Create 10x10 grid
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                cell = tk.Button(grid_frame, text="", width=6, height=3,
                               bg=self.colors['empty'], fg="#ffffff",
                               font=("Arial", 10, "bold"),
                               activebackground="#2c3e50",
                               command=lambda r=row, c=col: self.click_cell(r, c))
                cell.grid(row=row, column=col, padx=2, pady=2)
                self.cells[(row, col)] = cell
                self.cell_owners[(row, col)] = None
        
        # Status log
        log_label = tk.Label(self.root, text="Activity Log", font=("Arial", 12, "bold"),
                           bg="#1a1a2e", fg="#00d4ff")
        log_label.pack(pady=(20, 5))
        
        log_frame = tk.Frame(self.root, bg="#1a1a2e")
        log_frame.pack(pady=5, padx=50, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=8, bg="#16213e", fg="#00ff00",
                               font=("Courier", 10), yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
    def connect_to_server(self):
        try:
            init_packet = struct.pack(HEADER_FORMAT, b'GCLP', 1, 0, 0, 0,
                                     int(time.time() * 1000), 0)
            self.clientSocket.sendto(init_packet, (serverName, serverPort))
            self.log("Connecting to server...")
        except Exception as e:
            self.log(f"Connection error: {e}")
    
    def click_cell(self, row, col):
        if self.player_id is None:
            return
        
        cell_id = f"{row}_{col}"
        self.sequence_number += 1
        
        # Include last acknowledged snapshot ID for delta encoding
        game_event = f"ACQUIRE {cell_id} {self.player_id} ACK_SNAP:{self.last_acknowledged_snapshot}".encode()
        
        try:
            data_packet = struct.pack(HEADER_FORMAT, b'GCLP', 1, 1, 
                                     self.last_acknowledged_snapshot,  # Include last ack'd snapshot
                                     self.sequence_number,
                                     int(time.time() * 1000), len(game_event))
            self.clientSocket.sendto(data_packet + game_event, (serverName, serverPort))
            self.log(f"Attempting to acquire cell ({row}, {col}) [Seq: {self.sequence_number}]")
        except Exception as e:
            self.log(f"Send error: {e}")
    
    def send_ack(self, snapshot_id):
        """Send acknowledgment of received snapshot"""
        try:
            self.sequence_number += 1
            ack_payload = f"ACK {snapshot_id}".encode()
            ack_packet = struct.pack(HEADER_FORMAT, b'GCLP', 1, 4,  # msg_type 4 = ACK
                                    snapshot_id,
                                    self.sequence_number,
                                    int(time.time() * 1000), len(ack_payload))
            self.clientSocket.sendto(ack_packet + ack_payload, (serverName, serverPort))
        except Exception as e:
            self.log(f"ACK send error: {e}")
    
    def network_loop(self):
        while self.running:
            try:
                self.clientSocket.settimeout(0.1)
                data, _ = self.clientSocket.recvfrom(2048)
                header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
                protocol_id, version, msg_type, snapshot_id, seq_num, timestamp, payload_len = header
                
                if msg_type == 2:  # ACK (connection acknowledgment)
                    payload = data[HEADER_SIZE:HEADER_SIZE + payload_len].decode()
                    self.player_id = int(payload.split(':')[1])
                    self.message_queue.put(('connected', self.player_id))
                
                elif msg_type == 3:  # SNAPSHOT (delta update)
                    # Discard outdated updates
                    if snapshot_id < self.current_snapshot_id:
                        self.log(f"Discarded outdated snapshot {snapshot_id} (current: {self.current_snapshot_id})")
                        continue
                    
                    snapshot_data = data[HEADER_SIZE:HEADER_SIZE + payload_len].decode()
                    self.current_snapshot_id = snapshot_id
                    
                    # Process the delta update
                    self.message_queue.put(('snapshot', (snapshot_id, seq_num, timestamp, snapshot_data)))
                    
                    # Send acknowledgment
                    self.last_acknowledged_snapshot = snapshot_id
                    self.send_ack(snapshot_id)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.message_queue.put(('error', str(e)))
    
    def update_ui(self):
        try:
            while not self.message_queue.empty():
                msg_type, data = self.message_queue.get_nowait()
                
                if msg_type == 'connected':
                    self.player_label.config(text=f"Player {data} | Color: ●",
                                           fg=self.colors[data])
                    self.log(f"Connected as Player {data}")
                
                elif msg_type == 'snapshot':
                    snapshot_id, seq_num, timestamp, snapshot_data = data
                    self.process_snapshot(snapshot_data)
                    self.stats_label.config(text=f"Snapshot: {snapshot_id} | Seq: {seq_num} | Time: {timestamp}")
                    self.log(f"Applied delta update (Snapshot {snapshot_id})")
                
                elif msg_type == 'error':
                    self.log(f"Error: {data}")
        except:
            pass
        
        if self.running:
            self.root.after(50, self.update_ui)
    
    def process_snapshot(self, snapshot_data):
        """Process delta-encoded snapshot data"""
        if not snapshot_data.strip():
            return
            
        lines = snapshot_data.split('|')
        for line in lines:
            line = line.strip()
            if 'DELTA' in line and 'CELL' in line:
                # Delta format: "DELTA CELL cell_id owner"
                parts = line.split()
                if len(parts) >= 4:
                    cell_id = parts[2]
                    owner = int(parts[3])
                    row, col = map(int, cell_id.split('_'))
                    
                    if (row, col) in self.cells:
                        self.cells[(row, col)].config(bg=self.colors[owner])
                        self.cell_owners[(row, col)] = owner
    
    def log(self, message):
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
    
    def on_closing(self):
        self.running = False
        self.clientSocket.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GridClashClient(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
