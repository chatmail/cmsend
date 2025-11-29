"""
chatmail sendmail tool "cmsend" to send e2ee messages.
"""

import argparse
import sys
import time

from deltachat_rpc_client import DeltaChat, EventType, Rpc
from xdg_base_dirs import xdg_config_home


def main():
    """Send end-to-end encrypted messages to groups/contacts."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(
        "--init",
        type=str,
        help="initialize a profile with the specified chatmail relay",
    )
    parser.add_argument(
        "--join",
        type=str,
        help="setup a chat using the specified invite link",
    )
    parser.add_argument(
        "-m",
        type=str,
        dest="msg",
        default=None,
        help="the text message to send (defaults to reading from stdin)",
    )
    parser.add_argument(
        "-v", dest="verbose", action="count", default=0, help="increase verbosity"
    )
    parser.add_argument(
        "-a", dest="filename", type=str, default=None, help="add file attachment"
    )
    args = parser.parse_args()

    try:
        return perform_main(args)
    except KeyboardInterrupt:
        raise SystemExit(2)


def perform_main(args):
    accounts_dir = xdg_config_home().joinpath("cmsend")
    print(f"# using accounts_dir at: {accounts_dir}")
    with Rpc(accounts_dir=accounts_dir) as rpc:
        dc = DeltaChat(rpc)
        profile = Profile(dc, verbosity=args.verbose)
        if args.init:
            profile.perform_init(domain=args.init)
        elif args.join:
            profile.perform_join(invitelink=args.join)
        else:
            if args.msg is None:
                args.msg = sys.stdin.read()
            profile.perform_send(args.msg, filename=args.filename)


class Profile:
    _account = None

    def __init__(self, dc, verbosity=0):
        self.dc = dc
        self.verbosity = verbosity
        for account in self.dc.get_all_accounts():
            addr = account.get_config("configured_addr")
            if addr is not None:
                self._account = account
                print(f"profile {self!r} is active")

    def __repr__(self):
        if self._account:
            return f"Profile<{self._account.get_config('configured_addr')}>"
        return "Profile<unconfigured>"

    def perform_init(self, domain):
        if self._account:
            print(f"profile {self!r} already exists", file=sys.stderr)
            raise SystemExit(3)
        print(f"# creating profile on {domain}")
        self._account = account = self.dc.add_account()
        account.set_config_from_qr(f"dcaccount:{domain}")
        account.start_io()
        account.wait_for_event(EventType.IMAP_INBOX_IDLE)
        print(f"profile {self!r} is configured and active now")

    def perform_join(self, invitelink):
        if self._account is None:
            print("you must first call --init to setup a profile", file=sys.stderr)
            raise SystemExit(4)
        self._account.start_io()
        self._account.secure_join(invitelink)

        def check_joined(event):
            if (
                event.kind == EventType.SECUREJOIN_JOINER_PROGRESS
                and event["progress"] == 1000
            ):
                return event

        ev = self.wait_for_event(check_joined)
        print(f"established contact with contact_id == {ev.contact_id}")

        def idle_entering_remote(event):
            if event.kind == EventType.INFO and "IDLE entering wait" in event.msg:
                return event

        self.wait_for_event(idle_entering_remote)
        print(f"joining completed with contact_id == {ev.contact_id}")
        return 0

    def perform_send(self, text, filename=None):
        self._account.start_io()
        for chat in self._account.get_chatlist():
            snap = chat.get_full_snapshot()
            if snap.is_encrypted and snap.can_send:
                msg = chat.send_message(text=text, file=filename)
                print(f"message {msg.id} was queued, waiting for delivery")
                msg.wait_until_delivered()
                return 0
        print(f"No chat usable for sending on {self!r}")
        raise SystemExit(5)

    def wait_for_event(self, check_event=lambda ev: None):
        account = self._account
        start_clock = time.time()

        def log(msg):
            if self.verbosity > 0:
                print(msg)

        while event := account.wait_for_event():
            if event.kind == EventType.INCOMING_MSG:
                msg = account.get_message_by_id(event.msg_id)
                text = msg.get_snapshot().text
                log(f"!received historic message: {text}")
            if event.kind == EventType.ERROR:
                log(f"ERROR: {event.msg}")
            if event.kind == EventType.MSG_FAILED:
                msg = account.get_message_by_id(event.msg_id)
                text = msg.get_snapshot().text
                log(f"Message failed: {text}")
            elif event.kind in (EventType.INFO, EventType.WARNING):
                ms_now = (time.time() - start_clock) * 1000
                log(f"INFO {ms_now:07.1f}ms: {event.msg}")
            else:
                log(f"got event: {event}")
            if check_event(event):
                return event


if __name__ == "__main__":
    main()
