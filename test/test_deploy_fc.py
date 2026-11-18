import base64
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile
import zipfile

from alibabacloud_fc20230330 import models
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deploy_fc", ROOT / "scripts/deploy_fc.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeClient:
    def __init__(self, *, wrong_runtime=False, change_env=False, failed=False, mismatch=False, omit_state=False, ready_path=False):
        self.ready_path = ready_path
        self.wrong_runtime = wrong_runtime
        self.change_env = change_env
        self.failed = failed
        self.mismatch = mismatch
        self.omit_state = omit_state
        self.updated = False
        self.request = None

    def get_function(self, name, request):
        env = {"PRIVATE_RUNTIME_VALUE": "must-remain-private", "OTHER_CONFIG": "existing-value",
               "PYTHONPATH": "/code/python:/code:/opt/python" if self.ready_path else "/opt/python:/code/python:/code:/mnt/custom"}
        if self.updated and self.request.body.environment_variables is not None:
            env = dict(self.request.body.environment_variables)
        if self.change_env and self.updated:
            env = {}
        function = models.Function(
            runtime="nodejs20" if self.wrong_runtime else "python3.10", handler="index.handler",
            state="Failed" if self.failed and self.updated else "Active", last_update_status="Successful",
            timeout=900, code_size=123,
            code_checksum=("999" if self.mismatch else self.request.body.code.checksum) if self.updated else "old",
            environment_variables=env, cpu=0.35, memory_size=512, disk_size=10240,
            role="existing-role", internet_access=True,
            vpc_config=models.VPCConfig(vpc_id="preserved-vpc"),
        )
        if self.omit_state:
            function.state = None
            function.last_update_status = None
        return SimpleNamespace(body=function)

    def update_function_with_options(self, name, request, headers, runtime):
        self.request = request
        self.updated = True
        assert runtime.autoretry is False
        assert runtime.connect_timeout == 60000
        return SimpleNamespace(body=None)


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.target = module.target_from_env({"ALIYUN_FC_REGION": "cn-hangzhou", "ALIYUN_FC_FUNCTION_NAME": "cert-generator-test"})

    def test_crc64_standard_vector(self):
        self.assertEqual(module.crc64(b"123456789"), str(0x995DC9BBDF1939FA))
        self.assertEqual(module.crc64(b""), "0")

    def test_only_code_and_pythonpath_are_sent_and_other_configuration_is_preserved(self):
        client = FakeClient()
        result = module.deploy(client, self.target, b"zip-bytes", sleep=lambda _: None)
        payload = client.request.body.to_map()
        self.assertEqual(set(payload), {"code", "environmentVariables"})
        self.assertEqual(payload["environmentVariables"]["PRIVATE_RUNTIME_VALUE"], "must-remain-private")
        self.assertEqual(payload["environmentVariables"]["OTHER_CONFIG"], "existing-value")
        self.assertEqual(payload["environmentVariables"]["PYTHONPATH"], "/code/python:/code:/opt/python:/mnt/custom")
        self.assertEqual(base64.b64decode(payload["code"]["zipFile"]), b"zip-bytes")
        self.assertEqual(result["timeout"], 900)
        self.assertNotIn("must-remain-private", str(result))

    def test_mismatched_runtime_stops_before_update(self):
        client = FakeClient(wrong_runtime=True)
        with self.assertRaisesRegex(module.DeployError, "before writing"):
            module.deploy(client, self.target, b"zip")
        self.assertFalse(client.updated)

    def test_environment_drift_is_detected_without_printing_values(self):
        with self.assertRaisesRegex(module.DeployError, "configuration changed") as error:
            module.deploy(FakeClient(change_env=True), self.target, b"zip")
        self.assertNotIn("must-remain-private", str(error.exception))

    def test_cloud_failure_is_not_reported_as_success(self):
        with self.assertRaisesRegex(module.DeployError, "failed update"):
            module.deploy(FakeClient(failed=True), self.target, b"zip")

    def test_cpu_function_can_omit_container_state_fields_but_still_needs_matching_code(self):
        result = module.deploy(FakeClient(omit_state=True), self.target, b"zip")
        self.assertEqual(result["codeChecksum"], module.crc64(b"zip"))

    def test_checksum_mismatch_cannot_pass_verification(self):
        ticks = iter([0, 1, 181])
        with self.assertRaisesRegex(module.DeployError, "timed out"):
            module.deploy(FakeClient(mismatch=True), self.target, b"zip", sleep=lambda _: None, now=lambda: next(ticks))

    def test_workflow_runs_on_main_and_uses_only_existing_secret_names(self):
        # BaseLoader keeps the YAML 1.2 GitHub 'on' key as a string.
        workflow = yaml.load((ROOT / ".github/workflows/deploy-fc.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(workflow["on"]["push"]["branches"], ["main"])
        self.assertIn("workflow_dispatch", workflow["on"])
        self.assertEqual(workflow["concurrency"]["cancel-in-progress"], "false")
        deploy_step = next(s for s in workflow["jobs"]["deploy"]["steps"] if s.get("name") == "Deploy and verify FC code")
        self.assertEqual(set(deploy_step["env"]), {"ALIYUN_FC_ACCESS_KEY_ID", "ALIYUN_FC_ACCESS_KEY_SECRET", "ALIYUN_FC_REGION", "ALIYUN_FC_FUNCTION_NAME"})
        self.assertFalse((ROOT / ".github/workflows/registry-publish.yml").exists())
        step = deploy_step
        self.assertIn("steps.current.outputs.deploy", step["if"])

    def test_preflight_checks_cloud_target_without_loading_or_uploading_package(self):
        client = FakeClient()
        env = {"ALIYUN_FC_REGION": "cn-hangzhou", "ALIYUN_FC_FUNCTION_NAME": "cert-generator-test",
               "ALIYUN_FC_ACCESS_KEY_ID": "test-id", "ALIYUN_FC_ACCESS_KEY_SECRET": "test-secret"}
        with patch.dict(module.os.environ, env), patch.object(module.sys, "argv", ["deploy_fc.py", "--preflight"]), \
                patch.object(module, "Client", return_value=client), \
                patch.object(module, "load_zip", side_effect=AssertionError("Preflight must not require a ZIP")):
            self.assertEqual(module.main(), 0)
        self.assertFalse(client.updated)

    def test_disabled_accesskey_message_is_actionable_and_redacts_sdk_details(self):
        error = RuntimeError("secret-must-not-be-logged")
        error.code = "InvalidAccessKeyId.Inactive"
        message = module.safe_sdk_failure(error)
        self.assertIn("AccessKey is disabled", message)
        self.assertIn("ALIYUN_FC_ACCESS_KEY_ID", message)
        self.assertNotIn("secret-must-not-be-logged", message)

    def test_existing_correct_pythonpath_only_updates_code(self):
        client = FakeClient(ready_path=True)
        module.deploy(client, self.target, b"zip", sleep=lambda _: None)
        self.assertEqual(set(client.request.body.to_map()), {"code"})

    def test_settings_require_region_function_and_both_secrets(self):
        for env in [{}, {"ALIYUN_FC_REGION": "cn-hangzhou"},
                    {"ALIYUN_FC_REGION": "cn-hangzhou", "ALIYUN_FC_FUNCTION_NAME": "bad/name"}]:
            with self.assertRaises(module.DeployError):
                module.target_from_env(env)
        with self.assertRaises(module.DeployError):
            module.deployment_credentials({"ALIYUN_FC_ACCESS_KEY_ID": "one-key-only"})
        self.assertEqual(module.bundled_pythonpath("/mnt/x:/mnt/x:/code"), "/code/python:/code:/opt/python:/mnt/x")

    def test_zip_requires_dependencies_and_rejects_secret_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "code.zip"
            def write_zip(extra):
                with zipfile.ZipFile(path, "w") as archive:
                    for name in ["index.py", "dns_propagation.py", "requirements.txt", "cas/index.py", "alidns/index.py", "scripts/authenticator.sh", "scripts/cleanup.sh", "scripts/upload-certs.sh", "python/certbot/main.py", "python/acme/crypto_util.py", "python/OpenSSL/crypto.py"] + extra:
                        archive.writestr(name, "test")
            write_zip([])
            self.assertTrue(module.load_zip(path))
            write_zip([".env"])
            with self.assertRaisesRegex(module.DeployError, "forbidden"):
                module.load_zip(path)


if __name__ == "__main__":
    unittest.main()
