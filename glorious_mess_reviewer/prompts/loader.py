"""Jinja2 prompt rendering with version tracking."""

from __future__ import annotations

from functools import lru_cache
import hashlib
from dataclasses import dataclass
from importlib import resources

from jinja2 import Environment, StrictUndefined


@dataclass(frozen=True)
class PromptTemplate:
    """Rendered prompt plus metadata for observability."""

    template_name: str
    version: str
    content: str

    @property
    def sha1(self) -> str:
        """Return a stable hash for the rendered prompt."""

        return hashlib.sha1(self.content.encode("utf-8")).hexdigest()


_ENVIRONMENT = Environment(
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_TEMPLATE_ROOT = resources.files("glorious_mess_reviewer.prompts.templates")


@lru_cache(maxsize=None)
def _compiled_template(template_name: str):
    """Load and compile a packaged template once per process."""

    template_text = _TEMPLATE_ROOT.joinpath(template_name).read_text(encoding="utf-8")
    return _ENVIRONMENT.from_string(template_text)


def render_prompt(template_name: str, version: str = "v1", **context: object) -> PromptTemplate:
    """Render a prompt template from packaged Jinja files."""

    template = _compiled_template(template_name)
    context.setdefault("venue_guidance_text", "")
    context.setdefault("venue_examples_text", "")
    content = template.render(**context).strip()
    return PromptTemplate(template_name=template_name, version=version, content=content)
