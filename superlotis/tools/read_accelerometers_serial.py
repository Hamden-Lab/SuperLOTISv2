import serial
import csv
import time
from datetime import datetime, UTC

SERIAL_PORT = "COM6"
BAUD_RATE = 2000000

now_utc = datetime.now(UTC).isoformat().replace(":", "-")
OUTPUT_FILE = f"../data/{now_utc}_accelerometer_data.csv"

print(f"Opening {SERIAL_PORT}...")

ser = serial.Serial(
    port=SERIAL_PORT,
    baudrate=BAUD_RATE,
    timeout=1
)

time.sleep(2)
ser.reset_input_buffer()

print("Connected.")
print(f"Saving data to: {OUTPUT_FILE}")
print("Press Ctrl+C to stop.\n")


with open(OUTPUT_FILE, "w", newline="", buffering=1024 * 1024) as csv_file:

    writer = csv.writer(csv_file)

    writer.writerow([
        "time_us",
        "ax1_mps2",
        "ay1_mps2",
        "az1_mps2",
        "ax2_mps2",
        "ay2_mps2",
        "az2_mps2"
    ])

    sample_count = 0

    first_arduino_time = None
    last_arduino_time = None

    python_start = time.perf_counter()

    try:

        while True:

            line = ser.readline()

            if not line:
                continue

            # Decode once
            line = line.decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if line.startswith("time_us"):
                continue

            values = line.split(",")

            if len(values) != 7:
                continue

            try:

                time_us = int(values[0])

                ax1 = float(values[1])
                ay1 = float(values[2])
                az1 = float(values[3])

                ax2 = float(values[4])
                ay2 = float(values[5])
                az2 = float(values[6])

            except ValueError:
                continue

            writer.writerow([
                time_us,
                ax1,
                ay1,
                az1,
                ax2,
                ay2,
                az2
            ])

            sample_count += 1

            if first_arduino_time is None:
                first_arduino_time = time_us

            last_arduino_time = time_us

            # Only flush occasionally
            if sample_count % 1000 == 0:

                csv_file.flush()

                python_elapsed = time.perf_counter() - python_start

                arduino_elapsed = (
                    last_arduino_time - first_arduino_time
                ) / 1_000_000

                if arduino_elapsed > 0:

                    arduino_rate = (
                        sample_count / arduino_elapsed
                    )

                else:
                    arduino_rate = 0

                python_rate = (
                    sample_count / python_elapsed
                )

                print(
                    f"Samples: {sample_count:,} | "
                    f"Arduino: {arduino_rate:,.1f} Hz | "
                    f"Python: {python_rate:,.1f} Hz"
                )

    except KeyboardInterrupt:

        print("\nStopping logger...")

    finally:

        csv_file.flush()
        ser.close()


print("\nFinished.")
print(f"Total samples: {sample_count:,}")
print(f"Data saved to: {OUTPUT_FILE}")