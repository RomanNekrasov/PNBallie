#!/usr/bin/env python3
"""Exercise the real nginx image against disposable, isolated fake services.

Run from any directory: python scripts/check_analytics_proxy.py
An existing frontend image can be supplied with --image to skip the build.
Only containers, a network and an image tag created by this check are removed.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


WEBSITE = "03c9b13b-4507-517c-b008-c488152a163b"
BODY = json.dumps({"type": "event", "payload": {
    "website": WEBSITE, "url": "/app/game", "hostname": "probe.invalid",
}}).encode()
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "PNBallie-analytics-probe/1.0",
    "X-Umami-Cache": "synthetic-session-cache",
    "X-Umami-Website-Id": WEBSITE,
    "X-Umami-Hostname": "probe.invalid",
    "Cookie": "session=synthetic-private-cookie",
    "Authorization": "Bearer synthetic-private-credential",
    "Referer": "https://probe.invalid/join/synthetic-invite?email=private",
    "X-Custom-Private": "synthetic-private-property",
    "Forwarded": "for=203.0.113.91;host=private.invalid",
    "X-Forwarded-For": "203.0.113.91",
    "X-Real-IP": "203.0.113.92",
    "X-Forwarded-Host": "private.invalid",
    "X-Forwarded-Proto": "https",
    "X-Original-Forwarded-For": "203.0.113.93",
    "X-Client-IP": "203.0.113.94",
    "True-Client-IP": "203.0.113.95",
    "CF-Connecting-IP": "198.51.100.23",
    "CF-IPCountry": "XX",
}
PRIVATE_HEADERS = {
    name.lower() for name in HEADERS
    if name.lower() not in {
        "content-type", "user-agent", "x-umami-cache",
        "x-umami-website-id", "x-umami-hostname", "x-forwarded-for", "x-real-ip",
    }
}
PROBE_SERVER = r'''
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path.startswith("/script.js"):
            result = b"window.__PNBALLIE_PROXY_PROBE__ = true;"
            content_type = "application/javascript"
        else:
            result = json.dumps({"path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body.decode()}).encode()
            content_type = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Set-Cookie", "upstream-cookie=must-not-reach-browser")
        self.send_header("X-Probe-Path", self.path)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(result)

    do_GET = do_HEAD = do_POST = do_PUT = do_OPTIONS = respond

threading.Thread(target=ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever,
                 daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 3000), Handler).serve_forever()
'''


def docker(*args, capture=True, check=True):
    result = subprocess.run(["docker", *args], text=True, check=check,
                            capture_output=capture)
    return result.stdout.strip() if capture else result


def request(url, method="GET", body=None, headers=None):
    try:
        response = urlopen(Request(url, data=body, headers=headers or {}, method=method), timeout=8)
    except HTTPError as error:
        response = error
    with response:
        return response.status, dict(response.headers), response.read()


def ready(base):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            if request(base + "/healthz")[0] == 200:
                return
        except (URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.2)
    raise AssertionError("Frontend did not become ready")


def assert_echo(echo, trusted=False):
    assert echo["path"] == "/api/send", echo["path"]
    assert echo["body"] == BODY.decode(), "Collector body changed"
    headers = echo["headers"]
    for name in PRIVATE_HEADERS:
        assert name not in headers, f"Private header was forwarded: {name}"
    for name in ("Content-Type", "User-Agent", "X-Umami-Cache", "X-Umami-Website-Id", "X-Umami-Hostname"):
        assert headers.get(name.lower()) == HEADERS[name], f"Required collector header missing: {name}"
    for name in ("x-forwarded-for", "x-real-ip"):
        expected = HEADERS["CF-Connecting-IP"] if trusted else None
        assert headers.get(name) == expected, f"Incorrect client-IP trust boundary: {name}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="Existing frontend image to check")
    args = parser.parse_args()
    prefix = "pnballie-analytics-check-" + uuid.uuid4().hex[:10]
    image = args.image or prefix + ":test"
    network = prefix + "-net"
    containers = []
    network_created = False
    built_image = False
    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
    try:
        if not args.image:
            docker("build", "--tag", image, str(frontend_dir), capture=False)
            built_image = True
        docker("network", "create", network)
        network_created = True
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            probe_file = Path(directory) / "probe.py"
            probe_file.write_text(PROBE_SERVER)
            probe = prefix + "-probe"
            containers.append(probe)
            docker("run", "--detach", "--name", probe, "--network", network,
                   "--network-alias", "umami", "--network-alias", "backend",
                   "--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--user", "65534:65534",
                   "--mount", f"type=bind,src={probe_file},dst=/probe.py,readonly",
                   "python:3.12-alpine", "python", "-B", "/probe.py")
            probe_ip = json.loads(docker("inspect", probe))[0]["NetworkSettings"]["Networks"][network]["IPAddress"]

            def start_frontend(suffix, *, trust="", enabled=True, upstream="umami:3000"):
                name = prefix + "-" + suffix
                containers.append(name)
                docker("run", "--detach", "--name", name, "--network", network,
                       "--network-alias", suffix,
                       "--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL",
                       "--security-opt", "no-new-privileges", "--publish", "127.0.0.1::8080",
                       "--env", f"ANALYTICS_ENABLED={str(enabled).lower()}",
                       "--env", f"ANALYTICS_WEBSITE_ID={WEBSITE}",
                       "--env", f"ANALYTICS_UPSTREAM={upstream}",
                       "--env", f"ANALYTICS_TRUSTED_PROXY_CIDRS={trust}", image)
                port = json.loads(docker("inspect", name))[0]["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"]
                base = "http://127.0.0.1:" + port
                ready(base)
                assert docker("exec", name, "id", "-u") != "0", "Frontend runs as root"
                write_check = subprocess.run(["docker", "exec", name, "touch", "/must-not-write"], capture_output=True)
                assert write_check.returncode != 0, "Frontend can write to its root filesystem"
                state = json.loads(docker("inspect", name))[0]
                assert state["HostConfig"]["ReadonlyRootfs"], "Writable root filesystem"
                return name, base

            name, base = start_frontend("frontend-untrusted")
            status, response_headers, body = request(base + "/config.json")
            assert status == 200 and json.loads(body) == {"analytics": {"enabled": True, "websiteId": WEBSITE}}
            assert response_headers.get("Cache-Control") == "no-store"
            for method in ("GET", "HEAD"):
                status, response_headers, body = request(base + "/analytics/script.js?private=query", method)
                assert status == 200 and response_headers.get("X-Probe-Path") == "/script.js"
                assert "Set-Cookie" not in response_headers
                if method == "GET":
                    assert b"__PNBALLIE_PROXY_PROBE__" in body
            status, response_headers, body = request(base + "/analytics/api/send?private=query", "POST", BODY, HEADERS)
            assert status == 200 and "Set-Cookie" not in response_headers
            assert_echo(json.loads(body))
            for path in ("/analytics", "/analytics/", "/analytics/api/websites", "/analytics/api/heartbeat",
                         "/analytics/metrics", "/metrics", "/metrics/", "/api/metrics", "/internal/probe",
                         "/api/internal/probe", "/traces", "/api/traces", "/v1/traces"):
                assert request(base + path)[0] == 404, f"Private path is reachable: {path}"
            for path, method in (("/analytics/script.js", "POST"), ("/analytics/api/send", "GET"),
                                 ("/analytics/api/send", "HEAD"), ("/analytics/api/send", "PUT"),
                                 ("/analytics/api/send", "OPTIONS")):
                assert request(base + path, method)[0] == 403, f"Unexpected allowed method: {method} {path}"
            assert request(base + "/analytics/api/send", "POST", b"x" * 16385, HEADERS)[0] == 413
            marker = "synthetic-private-route-" + uuid.uuid4().hex
            request(base + "/join/" + marker + "?email=" + marker)
            request(base + "/api/missing/" + marker)
            request(base + "/analytics/api/send?private=" + marker, "POST", b"x" * 16385, HEADERS)
            logs = subprocess.run(["docker", "logs", name], text=True, capture_output=True, check=True)
            assert marker not in logs.stdout + logs.stderr, "Raw route/query appeared in nginx logs"
            print("PASS: read-only startup, runtime config, exact endpoints, method/body limits, private headers, untrusted IPs, raw URL log suppression", flush=True)

            start_frontend("frontend-trusted", trust=probe_ip + "/32")
            client = (
                "import json; from urllib.request import Request,urlopen; "
                f"request=Request('http://frontend-trusted:8080/analytics/api/send?private=query', data={BODY!r}, headers={HEADERS!r}, method='POST'); "
                "print(urlopen(request,timeout=8).read().decode())"
            )
            assert_echo(json.loads(docker("exec", probe, "python", "-c", client)), trusted=True)
            print("PASS: only an explicitly trusted proxy can supply the client IP; conflicting spoofed headers are removed", flush=True)

            _, missing_base = start_frontend("frontend-missing", upstream="missing-umami.invalid:3000")
            assert request(missing_base + "/")[0] == 200
            assert request(missing_base + "/analytics/script.js")[0] == 502
            _, disabled_base = start_frontend("frontend-disabled", enabled=False, upstream="")
            assert json.loads(request(disabled_base + "/config.json")[2])["analytics"]["enabled"] is False
            assert request(disabled_base + "/analytics/script.js")[0] == 404
            assert request(disabled_base + "/analytics/api/send", "POST", BODY)[0] == 404
            print("PASS: unavailable analytics DNS and disabled analytics leave the application available", flush=True)
    except Exception:
        for name in containers:
            subprocess.run(["docker", "logs", "--tail", "60", name], check=False)
        raise
    finally:
        if containers:
            docker("rm", "--force", *containers, check=False)
        if network_created:
            docker("network", "rm", network, check=False)
        if built_image:
            docker("image", "rm", image, check=False)


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, subprocess.CalledProcessError) as error:
        print(f"Analytics proxy check failed: {error}", file=sys.stderr)
        sys.exit(1)
