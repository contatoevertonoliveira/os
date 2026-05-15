import base64
import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import MicrosoftGraphToken


class MicrosoftAuthError(Exception):
    pass


def share_id_from_url(shared_url):
    raw = shared_url.encode('utf-8')
    b64 = base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
    return f"u!{b64}"


def http_json(method, url, headers=None, data=None, form=None, timeout=30):
    body = None
    final_headers = {}
    if headers:
        final_headers.update(headers)
    if form is not None:
        body = urllib.parse.urlencode(form).encode('utf-8')
        final_headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif data is not None:
        body = json.dumps(data).encode('utf-8')
        final_headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=final_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return None
        return json.loads(raw.decode('utf-8'))


def http_bytes(method, url, headers=None, timeout=60):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def tenant_id():
    return getattr(settings, 'MS_TENANT_ID', None) or ''


def client_id():
    return getattr(settings, 'MS_CLIENT_ID', None) or ''


def client_secret():
    return getattr(settings, 'MS_CLIENT_SECRET', None) or ''


def shared_clients_url():
    return getattr(settings, 'CLIENTS_SHAREPOINT_URL', None) or ''


def token_endpoint():
    tid = tenant_id()
    if not tid:
        raise MicrosoftAuthError('MS_TENANT_ID não configurado.')
    return f'https://login.microsoftonline.com/{tid}/oauth2/v2.0/token'


def device_code_endpoint():
    tid = tenant_id()
    if not tid:
        raise MicrosoftAuthError('MS_TENANT_ID não configurado.')
    return f'https://login.microsoftonline.com/{tid}/oauth2/v2.0/devicecode'


def get_app_token():
    cid = client_id()
    secret = client_secret()
    if not cid or not secret:
        return None
    data = http_json(
        'POST',
        token_endpoint(),
        form={
            'client_id': cid,
            'client_secret': secret,
            'grant_type': 'client_credentials',
            'scope': 'https://graph.microsoft.com/.default',
        },
    )
    if not data or 'access_token' not in data:
        raise MicrosoftAuthError('Falha ao obter token de aplicação (client_credentials).')
    expires_in = int(data.get('expires_in') or 0)
    return data['access_token'], timezone.now() + timedelta(seconds=max(expires_in - 60, 0))


def get_cached_delegated_token():
    token = MicrosoftGraphToken.objects.filter(purpose='graph_delegated').first()
    if not token or not token.access_token or not token.expires_at:
        return None
    if token.expires_at <= timezone.now() + timedelta(seconds=30):
        return None
    return token.access_token


def refresh_delegated_token():
    token = MicrosoftGraphToken.objects.filter(purpose='graph_delegated').first()
    if not token or not token.refresh_token:
        return None
    cid = client_id()
    if not cid:
        raise MicrosoftAuthError('MS_CLIENT_ID não configurado.')
    data = http_json(
        'POST',
        token_endpoint(),
        form={
            'client_id': cid,
            'grant_type': 'refresh_token',
            'refresh_token': token.refresh_token,
            'scope': 'offline_access Files.Read.All',
        },
    )
    if not data or 'access_token' not in data:
        raise MicrosoftAuthError('Falha ao renovar token (refresh_token).')
    expires_in = int(data.get('expires_in') or 0)
    token.access_token = data.get('access_token')
    if data.get('refresh_token'):
        token.refresh_token = data.get('refresh_token')
    token.expires_at = timezone.now() + timedelta(seconds=max(expires_in - 60, 0))
    token.save()
    return token.access_token


def get_graph_access_token():
    app = None
    try:
        app = get_app_token()
    except MicrosoftAuthError:
        app = None
    if app:
        return app[0]
    cached = get_cached_delegated_token()
    if cached:
        return cached
    try:
        refreshed = refresh_delegated_token()
        if refreshed:
            return refreshed
    except MicrosoftAuthError:
        return None
    return None


def start_device_code_flow():
    cid = client_id()
    if not cid:
        raise MicrosoftAuthError('MS_CLIENT_ID não configurado.')
    data = http_json(
        'POST',
        device_code_endpoint(),
        form={
            'client_id': cid,
            'scope': 'offline_access Files.Read.All',
        },
    )
    if not data or 'device_code' not in data:
        raise MicrosoftAuthError('Falha ao iniciar device code flow.')
    return data


def poll_device_code(device_code):
    cid = client_id()
    if not cid:
        raise MicrosoftAuthError('MS_CLIENT_ID não configurado.')
    try:
        data = http_json(
            'POST',
            token_endpoint(),
            form={
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'client_id': cid,
                'device_code': device_code,
            },
        )
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, 'read') else b''
        payload = {}
        try:
            payload = json.loads(raw.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        error = payload.get('error') or 'authorization_pending'
        return {'status': 'pending', 'error': error, 'raw': payload}
    if not data or 'access_token' not in data:
        return {'status': 'error', 'error': 'invalid_token_response', 'raw': data}
    expires_in = int(data.get('expires_in') or 0)
    token, _ = MicrosoftGraphToken.objects.get_or_create(purpose='graph_delegated')
    token.access_token = data.get('access_token')
    token.refresh_token = data.get('refresh_token') or token.refresh_token
    token.expires_at = timezone.now() + timedelta(seconds=max(expires_in - 60, 0))
    token.save()
    return {'status': 'ok'}


def graph_headers(access_token):
    return {'Authorization': f'Bearer {access_token}'}


def fetch_sharepoint_driveitem_metadata(share_url, access_token):
    sid = share_id_from_url(share_url)
    url = f'https://graph.microsoft.com/v1.0/shares/{sid}/driveItem?$select=eTag,lastModifiedDateTime,name'
    return http_json('GET', url, headers=graph_headers(access_token))


def download_sharepoint_driveitem_content(share_url, access_token):
    sid = share_id_from_url(share_url)
    url = f'https://graph.microsoft.com/v1.0/shares/{sid}/driveItem/content'
    return http_bytes('GET', url, headers=graph_headers(access_token))
