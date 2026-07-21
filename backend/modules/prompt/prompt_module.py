"""
PromptManager — the single public class for the prompt module.

19_Request_Lifecycle.md §4 — Phase 4: Prompt Compilation.
07_Module_Design.md §2.C — Prompt Manager responsibilities.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from backend.modules.prompt._compiler import PromptCompiler
from backend.modules.prompt._loader import load_template
from backend.modules.prompt._template import PromptTemplate
from backend.modules.prompt._validation import PromptValidator


class PromptManager:
    """Central prompt compilation manager.

    Owns the system prompt template, compiles it with runtime variables,
    and validates the output before returning it.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : Any | None
        Application configuration (``AppConfig`` or compatible).  Used
        to read feature flags and user preferences for template variables.
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is created.
    templates_dir : Path | None
        Directory containing ``.j2`` template files.  Defaults to
        ``backend/modules/prompt/templates/``.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        templates_dir: Path | None = None,
        event_bus: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("naira.prompt")
        self._templates_dir = templates_dir
        self._event_bus = event_bus
        self._template: PromptTemplate | None = None
        self._degraded: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Load the system prompt template from disk.

        Called once during boot.  Falls back to the built-in default
        if the file is missing.
        """
        try:
            self._template = load_template("system", templates_dir=self._templates_dir)
            self._logger.info(
                "System prompt template loaded — source: %s", self._template.source
            )
        except FileNotFoundError:
            self._template = load_template("system")
            self._logger.warning(
                "System prompt template file not found — using built-in fallback"
            )

    async def async_shutdown(self) -> None:
        """Release the cached template."""
        self._template = None
        self._logger.info("Prompt manager shut down.")

    def degrade(self) -> None:
        """Release heavyweight resources and mark as degraded."""
        self._template = None
        self._degraded = True
        self._logger.warning("Prompt manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile(self, variables: dict[str, str] | None = None) -> str:
        """Compile the system prompt with the given *variables*.

    19_Request_Lifecycle.md §4 — Prompt compilation (Phase 4).

        Parameters
        ----------
        variables : dict[str, str] | None
            Runtime variables to inject into the template (date,
            capabilities, user name, etc.).  If ``None``, only
            default variables (current date) are included.

        Returns
        -------
        str
            The fully compiled system prompt.

        Raises
        ------
        PromptValidationError
            If compilation fails or the result fails validation.
        RuntimeError
            If ``async_init()`` has not been called.
        """
        self._ensure_initialised()

        template = self._template

        merged_vars = _build_default_variables(self._config)
        if variables:
            merged_vars.update(variables)

        compiled = PromptCompiler.compile(template, merged_vars)

        PromptValidator.validate(compiled, max_length=len(compiled) + 1)

        return compiled

    def get_template_source(self) -> str | None:
        """Return the source description of the loaded template.

        Returns ``"built-in"``, a file path, or ``None`` if no template
        has been loaded.
        """
        if self._template is not None:
            return self._template.source
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_initialised(self) -> None:
        if self._template is None:
            raise RuntimeError(
                "PromptManager not initialised — call async_init() before compile()"
            )


def _build_default_variables(config: object | None) -> dict[str, str]:
    """Build a base set of template variables from *config*.

    Includes the current date and capabilities derived from feature flags.
    """
    variables: dict[str, str] = {
        "date": date.today().isoformat(),
    }

    capabilities: list[str] = []

    if config is not None:
        try:
            if getattr(config, "features", None) is not None:
                flags = config.features
                if getattr(flags, "vision", False):
                    capabilities.append("Screen vision and OCR")
                if getattr(flags, "voice", False):
                    capabilities.append("Voice input and output")
                if getattr(flags, "browser", False):
                    capabilities.append("Web browsing")
                if getattr(flags, "pc_control", False):
                    capabilities.append("PC control and automation")
                if getattr(flags, "file_manager", False):
                    capabilities.append("File management")
        except Exception:
            pass

        try:
            user_name = getattr(config, "user_name", None)
            if user_name:
                variables["user_name"] = str(user_name)
        except Exception:
            pass

    if capabilities:
        variables["capabilities"] = ", ".join(capabilities)
    else:
        variables["capabilities"] = ""

    return variables
