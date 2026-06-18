from superlotis.drivers.sophia.sophia import SOPHIA
from superlotis.tools.constants import SOPHIA_FRAME_TIMEOUT, SOPHIA_IP_ADDRESS, SOPHIA_PORT
import socketserver


HOST = SOPHIA_IP_ADDRESS
PORT = SOPHIA_PORT  # Port to listen on (non-privileged ports are > 1023)

def process_command(command):
    if command == b"get exptime":
        # sophia = SOPHIA()
        # exptime = sophia.get_exptime()
        exptime = 99
        return bytes(str(exptime), "utf-8")
    
    if command == b"expose":
        # sophia = SOPHIA()
        # data = sophia.take_exposure(SOPHIA_FRAME_TIMEOUT)
        return data.tobytes()
    
    if command == b"get temp":
        # sophia = SOPHIA()
        # temp = sophia.get_temperature()
        temp = 99
        return bytes(str(temp), "utf-8")
    

class MyUDPHandler(socketserver.BaseRequestHandler):
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        print(f"{self.client_address[0]} wrote:")
        print(data)
        res = process_command(data)
        socket.sendto(res, self.client_address)
        #socket.sendto(data.upper(), self.client_address)

if __name__ == "__main__":
    with socketserver.UDPServer((HOST, PORT), MyUDPHandler) as server:
        server.serve_forever()