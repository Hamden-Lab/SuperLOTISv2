# import socket
# from superlotis.tools.constants import PDU41001_SOCKET_IP_ADDRESS, PDU41001_SOCKET_PORT

# HOST = PDU41001_SOCKET_IP_ADDRESS
# PORT = PDU41001_SOCKET_PORT

# data = "power off 2"

# # SOCK_DGRAM is the socket type to use for UDP sockets
# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# # As you can see, there is no connect() call; UDP has no connections.
# # Instead, data is directly sent to the recipient via sendto().
# sock.sendto(bytes(data + "\n", "utf-8"), (HOST, PORT))
# received = str(sock.recv(1024), "utf-8")

# print("Sent:    ", data)
# print("Received:", received)

import socketserver
from pathlib import Path
from threading import Lock
from superlotis.tools.constants import TEST_SCHEDULER_SERVER_HOST, TEST_SCHEDULER_SERVER_PORT

# =========================================================
# CONFIG
# =========================================================

HOST = TEST_SCHEDULER_SERVER_HOST
PORT = TEST_SCHEDULER_SERVER_PORT

# =========================================================
# SHARED DATA
# =========================================================

data_lock = Lock()

data = """now 0 LYMAN PDU poweroff 2
now 15 LYMAN PDU poweron 2
now 30 LYMAN PDU get status 2
"""

# =========================================================
# COMMAND PROCESSING
# =========================================================

def process_command(command: bytes) -> bytes:
    """
    Process incoming UDP command.
    Only supported command:
        /all
    """

    cmd = command.decode("utf-8", errors="replace").strip()

    print("Received command '%s'", cmd)

    if cmd == "/all":
        with data_lock:
            return data.encode("utf-8")

    return b"Unknown command"


# =========================================================
# UDP HANDLER
# =========================================================

class PersistentUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):

        packet = self.request[0].strip()
        sock = self.request[1]

        try:
            response = process_command(packet)

            sock.sendto(response, self.client_address)

        except Exception:

            sock.sendto(
                b"Internal server error",
                self.client_address
            )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":


    with socketserver.ThreadingUDPServer(
        (HOST, PORT),
        PersistentUDPHandler
    ) as server:

        try:
            server.serve_forever()

        except KeyboardInterrupt:
            pass

        finally:
            server.shutdown()