from superlotis.drivers.pfeiffer.pfeiffer_controller import Controller, Pump
from superlotis.tools.constants import PFEIFFER_IP_ADDRESS, PFEIFFER_PORT

class Pfeiffer:

    def __init__(self, ip_address=PFEIFFER_IP_ADDRESS, port=PFEIFFER_PORT):

        self.ip_address = ip_address
        self.port = port
        self.url = f"opc.tcp://{self.ip_address}:{self.port}"

        self.controller = Controller(self.url)
        self.controller.client.connect()
    
        self.turbo = Pump(self.controller, "TC80", 1)
        self.backing = Pump(self.controller, "MVP", 2)

    def start_turbo(self):
        self.turbo.pumping_power = True

    def start_backing(self):
        self.backing.pumping_power = True

    def stop_turbo(self):
        self.turbo.pumping_power = False

    def stop_backing(self):
        self.backing.pumping_power = False

    def get_status(self):

        self.status_dict = {"backing_temperature": self.backing.temperature, 
                    "turbo_power_stage_temperature": self.turbo.temp_power_stage,
                    "turbo_electronics_temperature": self.turbo.temp_electronics,
                    "turbo_lower_temperature": self.turbo.temp_lower,
                    "turbo_pump_speed": self.turbo.actual_speed,
                    "turbo_driving_voltage": self.turbo.drv_voltage,
                    "turbo_driving_current": self.turbo.drv_current,
                    "turbo_driving_power": self.turbo.drv_power,
                    "turbo_rotor_temperature": self.turbo.temp_rotor,
                    "turbo_temperature_management_mode": self.turbo.cfg_acc_a1,
                    "configuration_accessory_connection_A1": self.turbo.cfg_acc_a1,
                    "backing_pump_error": self.backing.error_code,
                    "turbo_pump_error": self.turbo.error_code}
        
        return self.status_dict

    def close(self):
        self.controller.client.disconnect()
        
if __name__ == "__main__":
    pfeiffer = Pfeiffer()
    print(pfeiffer.get_status())
