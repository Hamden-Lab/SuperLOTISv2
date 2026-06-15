from drivers.pfeiffer.pfeiffer_controller import Controller, Pump
from tools.constants import PFEIFFER_IP_ADDRESS, PFEIFFER_PORT

from drivers.inficon.inficon import PxG55xRS485
# from tools.constants import CAM_INFICON_VACUUM_GAUGE_IP_ADDRESS, CAM_INFICON_VACUUM_GAUGE_PORT
# from tools.constants import PUMP_INFICON_VACUUM_GAUGE_IP_ADDRESS, PUMP_INFICON_VACUUM_GAUGE_PORT

import socket
import time

try:
    # Connect to Pfeiffer vacuum pump
    url = f"opc.tcp://{PFEIFFER_IP_ADDRESS}:{PFEIFFER_PORT}"
    controller = Controller(url)
    controller.client.connect()
    turbo = Pump(controller, "TC80", 1)
    backing = Pump(controller, "MVP", 2)

    