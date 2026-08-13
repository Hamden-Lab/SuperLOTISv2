import json
import socket
from datetime import datetime, timezone
import time
from influxdb_client_3 import InfluxDBClient3, Point

from superlotis.tools.constants import (
    TEST_STATUS_SERVER_HOST,
    TEST_STATUS_SERVER_PORT, INFLUXDB_TOKEN, INFLUXDB_DATABASE, INFLUXDB_HOST
)

UDP_HOST = TEST_STATUS_SERVER_HOST
UDP_PORT = TEST_STATUS_SERVER_PORT
BUFFER_SIZE = 4096

MEASUREMENT = "devices_status"

client = InfluxDBClient3(
        host=INFLUXDB_HOST,
        database=INFLUXDB_DATABASE,
        token=INFLUXDB_TOKEN,
    )

def write_status_to_influxdb(status: dict) -> None:
    """
    Write all status values in a single InfluxDB request.
    Each status key remains a separate field.
    """

    point = Point(MEASUREMENT).time(datetime.now(timezone.utc))

    for key, value in status.items():
        if isinstance(value, (dict, list)):
            continue

        point = point.field(field=key, value=value)

    client.write(record=point)

    print(
        f"{datetime.now(timezone.utc).isoformat()} | "
        f"INFLUXDB | Written {len(status)} fields"
    )


with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.settimeout(2.0)

    while True:
        try:
            # Send request to status server
            sock.sendto(b"get all", (UDP_HOST, UDP_PORT))

            data, _ = sock.recvfrom(BUFFER_SIZE)

            # Decode JSON response into a Python dict
            status = json.loads(data.decode("utf-8"))

            print(
                f"{datetime.now(timezone.utc).isoformat()} | "
                f"STATUS SERVER | Received status of {len(status)} fields"
            )

            # Write status to InfluxDB
            write_status_to_influxdb(status)

            time.sleep(5)

        except socket.timeout:
            print("Timed out waiting for response from status server.")

        except json.JSONDecodeError as exc:
            print(f"Invalid JSON received from status server: {exc}")

        except Exception as exc:
            print(f"Failed to write status to InfluxDB: {exc}")

        except KeyboardInterrupt:
            break