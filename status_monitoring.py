import socket
from datetime import datetime, timezone
import time

from influxdb_client_3 import InfluxDBClient3, Point

from superlotis.tools.utilities import parse_status_response

from superlotis.tools.constants import (
    SLOTIS_STATUS_SERVER_IP_ADDRESS,
    SLOTIS_STATUS_SERVER_PORT,
    INFLUXDB_TOKEN,
    INFLUXDB_DATABASE,
    INFLUXDB_HOST, TCP_BUFFER_SIZE
)

TCP_HOST = SLOTIS_STATUS_SERVER_IP_ADDRESS
TCP_PORT = SLOTIS_STATUS_SERVER_PORT

MEASUREMENT = "devices_status"

client = InfluxDBClient3(
    host=INFLUXDB_HOST,
    database=INFLUXDB_DATABASE,
    token=INFLUXDB_TOKEN,
)


def convert_value(value: str):
    """
    Convert a status value to an appropriate Python type.

    Integer-looking values become int.
    Decimal/exponent values become float.
    Boolean values become bool.
    'None' becomes None.
    Everything else remains a string.
    """

    value = value.strip()

    if value == "None":
        return None

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float / scientific notation
    try:
        return float(value)
    except ValueError:
        pass

    return value



def write_status_to_influxdb(status: dict) -> None:
    """
    Write all status values in a single InfluxDB request.
    Each status key remains a separate field.
    """

    point = Point(MEASUREMENT).time(datetime.now(timezone.utc))

    written = 0

    for key, value in status.items():
        value = convert_value(value)

        # InfluxDB fields cannot be None.
        if value is None:
            continue

        point = point.field(field=key, value=value)
        written += 1

    client.write(record=point)

    print(
        f"{datetime.now(timezone.utc).isoformat()} | "
        f"INFLUXDB | Written {written} fields"
    )


while True:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            sock.connect((TCP_HOST, TCP_PORT))
            sock.sendall(b"get all")

            chunks = []

            while True:
                try:
                    data = sock.recv(TCP_BUFFER_SIZE)

                    if not data:
                        break

                    chunks.append(data)

                    if b"\n.EOF" in data or data.endswith(b".EOF\n"):
                        break

                except socket.timeout:
                    break

            data = b"".join(chunks)

        print(
            f"{datetime.now(timezone.utc).isoformat()} | "
            f"STATUS SERVER | Received {len(data)} bytes"
        )

        status = parse_status_response(data)

        print(
            f"{datetime.now(timezone.utc).isoformat()} | "
            f"STATUS SERVER | Parsed {len(status)} fields"
        )

        write_status_to_influxdb(status)

    except socket.timeout:
        print("Timed out waiting for response from status server.")

    except ConnectionRefusedError:
        print("Connection refused by status server.")

    except ConnectionResetError:
        print("Connection reset by status server.")

    except UnicodeDecodeError as exc:
        print(f"Invalid UTF-8 received from status server: {exc}")

    except Exception as exc:
        print(f"Failed to write status to InfluxDB: {exc}")

    finally:
        time.sleep(5)
