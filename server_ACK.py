import socket
import time
import struct
import tkinter as tk
from tkinter import ttk
import threading

serverPort = 12000
HEADER_FORMAT = '!4s B B I I Q H'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

class GridClashServer:
    def __init__(self, root):
        self.root = root
        self.root.title("GridClash - Server")
        self.root.geometry("900x800")
        self.root.configure(bg="#1a1a2e")
        
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.serverSocket.bind(('', serverPort))
        
        self.clients = {}
        self.snapshot_id = 0
        self.grid_state = {}  # cell_id -> player_id
        self.grid_size = 10
        self.next_player_id = 1  # Start from 1
        self.running = True
        
        # Player colors (1-4)
        self.colors = {
            1: "#3498db",
            2: "#e74c3c",
            3: "#2ecc71",
            4: "#f39c12",
            'empty': "#34495e"
        }
        
        self.setup_ui()
        
        # Start server thread
        self.server_thread = threading.Thread(target=self.server_loop, daemon=True)
        self.server_thread.start()
        
        self.log("Server started on port 12000")
    
    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="GridClash Server", font=("Arial", 28, "bold"),
                        bg="#1a1a2e", fg="#00d4ff")
        title.pack(pady=20)
        
        # Stats frame
        stats_frame = tk.Frame(self.root, bg="#16213e", bd=3, relief=tk.RIDGE)
        stats_frame.pack(pady=10, padx=50, fill=tk.X)
        
        self.clients_label = tk.Label(stats_frame, text="Connected Players: 0",
                                     font=("Arial", 12), bg="#16213e", fg="#ffffff")
        self.clients_label.pack(pady=10)
        
        # Grid display
        grid_label = tk.Label(self.root, text="Game Grid", font=("Arial", 14, "bold"),
                            bg="#1a1a2e", fg="#00d4ff")
        grid_label.pack(pady=10)
        
        grid_frame = tk.Frame(self.root, bg="#0f0f1e", bd=5, relief=tk.RAISED)
        grid_frame.pack(pady=10, padx=50)
        
        self.grid_cells = {}
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                cell = tk.Label(grid_frame, text="", width=5, height=2,
                              bg=self.colors['empty'], relief=tk.RAISED, bd=2)
                cell.grid(row=row, column=col, padx=1, pady=1)
                self.grid_cells[(row, col)] = cell
        
        # Server log
        log_label = tk.Label(self.root, text="Server Log", font=("Arial", 12, "bold"),
                           bg="#1a1a2e", fg="#00d4ff")
        log_label.pack(pady=(20, 5))
        
        log_frame = tk.Frame(self.root, bg="#1a1a2e")
        log_frame.pack(pady=5, padx=50, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=10, bg="#16213e", fg="#00ff00",
                               font=("Courier", 10), yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
    
    def server_loop(self):
        while self.running:
            try:
                self.serverSocket.settimeout(0.1)
                data, clientAddress = self.serverSocket.recvfrom(2048)
                
                header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
                protocol_id, version, msg_type, snap_id, seq, timestamp, payload_len = header
                
                if msg_type == 0:  # INIT
                    player_id = ((self.next_player_id - 1) % 4) + 1  # Cycle 1-4
                    self.clients[clientAddress] = {
                        'seq': 0,
                        'last_snapshot': 0,
                        'player_id': player_id
                    }
                    self.next_player_id += 1
                    
                    self.root.after(0, self.log, f"Player {player_id} connected from {clientAddress}")
                    self.root.after(0, self.update_client_count)
                    
                    # Send ACK with player ID
                    ack_payload = f"PLAYER:{player_id}".encode()
                    response = struct.pack(HEADER_FORMAT, b'GCLP', 1, 2, 0, 0,
                                         int(time.time() * 1000), len(ack_payload))
                    self.serverSocket.sendto(response + ack_payload, clientAddress)
                
                elif msg_type == 1:  # DATA (cell acquisition)
                    payload = data[HEADER_SIZE:HEADER_SIZE + payload_len].decode()
                    
                    if 'ACQUIRE' in payload:
                        parts = payload.split()
                        cell_id = parts[1]
                        player_id = int(parts[2])
                        
                        # Update grid state
                        self.grid_state[cell_id] = player_id
                        
                        self.root.after(0, self.log, f"Player {player_id} acquired cell {cell_id}")
                        self.root.after(0, self.update_grid_display)
                        
                        # Broadcast snapshot
                        self.broadcast_snapshot()
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.root.after(0, self.log, f"Error: {e}")
    
    def broadcast_snapshot(self):
        self.snapshot_id += 1
        
        # Build snapshot data
        snapshot_parts = []
        for cell_id, owner in self.grid_state.items():
            snapshot_parts.append(f"CELL {cell_id} {owner}")
        
        snapshot_data = " | ".join(snapshot_parts).encode()
        
        # Send to all clients
        for client_addr in list(self.clients.keys()):
            try:
                response = struct.pack(HEADER_FORMAT, b'GCLP', 1, 3, self.snapshot_id,
                                     self.clients[client_addr]['seq'],
                                     int(time.time() * 1000), len(snapshot_data))
                self.serverSocket.sendto(response + snapshot_data, client_addr)
            except:
                pass
    
    def update_grid_display(self):
        for cell_id, owner in self.grid_state.items():
            row, col = map(int, cell_id.split('_'))
            if (row, col) in self.grid_cells:
                self.grid_cells[(row, col)].config(bg=self.colors[owner])
    
    def update_client_count(self):
        self.clients_label.config(text=f"Connected Players: {len(self.clients)}")
    
    def log(self, message):
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
    
    def on_closing(self):
        self.running = False
        self.serverSocket.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    server = GridClashServer(root)
    root.protocol("WM_DELETE_WINDOW", server.on_closing)
    root.mainloop()
