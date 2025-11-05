import socket
import time
import struct

serverPort = 12000
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
serverSocket.bind(('', serverPort))
frequency = 20

clients = {}  # Track connected clients
snapshot_id = 0

# Define your protocol header format
# '!4sB B I I Q H' = protocol_id, version, msg_type, snapshot_id, seq_num, timestamp, payload_len
HEADER_FORMAT = '!4s B B I I Q H'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

while True:
    data, clientAddress = serverSocket.recvfrom(2048)

    # Parse header
    header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    protocol_id, version, msg_type, snap_id, seq, timestamp, payload_len = header

    # Handle INIT message (client connecting)
    if msg_type == 0:  # INIT
        clients[clientAddress] = {'seq': 0, 'last_snapshot': 0}
        print(f"[INIT] Client connected: {clientAddress}")

        # Send ACK back
        response = struct.pack(HEADER_FORMAT, b'GCLP', 1, 2, 0, 0, int(time.time() * 1000), 0)
        serverSocket.sendto(response, clientAddress)

    # Handle DATA message (game events like cell acquisition)
    elif msg_type == 1:  # DATA
        payload = data[HEADER_SIZE:HEADER_SIZE + payload_len]
        print(f"[DATA] From {clientAddress}: {payload.decode()}")

        # Broadcast state snapshot to all clients
        snapshot_id += 1
        for client_addr in clients:
            snapshot_data = f"Snapshot {snapshot_id}".encode()
            response = struct.pack(HEADER_FORMAT, b'GCLP', 1, 3, snapshot_id,
                                   clients[client_addr]['seq'],
                                   int(time.time() * 1000), len(snapshot_data))
            serverSocket.sendto(response + snapshot_data, client_addr)

#    time.wait(1/frequency)