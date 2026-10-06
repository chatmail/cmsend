"""
chatmail sendmail tool "cmsend" to send e2ee messages.
"""

import argparse
import shutil
import socket
import sys
import sysconfig
import time
from queue import Empty

from deltachat_rpc_client import AttrDict, DeltaChat, EventType, JsonRpcError, Rpc
from xdg_base_dirs import xdg_config_home


def main(argv=None):
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
        "-l", dest="listtags", action="store_true", help="list existing tagged chats"
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
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="give up on network operations after this many seconds (default: 60)",
    )
    args = parser.parse_args(argv)

    try:
        return perform_main(args)
    except KeyboardInterrupt:
        raise SystemExit(2)
    except TimeoutError:
        raise SystemExit(f"cmsend timed out after {args.timeout:g}s")


def perform_main(args):
    accounts_dir = xdg_config_home().joinpath("cmsend")
    if args.verbose >= 1:
        print(f"# using accounts_dir at: {accounts_dir}")
    # "uv tool install" puts only cmsend on PATH, not the server installed with it
    server = shutil.which("deltachat-rpc-server", path=sysconfig.get_path("scripts"))
    server = server or shutil.which("deltachat-rpc-server")
    if not server:
        raise SystemExit("deltachat-rpc-server not found, install it or put it on PATH")
    if args.msg is None and not (args.relay or args.invitelink or args.listtags):
        args.msg = sys.stdin.read()

    with Rpc(accounts_dir=accounts_dir, rpc_server_path=server) as rpc:
        profile = Profile(DeltaChat(rpc), verbosity=args.verbose, timeout=args.timeout)

        if args.relay:
            profile.perform_init(domain=args.relay)
            return
        if not profile._account:
            print("profile is not configured, run --init", file=sys.stderr)
            raise SystemExit(2)

        if args.invitelink:
            profile.perform_join(tag=args.tag, invitelink=args.invitelink)
        elif args.listtags:
            profile.perform_listtags()
        else:
            profile.perform_send(args.tag, args.msg, args.filename)


class Profile:
    _account = None
    UI_CONFIG_TAGGED_CHATS = "ui.cmsend.tagged_chats"

    def __init__(self, dc, verbosity=0, timeout=60):
        self.dc = dc
        self.verbosity = verbosity
        self.deadline = time.monotonic() + timeout
        for account in self.dc.get_all_accounts():
            if account.is_configured():
                self._account = account
                self.verbose1(f"profile {self!r} is active")

    def __repr__(self):
        if self._account:
            return f"Profile<{self._account.self_contact.get_snapshot().address}>"
        return "Profile<unconfigured>"

    def verbose1(self, msg):
        if self.verbosity >= 1:
            print(msg)

    def verbose2(self, msg):
        if self.verbosity >= 2:
            print(msg)

    def start_io(self):
        # checked on every start, so a profile copied to another host follows it
        displayname = f"cmsend[{socket.gethostname()}]"
        if self._account.get_config("displayname") != displayname:
            self._account.set_config("displayname", displayname)
        self._account.start_io()

    def perform_init(self, domain):
        if self._account:
            print(f"profile {self!r} already exists", file=sys.stderr)
            raise SystemExit(3)
        print(f"# creating profile on {domain}")
        self._account = account = self.dc.add_account()
        try:
            account.set_config_from_qr(f"dcaccount:{domain}")
            self.start_io()
            self.wait_for_event(lambda event: event.kind == EventType.IMAP_INBOX_IDLE)
        except JsonRpcError as e:
            account.remove()
            raise SystemExit(f"could not create profile: {e.args[0]['message']}")
        except TimeoutError:
            account.remove()
            raise
        self.verbose1(f"profile {self!r} is configured and active now")

    def perform_join(self, tag, invitelink):
        kind = self._account.check_qr(invitelink)["kind"]
        if kind not in ("askVerifyContact", "askVerifyGroup"):
            raise SystemExit(f"not a contact or group invite link: {kind}")

        self.start_io()
        chat = self._account.secure_join(invitelink)

        def check_joined(event):
            if event.kind == EventType.MSG_FAILED:
                msg = self._account.get_message_by_id(event.msg_id)
                raise SystemExit(f"joining failed: {msg.get_snapshot().error}")
            if (
                event.kind == EventType.SECUREJOIN_JOINER_PROGRESS
                and event["progress"] == 1000
            ):
                return event

        ev = self.wait_for_event(check_joined)
        print(f"established contact with contact_id == {ev.contact_id}")

        # for a group, progress 1000 arrives before "member added" is applied
        if not chat.get_full_snapshot().can_send:

            def check_can_send(event):
                if event.get("chat_id") == chat.id:
                    return chat.get_full_snapshot().can_send

            self.wait_for_event(check_can_send)

        print(f"joining completed with chat_id == {chat.id} tag={tag}")
        self._account.set_config(f"{self.UI_CONFIG_TAGGED_CHATS}.{tag}", str(chat.id))
        list_tags = self._account.get_config(self.UI_CONFIG_TAGGED_CHATS) or ""
        tags = set(filter(None, list_tags.split(",")))
        tags.add(tag)
        self._account.set_config(self.UI_CONFIG_TAGGED_CHATS, ",".join(tags))

    def perform_listtags(self):
        list_tags = self._account.get_config(self.UI_CONFIG_TAGGED_CHATS) or ""
        for tag in filter(None, list_tags.split(",")):
            chat = self.get_tagged_chat(tag)
            snap = chat.get_full_snapshot()
            print(f"{tag}: chat_id={chat.id} name={snap.name}")
            for contact in chat.get_contacts():
                contact_snap = contact.get_snapshot()
                print(f"   - {contact_snap.display_name} <{contact_snap.address}>")

    def perform_send(self, tag, text, filename=None):
        self.start_io()

        chat = self.get_tagged_chat(tag)
        snap = chat.get_full_snapshot()
        if snap.is_encrypted and snap.can_send:
            msg = chat.send_message(text=text, file=filename)
            print(f"message {msg.id} was queued, waiting for delivery")

            def check_sent(event):
                if event.kind in (EventType.MSG_DELIVERED, EventType.MSG_FAILED):
                    return event.msg_id == msg.id

            if self.wait_for_event(check_sent).kind == EventType.MSG_FAILED:
                raise SystemExit(f"message {msg.id} failed: {msg.get_snapshot().error}")
            return 0
        print(f"chat_id={chat.id} tag={tag} is not sendable", file=sys.stderr)
        raise SystemExit(5)

    def get_tagged_chat(self, tag):
        chat_id = self._account.get_config(f"{self.UI_CONFIG_TAGGED_CHATS}.{tag}")
        if not chat_id:
            print(
                f"No chat tagged with tag={tag} found for sending on {self!r}, "
                f"use -t {tag} --join 'https://i.delta.chat/...'",
                file=sys.stderr,
            )
            raise SystemExit(5)

        return self._account.get_chat_by_id(int(chat_id))

    def wait_for_event(self, check_event):
        account = self._account
        events = self.dc.rpc.get_queue(account.id)
        start_clock = time.time()

        log = self.verbose2

        while True:
            remaining = max(0, self.deadline - time.monotonic())
            try:
                event = AttrDict(events.get(timeout=remaining))
            except Empty:
                raise TimeoutError
            if event.kind == EventType.INCOMING_MSG:
                msg = account.get_message_by_id(event.msg_id)
                text = msg.get_snapshot().text
                log(f"!received historic message: {text}")
            elif event.kind == EventType.ERROR:
                log(f"ERROR: {event.msg}")
            elif event.kind == EventType.MSG_FAILED:
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
