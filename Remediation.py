# DummyApp/remediation_engine.py
#
# Demo remediation engine for the Toilet Management dummy app.
#
# Each function simulates fixing a specific error type:
#   - Renewing an SSL certificate (via simulated ACM call)
#   - Rotating a service account password (via simulated Secrets Manager)
#   - Expanding DB storage (via simulated RDS call)
#   - Draining and restarting DB connections
#   - Scaling out ECS compute
#
# In a real deployment these would call boto3 (ACM, Secrets Manager, RDS, ECS).
# Here they simulate the steps with realistic delays and log every action so the
# demo is visually convincing.  Each function returns a RemediationResult dict:
#
#   {
#     "success":   bool,
#     "steps":     [{"step": str, "status": "ok"|"warn"|"fail", "detail": str}],
#     "summary":   str,            # one-line result for ServiceNow work_notes
#     "new_state": "resolved"|"in_progress"|"failed",
#   }

import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def _step(description: str, status: str = 'ok', detail: str = '') -> dict:
    return {'step': description, 'status': status, 'detail': detail, 'ts': _ts()}


def _simulate_delay(min_s=0.1, max_s=0.4):
    """Small delay to make demo feel realistic."""
    time.sleep(random.uniform(min_s, max_s))


# ── Individual remediation functions ──────────────────────────────────────────

def fix_ssl_expired(log_path: str = '', session_id: str = '') -> dict:
    """
    Fix an expired SSL certificate.
    Delegates to ssl_remediation_agent which:
      1. Calls the Bedrock agent for a real remediation plan (falls back to demo plan)
      2. Executes each AWS step (ACM, ALB, Secrets Manager) with realistic timing
      3. Writes a RESOLVED line to application.log
    """
    logger.info('[remediation] Starting ssl_expired fix via Bedrock agent')
    try:
        from ssl_remediation_agent import run_ssl_expired_fix  # type: ignore
        return run_ssl_expired_fix(log_path=log_path, session_id=session_id)
    except Exception as exc:
        logger.error('[remediation] ssl_remediation_agent failed: %s', exc)
        # Hard fallback — basic steps without Bedrock
        import random as _r
        cert_arn = f'arn:aws:acm:us-east-1:123456789012:certificate/{_r.randint(10000,99999)}-demo'
        steps = [
            _step('Detected expired certificate for api.dummy-app.internal', 'ok', 'Serial: A1:B2:C3:D4'),
            _step('Requested new TLS certificate from ACM', 'ok', f'ARN: {cert_arn[-40:]}'),
            _step('DNS CNAME validation completed', 'ok', 'Status: ISSUED'),
            _step('New cert attached to ALB HTTPS:443', 'ok', 'Old cert detached'),
            _step('ARN stored in Secrets Manager', 'ok', '/dummy-app/ssl/cert-arn updated'),
            _step('HTTPS handshake verified', 'ok', 'TLS 1.3 ✔ — valid 365 days'),
        ]
        _write_resolution_log(log_path, 'ssl_expired',
                              f'SSL cert renewed. ARN: {cert_arn[-30:]}. 365 days.')
        return {
            'success':   True,
            'steps':     steps,
            'summary':   f'SSL certificate renewed via ACM. ARN: ...{cert_arn[-30:]}.',
            'new_state': 'resolved',
        }


def fix_ssl_expiring(log_path: str = '') -> dict:
    """Proactively rotate an SSL certificate expiring within 7 days."""
    steps = []
    logger.info('[remediation] Starting ssl_expiring proactive rotation')

    _simulate_delay()
    steps.append(_step('Confirmed certificate expiry in 7 days', 'ok',
                       'Expiry: ' + _ts()))

    _simulate_delay()
    cert_arn = f'arn:aws:acm:us-east-1:123456789012:certificate/{random.randint(10000,99999)}-demo'
    steps.append(_step('Requested replacement certificate from ACM', 'ok',
                       f'New cert ARN: {cert_arn}'))

    _simulate_delay()
    steps.append(_step('DNS validation completed automatically (CNAME in place)', 'ok', ''))

    _simulate_delay()
    steps.append(_step('Swapped certificate on ALB — zero-downtime rotation', 'ok', ''))

    _write_resolution_log(log_path, 'ssl_expiring',
                          f'SSL cert rotated proactively. New cert valid 365 days.')

    return {
        'success':   True,
        'steps':     steps,
        'summary':   'SSL certificate proactively rotated. New cert valid 365 days.',
        'new_state': 'resolved',
    }


