"""Environmental sensors: drivers and the physical validation of issue #4.

- :mod:`.bme280`: Grove BME280 (pressure, temperature, humidity) over I2C.
- :mod:`.grove_adc`: ADC of the Grove Base Hat, used by the analogue Grove
  light sensor. Reported in raw units: no lux without a validated conversion.
- :mod:`.sensors`: one sample per channel as a contract reading, with
  ``value=None`` and quality ``unavailable``/``error`` instead of an invented 0.
- :mod:`.env_check`: command that produces the Markdown evidence report.
"""
