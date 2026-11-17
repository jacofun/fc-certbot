"""Deploy cert-generator code to an existing FC function and verify the readback."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
import zipfile

from alibabacloud_fc20230330.client import Client
from alibabacloud_fc20230330 import models
from alibabacloud_tea_openapi.models import Config
from alibabacloud_tea_util.models import RuntimeOptions


class DeployError(Exception):
    pass


def target_from_env(env):
    region = env.get("ALIYUN_FC_REGION", "").strip()
    name = env.get("ALIYUN_FC_FUNCTION_NAME", "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,50}", region):
        raise DeployError("Set Repository variable ALIYUN_FC_REGION to the existing cert-generator region.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name):
        raise DeployError("Set Repository variable ALIYUN_FC_FUNCTION_NAME to the existing cert-generator name.")
    return {"region": region, "functionName": name, "runtime": "python3.10", "handler": "index.handler"}


def deployment_credentials(env):
    values = [env.get(key, "").strip() for key in ("ALIYUN_FC_ACCESS_KEY_ID", "ALIYUN_FC_ACCESS_KEY_SECRET")]
    if not all(values):
        raise DeployError("Configure Repository secrets ALIYUN_FC_ACCESS_KEY_ID and ALIYUN_FC_ACCESS_KEY_SECRET.")
    return values


def bundled_pythonpath(existing):
    parts = ["/code/python", "/code", "/opt/python"]
    parts += (existing or "").split(":")
    return ":".join(dict.fromkeys(part for part in parts if part))


def load_zip(path):
    data = Path(path).read_bytes()
    # Keep the Base64 request comfortably inside the direct-upload limit.
    if not 0 < len(data) <= 60 * 1024 * 1024:
        raise DeployError("ZIP must be between 1 byte and 60 MiB for direct upload.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            required = {"index.py", "requirements.txt", "cas/index.py", "alidns/index.py", "scripts/authenticator.sh", "scripts/cleanup.sh", "scripts/upload-certs.sh", "python/certbot/main.py", "python/acme/crypto_util.py", "python/OpenSSL/crypto.py"}
            if not required.issubset(names) or len(names) != len(set(names)):
                raise DeployError("ZIP layout or dependencies are invalid.")
            if any(name.startswith("/") or ".." in Path(name).parts or
                   any(part.startswith(".env") or part in {".git", ".github"} for part in Path(name).parts)
                   for name in names):
                raise DeployError("ZIP contains a forbidden path or configuration file.")
    except zipfile.BadZipFile:
        raise DeployError("Deployment package is not a ZIP file.") from None
    return data


def crc64(data):
    # Reflected ECMA-182, with all-one init/xorout (same as Go crc64.ECMA).
    polynomial = 0xC96C5795D7870F42
    table = []
    for byte in range(256):
        value = byte
        for _ in range(8):
            value = (value >> 1) ^ (polynomial if value & 1 else 0)
        table.append(value)
    result = 0xFFFFFFFFFFFFFFFF
    for byte in data:
        result = table[(result ^ byte) & 0xFF] ^ (result >> 8)
    return str(result ^ 0xFFFFFFFFFFFFFFFF)


PRESERVED_FIELDS = (
    "environment_variables", "role", "cpu", "memory_size", "disk_size", "internet_access",
    "vpc_config", "nas_config", "oss_mount_config", "log_config", "resource_group_id",
    "instance_concurrency", "instance_isolation_mode", "session_affinity", "layers",
    "custom_dns", "instance_lifecycle_config", "disable_ondemand", "disable_inject_credentials",
    "timeout", "initializer", "initialization_timeout",
)


def value_of(value):
    if hasattr(value, "to_map"):
        return value.to_map()
    if isinstance(value, list):
        return [value_of(item) for item in value]
    return value


def snapshot(function):
    return {key: value_of(getattr(function, key, None)) for key in PRESERVED_FIELDS}


def check_existing_function(client, target):
    current = client.get_function(target["functionName"], models.GetFunctionRequest()).body
    if current.runtime != target["runtime"] or current.handler != target["handler"]:
        raise DeployError("Existing function must use runtime python3.10 and handler index.handler; stopped before writing.")
    return current


def deploy(client, target, package, *, sleep=time.sleep, now=time.monotonic):
    name = target["functionName"]
    current = check_existing_function(client, target)
    before = snapshot(current)
    environment = dict(current.environment_variables or {})
    environment["PYTHONPATH"] = bundled_pythonpath(environment.get("PYTHONPATH"))
    expected = dict(before)
    expected["environment_variables"] = environment
    checksum = crc64(package)
    print(json.dumps({"event": "fc_preflight", "state": current.state,
                      "lastUpdateStatus": current.last_update_status, "expectedCodeChecksum": checksum}), flush=True)
    body = models.UpdateFunctionInput(
        code=models.InputCodeLocation(zip_file=base64.b64encode(package).decode("ascii"), checksum=checksum),
    )
    # Preserve all existing variables; only make bundled dependencies take priority.
    # Roles, triggers, runtime, timeout and network settings stay console-managed.
    if environment != (current.environment_variables or {}):
        body.environment_variables = environment
    client.update_function_with_options(
        name, models.UpdateFunctionRequest(body=body), {},
        RuntimeOptions(connect_timeout=60000, read_timeout=180000, autoretry=False),
    )
    print("FC accepted the code update; reading back deployment state.", flush=True)
    deadline = now() + 180
    previous_status = None
    while now() < deadline:
        deployed = client.get_function(name, models.GetFunctionRequest()).body
        status = {"state": deployed.state, "lastUpdateStatus": deployed.last_update_status,
                  "codeChecksum": str(deployed.code_checksum), "checksumMatches": str(deployed.code_checksum) == checksum}
        if status != previous_status:
            print(json.dumps({"event": "fc_verification", **status}), flush=True)
            previous_status = status
        if deployed.state == "Failed" or deployed.last_update_status == "Failed":
            raise DeployError("FC reports a failed update; inspect the FC console for the reason.")
        # Some ordinary CPU functions omit the container-oriented state fields.
        # In that case the code checksum and runtime/config readback remain required.
        if (deployed.state in (None, "", "Active") and deployed.last_update_status in (None, "", "Successful")
                and str(deployed.code_checksum) == checksum):
            if deployed.runtime != target["runtime"] or deployed.handler != target["handler"] or deployed.timeout != current.timeout:
                raise DeployError("Deployed runtime/handler/timeout verification failed.")
            if snapshot(deployed) != expected:
                raise DeployError("FC configuration changed during deployment; inspect the console before continuing.")
            return {
                "functionName": name, "region": target["region"], "runtime": deployed.runtime,
                "handler": deployed.handler, "timeout": deployed.timeout,
                "codeChecksum": checksum, "zipSha256": hashlib.sha256(package).hexdigest(),
                "codeSize": deployed.code_size, "sourceCommit": os.environ.get("GITHUB_SHA", "local"),
            }
        sleep(5)
    raise DeployError("FC update verification timed out; inspect fc_verification status above before retrying.")


def main():
    root = Path(__file__).resolve().parents[1]
    target = target_from_env(os.environ)
    credentials = deployment_credentials(os.environ)
    if "--validate" in sys.argv[1:]:
        print("Required FC deployment settings are present.")
        return 0
    config = Config(access_key_id=credentials[0], access_key_secret=credentials[1],
                    endpoint=f"fcv3.{target['region']}.aliyuncs.com", connect_timeout=60000, read_timeout=180000)
    client = Client(config)
    if "--preflight" in sys.argv[1:]:
        current = check_existing_function(client, target)
        print(json.dumps({"event": "fc_target_validated", **target}))
        return 0
    package = load_zip(root / "dist/cert-generator.zip")
    print(f"Deploying {target['functionName']} in {target['region']}; updating code and bundled PYTHONPATH while preserving other configuration.")
    result = deploy(client, target, package)
    (root / "dist/deploy-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
            output.write("## FC deployment verified\n\n")
            for key, value in result.items():
                output.write(f"- {key}: `{value}`\n")
    return 0


def safe_sdk_failure(error):
    code = getattr(error, "code", "")
    code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", code) else type(error).__name__
    if code == "InvalidAccessKeyId.Inactive":
        return ("Deployment failed (InvalidAccessKeyId.Inactive): the deployment AccessKey is disabled. "
                "Update fc-certbot Repository secrets ALIYUN_FC_ACCESS_KEY_ID and ALIYUN_FC_ACCESS_KEY_SECRET "
                "with a matching Active key pair, then rerun this workflow.")
    return f"Deployment failed ({code}); check FC permissions and GitHub Actions network access."


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DeployError as error:
        print(f"Deployment failed: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        # Alibaba SDK exceptions can contain request bodies, signed URLs or envs.
        print(safe_sdk_failure(error), file=sys.stderr)
        sys.exit(1)
