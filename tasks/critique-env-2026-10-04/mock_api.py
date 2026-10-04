"""Critique test backend for the EarningsNerd frontend.

Read-only GETs for public data pass through to https://api.earningsnerd.io (cached on disk);
authenticated/Pro/error/streaming states are simulated per request via the `en_scenario` cookie
(or `X-EN-Scenario` header). No production mutation ever happens. Scenario tokens (comma-joined):

  anon (default) | free | pro        identity + plan
  content                            serve fixtures/filing-3-content.md for /filings/3/content (other ids pass through)
  nosummary                          summary 404 until a mocked generate-stream completes
  summaryerror                       summary GET -> 500
  partial                            summary served with quality.tier=partial (+status partial)
  genfail                            generate-stream ends with an error event
  askfail                            ask-stream -> 500
  exhausted                          free user with no Copilot taste left
  saved                              summary already saved
  watch                              AAPL on the watchlist
  slow                               +2.5s latency on summary/content/company reads
  offline                            every passthrough -> 503 (backend unreachable)
"""
import json, os, sys, time, hashlib, re, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
CACHE = os.path.join(HERE, 'cache')
FIXTURES = os.path.join(HERE, 'fixtures')
UPSTREAM = 'https://api.earningsnerd.io'
PORT = int(os.environ.get('MOCK_PORT', '8010'))
os.makedirs(CACHE, exist_ok=True)
LOCK = threading.Lock()
GENERATED = set()      # (scenario, filing_id) summaries "generated" via the mocked stream
SAVED = set()          # (scenario, summary_id)
WATCH = {}             # scenario -> set(tickers)
LOG = open(os.path.join(HERE, 'mock_api.log'), 'a')

def log(*a):
    LOG.write(' '.join(str(x) for x in a) + '\n'); LOG.flush()

