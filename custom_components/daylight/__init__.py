"""A shared clear-sky daylight reference, with no lighting-control policy."""

import logging
from datetime import timedelta

import voluptuous as vol
from aiohttp import web
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NAME
from .model import from_elevation, from_level, load_table, number
from .orientation import _direct_nodes, oriented_daylight, validate_options
from .solar import solar_context

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class DaylightPreviewView(HomeAssistantView):
    """Serve a short-lived, signed review image."""

    url = "/api/daylight/preview/{token}"
    name = "api:daylight:preview"

    def __init__(self, previews):
        self.previews = previews

    async def get(self, request, token):
        svg = self.previews.get(token)
        if svg is None:
            raise web.HTTPNotFound()
        return web.Response(
            text=svg,
            content_type="image/svg+xml",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )


def current_context(hass):
    return solar_context(
        hass.config.latitude, hass.config.longitude, hass.config.time_zone, dt_util.utcnow()
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register pure response actions once, independent of config-entry lifecycle."""
    await hass.async_add_executor_job(load_table)
    await hass.async_add_executor_job(_direct_nodes)
    hass.data[DOMAIN] = {"previews": {}}
    hass.http.register_view(DaylightPreviewView(hass.data[DOMAIN]["previews"]))

    async def calculate_elevation(call: ServiceCall) -> dict:
        try:
            return from_elevation(call.data["geometric_elevation"])
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def calculate_level(call: ServiceCall) -> dict:
        try:
            peak = call.data.get("noon_elevation")
            if peak is None:
                peak = current_context(hass)["noon_elevation"]
            return from_level(call.data["daylight_level"], peak)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    def numeric_input(name, low, high):
        def validate(value):
            try:
                return number(value, name, low, high)
            except ValueError as err:
                raise vol.Invalid(str(err)) from err

        return validate

    hass.services.async_register(
        DOMAIN,
        "from_elevation",
        calculate_elevation,
        schema=vol.Schema(
            {vol.Required("geometric_elevation"): numeric_input("geometric_elevation", -90, 90)}
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "from_level",
        calculate_level,
        schema=vol.Schema(
            {
                vol.Required("daylight_level"): numeric_input("daylight_level", 0, 1),
                vol.Optional("noon_elevation"): numeric_input("noon_elevation", -90, 90),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


class DaylightCoordinator(DataUpdateCoordinator[dict]):
    """One synchronized current reference for all daylight entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass, _LOGGER, name=NAME, config_entry=entry, update_interval=timedelta(minutes=1)
        )

    async def _async_update_data(self):
        context = current_context(self.hass)
        options = validate_options(self.config_entry.options)
        return {
            **oriented_daylight(
                context["geometric_elevation"], context["solar_azimuth"], **options
            ),
            **context,
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = DaylightCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Refresh current values as soon as reviewed options are saved."""
    await entry.runtime_data.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
