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

# data = """now 0 LYMAN PDU poweroff 2
# now 15 LYMAN PDU poweron 2
# now 30 LYMAN PDU get status 2
# """

# data = """now 5 LYMAN SOPHIA get exptime
# now 10 LYMAN SOPHIA set exptime 0.001
# now 20 LYMAN SOPHIA expose"""

# data = """now 6 LYMAN INFICON get camera_pressure
# now 11 LYMAN INFICON get pump_pressure"""

# data = """now 6 LYMAN CHILLER get temperature
# now 11 LYMAN CHILLER get pump_temperature"""

#data = """now 6 LYMAN CHILLER get backing_temperature"""

# data = """now 0 LYMAN PDU poweron 7
# now 10 LYMAN PDU poweron 1
# now 30 LYMAN SOPHIA set temperature -10
# now 60 LYMAN SOPHIA set temperature -40
# now 120 LYMAN SOPHIA set temperature -80
# now 130 LYMAN SOPHIA set exptime 0.01
# now 480 LYMAN SOPHIA expose
# now 490 LYMAN SOPHIA expose"""

# data = """now 0 LYMAN PDU poweron 7
# now 30 LYMAN PDU poweroff 2
# now 35 LYMAN PFEIFFER stop turbo
# now 40 LYMAN PDU poweron 1
# now 50 LYMAN SOPHIA set temperature -10
# now 120 LYMAN SOPHIA set temperature -40
# now 240 LYMAN SOPHIA set temperature -80"""

data = """now 10 LYMAN PDU poweroff 2
now 100 LYMAN PFEIFFER stop turbo
now 1000 LYMAN PFEIFFER stop backing"""

# data = """now 0 LYMAN PDU poweron 7
# now 10 LYMAN PDU poweron 1
# now 10 LYMAN CHILLER set temperature 20
# now 20 LYMAN SOPHIA set temperature 0
# now 140 LYMAN SOPHIA set temperature -30
# now 260 LYMAN SOPHIA set temperature -80
# now 380 LYMAN SOPHIA set temperature -85
# """

# data = """now 0 LYMAN PFEIFFER start backing
# now 120 LYMAN PFEIFFER start turbo
# now 240 LYMAN PDU poweron 2"""

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