def fix_password_expired(log_path: str = '') -> dict:
    """
    Simulate rotating a service account password via Secrets Manager.
    Steps: detect → generate new password → update Secrets Manager → reconnect services
    """
    steps = []
    logger.info('[remediation] Starting password_expired fix')

    _simulate_delay()
    steps.append(_step('Identified expired service account: svc-dummy-app@internal', 'ok',
                       'Password last rotated: 91 days ago (policy: 90 days)'))

    _simulate_delay()
    new_pwd_hint = '***' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
    steps.append(_step('Generated new secure password (32 chars, complexity compliant)', 'ok',
                       f'New password (masked): {new_pwd_hint}'))

    _simulate_delay()
    steps.append(_step('Updated Secrets Manager secret: /dummy-app/svc-account/password', 'ok',
                       'Version AWSCURRENT updated, previous moved to AWSPREVIOUS'))

    _simulate_delay()
    steps.append(_step('Rotated password in target system (AD / LDAP)', 'ok',
                       'svc-dummy-app password updated in directory service'))

    _simulate_delay()
    steps.append(_step('Restarted dependent services to pick up new credentials', 'ok',
                       'ECS task recycled — new task healthy (3/3 checks passing)'))

    _simulate_delay()
    steps.append(_step('Verified authentication with new password', 'ok',
                       'POST /api/dummy/auth → HTTP 200 ✔'))

    _write_resolution_log(log_path, 'password_expired',
                          'Service account password rotated via Secrets Manager. Auth reconnected.')

    return {
        'success':   True,
        'steps':     steps,
        'summary':   'Service account password rotated via Secrets Manager. Auth reconnected.',
        'new_state': 'resolved',
    }


def fix_db_storage(log_path: str = '') -> dict:
    """Simulate increasing RDS allocated storage."""
    steps = []
    logger.info('[remediation] Starting db_storage fix')

    _simulate_delay()
    steps.append(_step('Confirmed RDS storage at 92% — writes failing intermittently', 'ok',
                       'Instance: db-dummy-app-prod  Current: 920 GB / 1000 GB'))

    _simulate_delay()
    steps.append(_step('Initiated RDS storage modification: 1000 GB → 2000 GB', 'ok',
                       'RDS ModifyDBInstance called — zero downtime (autoscale eligible)'))

    _simulate_delay(0.5, 1.0)
    steps.append(_step('Storage expansion applied — RDS status: available', 'ok',
                       'New capacity: 2000 GB  |  Used: 920 GB (46%)'))

    _simulate_delay()
    steps.append(_step('Enabled RDS storage autoscaling (max 4000 GB)', 'ok',
                       'MaxAllocatedStorage set to 4000 GB to prevent recurrence'))

    _write_resolution_log(log_path, 'db_storage',
                          'RDS storage expanded from 1 TB to 2 TB. Autoscaling enabled.')

    return {
        'success':   True,
        'steps':     steps,
        'summary':   'RDS storage expanded 1 TB → 2 TB. Autoscaling enabled (max 4 TB).',
        'new_state': 'resolved',
    }


def fix_db_connection(log_path: str = '') -> dict:
    """Simulate draining exhausted DB connections and scaling RDS."""
    steps = []
    logger.info('[remediation] Starting db_connection fix')

    _simulate_delay()
    steps.append(_step('Detected connection pool exhaustion on db-dummy-app-prod', 'ok',
                       'Active connections: 500/500  |  Waiting: 47'))

    _simulate_delay()
    steps.append(_step('Identified connection leak in ECS task revision 14', 'warn',
                       '~12 connections per task not being released on idle'))

    _simulate_delay()
    steps.append(_step('Force-terminated idle connections older than 60s', 'ok',
                       '183 stale connections closed — pool freed to 317/500'))

    _simulate_delay()
    steps.append(_step('Deployed patched ECS task (revision 15) — connection leak fixed', 'ok',
                       'Rolling update complete — 4/4 tasks healthy'))

    _simulate_delay()
    steps.append(_step('Upgraded RDS instance class: db.t3.large → db.r6g.xlarge', 'ok',
                       'Max connections increased: 500 → 2000'))

    _simulate_delay()
    steps.append(_step('Verified connection pool stable at 120/2000', 'ok', ''))

    _write_resolution_log(log_path, 'db_connection',
                          'Connection leak patched. RDS instance upgraded. Pool stable at 120/2000.')

    return {
        'success':   True,
        'steps':     steps,
        'summary':   'DB connection leak patched, ECS redeployed, RDS upgraded to r6g.xlarge.',
        'new_state': 'resolved',
    }


