import os
from superlotis.drivers.pfeiffer.pfeiffer_controller import Controller, Pump
from superlotis.tools.constants import PFEIFFER_IP_ADDRESS, PFEIFFER_PORT
import socket
import time

url = f"opc.tcp://{PFEIFFER_IP_ADDRESS}:{PFEIFFER_PORT}"

try:
    controller = Controller(url)
    controller.client.connect()

    turbo = Pump(controller, "TC80", 1)
    backing = Pump(controller, "MVP", 2)

    backing.pumping_power = True

    turbo.pumping_power = True

    while True:

        print(f"Backing temperature: {backing.temperature}")

        print(f"Turbo power stage temperature: {turbo.temp_power_stage}")
        print(f"Turbo electronics temperature: {turbo.temp_electronics}")
        print(f"Turbo lower temperature: {turbo.temp_lower}")
        print(f"Turbo pump speed: {turbo.actual_speed}")
        print(f"Turbo driving voltage (V): {turbo.drv_voltage:.2f}")
        print(f"Turbo driving current (A): {turbo.drv_current:.2f}")
        print(f"Turbo driving power (W): {turbo.drv_power}")
        print(f"Turbo rotor temperature (C): {turbo.temp_rotor}")

        print(f"Turbo temperature management mode: {turbo.cfg_acc_a1}")

        print(f"Configuration accessory connection A1: {turbo.cfg_acc_a1}")

        

        print(f"Backing pump error: {backing.error_code}")
        print(f"Turbo pump error: {turbo.error_code}")

        time.sleep(5)

except KeyboardInterrupt:

# time.sleep(15)
    controller.client.disconnect()