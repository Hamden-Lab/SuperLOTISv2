import socket
from superlotis.tools.constants import TEST_STATUS_SERVER_HOST, TEST_STATUS_SERVER_PORT

UDP_HOST = TEST_STATUS_SERVER_HOST
UDP_PORT = TEST_STATUS_SERVER_PORT
BUFFER_SIZE = 4096

if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((UDP_HOST, UDP_PORT))
        print(f"Listening for Inficon pressure reports on {UDP_HOST}:{UDP_PORT}")
        try:
            while True:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                print(f"Received {len(data)} bytes from {addr}:\n{data.decode('utf-8', errors='replace')}\n")
        except KeyboardInterrupt:
            print("Stopping Inficon test receiver")