def upstream(path):
    key = hashlib.sha256(path.encode()).hexdigest()[:24]
    fp = os.path.join(CACHE, key + '.json')
    if os.path.exists(fp):
        with open(fp) as f: return json.load(f)
    req = urllib.request.Request(UPSTREAM + path, headers={'accept': 'application/json', 'user-agent': 'earningsnerd-critique-mock/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode('utf-8', 'replace'); status = r.status; ctype = r.headers.get('content-type', 'application/json')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace'); status = e.code; ctype = e.headers.get('content-type', 'application/json')
    rec = {'status': status, 'ctype': ctype, 'body': body, 'path': path}
    with open(fp, 'w') as f: json.dump(rec, f)
    return rec

USER_FREE = {'id': 1001, 'email': 'riley.reader@example.com', 'full_name': 'Riley Reader', 'is_pro': False, 'is_beta': False, 'is_admin': False, 'email_verified': True}
USER_PRO = {**USER_FREE, 'id': 1002, 'email': 'alex.analyst@example.com', 'full_name': 'Alex Analyst', 'is_pro': True}
SUB_FREE = {'is_pro': False, 'stripe_customer_id': None, 'stripe_subscription_id': None, 'subscription_status': None, 'plan': 'free', 'status': None, 'trial_end': None, 'current_period_end': None, 'cancel_at_period_end': False}
SUB_PRO = {'is_pro': True, 'stripe_customer_id': 'cus_test', 'stripe_subscription_id': 'sub_test', 'subscription_status': 'active', 'plan': 'pro', 'status': 'active', 'trial_end': None, 'current_period_end': '2026-11-04T00:00:00+00:00', 'cancel_at_period_end': False}
def usage(sc):
    if 'pro' in sc:
        return {'summaries_used': 14, 'summaries_limit': None, 'is_pro': True, 'month': '2026-10', 'qa_used': 37, 'qa_limit': 300, 'copilot_free_taste_used': 0, 'copilot_free_taste_total': 0, 'analysis_used': 2, 'analysis_limit': 30}
    used = 3 if 'exhausted' in sc else 1
    return {'summaries_used': 2, 'summaries_limit': 3, 'is_pro': False, 'month': '2026-10', 'qa_used': used, 'qa_limit': 0, 'copilot_free_taste_used': used, 'copilot_free_taste_total': 3, 'analysis_used': 0, 'analysis_limit': 0}

SEC_URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'
def ask_completion(question):
    q = (question or '').lower()
    if 'dividend policy' in q or 'not disclosed' in q or 'headcount by country' in q:
        return {'type': 'complete', 'kind': 'not_disclosed', 'answer': 'The filing does not disclose this. The 10-K reports total employees but does not break headcount down by country or function.', 'citations': [], 'grounded': 0, 'followups': ['What does the filing say about supply concentration?', 'How did Services net sales change year over year?']}
    if 'risk' in q or 'tariff' in q:
        cits = [
            {'n': 1, 'excerpt': 'Tariffs and other measures that are applied to the Company’s products or their components can have a material adverse impact on the Company’s business, results of operations and financial condition, including impacting the Company’s supply chain, the availability of rare earths and other raw materials and components, pricing and gross margin.', 'section_ref': 'Item 1A. Risk Factors – Macroeconomic and Industry Risks', 'verified': True, 'fragment_url': SEC_URL + '#:~:text=Tariffs%20and%20other%20measures'},
            {'n': 2, 'excerpt': 'Substantially all of the Company’s hardware products are manufactured by outsourcing partners that are located primarily in China mainland, India, Japan, South Korea, Taiwan and Vietnam.', 'section_ref': 'Item 1A. Risk Factors – Business Risks', 'verified': True, 'fragment_url': SEC_URL + '#:~:text=Substantially%20all%20of%20the%20Company'},
        ]
        return {'type': 'complete', 'kind': 'answer', 'answer': 'The filing names tariffs and trade measures as a direct risk to supply chain, raw-material availability, pricing and gross margin [1]. That exposure is concentrated: substantially all hardware is manufactured by outsourcing partners in China mainland, India, Japan, South Korea, Taiwan and Vietnam [2].', 'citations': cits, 'grounded': 2, 'followups': ['How much gross unrecognized tax benefit does the filing report?', 'What does management say about gross margin pressure?', 'Which segment declined in 2025?']}
    cits = [
        {'n': 1, 'excerpt': 'As a result, the Company believes, in general, gross margins will be subject to volatility and downward pressure.', 'section_ref': 'Item 7. MD&A – Gross Margin', 'verified': True, 'fragment_url': SEC_URL + '#:~:text=As%20a%20result%2C%20the%20Company%20believes'},
        {'n': 2, 'excerpt': 'Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services.', 'section_ref': 'Item 7. MD&A – Products and Services Performance', 'verified': True, 'fragment_url': SEC_URL + '#:~:text=Services%20net%20sales%20increased'},
        {'n': 'F1', 'excerpt': 'RevenueFromContractWithCustomerExcludingAssessedTax = 416,161,000,000 USD (FY2025, 2024-09-29 to 2025-09-27)', 'section_ref': 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', 'verified': True, 'fragment_url': SEC_URL},
    ]
    return {'type': 'complete', 'kind': 'answer', 'answer': 'Total net sales were $416.2B in FY2025 [F1]. Growth came mainly from Services, which management attributes to advertising, the App Store and cloud services [2]. Management cautions that gross margins remain subject to volatility and downward pressure [1].', 'citations': cits, 'grounded': 3, 'followups': ['Which geographic segment declined in 2025?', 'What drove the lower effective tax rate?', 'How large is deferred revenue at year end?']}

DEMO = json.load(open(os.path.join(REPO, 'frontend', 'features', 'analysis', 'demo', 'demo-analysis.json')))

def analysis_coverage(ticker):
    ds = DEMO['dataset']
    return {'ticker': ticker.upper(), 'company_name': ds['company_name'] if ticker.upper() == 'AAPL' else ticker.upper(), 'supported': ticker.upper() in ('AAPL', 'MSFT'), 'reason': None if ticker.upper() in ('AAPL', 'MSFT') else 'no_facts', 'syncing': False, 'synced_at': '2026-10-03T06:00:00+00:00',
            'annual': [{'key': p['key'], 'fiscal_year': p['fiscal_year'], 'period_end': p['period_end'], 'has_core': True} for p in ds['periods']],
            'quarterly': [], 'limits': {'annual': 10, 'quarterly': 12}}

def analysis_dataset(ticker, body):
    ds = json.loads(json.dumps(DEMO['dataset']))
    keys = [p['key'] for p in ds['periods']]
    try:
        s, e = keys.index(body.get('start_period')), keys.index(body.get('end_period'))
    except ValueError:
        s, e = 0, len(keys) - 1
    keep = set(keys[s:e + 1])
    ds['periods'] = [p for p in ds['periods'] if p['key'] in keep]
    for ser in ds['series']:
        ser['points'] = [pt for pt in ser['points'] if pt['period'] in keep]
    ds['period_key'] = f"{keys[s]}..{keys[e]}"
    ds['ticker'] = ticker.upper()
    return ds

class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, fmt, *a): log(time.strftime('%H:%M:%S'), self.command, self.path, fmt % a)

    # --- helpers ---
    def scenario(self):
        sc = self.headers.get('X-EN-Scenario')
        if not sc:
            c = SimpleCookie(self.headers.get('Cookie', ''))
            sc = c['en_scenario'].value if 'en_scenario' in c else 'anon'
        return set(t.strip() for t in sc.split(',') if t.strip()) or {'anon'}
    def cors(self):
        origin = self.headers.get('Origin')
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Access-Control-Allow-Credentials', 'true')
            self.send_header('Vary', 'Origin')
    def send(self, status, body=b'', ctype='application/json', extra=None):
        if isinstance(body, (dict, list)): body = json.dumps(body).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(status); self.cors()
        self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)
    def sse(self, events, gap=0.6):
        self.send_response(200); self.cors()
        self.send_header('Content-Type', 'text/event-stream'); self.send_header('Cache-Control', 'no-cache')
        self.send_header('Transfer-Encoding', 'chunked'); self.end_headers()
        def chunk(s):
            b = s.encode(); self.wfile.write(f'{len(b):X}\r\n'.encode() + b + b'\r\n'); self.wfile.flush()
        try:
            for ev in events:
                chunk('data: ' + json.dumps(ev) + '\n\n'); time.sleep(gap)
            self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
    def body_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b''
        try: return json.loads(raw or b'{}')
        except Exception: return {}
    def passthrough(self, sc):
        if 'offline' in sc: return self.send(503, {'detail': 'Service Unavailable'})
        if 'slow' in sc and re.search(r'/api/(summaries|filings/\d+/content|companies/[A-Z]+$)', self.path): time.sleep(2.5)
        rec = upstream(self.path)
        self.send(rec['status'], rec['body'].encode(), rec.get('ctype') or 'application/json')

    def do_OPTIONS(self):
        self.send_response(204); self.cors()
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', self.headers.get('Access-Control-Request-Headers') or 'content-type')
        self.send_header('Access-Control-Max-Age', '600'); self.send_header('Content-Length', '0'); self.end_headers()

    def do_GET(self):
        sc = self.scenario(); p = self.path.split('?')[0]
        authed = 'free' in sc or 'pro' in sc; pro = 'pro' in sc
        unauth = lambda: self.send(401, {'detail': 'Could not validate credentials'})
        if p == '/health': return self.send(200, {'status': 'healthy', 'mock': True})
        if p == '/api/auth/me': return self.send(200, USER_PRO if pro else USER_FREE) if authed else unauth()
        if p == '/api/subscriptions/subscription': return self.send(200, SUB_PRO if pro else SUB_FREE) if authed else unauth()
        if p == '/api/subscriptions/usage': return self.send(200, usage(sc)) if authed else unauth()
        if p in ('/api/watchlist/', '/api/watchlist'):
            if not authed: return unauth()
            items = []
            tick = WATCH.get(','.join(sorted(sc)), set()) | ({'AAPL'} if 'watch' in sc else set())
            for i, t in enumerate(sorted(tick)): items.append({'id': 10 + i, 'company_id': 3, 'created_at': '2026-09-20T10:00:00+00:00', 'company': {'id': 3, 'ticker': t, 'name': 'Apple Inc.' if t == 'AAPL' else t}})
            return self.send(200, items)
        if p in ('/api/watchlist/insights', '/api/watchlist/earnings-alerts'): return self.send(200, []) if authed else unauth()
        if p == '/api/users/me/notifications': return self.send(200, {'items': [], 'unread_count': 0}) if authed else unauth()
        if p == '/api/users/me/notification-preferences': return self.send(200, {'notify_10k': True, 'notify_10q': True, 'notify_8k': False, 'notify_20f': True, 'notify_6k': False, 'channel': 'email', 'digest': 'weekly', 'realtime': False, 'realtime_available': pro, 'eightk_available': pro}) if authed else unauth()
        if p == '/api/dashboard/feed': return self.send(200, {'items': []}) if authed else unauth()
        if p == '/api/dashboard/calendar/upcoming': return self.send(200, {'events': []}) if authed else unauth()
        if p == '/api/saved-summaries/': return self.send(200, []) if authed else unauth()
        m = re.match(r'^/api/saved-summaries/status/(\d+)$', p)
        if m:
            if not authed: return unauth()
            return self.send(200, {'is_saved': 'saved' in sc or (','.join(sorted(sc)), m.group(1)) in SAVED})
        m = re.match(r'^/api/filings/(\d+)/content$', p)
        if m and 'content' in sc and m.group(1) == '3':  # the committed fixture is filing 3's; other ids pass through
            if 'slow' in sc: time.sleep(2.5)
            md = open(os.path.join(FIXTURES, 'filing-3-content.md')).read()
            return self.send(200, {'filing_id': int(m.group(1)), 'has_content': True, 'markdown_content': md})
        m = re.match(r'^/api/summaries/filing/(\d+)$', p)
        if m:
            if 'summaryerror' in sc: return self.send(500, {'detail': 'Internal Server Error'})
            if 'nosummary' in sc and (','.join(sorted(sc)), m.group(1)) not in GENERATED: return self.send(404, {'detail': 'Summary not found'})
            if 'partial' in sc:
                rec = upstream(self.path); d = json.loads(rec['body'])
                rs = d.setdefault('raw_summary', {}) or {}
                rs['quality'] = {'tier': 'partial', 'reasons': ['segments section not covered', 'financial figures not grounded in SEC XBRL data']}; rs['status'] = 'partial'; d['raw_summary'] = rs
                return self.send(200, d)
            return self.passthrough(sc)
        m = re.match(r'^/api/summaries/filing/(\d+)/progress$', p)
        if m: return self.send(200, {'stage': 'analyzing', 'elapsedSeconds': 14})
        m = re.match(r'^/api/summaries/filing/(\d+)/export/(pdf|csv)$', p)
        if m:
            if not authed: return unauth()
            if not pro: return self.send(403, {'detail': 'Exports are a Pro feature. Upgrade to Pro to download summaries.'})
            return self.send(200, b'%PDF-1.4 mock\n' if m.group(2) == 'pdf' else b'metric,current,prior\n', 'application/pdf' if m.group(2) == 'pdf' else 'text/csv')
        m = re.match(r'^/api/analysis/([A-Za-z.\-]+)/coverage$', p)
        if m: return self.send(200, analysis_coverage(m.group(1))) if authed else unauth()
        m = re.match(r'^/api/analysis/export/(\d+)/pdf$', p)
        if m: return self.send(200, b'%PDF-1.4 mock\n', 'application/pdf') if pro else (unauth() if not authed else self.send(403, {'detail': 'Multi-Period Analysis is a Pro feature.'}))
        if p.startswith('/api/admin'): return unauth()
        return self.passthrough(sc)

    def do_POST(self):
        sc = self.scenario(); p = self.path.split('?')[0]
        authed = 'free' in sc or 'pro' in sc; pro = 'pro' in sc
        unauth = lambda: self.send(401, {'detail': 'Could not validate credentials'})
        body = self.body_json()
        m = re.match(r'^/api/summaries/filing/(\d+)/generate-stream$', p)
        if m:
            if not authed: return unauth()
            fid = m.group(1)
            if 'genfail' in sc:
                return self.sse([{'type': 'start', 'message': 'Starting analysis'}, {'type': 'progress', 'stage': 'fetching', 'message': 'Fetching filing from SEC EDGAR', 'percent': 10, 'elapsed_seconds': 1}, {'type': 'progress', 'stage': 'parsing', 'message': 'Parsing filing sections', 'percent': 30, 'elapsed_seconds': 3}, {'type': 'error', 'message': 'The AI provider timed out while analyzing this filing. Please try again.'}], gap=0.9)
            rec = upstream(f'/api/summaries/filing/{fid}'); d = json.loads(rec['body'])
            preview = (d.get('business_overview') or '')[:900]
            evs = [{'type': 'start', 'message': 'Starting analysis'},
                   {'type': 'progress', 'stage': 'fetching', 'message': 'Fetching filing from SEC EDGAR', 'percent': 10, 'elapsed_seconds': 2},
                   {'type': 'progress', 'stage': 'parsing', 'message': 'Parsing filing sections and XBRL facts', 'percent': 30, 'elapsed_seconds': 5},
                   {'type': 'progress', 'stage': 'analyzing', 'message': 'Analyzing financial statements', 'percent': 55, 'elapsed_seconds': 9, 'heartbeat_count': 2},
                   {'type': 'preview', 'markdown': preview},
                   {'type': 'progress', 'stage': 'summarizing', 'message': 'Writing the summary', 'percent': 80, 'elapsed_seconds': 14},
                   {'type': 'chunk', 'content': d.get('business_overview') or ''},
                   {'type': 'complete', 'summary_id': d.get('id', 58), 'message': 'summary ready'}]
            with LOCK: GENERATED.add((','.join(sorted(sc)), fid))
            return self.sse(evs, gap=1.1)
        m = re.match(r'^/api/summaries/filing/(\d+)/ask-stream$', p)
        if m:
            if not authed: return unauth()
            if 'askfail' in sc: return self.send(500, {'detail': 'Internal Server Error'})
            if not pro and usage(sc)['copilot_free_taste_used'] >= usage(sc)['copilot_free_taste_total']:
                return self.send(403, {'detail': 'You have used your free Copilot questions. Upgrade to Pro for unlimited questions.'})
            comp = ask_completion(body.get('question'))
            return self.sse([{'type': 'progress', 'stage': 'reading'}, {'type': 'activity', 'label': 'Searching filing sections'}, {'type': 'progress', 'stage': 'reading'}, comp], gap=0.8)
        if p == '/api/saved-summaries/':
            if not authed: return unauth()
            with LOCK: SAVED.add((','.join(sorted(sc)), str(body.get('summary_id'))))
            return self.send(201, {'id': 501, 'summary_id': body.get('summary_id'), 'notes': None, 'created_at': '2026-10-04T16:00:00+00:00', 'summary': {'id': body.get('summary_id'), 'filing_id': 3}, 'filing': {'id': 3, 'filing_type': '10-K', 'filing_date': '2025-10-31T00:00:00+00:00', 'period_end_date': '2025-09-27'}, 'company': {'id': 3, 'ticker': 'AAPL', 'name': 'Apple Inc.'}})
        m = re.match(r'^/api/watchlist/([A-Za-z.\-]+)$', p)
        if m:
            if not authed: return unauth()
            with LOCK: WATCH.setdefault(','.join(sorted(sc)), set()).add(m.group(1).upper())
            return self.send(201, {'id': 11, 'company_id': 3, 'created_at': '2026-10-04T16:00:00+00:00', 'company': {'id': 3, 'ticker': m.group(1).upper(), 'name': 'Apple Inc.'}})
        m = re.match(r'^/api/analysis/([A-Za-z.\-]+)/dataset$', p)
        if m:
            if not authed: return unauth()
            if not pro: return self.send(403, {'detail': 'Multi-Period Analysis is a Pro feature. Upgrade to Pro to compare up to 10 fiscal years.'})
            if 'slow' in sc: time.sleep(2.5)
            return self.send(200, analysis_dataset(m.group(1), body))
        m = re.match(r'^/api/analysis/([A-Za-z.\-]+)/stream$', p)
        if m:
            if not authed: return unauth()
            if not pro: return self.send(403, {'detail': 'Multi-Period Analysis is a Pro feature. Upgrade to Pro to compare up to 10 fiscal years.'})
            comp = json.loads(json.dumps(DEMO['completion'])); narrative = comp.get('narrative', '')
            words = narrative.split(' '); toks = [' '.join(words[i:i + 12]) + ' ' for i in range(0, len(words), 12)]
            evs = [{'type': 'progress', 'stage': 'reading'}] + [{'type': 'token', 'text': t} for t in toks] + [{'type': 'complete', **comp, 'analysis_id': 777, 'cached': False, 'n_periods': len(analysis_dataset(m.group(1), body)['periods'])}]
            return self.sse(evs, gap=0.12)
        m = re.match(r'^/api/analysis/([A-Za-z.\-]+)/export/xlsx$', p)
        if m: return self.send(200, b'PK mock', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') if pro else (unauth() if not authed else self.send(403, {'detail': 'Multi-Period Analysis is a Pro feature.'}))
        if p == '/api/users/me/notifications/seen': return self.send(200, {'items': [], 'unread_count': 0}) if authed else unauth()
        if p in ('/api/feedback/', '/api/contact/'): return self.send(201, {'ok': True})
        if p == '/api/auth/logout': return self.send(200, {'ok': True})
        if p == '/api/auth/refresh': return unauth()
        return self.send(404, {'detail': 'Not Found (mock: no POST passthrough)'})

    def do_DELETE(self):
        sc = self.scenario(); p = self.path.split('?')[0]
        if not ('free' in sc or 'pro' in sc): return self.send(401, {'detail': 'Could not validate credentials'})
        m = re.match(r'^/api/watchlist/([A-Za-z.\-]+)$', p)
        if m:
            with LOCK: WATCH.setdefault(','.join(sorted(sc)), set()).discard(m.group(1).upper())
            return self.send(204, b'')
        return self.send(204, b'')
    def do_PUT(self): self.send(200, self.body_json())
    def do_PATCH(self): self.send(200, self.body_json())

if __name__ == '__main__':
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    srv.daemon_threads = True
    print(f'mock api on http://localhost:{PORT} (pid {os.getpid()})', flush=True)
    srv.serve_forever()
