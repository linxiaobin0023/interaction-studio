"""Local administrator CLI. Passwords are read from a terminal or stdin, never argv."""

import argparse
import getpass
import sys

from .api.auth import AccountCreate
from .auth import create_account
from .db import make_session_factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--roles", default="ADMIN,OPERATOR,AUDITOR")
    parser.add_argument("--password-stdin", action="store_true")
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass()
    body = AccountCreate(username=args.username, password=password, roles=args.roles.split(","))
    with make_session_factory().begin() as session:
        create_account(session, body.username, body.password, body.roles, "LOCAL_ADMIN_CLI")
    print("Account created. Sign in at the Studio.")


if __name__ == "__main__":
    main()
