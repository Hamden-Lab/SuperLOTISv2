import os
from superlotis.drivers.pfeiffer.pfeiffer_controller import Controller, Pump
from superlotis.tools.constants import PFEIFFER_IP_ADDRESS, PFEIFFER_PORT
import socket
import time

url = f"opc.tcp://{PFEIFFER_IP_ADDRESS}:{PFEIFFER_PORT}"

controller = Controller(url)
controller.client.connect()

turbo = Pump(controller, "TC80", 1)
backing = Pump(controller, "MVP", 2)

# print(PUMP_PARAMETERS["MVP"]["pumping_power"])

backing.pumping_power = False

print(turbo.heating)

# time.sleep(15)

# backing.pumping_power = False

controller.client.disconnect()