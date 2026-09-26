"""Set up Daylight and review receiver changes before applying them."""

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN, NAME
from .orientation import DEFAULT_OPTIONS, FACING_MODES, validate_options
from .preview import daily_curve, render_svg


class DaylightConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return DaylightOptionsFlow()

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input.get("name", NAME), data={})
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Optional("name", default=NAME): vol.All(str, vol.Length(min=1, max=64))}
            ),
        )


class DaylightOptionsFlow(OptionsFlow):
    """Use a native two-step Configure dialog with an unsaved plot."""

    def __init__(self):
        self._proposed = None

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self._proposed = validate_options(user_input)
            return await self.async_step_review()
        current = self._proposed or {**DEFAULT_OPTIONS, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("tilt", default=current["tilt"]): NumberSelector(
                        NumberSelectorConfig(min=0, max=90, step=1, mode=NumberSelectorMode.SLIDER)
                    ),
                    vol.Required("facing_mode", default=current["facing_mode"]): SelectSelector(
                        SelectSelectorConfig(options=list(FACING_MODES))
                    ),
                    vol.Required("bearing", default=current["bearing"]): NumberSelector(
                        NumberSelectorConfig(min=0, max=359, step=1, mode=NumberSelectorMode.SLIDER)
                    ),
                }
            ),
        )

    async def async_step_review(self, user_input=None):
        local_date = datetime.now(ZoneInfo(self.hass.config.time_zone)).date()
        curve = await self.hass.async_add_executor_job(
            daily_curve,
            self.hass.config.latitude,
            self.hass.config.longitude,
            self.hass.config.time_zone,
            local_date,
            self._proposed,
        )
        token = uuid4().hex
        previews = self.hass.data[DOMAIN]["previews"]
        while len(previews) >= 8:
            previews.pop(next(iter(previews)))
        previews[token] = render_svg(curve)
        path = f"/api/daylight/preview/{token}"
        signed = async_sign_path(self.hass, path, timedelta(minutes=15))
        return self.async_show_menu(
            step_id="review",
            menu_options={"save": "Save settings", "init": "Back to settings"},
            description_placeholders={"preview_url": signed, "date": local_date.isoformat()},
        )

    async def async_step_save(self, user_input=None):
        return self.async_create_entry(title="", data=self._proposed)
