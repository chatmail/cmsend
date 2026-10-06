import os
import socket
import subprocess
import sys

import pytest

pytest_plugins = ("deltachat_rpc_client.pytestplugin",)
ci_chatmail_domain = os.environ.get("CHATMAIL_DOMAIN", "ci-chatmail.testrun.org")


@pytest.fixture
def run_cmsend(capfd, monkeypatch, tmp_path):
    """Run cmsend as a subprocess: an in-process hang would wedge pytest itself."""
    monkeypatch.setenv("CHATMAIL_DOMAIN", ci_chatmail_domain)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path.joinpath("xdg-config")))

    def run(*args):
        subprocess.run([sys.executable, "-m", "cmsend", *args], check=True)
        return capfd.readouterr().out

    return run


def test_join_and_send(acf, run_cmsend, capfd):
    (ac,) = acf.get_online_accounts(1)
    # a timed-out --init must not leave a profile behind
    with pytest.raises(subprocess.CalledProcessError):
        run_cmsend("--timeout", "0", "--init", ci_chatmail_domain)
    assert "timed out after 0s" in capfd.readouterr().err
    run_cmsend("--init", ci_chatmail_domain)

    run_cmsend("-t", "GROUP", "--join", ac.create_group("log").get_qr_code())
    out = run_cmsend("-vv", "-t", "SINGLE", "--join", ac.get_qr_code())
    assert "Taking securejoin protocol shortcut" in out

    out = run_cmsend("-l")
    assert "GROUP" in out and "SINGLE" in out

    for tag in ("GROUP", "SINGLE"):
        run_cmsend("-t", tag, "-m", f"hello {tag}")
        snapshot = ac.wait_for_incoming_msg().get_snapshot()
        assert snapshot.text == f"hello {tag}"
    sender = ac.get_contact_by_id(snapshot.from_id).get_snapshot()
    assert sender.display_name == f"cmsend[{socket.gethostname()}]"

    ac.stop_io()
    invitelink = ac.create_group("offline").get_qr_code()
    with pytest.raises(subprocess.CalledProcessError):
        run_cmsend("--timeout", "1", "-t", "OFFLINE", "--join", invitelink)
    assert "timed out after 1s" in capfd.readouterr().err
