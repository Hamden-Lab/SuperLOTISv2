import socket
from superlotis.tools.constants import LYMAN_COMPUTER_IP_ADDRESS, SLOTIS_SCHEDULER_PORT

# =========================================================
# CONFIG
# =========================================================

SERVER_IP = LYMAN_COMPUTER_IP_ADDRESS
SERVER_PORT = SLOTIS_SCHEDULER_PORT

COMMAND = "/all"

# =========================================================
# CLIENT
# =========================================================

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

try:
    # Send command
    client.sendto(COMMAND.encode("utf-8"), (SERVER_IP, SERVER_PORT))

    # Receive response
    response, addr = client.recvfrom(4096)

    print("Response from server:")
    print(response.decode("utf-8"))

finally:
    client.close()