import socket
import struct
import time

serverName = 'localhost'
serverPort = 12000

clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

HEADER_FORMAT = '!4s B B I I Q H'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Send INIT message
init_packet = struct.pack(HEADER_FORMAT, b'GCLP', 1, 0, 0, 0, int(time.time() * 1000), 0)
clientSocket.sendto(init_packet, (serverName, serverPort))
print("Sent INIT message")

# Wait for ACK
data, serverAddress = clientSocket.recvfrom(2048)
header = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
print(f"Received ACK: msg_type={header[2]}")

# Send DATA messages (simulate game events)
for i in range(5):
    game_event = f"ACQUIRE cell_{i}".encode()
    data_packet = struct.pack(HEADER_FORMAT, b'GCLP', 1, 1, 0, i,
                              int(time.time() * 1000), len(game_event))
    clientSocket.sendto(data_packet + game_event, (serverName, serverPort))
    print(f"Sent DATA: {game_event.decode()}")

    # Receive snapshot
    response, _ = clientSocket.recvfrom(2048)
    header = struct.unpack(HEADER_FORMAT, response[:HEADER_SIZE])
    snapshot_data = response[HEADER_SIZE:HEADER_SIZE + header[6]]
    print(f"Received SNAPSHOT {header[3]}: {snapshot_data.decode()}")

    time.sleep(1/20)

clientSocket.close()




# def broadcast_snapshots():
#     """Periodically broadcast current game state to all clients."""
#     while True:
#         snapshot_str = str(game_state).encode()
#         for client in list(clients):
#             snapshot_packet = struct.pack(
#                 HEADER_FORMAT, b'GCLP', 1, 2, 0, 0,
#                 int(time.time() * 1000), len(snapshot_str)
#             )
#             serverSocket.sendto(snapshot_packet + snapshot_str, client)
#         time.sleep(TICK_INTERVAL)
#
# # Start broadcasting in a background thread
# threading.Thread(target=broadcast_snapshots, daemon=True).start()
