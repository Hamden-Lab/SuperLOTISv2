import socket
from superlotis.tools.constants import SOPHIA_IP_ADDRESS, SOPHIA_PORT

HOST = SOPHIA_IP_ADDRESS
PORT = SOPHIA_PORT


data = "get exptime"

# SOCK_DGRAM is the socket type to use for UDP sockets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# As you can see, there is no connect() call; UDP has no connections.
# Instead, data is directly sent to the recipient via sendto().
sock.sendto(bytes(data + "\n", "utf-8"), (HOST, PORT))
received = str(sock.recv(1024), "utf-8")

print("Sent:    ", data)
print("Received:", received)