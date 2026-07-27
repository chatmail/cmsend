import pytest

import cmsend

pytest_plugins = ("deltachat_rpc_client.pytestplugin",)
ci_chatmail_domain = "ci-chatmail.testrun.org"


@pytest.fixture(autouse=True)
def _inject_xdg_config_home(tmp_path, monkeypatch):
    xdg_config = tmp_path.joinpath("xdg-config")
    monkeypatch.setattr(cmsend, "xdg_config_home", lambda: xdg_config)
    monkeypatch.setenv("CHATMAIL_DOMAIN", ci_chatmail_domain)


@pytest.fixture
def invoke_main(capsys):
    def invoke(*args):
        with capsys.disabled():
            print(f"$ cmsend {' '.join(args)}")
        ret = cmsend.main(args)
        out, err = capsys.readouterr()
        with capsys.disabled():
            if out:
                print(out)
        return ret, out, err

    return invoke


def test_init_join_and_send(acfactory, invoke_main):
    (ac,) = acfactory.get_online_accounts(1)

    invoke_main("--init", ci_chatmail_domain)

    _ret, out, _err = invoke_main("-l")
    assert "LOG" not in out

    # "--join" expects a Join-Group QR code, not a Setup-Contact one.
    group = ac.create_group("cmsend log")
    invoke_main("-t", "LOG", "--join", group.get_qr_code())

    _ret, out, _err = invoke_main("-l")
    assert "LOG" in out
    assert "cmsend log" in out

    invoke_main("-t", "LOG", "-m", "hello from cmsend")
    event = ac.wait_for_incoming_msg_event()
    snapshot = ac.get_message_by_id(event.msg_id).get_snapshot()
    assert snapshot.text == "hello from cmsend"
