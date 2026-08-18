import subprocess
import sys

import pytest

pytest_plugins = ("deltachat_rpc_client.pytestplugin",)
ci_chatmail_domain = "ci-chatmail.testrun.org"


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    """Keep every test off the real ~/.config/cmsend, however it invokes cmsend."""
    monkeypatch.setenv("CHATMAIL_DOMAIN", ci_chatmail_domain)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path.joinpath("xdg-config")))


@pytest.fixture
def run_cmsend(capfd):
    """Run cmsend as a subprocess: an in-process hang would wedge pytest itself."""

    def run(*args, timeout=60):
        cmd = [sys.executable, "-m", "cmsend", *args]
        try:
            subprocess.run(cmd, check=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pytest.fail(f"cmsend did not terminate within {timeout}s")
        return capfd.readouterr().out

    return run


@pytest.mark.parametrize("invite", ["setup", "group"])
def test_init_join_and_send(acfactory, run_cmsend, invite):
    (ac,) = acfactory.get_online_accounts(1)

    run_cmsend("--init", ci_chatmail_domain, timeout=120)

    assert "LOG" not in run_cmsend("-l")

    if invite == "setup":
        invitelink = ac.get_qr_code()
        expected_name = ac.get_config("configured_addr")
    else:
        invitelink = ac.create_group("cmsend log").get_qr_code()
        expected_name = "cmsend log"

    run_cmsend("-t", "LOG", "--join", invitelink)

    out = run_cmsend("-l")
    assert "LOG" in out
    assert expected_name in out

    run_cmsend("-t", "LOG", "-m", "hello from cmsend")
    event = ac.wait_for_incoming_msg_event()
    snapshot = ac.get_message_by_id(event.msg_id).get_snapshot()
    assert snapshot.text == "hello from cmsend"


def test_name_reaches_recipient(acfactory, run_cmsend):
    (ac,) = acfactory.get_online_accounts(1)

    run_cmsend("--init", ci_chatmail_domain, timeout=120)
    run_cmsend("--name", "CI Bot")

    run_cmsend("-t", "LOG", "--join", ac.get_qr_code())
    run_cmsend("-t", "LOG", "-m", "named hello")

    event = ac.wait_for_incoming_msg_event()
    snapshot = ac.get_message_by_id(event.msg_id).get_snapshot()
    assert snapshot.text == "named hello"
    sender = ac.get_contact_by_id(snapshot.from_id).get_snapshot()
    assert sender.display_name == "CI Bot"
