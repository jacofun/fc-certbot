"""Wait for the current DNS-01 value before asking ACME to validate it."""
import json
import shlex
import time


def propagation_settings(env):
    try:
        delay = int(env.get("DNS_PROPAGATION_SECONDS", "120"))
        timeout = int(env.get("DNS_PROPAGATION_TIMEOUT_SECONDS", "600"))
        if not 30 <= delay <= 300 or not delay + 10 <= timeout <= 600:
            raise ValueError()
        return delay, timeout
    except (TypeError, ValueError):
        raise ValueError("DNS_PROPAGATION_SECONDS must be 30..300 and "
                         "DNS_PROPAGATION_TIMEOUT_SECONDS must be delay+10..600") from None


def public_txt_values(name, timeout):
    # Public DNS only: never send cloud credentials or the expected TXT value.
    # requests uses the current bundled certifi CA bundle on the FC runtime.
    import requests

    response = requests.get(
        "https://dns.alidns.com/resolve",
        params={"name": name, "type": "TXT"},
        headers={"Accept": "application/dns-json"},
        timeout=timeout,
        allow_redirects=False,
    )
    try:
        if response.status_code != 200:
            raise RuntimeError("Public DNS HTTPS lookup failed")
        data = response.json()
        if data.get("Status") not in (0, 3):
            raise RuntimeError("Public DNS returned a resolution error")
        if data.get("Status") == 3:
            return set()
        values = set()
        for answer in data.get("Answer", []):
            if answer.get("type") == 16 and isinstance(answer.get("data"), str):
                values.add("".join(shlex.split(answer["data"])))
        return values
    finally:
        response.close()


def wait_for_txt(name, expected, delay=120, timeout=600, *,
                 lookup=public_txt_values, clock=time.monotonic, sleep=time.sleep,
                 log=print):
    if not expected:
        raise ValueError("CERTBOT_VALIDATION is missing")
    start = clock()
    deadline = start + timeout
    log(json.dumps({"event": "dns_propagation_wait", "name": name,
                    "minimumSeconds": delay, "timeoutSeconds": timeout}), flush=True)
    sleep(delay)
    while clock() < deadline:
        try:
            found = expected in lookup(name, min(15, deadline - clock()))
        except Exception:
            # Do not print HTTP error bodies or request credentials from libraries.
            found = False
            status = "lookup_error"
        else:
            status = "ready" if found else "not_visible"
        log(json.dumps({"event": "dns_propagation_check", "name": name,
                        "status": status, "elapsedSeconds": int(clock() - start)}), flush=True)
        if found:
            return
        remaining = deadline - clock()
        if remaining > 0:
            sleep(min(10, remaining))
    raise RuntimeError(f"DNS propagation timed out for {name}: current TXT value is not "
                       "visible in public DNS. Check authoritative DNS, DNSSEC, and "
                       "outbound HTTPS access to dns.alidns.com before retrying.")