def fix_compute_overload(log_path: str = '') -> dict:
    """Simulate scaling out ECS service to relieve CPU/memory pressure."""
    steps = []
    logger.info('[remediation] Starting compute_overload fix')

    _simulate_delay()
    steps.append(_step('Confirmed ECS service overloaded: CPU 95%, memory 88%', 'ok',
                       'Service: dummy-app-svc  Running: 2/2  Desired: 2'))

    _simulate_delay()
    steps.append(_step('Scaled ECS desired count: 2 → 6 tasks', 'ok',
                       'ECS UpdateService called — 4 new tasks launching'))

    _simulate_delay(0.5, 1.0)
    steps.append(_step('New tasks healthy and receiving traffic (3/3 ALB checks)', 'ok',
                       'Running: 6/6  CPU: 28%  Memory: 41%'))

    _simulate_delay()
    steps.append(_step('Updated ECS autoscaling policy: min=2, max=12, target CPU=60%', 'ok',
                       'StepScaling → TargetTracking policy applied'))

    _simulate_delay()
    steps.append(_step('Verified all API endpoints responding < 200ms', 'ok', ''))

    _write_resolution_log(log_path, 'compute_overload',
                          'ECS scaled 2→6 tasks. Autoscaling policy updated. CPU now 28%.')

    return {
        'success':   True,
        'steps':     steps,
        'summary':   'ECS scaled out from 2 to 6 tasks. CPU reduced from 95% to 28%. Autoscaling updated.',
        'new_state': 'resolved',
    }


# ── Dispatcher ─────────────────────────────────────────────────────────────────

REMEDIATION_MAP = {
    'ssl_expired':      fix_ssl_expired,
    'ssl_expiring':     fix_ssl_expiring,
    'password_expired': fix_password_expired,
    'db_storage':       fix_db_storage,
    'db_connection':    fix_db_connection,
    'compute_overload': fix_compute_overload,
}

# Map dashboard error codes (from unique_errors.json) to remediation keys
ERROR_CODE_MAP = {
    '9010': 'ssl_expired',
    '9011': 'ssl_expiring',
    '9012': 'password_expired',
    '9013': 'db_storage',
    '9014': 'db_connection',
    '9015': 'compute_overload',
    # 2000-series random errors — map to closest analogue
    '2001': 'compute_overload',
    '2002': 'db_connection',
    '2004': 'db_connection',
    '2005': 'password_expired',
    '2007': 'compute_overload',
    '2008': 'compute_overload',
}


def run_remediation(error_code: str, description: str = '', log_path: str = '',
                    session_id: str = '', **kwargs) -> dict:
    """
    Dispatch to the right fix function by error_code.
    session_id is passed through to fix functions that accept it (e.g. fix_ssl_expired).
    **kwargs makes the signature forward-compatible — extra args are silently ignored.
    """
    import inspect
    key = ERROR_CODE_MAP.get(str(error_code))
    if key and key in REMEDIATION_MAP:
        logger.info('[remediation] Dispatching error_code=%s → %s()', error_code, key)
        fn  = REMEDIATION_MAP[key]
        sig = inspect.signature(fn).parameters
        call_kwargs = {'log_path': log_path}
        if 'session_id' in sig:
            call_kwargs['session_id'] = session_id
        return fn(**call_kwargs)

    # Generic fallback — mark as in-progress, no automated fix available
    logger.warning('[remediation] No automated fix for error_code=%s', error_code)
    return {
        'success':   False,
        'steps':     [_step(f'No automated remediation for error code {error_code}', 'warn',
                            'Manual investigation required. Error acknowledged in ServiceNow.')],
        'summary':   f'Error {error_code} acknowledged. No automated fix available — manual review required.',
        'new_state': 'in_progress',
    }


def _write_resolution_log(log_path: str, error_type: str, message: str):
    """Write a RESOLVED line to application.log so the dashboard pipeline picks it up."""
    if not log_path:
        return
    try:
        ts   = _ts()
        line = f'[{ts}] [INFO] RESOLVED: {error_type} — {message}\n'
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as fh:
            fh.write(line)
    except Exception as exc:
        logger.warning('[remediation] Could not write resolution log: %s', exc)
