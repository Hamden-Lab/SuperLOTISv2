import json
import socket

from superlotis.tools.constants import (
    TEST_STATUS_SERVER_HOST,
    TEST_STATUS_SERVER_PORT,
)

UDP_HOST = TEST_STATUS_SERVER_HOST
UDP_PORT = TEST_STATUS_SERVER_PORT
BUFFER_SIZE = 4096

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    # Optional: avoid waiting forever if the server is unavailable
    sock.settimeout(2.0)

    # Send request
    sock.sendto(b"get all", (UDP_HOST, UDP_PORT))

    try:
        data, _ = sock.recvfrom(BUFFER_SIZE)
        
        # Decode JSON response into a Python dict
        status = json.loads(data.decode("utf-8"))

        print("Received status:")
        print(status)

    except socket.timeout:
        print("Timed out waiting for response from status server.")