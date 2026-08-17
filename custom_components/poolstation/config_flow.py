"""Config flow for PoolStation integration."""
from __future__ import annotations

import logging
from typing import Any, Final

import voluptuous as vol
from aiohttp import ClientResponseError, DummyCookieJar
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from pypoolstation import AuthenticationException, TwoFactorAuthRequiredException

from .const import CONF_AUTH_CODE, DOMAIN, TOKEN
from .util import create_account

_LOGGER: Final = logging.getLogger(__name__)

DATA_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

TWO_FACTOR_SCHEMA: Final = vol.Schema(
    {
        vol.Required(CONF_AUTH_CODE): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Poolstation."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self._original_data: Any = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
        return await self._attempt_login(user_input)

    async def async_step_reauth(self, user_input: dict[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._original_data = user_input.copy()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self._show_reauth_confirm_form()

        # Update original data with new credentials
        self._original_data.update(user_input)

        return await self._attempt_reauth(self._original_data)

    async def _attempt_reauth(self, user_input):
        account = self._create_account(user_input)
        errors: dict[str, str]
        errors = {}
        try:
            login_code = user_input.get(CONF_AUTH_CODE, "")
            token = await account.login(login_code=login_code)
        except TwoFactorAuthRequiredException:
            return await self.async_step_reauth_two_factor()
        except (TimeoutError, ClientResponseError):
            errors["base"] = "cannot_connect"
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            existing_entry = await self.async_set_unique_id(
                self._original_data[CONF_EMAIL].lower()
            )
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        TOKEN: token,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            return self.async_abort(reason="reauth_failed_existing")
        # Errors are shown on a form so the user can retry instead of the
        # flow aborting. A failure coming from the 2FA step re-shows that
        # step so the code can be re-entered; anything else re-shows the
        # credentials form.
        if CONF_AUTH_CODE in user_input:
            return self.async_show_form(
                step_id="reauth_two_factor",
                data_schema=TWO_FACTOR_SCHEMA,
                errors=errors,
            )
        return self._show_reauth_confirm_form(errors)

    def _create_account(self, user_input):
        session = async_create_clientsession(self.hass, cookie_jar=DummyCookieJar())
        return create_account(
            session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD], _LOGGER
        )

    async def _attempt_login(self, user_input):
        errors: dict[str, str]
        errors = {}
        account = self._create_account(user_input)

        try:
            login_code = user_input.get(CONF_AUTH_CODE, "")
            token = await account.login(login_code=login_code)
        except TwoFactorAuthRequiredException:
            self._original_data = user_input.copy()
            return await self.async_step_two_factor()
        except (TimeoutError, ClientResponseError):
            errors["base"] = "cannot_connect"
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_EMAIL].lower(),
                data={
                    TOKEN: token,
                    CONF_EMAIL: user_input[CONF_EMAIL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
            )

        if CONF_AUTH_CODE in user_input:
            # The call came from the 2FA step; retry the code instead of
            # discarding it and jumping back to the credentials form.
            return self.async_show_form(
                step_id="two_factor", data_schema=TWO_FACTOR_SCHEMA, errors=errors
            )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    def _show_reauth_confirm_form(
        self, errors: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the API keys form."""
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=self._original_data[CONF_EMAIL]
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_two_factor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the 2FA step."""
        if user_input is None:
            return self.async_show_form(
                step_id="two_factor", data_schema=TWO_FACTOR_SCHEMA
            )

        login_data = self._original_data.copy()
        login_data[CONF_AUTH_CODE] = user_input[CONF_AUTH_CODE]

        return await self._attempt_login(login_data)

    async def async_step_reauth_two_factor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the 2FA step for reauth."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_two_factor", data_schema=TWO_FACTOR_SCHEMA
            )

        login_data = self._original_data.copy()
        login_data[CONF_AUTH_CODE] = user_input[CONF_AUTH_CODE]

        return await self._attempt_reauth(login_data)
