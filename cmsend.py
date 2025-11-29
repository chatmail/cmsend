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
        dest="relay",
        help="initialize a profile with the specified chatmail relay",
    )
    parser.add_argument(
        "--join",
        dest="invitelink",
        type=str,
        help="setup a chat using the specified invite link",
    )
    parser.add_argument(
        "-t",
        type=str,
        dest="tag",
        default="GENESIS",
        help="use the specified tag for joining a chat or sending a message (default: GENESIS)",
    )
    parser.add_argument(
        "-l",
        dest="listtags",
        action="store_true",
        help="list existing tagged chats"
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
    if args.verbose >= 1:
        print(f"# using accounts_dir at: {accounts_dir}")
    with Rpc(accounts_dir=accounts_dir) as rpc:
        dc = DeltaChat(rpc)
        profile = Profile(dc, verbosity=args.verbose)

        if args.relay:
            profile.perform_init(domain=args.relay)
        elif args.invitelink:
            profile.perform_join(tag=args.tag, invitelink=args.invitelink)
        elif args.listtags:
            profile.perform_listtags()
        else:
            if not profile._account:
                print("profile is not configured, run --init")
                raise SystemExit(2)

            if args.msg is None:
                args.msg = sys.stdin.read()
            profile.perform_send(text=args.msg, filename=args.filename, tag=args.tag)


class Profile:
    _account = None
    UI_CONFIG_TAGGED_CHATS = "ui.cmsend.tagged_chats"

    def __init__(self, dc, verbosity=0):
        self.dc = dc
        self.verbosity = verbosity
        for account in self.dc.get_all_accounts():
            addr = account.get_config("configured_addr")
            if addr is not None:
                self._account = account
                self.verbose1(f"profile {self!r} is active")

    def __repr__(self):
        if self._account:
            return f"Profile<{self._account.get_config('configured_addr')}>"
        return "Profile<unconfigured>"

    def verbose1(self, msg):
        if self.verbosity >= 1:
            print(msg)

    def verbose2(self, msg):
        if self.verbosity >= 2:
            print(msg)

    def perform_init(self, domain):
        if self._account:
            print(f"profile {self!r} already exists", file=sys.stderr)
            raise SystemExit(3)
        print(f"# creating profile on {domain}")
        self._account = account = self.dc.add_account()
        account.set_config_from_qr(f"dcaccount:{domain}")
        account.start_io()
        account.wait_for_event(EventType.IMAP_INBOX_IDLE)
        self.verbose1(f"profile {self!r} is configured and active now")

    def perform_join(self, tag, invitelink):
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

        def me_was_added(event):
            if event.kind == EventType.INCOMING_MSG:
                msg = self._account.get_message_by_id(event.msg_id)
                text = msg.get_snapshot().text
                if text.startswith("Member Me added"):
                    return True

        ev_chat_id = self.wait_for_event(me_was_added)
        chat_id = ev_chat_id.chat_id
        print(f"joining completed with chat_id == {chat_id} tag={tag}")
        self._account.set_config(f"{self.UI_CONFIG_TAGGED_CHATS}.{tag}", str(chat_id))
        list_tags = self._account.get_config(self.UI_CONFIG_TAGGED_CHATS) or ""
        tags = set(list_tags.split(","))
        tags.add(tag)
        self._account.set_config(self.UI_CONFIG_TAGGED_CHATS, ",".join(tags))

    def perform_listtags(self):
        list_tags = self._account.get_config(self.UI_CONFIG_TAGGED_CHATS) or ""
        for tag in filter(None, list_tags.split(",")):
            chat = self.get_tagged_chat(tag)
            snap = chat.get_full_snapshot()
            print(f"{tag}: chat_id={chat.id} name={snap.name}")
            for contact in snap.contacts:
                print(f"   - {contact.name_and_addr}")

    def perform_send(self, tag, text, filename=None):
        self._account.start_io()

        chat = self.get_tagged_chat(tag)
        snap = chat.get_full_snapshot()
        if snap.is_encrypted and snap.can_send:
            msg = chat.send_message(text=text, file=filename)
            print(f"message {msg.id} was queued, waiting for delivery")
            msg.wait_until_delivered()
            return 0
        raise SystemExit(5)

    def get_tagged_chat(self, tag):
        chat_id = self._account.get_config(f"{self.UI_CONFIG_TAGGED_CHATS}.{tag}")
        if not chat_id:
            print(f"No chat tagged with tag={tag} found for sending on {self!r}, "
                  f"use -t {tag} --join 'https://i.delta.chat/...'")
            raise SystemExit(5)

        return self._account.get_chat_by_id(int(chat_id))

    def wait_for_event(self, check_event=lambda ev: None):
        account = self._account
        start_clock = time.time()

        log = self.verbose2

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
