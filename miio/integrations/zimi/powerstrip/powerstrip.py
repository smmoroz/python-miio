import enum
import logging
from collections import defaultdict
from typing import Any, Optional

import click

from miio import Device, DeviceStatus
from miio.click_common import EnumType, command, format_output
from miio.devicestatus import sensor, setting
from miio.utils import deprecated

_LOGGER = logging.getLogger(__name__)

MODEL_POWER_STRIP_V1 = "qmi.powerstrip.v1"
MODEL_POWER_STRIP_V2 = "zimi.powerstrip.v2"

AVAILABLE_PROPERTIES = {
    MODEL_POWER_STRIP_V1: [
        "power",
        "temperature",
        "current",
        "mode",
        "power_consume_rate",
        "voltage",
        "power_factor",
        "elec_leakage",
    ],
    MODEL_POWER_STRIP_V2: [
        "power",
        "temperature",
        "current",
        "mode",
        "power_consume_rate",
        "wifi_led",
        "power_price",
    ],
}


class PowerMode(enum.Enum):
    Eco = "green"
    Normal = "normal"


class PowerStripStatus(DeviceStatus):
    """Container for status reports from the power strip."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Supported device models: qmi.powerstrip.v1, zimi.powerstrip.v2.

        Response of a Power Strip 2 (zimi.powerstrip.v2):
        {'power','on', 'temperature': 48.7, 'current': 0.05, 'mode': None,
         'power_consume_rate': 4.09, 'wifi_led': 'on', 'power_price': 49}
        """
        self.data = data

    @property
    def power(self) -> str:
        """Current power state."""
        return self.data["power"]

    @property
    @setting(name="Power", setter_name="set_power", device_class="outlet")
    def is_on(self) -> bool:
        """True if the device is turned on."""
        return self.power == "on"

    @property
    @sensor(name="Temperature", unit="C", device_class="temperature")
    def temperature(self) -> float:
        """Current temperature."""
        return self.data["temperature"]

    @property
    @sensor(name="Current", unit="A", device_class="current")
    def current(self) -> Optional[float]:
        """Current, if available.

        Meaning and voltage reference unknown.
        """
        if self.data["current"] is not None:
            return self.data["current"]
        return None

    @property
    @sensor(name="Load power", unit="W", device_class="power")
    def load_power(self) -> Optional[float]:
        """Current power load, if available."""
        if self.data["power_consume_rate"] is not None:
            return self.data["power_consume_rate"]
        return None

    @property
    def mode(self) -> Optional[PowerMode]:
        """Current operation mode, can be either green or normal."""
        if self.data["mode"] is not None:
            return PowerMode(self.data["mode"])
        return None

    @property  # type: ignore
    @deprecated("Use led instead of wifi_led")
    def wifi_led(self) -> Optional[bool]:
        """True if the wifi led is turned on."""
        return self.led

    @property
    @setting(
        name="LED", icon="mdi:led-outline", setter_name="set_led", device_class="switch"
    )
    def led(self) -> Optional[bool]:
        """True if the wifi led is turned on."""
        if "wifi_led" in self.data and self.data["wifi_led"] is not None:
            return self.data["wifi_led"] == "on"
        return None

    @property
    def power_price(self) -> Optional[int]:
        """The stored power price, if available."""
        if "power_price" in self.data and self.data["power_price"] is not None:
            return self.data["power_price"]
        return None

    @property
    @sensor(name="Leakage current", unit="A", device_class="current")
    def leakage_current(self) -> Optional[int]:
        """The leakage current, if available."""
        if "elec_leakage" in self.data and self.data["elec_leakage"] is not None:
            return self.data["elec_leakage"]
        return None

    @property
    @sensor(name="Voltage", unit="V", device_class="voltage")
    def voltage(self) -> Optional[float]:
        """The voltage, if available."""
        if "voltage" in self.data and self.data["voltage"] is not None:
            return self.data["voltage"] / 100.0
        return None

    @property
    @sensor(name="Power Factor", unit="%", device_class="power_factor")
    def power_factor(self) -> Optional[float]:
        """The power factor, if available."""
        if "power_factor" in self.data and self.data["power_factor"] is not None:
            return self.data["power_factor"]
        return None


class PowerStrip(Device):
    """Main class representing the smart power strip."""

    _supported_models = [MODEL_POWER_STRIP_V1, MODEL_POWER_STRIP_V2]

    @command(
        default_output=format_output(
            "",
            "Power: {result.power}\n"
            "Temperature: {result.temperature} °C\n"
            "Voltage: {result.voltage} V\n"
            "Current: {result.current} A\n"
            "Load power: {result.load_power} W\n"
            "Power factor: {result.power_factor}\n"
            "Power price: {result.power_price}\n"
            "Leakage current: {result.leakage_current} A\n"
            "Mode: {result.mode}\n"
            "WiFi LED: {result.wifi_led}\n",
        )
    )
    def status(self) -> PowerStripStatus:
        """Retrieve properties."""
        properties = AVAILABLE_PROPERTIES.get(
            self.model, AVAILABLE_PROPERTIES[MODEL_POWER_STRIP_V1]
        )
        values = self.get_properties(properties)

        return PowerStripStatus(defaultdict(lambda: None, zip(properties, values)))

    @command(click.argument("power", type=bool))
    def set_power(self, power: bool):
        """Set the power on or off."""
        if power:
            return self.on()
        return self.off()

    @command(default_output=format_output("Powering on"))
    def on(self):
        """Power on."""
        return self.send("set_power", ["on"])

    @command(default_output=format_output("Powering off"))
    def off(self):
        """Power off."""
        return self.send("set_power", ["off"])

    @command(
        click.argument("mode", type=EnumType(PowerMode)),
        default_output=format_output("Setting mode to {mode}"),
    )
    def set_power_mode(self, mode: PowerMode):
        """Set the power mode."""

        # green, normal
        return self.send("set_power_mode", [mode.value])

    @deprecated("use set_led instead of set_wifi_led")
    @command(
        click.argument("led", type=bool),
        default_output=format_output(
            lambda led: "Turning on WiFi LED" if led else "Turning off WiFi LED"
        ),
    )
    def set_wifi_led(self, led: bool):
        """Set the wifi led on/off."""
        self.set_led(led)

    @command(
        click.argument("led", type=bool),
        default_output=format_output(
            lambda led: "Turning on LED" if led else "Turning off LED"
        ),
    )
    def set_led(self, led: bool):
        """Set the wifi led on/off."""
        if led:
            return self.send("set_wifi_led", ["on"])
        else:
            return self.send("set_wifi_led", ["off"])

    @command(
        click.argument("price", type=int),
        default_output=format_output("Setting power price to {price}"),
    )
    def set_power_price(self, price: int):
        """Set the power price."""
        if price < 0 or price > 999:
            raise ValueError("Invalid power price: %s" % price)

        return self.send("set_power_price", [price])

    @command(
        click.argument("power", type=bool),
        default_output=format_output(
            lambda led: (
                "Turning on real-time power measurement"
                if led
                else "Turning off real-time power measurement"
            )
        ),
    )
    def set_realtime_power(self, power: bool):
        """Set the realtime power on/off."""
        if power:
            return self.send("set_rt_power", [1])
        else:
            return self.send("set_rt_power", [0])
