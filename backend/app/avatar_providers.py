"""Image-provider boundaries. Provider choice never silently changes to cloud."""

import base64
import binascii
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.avatar_images import MAX_OUTPUT_BYTES, InvalidAvatarImage, normalize_upload
from app.avatar_pixel import LEGACY_STYLE, LOCAL_STYLES, PIXEL_STYLE
from app.telemetry import (
    SpanKind,
    operation_span,
    provider_finished,
    provider_label,
    span_result,
    trace_headers,
)

AVATAR_PROMPT = (
    "Create one PNBallie foosball player avatar. Image 1 is the user's portrait: "
    "preserve their recognizable facial features and hairstyle. Image 2 is our "
    "headless foosball body and style reference. Put the person's head on that "
    "same miniature foosball body, with the same pose, green-and-white shirt, "
    "horizontal rod, football, proportions, bold outlines and cheerful cartoon "
    "style. Give the portrait a slightly pixelated game-art finish; do not paste "
    "a photorealistic face. One centered complete figure, ample margin, no text, "
    "no other people, no scene, no shadow outside the figure. Transparent PNG "
    "background, never draw a checkerboard to imitate transparency."
)

AZURE_AVATAR_PROMPT = 'We hebben een kleine app om tafelvoetbal ranking bij te houden, kan je een kleine animated voetbal retro avatar stijl profielfoto maken met transparante achtergrond van die profielfoto.\n\nAfbeelding 1 is mijn selfie: gebruik deze voor mijn herkenbare gezicht, kapsel en gezichtsuitdrukking. Afbeelding 2 is de template: zet mijn getekende hoofd op dit tafelvoetbalpoppetje en behoud het groen-witte shirt, de houding, de horizontale stang, de voetbal en de volledige omlijning van het poppetje. Laat het gezicht aansluiten bij de getekende retrostijl van de template, met voldoende detail om mij makkelijk te herkennen. Geen fotografisch uitgeknipt hoofd en geen grove pixelblokken. Met animated bedoel ik hier de uitstraling van een getekend personage in één stilstaande afbeelding. Eén compleet poppetje met ruimte rondom, geen tekst of extra objecten. Lever een PNG met echte transparantie, geen getekend schaakbordpatroon of achtergrondkleur.\n'

LOCAL_BUSY_HEADER = "X-PNBallie-Avatar-State"
LOCAL_BUSY_RETRY_SECONDS = 30
MAX_BUSY_RETRY_SECONDS = 300


class AvatarProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AvatarProviderBusy(AvatarProviderError):
    """The private local service accepted no work because its sole slot is busy."""

    def __init__(self, retry_after: int = LOCAL_BUSY_RETRY_SECONDS, *, capacity: bool = False):
        super().__init__("De eigen server heeft onvoldoende vrije capaciteit. Je opdracht wacht." if capacity else
                         "De afbeeldingsdienst is bezig. Je opdracht wacht op een vrije plek.", retryable=True)
        self.retry_after = max(LOCAL_BUSY_RETRY_SECONDS, min(MAX_BUSY_RETRY_SECONDS, retry_after))


