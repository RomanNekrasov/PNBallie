"""Private child-process protocol: bounded JSON stdin, PNG stdout, safe stderr.

Only the local model service launches this module. No service token, user ID,
cloud credentials or database access are passed in the request payload.
"""

import base64
import json
import os
import sys

from app.avatar_images import MAX_UPLOAD_BYTES, InvalidAvatarImage
from app.avatar_service import InferenceUnavailable, QwenRuntime
from app.telemetry import INFERENCE_SERVICE, Runtime, span_result


def main() -> int:
    binary_output = sys.stdout.buffer
    # Keep raw third-party output out of both PNG transport and application logs.
    console = sys.stderr
    sys.stdout = sys.stderr = open(os.devnull, "w")
    telemetry = Runtime(INFERENCE_SERVICE)
    telemetry.configure(console_stream=console)
    limit = MAX_UPLOAD_BYTES * 8 // 3 + 8192
    try:
        request = sys.stdin.buffer.read(limit + 1)
        if len(request) > limit:
            raise ValueError("Oversized inference request")
        payload = json.loads(request)
        source = base64.b64decode(payload["source_png"], validate=True)
        reference = base64.b64decode(payload["reference_png"], validate=True)
        with telemetry.span("avatar.model", parent=payload.get("traceparent") or "", root=True) as span:
            try:
                png = QwenRuntime().generate(source, reference)
                binary_output.write(png)
                binary_output.flush()
                span_result(span, outcome="success")
                return 0
            except Exception:
                span_result(span, outcome="failure", error="unexpected")
                raise
    except InvalidAvatarImage:
        telemetry.log("avatar.inference.finished", level="WARNING", outcome="failure", error_type="invalid_image")
        return 2
    except InferenceUnavailable:
        telemetry.log("avatar.inference.finished", level="WARNING", outcome="unavailable", error_type="unavailable")
        return 3
    except Exception:
        telemetry.log("avatar.inference.finished", level="ERROR", outcome="failure", error_type="unexpected")
        return 1
    finally:
        telemetry.close()


if __name__ == "__main__":
    raise SystemExit(main())
