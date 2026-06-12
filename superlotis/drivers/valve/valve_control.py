import cyberpower.cyberpower as cp

class valve(object):

    def __init__(self, host, user, password, outlet):
        self.pdu = cp.CyberPower(host, user, password)
        self.outlet = outlet

    def open(self):
        self.pdu.power_on(self.outlet)

    def close(self):
        self.pdu.power_off(self.outlet)