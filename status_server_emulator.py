import json
import socket
from datetime import datetime, UTC

from superlotis.tools.constants import (
    TEST_STATUS_SERVER_HOST,
    TEST_STATUS_SERVER_PORT,
)

UDP_HOST = TEST_STATUS_SERVER_HOST
UDP_PORT = TEST_STATUS_SERVER_PORT
BUFFER_SIZE = 4096

# Main shared status dictionary
status = {}


def parse_value(value: str):
    """Convert strings into int/float/bool when possible."""
    value = value.strip()

    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value


if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((UDP_HOST, UDP_PORT))

        print(f"Status server listening on {UDP_HOST}:{UDP_PORT}")

        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                message = data.decode("utf-8").strip()

                print(f"{datetime.now(UTC).isoformat()} | Received from {addr}: {message}")

                parts = message.split(maxsplit=2)

                if not parts:
                    continue

                command = parts[0].lower()

                # --------------------
                # SET
                # --------------------
                if command == "set":
                    if len(parts) != 3:
                        response = "ERROR: usage: set <key> <value>"
                    else:
                        key = parts[1]
                        value = parse_value(parts[2])

                        status[key] = value

                        print(f"{datetime.now(UTC).isoformat()} | Updated status: {key} = {value!r}")

                        response = "OK"

                    sock.sendto(response.encode(), addr)

                # --------------------
                # GET
                # --------------------
                elif command == "get":
                    if len(parts) < 2:
                        response = "ERROR: usage: get <key|all>"

                    elif parts[1].lower() == "all":
                        response = json.dumps(status)

                    else:
                        key = parts[1]
                        if key in status:
                            response = json.dumps(status[key])
                        else:
                            response = "ERROR: unknown key"

                    sock.sendto(response.encode(), addr)

                else:
                    sock.sendto(b"ERROR: unknown command", addr)

            except KeyboardInterrupt:
                print("Stopping status server")
                break