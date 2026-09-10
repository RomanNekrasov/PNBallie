"""Image-provider boundaries. Provider choice never silently changes to cloud."""

import base64
import binascii
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.avatar_images import MAX_OUTPUT_BYTES, InvalidAvatarImage, normalize_upload
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


class AvatarProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class AvatarSettings:
    local_url: str
    local_token: str
    openai_key: str
    openai_model: str
    reference_path: Path
    timeout: float = 3600

    @classmethod
    def from_env(cls) -> "AvatarSettings":
        return cls(
            local_url=os.getenv("AVATAR_LOCAL_URL", "").strip(),
            local_token=os.getenv("AVATAR_SERVICE_TOKEN", "").strip(),
            openai_key=os.getenv("OPENAI_API_KEY", "").strip(),
            # Explicit selection prevents an unnoticed model/cost change.
            openai_model=os.getenv("OPENAI_IMAGE_MODEL", "").strip(),
            reference_path=Path(os.getenv(
                "AVATAR_REFERENCE_PATH", str(Path(__file__).parent / "assets" / "avatar-body.png"),
            )),
            timeout=max(30, min(3600, float(os.getenv("AVATAR_TIMEOUT_SECONDS", "3600")))),
        )

    @property
    def local_available(self) -> bool:
        return bool(self.local_url and self.local_token and self.reference_path.is_file())

    @property
    def openai_available(self) -> bool:
        return bool(self.openai_key and self.openai_model and self.reference_path.is_file())


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
        if provider not in {"local", "openai"}:
            raise AvatarProviderError("Deze afbeeldingsdienst wordt niet ondersteund.")
        if provider == "openai" and not cloud_consent:
            raise AvatarProviderError("Toestemming voor verwerking door OpenAI ontbreekt.")
        available = config.local_available if provider == "local" else config.openai_available
        if not available:
            raise AvatarProviderError("Deze afbeeldingsdienst is nog niet ingesteld.")
        try:
            reference = normalize_upload(config.reference_path.read_bytes(), "image/png")
        except (OSError, InvalidAvatarImage) as exc:
            raise AvatarProviderError("Het referentiepoppetje is niet beschikbaar.") from exc

        try:
            # Stream the response so a misbehaving local endpoint cannot allocate
            # unbounded memory. Do not follow provider-controlled result URLs.
            with httpx.Client(timeout=httpx.Timeout(config.timeout, connect=10),
                              transport=self.transport, follow_redirects=False) as client:
                if provider == "local":
                    request = client.build_request("POST", config.local_url,
                        headers={"Authorization": f"Bearer {config.local_token}", **trace_headers()},
                        json={"source_png": base64.b64encode(source_png).decode(),
                              "reference_png": base64.b64encode(reference).decode()})
                else:
                    request = client.build_request("POST", "https://api.openai.com/v1/images/edits",
                        headers={"Authorization": f"Bearer {config.openai_key}"},
                        data={"model": config.openai_model, "prompt": AVATAR_PROMPT,
                              "background": "transparent", "output_format": "png",
                              "size": "1024x1024", "quality": "medium", "n": "1"},
                        files=[("image[]", ("portrait.png", source_png, "image/png")),
                               ("image[]", ("body.png", reference, "image/png"))])
                response = client.send(request, stream=True)
                try:
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
        return _decode_response(payload)