@dataclass(frozen=True)
class AvatarSettings:
    local_url: str
    local_token: str
    openai_key: str
    openai_model: str
    reference_path: Path
    timeout: float = 3600
    local_style: str = LEGACY_STYLE
    check_capacity: bool = False

    azure_key: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = ""
    azure_reference_path: Path = Path(__file__).parent / "assets" / "avatar-cloud-template.png"
    default_provider: str = "local"

    @classmethod
    def from_env(cls) -> "AvatarSettings":
        return cls(
            azure_key=os.getenv("AZURE_OPENAI_API_KEY", "").strip(),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/"),
            azure_deployment=os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT", "").strip(),
            default_provider=os.getenv("AVATAR_DEFAULT_PROVIDER", "local").strip(),
            local_url=os.getenv("AVATAR_LOCAL_URL", "").strip(),
            local_token=os.getenv("AVATAR_SERVICE_TOKEN", "").strip(),
            openai_key=os.getenv("OPENAI_API_KEY", "").strip(),
            # Explicit selection prevents an unnoticed model/cost change.
            openai_model=os.getenv("OPENAI_IMAGE_MODEL", "").strip(),
            reference_path=Path(os.getenv(
                "AVATAR_REFERENCE_PATH", str(Path(__file__).parent / "assets" / "avatar-body.png"),
            )),
            timeout=max(30, min(3600, float(os.getenv("AVATAR_TIMEOUT_SECONDS", "3600")))),
            local_style=os.getenv("AVATAR_LOCAL_STYLE", LEGACY_STYLE).strip(),
            check_capacity=os.getenv("AVATAR_CHECK_CAPACITY", "false").lower() == "true",
        )

    @property
    def local_available(self) -> bool:
        return bool(self.local_url and self.local_token and self.local_style in LOCAL_STYLES
                    and (self.local_style == PIXEL_STYLE or self.reference_path.is_file()))

    @property
    def openai_available(self) -> bool:
        return bool(self.openai_key and self.openai_model and self.reference_path.is_file())

    @property
    def azure_available(self) -> bool:
        try:
            url = urlsplit(self.azure_endpoint)
            # Credentials are only sent to explicitly configured Azure HTTPS hosts.
            valid_url = (url.scheme == "https" and url.hostname is not None
                         and url.hostname.endswith((".openai.azure.com", ".cognitiveservices.azure.com"))
                         and not url.username and not url.password and url.port in {None, 443}
                         and url.path in {"", "/"} and not url.query and not url.fragment)
        except ValueError:
            return False
        return bool(valid_url and self.azure_key and self.azure_deployment and self.azure_reference_path.is_file())

    def available(self, provider: str) -> bool:
        return {"local": self.local_available, "openai": self.openai_available,
                "azure": self.azure_available}.get(provider, False)


def _decode_response(payload: dict) -> bytes:
    try:
        encoded = payload["data"][0]["b64_json"]
        if not isinstance(encoded, str) or len(encoded) > MAX_OUTPUT_BYTES * 4 // 3 + 4:
            raise ValueError("Oversized provider image")
        return base64.b64decode(encoded, validate=True)
    except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as exc:
        raise AvatarProviderError("Het model gaf geen bruikbare afbeelding terug.") from exc


