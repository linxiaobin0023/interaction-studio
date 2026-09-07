"""Check the packaged Studio against a disposable PostgreSQL database."""

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from interaction_studio_api.config import get_settings
from sqlalchemy.engine import make_url

CHECK = r'''
import hashlib, io, json, re, subprocess, sys, time, urllib.error, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from interaction_studio_api.db import make_session_factory
from interaction_studio_api.auth import create_account
from interaction_studio_api.domain.studio_evidence import verify_evidence
from interaction_studio_api.domain.studio_jobs import claim_job
from sqlalchemy import select
from interaction_studio_api.models import StudioJob
subprocess.run(['alembic', 'upgrade', 'head'], check=True)
subprocess.run(['alembic', 'check'], check=True)
worker = None
password=uuid4().hex
with make_session_factory().begin() as session:
    create_account(session,'smoke_operator',password,['ADMIN','OPERATOR'],'SMOKE_TEST')
cookie=''
server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'interaction_studio_api.main:app',
                           '--host', '127.0.0.1', '--port', '8000', '--log-level', 'error'])
base='http://127.0.0.1:8000'
def call(path, data=None, method=None):
    request=urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None,
                                  method=method, headers={'Content-Type':'application/json',
                                                          'X-Studio-Request':'1','Cookie':cookie})
    return urllib.request.urlopen(request, timeout=30)
try:
    for _ in range(100):
        try:
            with call('/health/live') as response: assert response.status==200
            break
        except urllib.error.URLError: time.sleep(.1)
    else: raise RuntimeError('API did not start')
    try:
        call('/api/v1/development/catalog')
        raise AssertionError('anonymous access accepted')
    except urllib.error.HTTPError as exc: assert exc.code==401
    with call('/api/v1/auth/login',{'username':'smoke_operator','password':password}) as response:
        cookie=response.headers['Set-Cookie'].split(';',1)[0]
    with call('/') as response: page=response.read().decode()
    assert 'Interaction Studio' in page
    assets=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',page)
    assert len(assets)>=2
    for path in assets:
        with call(path) as response: assert response.status==200
    with call('/api/v1/development/catalog') as response:
        assert len(json.load(response)['cases'])==30
    draft='/api/v1/development/studio/drafts/DEV_HAND_001'
    body={'expected_version':0,'parameters':{'case_id':'DEV_HAND_001'}}
    with call(draft,body,'PUT') as response: first=json.load(response)
    assert first['draft']['resource_version']==1
    try:
        call(draft,body,'PUT')
        raise AssertionError('stale save accepted')
    except urllib.error.HTTPError as exc: assert exc.code==409
    with call(draft) as response: saved=json.load(response)
    assert saved==first and saved['history_verified']
    template={'name':'Smoke test','parameters':first['draft']['parameters']}
    with call('/api/v1/development/studio/templates',template) as response:
        assert json.load(response)['version']==1
    with call('/api/v1/development/studio/templates',template) as response:
        assert json.load(response)['version']==2
    with call('/api/v1/development/previews?format=bundle',body['parameters']) as response:
        data=response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        for ref in manifest['artifacts']:
            assert hashlib.sha256(archive.read(ref['path'])).hexdigest()==ref['sha256']
    assert manifest['provider_execution_performed'] is False
    for path in ['/api/v1/development/studio/drafts/VAL_MOUTH_001',
                 '/api/v1/development/studio/drafts/FORMAL_MOUTH_001']:
        try:
            call(path)
            raise AssertionError('non-Development draft accepted')
        except urllib.error.HTTPError as exc: assert exc.code==422
    jobs='/api/v1/development/studio/jobs'
    submission={'idempotency_key':str(uuid4()), 'parameters':{'case_id':'DEV_HAND_001'}}
    def enqueue(_):
        with call(jobs,submission) as response:
            assert response.status==202
            return json.load(response)['id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(enqueue,range(4)))
    assert len(set(ids))==1
    job_id=ids[0]
    with call(jobs,{'idempotency_key':str(uuid4()),
                    'parameters':{'case_id':'DEV_MOUTH_001'}}) as response:
        second_id=json.load(response)['id']
    factory=make_session_factory()
    with factory() as first, factory() as second:
        first.scalar(select(StudioJob).where(StudioJob.id==job_id).with_for_update())
        claimed=claim_job(second)
        assert claimed['id']==second_id
        assert claim_job(first)['id']==job_id
        second.rollback()
        first.rollback()
    worker=subprocess.Popen([sys.executable,'-m','interaction_studio_api.studio_worker'])
    for _ in range(100):
        with call(jobs+'/'+job_id) as response: result=json.load(response)
        if result['state'] in ['SUCCEEDED','FAILED']: break
        time.sleep(.2)
    assert result['state']=='SUCCEEDED',result
    with call(jobs+'/'+job_id+'/output') as response: bundle=response.read()
    assert hashlib.sha256(bundle).hexdigest()==result['output_sha256']
    review={'expected_version':0, 'output_sha256':result['output_sha256'],
            'dimensions':{key:{'decision':'PASS'}
                          for key in ['product','interaction','identity','scene','overall']}}
    def save_review(_):
        try:
            with call(jobs+'/'+job_id+'/reviews',review) as response: return response.status
        except urllib.error.HTTPError as exc: return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(save_review,range(2)))
    assert sorted(statuses)==[201,409],statuses
    worker.terminate()
    worker.wait(timeout=10)
    worker=None
    with call(jobs+'/'+job_id) as response: persisted=json.load(response)
    assert len(persisted['reviews'])==1
    assert persisted['reviews'][0]['scope']=='LOCAL_DEVELOPMENT_ONLY'
    assert persisted['output_sha256']==result['output_sha256']
    assert persisted['provider_execution_performed'] is False
    with call(jobs+'/'+job_id+'/evidence') as response:
        assert verify_evidence(response.read())['review_count']==1
    with call('/api/v1/auth/users',{'username':'smoke_reader','password':password,
                                  'roles':['AUDITOR']}) as response:
        assert response.status==201
    with call('/api/v1/auth/login',{'username':'smoke_reader','password':password}) as response:
        cookie=response.headers['Set-Cookie'].split(';',1)[0]
    try:
        call(jobs,{'idempotency_key':str(uuid4()),'parameters':{'case_id':'DEV_HAND_001'}})
        raise AssertionError('readonly account created job')
    except urllib.error.HTTPError as exc: assert exc.code==403
    with call('/api/v1/auth/logout',{}) as response: assert response.status==200
    try:
        call(jobs+'/'+job_id)
        raise AssertionError('revoked session accepted')
    except urllib.error.HTTPError as exc: assert exc.code==401
    print(json.dumps({'studio_html_assets':True,'catalog_cases':30,'postgres_draft_saved':True,
                      'stale_write_rejected':True,'template_versions':2,'bundle_verified':True,
                      'durable_job_and_output':True,'concurrent_idempotency':True,
                      'authentication_rbac_revocation':True,'offline_evidence_replay':True,
                      'postgres_skip_locked':True,'qc_conflict_and_persistence':True,
                      'provider_execution_performed':False}))
finally:
    if worker is not None:
        worker.terminate()
        worker.wait(timeout=10)
    server.terminate()
    server.wait(timeout=10)
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore-report", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    configured = make_url(settings.database_url)
    database = "studio_smoke_" + uuid4().hex[:12]
    user = configured.username or "interaction_studio"
    command = ["docker", "compose", "exec", "-T", "postgres"]
    subprocess.run(command + ["createdb", "-U", user, database], check=True)
    try:
        environment = dict(os.environ)
        # Pass by environment name; never include the secret in the command line or logs.
        environment["STUDIO_SMOKE_DATABASE_URL"] = configured.set(
            host="postgres", port=5432, database=database).render_as_string(hide_password=False)
        run = ["docker", "compose", "run", "--rm", "--no-deps", "-T", "--entrypoint", "sh",
               "-e", "STUDIO_SMOKE_DATABASE_URL", "api", "-c",
               'export DATABASE_URL="$STUDIO_SMOKE_DATABASE_URL"; exec python -']
        subprocess.run(run, input=CHECK, text=True, env=environment, check=True)
        if args.restore_report:
            from studio_backup import create_backup, restore_drill

            with tempfile.TemporaryDirectory(prefix="studio-backup-fixture-") as directory:
                root = Path(directory)
                key = root / "backup.key"
                key.write_text(secrets.token_hex(32) + "\n")
                key.chmod(0o600)
                create_backup(root / "backup", key, environment["STUDIO_SMOKE_DATABASE_URL"])
                report = restore_drill(root / "backup", key)
                assert report["counts"]["studio_job_outputs"] >= 1
                assert report["counts"]["studio_reviews"] == 1
                args.restore_report.parent.mkdir(parents=True, exist_ok=True)
                args.restore_report.write_text(json.dumps(report, indent=2) + "\n")
                print("Populated backup/restore drill passed.")
    finally:
        subprocess.run(command + ["dropdb", "-U", user, database], check=True)


if __name__ == "__main__":
    main()
