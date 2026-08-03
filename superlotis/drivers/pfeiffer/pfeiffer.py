from superlotis.drivers.pfeiffer.pfeiffer_controller import Controller, Pump
from superlotis.tools.constants import PFEIFFER_IP_ADDRESS, PFEIFFER_PORT

url = f"opc.tcp://{PFEIFFER_IP_ADDRESS}:{PFEIFFER_PORT}"

class Pfeiffer:

    def __init__(self):

        self.controller = Controller(url)
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

    def status(self):

        self.status_dict = {"Backing temperature": self.backing.temperature, 
                    "Turbo power stage temperature": self.turbo.temp_power_stage,
                    "Turbo electronics temperature": self.turbo.temp_electronics,
                    "Turbo lower temperature": self.turbo.temp_lower,
                    "Turbo pump speed": self.turbo.actual_speed,
                    "Turbo driving voltage (V)": self.turbo.drv_voltage,
                    "Turbo driving current (A)": self.turbo.drv_current,
                    "Turbo driving power (W)": self.turbo.drv_power,
                    "Turbo rotor temperature (C)": self.turbo.temp_rotor,
                    "Turbo temperature management mode": self.turbo.cfg_acc_a1,
                    "Configuration accessory connection A1": self.turbo.cfg_acc_a1,
                    "Backing pump error": self.backing.error_code,
                    "Turbo pump error": self.turbo.error_code}
        return self.status_dict

    def close(self):
        self.controller.client.disconnect()
        
if __name__ == "__main__":
    pfeiffer = Pfeiffer()
    print(pfeiffer.status())