class AvatarProvider:
    def __init__(self, settings: AvatarSettings | None = None, *, transport=None):
        self.settings = settings or AvatarSettings.from_env()
        self.transport = transport

    def generate(self, *, source_png: bytes, provider: str, cloud_consent: bool,
                 job_id: str) -> bytes:
        started = time.monotonic()
        outcome, error_type = "success", "none"
        with operation_span("avatar.provider", kind=SpanKind.CLIENT,
                            attributes={"avatar.provider": provider_label(provider)}) as span:
            try:
                return self._generate(source_png=source_png, provider=provider,
                                      cloud_consent=cloud_consent, job_id=job_id)
            except AvatarProviderBusy:
                outcome = "unavailable"
                raise
            except AvatarProviderError as exc:
                outcome, error_type = ("retry" if exc.retryable else "failure"), "provider_error"
                raise
            except Exception:
                outcome, error_type = "failure", "unexpected"
                raise
            finally:
                span_result(span, outcome=outcome, error=error_type)
                provider_finished(provider, outcome, time.monotonic() - started)

    def _generate(self, *, source_png: bytes, provider: str, cloud_consent: bool,
                  job_id: str) -> bytes:
        config = self.settings
        if provider not in {"local", "openai", "azure"}:
            raise AvatarProviderError("Deze afbeeldingsdienst wordt niet ondersteund.")
        if provider in {"openai", "azure"} and not cloud_consent:
            raise AvatarProviderError("Toestemming voor verwerking door de clouddienst ontbreekt.")
        available = config.available(provider)
        if not available:
            raise AvatarProviderError("Deze afbeeldingsdienst is nog niet ingesteld.")
        reference = b""
        if provider != "local" or config.local_style == LEGACY_STYLE:
            try:
                reference_path = config.azure_reference_path if provider == "azure" else config.reference_path
                reference = normalize_upload(reference_path.read_bytes(), "image/png")
            except (OSError, InvalidAvatarImage) as exc:
                raise AvatarProviderError("Het referentiepoppetje is niet beschikbaar.") from exc

        try:
            # Stream the response so a misbehaving local endpoint cannot allocate
            # unbounded memory. Do not follow provider-controlled result URLs.
            with httpx.Client(timeout=httpx.Timeout(config.timeout, connect=10),
                              transport=self.transport, follow_redirects=False) as client:
                if provider == "local":
                    inputs = {"source_png": base64.b64encode(source_png).decode()}
                    if config.local_style == PIXEL_STYLE:
                        inputs["style"] = PIXEL_STYLE
                    else:
                        inputs["reference_png"] = base64.b64encode(reference).decode()
                    request = client.build_request("POST", config.local_url,
                        headers={"Authorization": f"Bearer {config.local_token}", **trace_headers()},
                        json=inputs)
                else:
                    azure = provider == "azure"
                    url = (config.azure_endpoint.rstrip("/") + "/openai/v1/images/edits?api-version=preview"
                           if azure else "https://api.openai.com/v1/images/edits")
                    headers = {"api-key": config.azure_key} if azure else {"Authorization": f"Bearer {config.openai_key}"}
                    request = client.build_request("POST", url, headers=headers,
                        data={"model": config.azure_deployment if azure else config.openai_model,
                              "prompt": AZURE_AVATAR_PROMPT if azure else AVATAR_PROMPT,
                              "background": "transparent", "output_format": "png",
                              "size": "1024x1024", "quality": "high" if azure else "medium", "n": "1"},
                        files=[("image[]", ("portrait.png", source_png, "image/png")),
                               ("image[]", ("body.png", reference, "image/png"))])
                response = client.send(request, stream=True)
                try:
                    if provider == "local" and response.status_code == 503 \
                            and response.headers.get(LOCAL_BUSY_HEADER) in {"busy", "capacity"}:
                        # Only this explicit private protocol signal refunds an
                        # attempt. Generic 503s, cloud responses and timeouts do not.
                        raw_delay = response.headers.get("Retry-After", "")
                        delay = int(raw_delay) if len(raw_delay) <= 3 and raw_delay.isascii() and raw_delay.isdecimal() else LOCAL_BUSY_RETRY_SECONDS
                        raise AvatarProviderBusy(delay, capacity=response.headers.get(LOCAL_BUSY_HEADER) == "capacity")
                    if response.status_code >= 400:
                        raise AvatarProviderError(
                            "De afbeeldingsdienst is tijdelijk niet beschikbaar." if
                            response.status_code in {429, 502, 503, 504} else
                            "De afbeeldingsdienst kon deze opdracht niet verwerken.",
                            retryable=response.status_code in {429, 502, 503, 504},
                        )
                    if response.status_code != 200:
                        raise AvatarProviderError("Onverwacht antwoord van de afbeeldingsdienst.")
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_OUTPUT_BYTES * 4 // 3 + 8192:
                            raise AvatarProviderError("Het modelantwoord is te groot.")
                    # Rebuild a bounded response for JSON parsing without ever
                    # recording response bodies, source photographs or keys.
                    payload = httpx.Response(200, content=bytes(chunks)).json()
                finally:
                    response.close()
        except AvatarProviderError:
            raise
        except httpx.ConnectError as exc:
            raise AvatarProviderError("De afbeeldingsdienst is niet bereikbaar.", retryable=True) from exc
        except httpx.TimeoutException as exc:
            # An OpenAI timeout may already have incurred a charge. Let the user
            # choose to try again instead of automatically resubmitting a photo.
            raise AvatarProviderError("Het maken van de avatar duurde te lang.",
                                      retryable=provider == "local") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise AvatarProviderError("Het model gaf geen bruikbaar antwoord.") from exc
        if provider == "local" and config.local_style == PIXEL_STYLE \
                and (not isinstance(payload, dict) or payload.get("style") != PIXEL_STYLE):
            raise AvatarProviderError("De afbeeldingsdienst ondersteunt de gekozen avatarstijl nog niet.")
        return _decode_response(payload)
