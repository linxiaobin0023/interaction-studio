"""Install/update the local Studio, preserving existing data and accounts."""

import argparse
import ipaddress
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments, **kwargs):
    return subprocess.run(["docker", "compose", *arguments], cwd=ROOT, check=True, **kwargs)


def studio_urls(container):
    """Report all live API bindings, preferring a concrete network address."""
    entries = []
    for port in container.get("Publishers") or []:
        if port["TargetPort"] != 8000 or port["Protocol"] != "tcp":
            continue
        address = ipaddress.ip_address(port["URL"])
        if address.is_unspecified:
            address = ipaddress.ip_address("::1" if address.version == 6 else "127.0.0.1")
        host = f"[{address}]" if address.version == 6 else str(address)
        entries.append((address.is_loopback, f"http://{host}:{port['PublishedPort']}/"))
    urls = list(dict.fromkeys(url for _, url in sorted(entries)))
    if not urls:
        raise RuntimeError("Studio has no published API port; inspect docker compose ps api.")
    return urls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    if not args.skip_build:
        run("build", "api")
    run("up", "-d", "--wait", "postgres", "redis", "minio")
    run("run", "--rm", "--no-deps", "migrate")
    probe = run("run", "--rm", "--no-deps", "-T", "--entrypoint", "python", "api", "-c",
                "from interaction_studio_api.db import make_session_factory; "
                "from interaction_studio_api.models import StudioUser; "
                "from sqlalchemy import select,func; "
                "s=make_session_factory()(); print(s.scalar(select(func.count(StudioUser.id))))",
                stdout=subprocess.PIPE, text=True)
    created_credentials = None
    if int(probe.stdout.strip()) == 0:
        directory = ROOT / "data/local-delivery"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        credentials = directory / "initial-login.txt"
        if credentials.exists():
            raise SystemExit("Initial credentials already exist; investigate before creating accounts.")
        password = secrets.token_urlsafe(24)
        # Save before provisioning so a successful creation cannot lose its generated password.
        with credentials.open("x") as file:
            os.chmod(credentials, 0o600)
            file.write("Interaction Studio — local initial login\n"
                       "URL: http://127.0.0.1:8000/\nUsername: studio_owner\n"
                       f"Password: {password}\n\nChange this password in Account Settings.\n")
        run("run", "--rm", "--no-deps", "-T", "--entrypoint", "python", "api", "-m",
            "interaction_studio_api.accounts", "--username", "studio_owner", "--password-stdin",
            input=password + "\n", text=True)
        created_credentials = credentials
        print(f"Initial credentials saved privately: {credentials}")
    else:
        print("Existing accounts preserved; no passwords changed.")
    run("up", "-d", "--no-deps", "api", "studio-worker")
    status = json.loads(run("ps", "--format", "json", "api",
                            text=True, stdout=subprocess.PIPE).stdout)
    urls = studio_urls(status[0] if isinstance(status, list) else status)
    url = urls[0]
    if created_credentials:
        text = created_credentials.read_text().replace("http://127.0.0.1:8000/", url)
        created_credentials.write_text(text)
    print("Local Studio: " + url)
    for alternative in urls[1:]:
        print("Additional Studio address: " + alternative)


if __name__ == "__main__":
    main()
