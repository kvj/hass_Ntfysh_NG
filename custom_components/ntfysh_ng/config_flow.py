from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector

from .constants import DOMAIN
from .coordinator import async_rest_status_code

import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)

async def _validate(hass, input: dict) -> (str | None, dict):
    code = await async_rest_status_code(input["url"], "/v1/health")
    if code != 200:
        return "invalid_url", None
    return None, input

def _create_schema(hass, input: dict, flow: str = "config"):
    schema = vol.Schema({})
    if flow == "config":
        schema = schema.extend({
            vol.Required("title", default=input.get("title")): selector({"text": {}}),
        })
    
    schema = schema.extend({
        vol.Required("url", default=input.get("url")): selector({
            "text": { "type": "url" }
        }),
        vol.Optional("token", default=input.get("token", "")): selector({
            "text": { "type": "password" }
        }),
        vol.Optional("subscribe", default=input.get("subscribe", "")): selector({
            "text": {}
        }),
    })
    return schema

class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):


    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_create_schema(self.hass, {
                "url": "https://ntfy.sh",
                "title": "ntfy.sh",
            }))
        else:
            _LOGGER.debug(f"Input: {user_input}")
            err, data = await _validate(self.hass, user_input)
            if err is None:
                await self.async_set_unique_id(data["title"])
                self._abort_if_unique_id_configured()
                _LOGGER.debug(f"Ready to save: {data}")
                return self.async_create_entry(title=data["title"], options=data, data={"title": data["title"]})
            else:
                return self.async_show_form(step_id="user", data_schema=_create_schema(self.hass, user_input), errors=dict(base=err))

    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):

    def __init__(self, entry):
        self.config_entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is None:
            _LOGGER.debug(f"Making options: {self.config_entry.as_dict()}")
            return self.async_show_form(step_id="init", data_schema=_create_schema(self.hass, self.config_entry.as_dict()["options"], flow="options"))
        else:
            _LOGGER.debug(f"Input: {user_input}")
            err, data = await _validate(self.hass, user_input)
            if err is None:
                _LOGGER.debug(f"Ready to update: {data}")
                result = self.async_create_entry(title="", data=data)
                return result
            else:
                return self.async_show_form(step_id="init", data_schema=_create_schema(self.hass, user_input), errors=dict(base=err))
