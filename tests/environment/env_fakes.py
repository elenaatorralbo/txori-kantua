"""Fake I2C bus with a BME280 and a Grove Base Hat ADC, no hardware needed."""

import struct

EREMOTEIO = 121  # Linux errno of an I2C NACK; not defined on macOS

# Calibration of the worked example in the Bosch BMP280 datasheet (section 8.2):
# adc_T = 519888 -> 25.08 degC, adc_P = 415148 -> 100653.27 Pa. The BME280
# uses the same temperature and pressure compensation.
TP_EXAMPLE = (27504, 26435, -1000, 36477, -10685, 3024, 2855, 140, -7, 15500, -14600, 6000)
ADC_T_EXAMPLE = 519888
ADC_P_EXAMPLE = 415148
# Humidity calibration typical of a real BME280.
H_EXAMPLE = dict(H1=75, H2=362, H3=0, H4=313, H5=50, H6=30)
ADC_H_EXAMPLE = 30000


def tp_block(tp=TP_EXAMPLE, h1=H_EXAMPLE["H1"]):
    return list(struct.pack("<HhhHhhhhhhhh", *tp) + bytes([0, h1]))


def h_block(H2, H3, H4, H5, H6, **_):
    h4, h5 = H4 & 0xFFF, H5 & 0xFFF
    return list(struct.pack("<hB", H2, H3)) + [h4 >> 4, (h4 & 0x0F) | ((h5 & 0x0F) << 4), h5 >> 4,
                                               H6 & 0xFF]


def data_block(adc_t, adc_p, adc_h):
    return [adc_p >> 12, (adc_p >> 4) & 0xFF, (adc_p & 0x0F) << 4,
            adc_t >> 12, (adc_t >> 4) & 0xFF, (adc_t & 0x0F) << 4,
            adc_h >> 8, adc_h & 0xFF]


class FakeBme280:
    def __init__(self, chip_id=0x60, adc=(ADC_T_EXAMPLE, ADC_P_EXAMPLE, ADC_H_EXAMPLE), busy_polls=0):
        self.registers = {0xD0: chip_id}
        self.calib_tp = tp_block()
        self.calib_h = h_block(**H_EXAMPLE)
        self.adc = adc
        self.busy_polls = busy_polls
        self.writes = []

    def read_byte(self, register):
        if register == 0xF3:  # status
            if self.busy_polls:
                self.busy_polls -= 1
                return 0x08
            return 0x00
        return self.registers.get(register, 0)

    def read_block(self, register, length):
        if register == 0x88:
            return self.calib_tp[:length]
        if register == 0xE1:
            return self.calib_h[:length]
        if register == 0xF7:
            return data_block(*self.adc)[:length]
        raise AssertionError(f"unexpected block read at {register:#x}")


class FakeAdc:
    def __init__(self, product=0x0004, ratio=420, millivolts=1386):
        self.product = product
        self.ratio = {0: ratio}
        self.millivolts = {0: millivolts}
        self.selected = None

    def read_word(self, register):
        if register == 0x00:
            return self.product
        if 0x30 <= register < 0x38:
            return self.ratio.get(register - 0x30, 0)
        if 0x20 <= register < 0x28:
            return self.millivolts.get(register - 0x20, 0)
        if 0x10 <= register < 0x18:
            return self.ratio.get(register - 0x10, 0) * 4095 // 1000
        raise AssertionError(f"unexpected ADC register {register:#x}")


class FakeBus:
    """smbus-like bus. Absent addresses fail like a NACK (EREMOTEIO)."""

    def __init__(self, devices=None):
        self.devices = dict(devices or {})

    def _device(self, address):
        if address not in self.devices:
            raise OSError(EREMOTEIO, "Remote I/O error")
        return self.devices[address]

    def read_byte_data(self, address, register):
        return self._device(address).read_byte(register)

    def read_i2c_block_data(self, address, register, length):
        return self._device(address).read_block(register, length)

    def write_byte_data(self, address, register, value):
        self._device(address).writes.append((register, value))

    def write_byte(self, address, value):
        self._device(address).selected = value

    def read_word_data(self, address, register):
        return self._device(address).read_word(register)

    def unplug(self, address):
        return self.devices.pop(address)

    def plug(self, address, device):
        self.devices[address] = device
