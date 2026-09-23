#!/usr/bin/env python3
"""Sync the Tracker EXP.xlsx 'Pipeline' sheet into the experiment-hq Firestore.

Usage: python3 sync_pipeline.py /path/to/tracker.xlsx
The sheet owns: name, client, deadline (SUBMISSION date), owner, status, notes.
The app owns: steps (action plans) — never written by this script.
Rows marked Cancelled / "did not participate" are deleted from the board.
Doc ids are pl<row-index>, matching the original import.
"""
import sys, json, re, zipfile, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

PROJECT = "experiment-hq"
API_KEY = "AIzaSyBLp3PGnhy6CFPWQE_R8CvlUXiZzsasAPY"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MON = {m.lower()[:3]: i+1 for i, m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}
OWN = {'maissa':'maissa','maisa':'maissa','meera':'meera','zameel':'zameel','dhafir':'dhafer','dhafer':'dhafer','suzan':'suzan','suzane':'suzan','hamza':'hamza','hmza':'hamza','mehdiah':'mehdiah','hossam':'hossam','kayan':'kayan','ram':'ram','anas':'anas'}
SYNC_FIELDS = ['name','client','deadline','owner','status','notes','source','updatedAt']

def parse_sheet(path):
    z = zipfile.ZipFile(path)
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rmap = {r.attrib['Id']: r.attrib['Target'] for r in rels}
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    target = None
    for sh in wb.find('m:sheets', NS):
        if sh.attrib['name'] == 'Pipeline':
            rid = sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = 'xl/' + rmap[rid].lstrip('/')
    ss = []
    try:
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            ss.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
    except KeyError:
        pass
    sheet = ET.fromstring(z.read(target))
    def colidx(ref):
        n = 0
        for ch in re.match(r'([A-Z]+)', ref).group(1):
            n = n*26 + ord(ch) - 64
        return n - 1
    rows = []
    for row in sheet.iter('{%s}row' % NS['m']):
        cells = {}
        for c in row:
            ref = c.attrib.get('r',''); t = c.attrib.get('t'); v = c.find('m:v', NS)
            if t == 'inlineStr':
                isel = c.find('m:is', NS)
                val = ''.join(x.text or '' for x in isel.iter('{%s}t' % NS['m'])) if isel is not None else ''
            elif v is None: val = ''
            elif t == 's': val = ss[int(v.text)]
            else: val = v.text
            cells[colidx(ref)] = str(val).strip()
        rows.append(cells)
    return rows

def serial(v):
    try: f = float(v)
    except Exception: return None
    if 40000 < f < 50000:
        return (datetime.date(1899,12,30) + datetime.timedelta(days=int(f))).isoformat()
    return None

def parse_date(s0):
    s0 = s0.strip()
    if not s0: return '', ''
    d = serial(s0)
    if d: return d, ''
    t = s0.lower().replace('@',' ').replace('.',' ')
    m = re.search(r'(\d{1,2})(?:st|nd|rd|th)?[\s\-/]+([a-z]{3,9})[\s\-/]*(\d{4})?', t)
    if m and m.group(2)[:3] in MON:
        y = int(m.group(3)) if m.group(3) else datetime.date.today().year
        if y < 2000: y = datetime.date.today().year
        try: return datetime.date(y, MON[m.group(2)[:3]], int(m.group(1))).isoformat(), ''
        except ValueError: pass
    m = re.search(r'([a-z]{3,9})[\s\-/]+(\d{1,2})', t)
    if m and m.group(1)[:3] in MON:
        try: return datetime.date(datetime.date.today().year, MON[m.group(1)[:3]], int(m.group(2))).isoformat(), ''
        except ValueError: pass
    m = re.match(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', t)
    if m:
        try: return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat(), ''
        except ValueError: pass
    m = re.match(r'(\d{1,2})[/\-](\d{1,2})$', t.split()[0]) if t.split() else None
    if m:
        try: return datetime.date(datetime.date.today().year, int(m.group(2)), int(m.group(1))).isoformat(), ''
        except ValueError: pass
    return '', s0

def owner_of(mgr):
    for tok in re.split(r'[&,/\s]+', mgr.lower()):
        if tok in OWN: return OWN[tok]
    return ''

def status_of(s):
    sl = s.lower().strip()
    if not sl: return 'planning', False
    if 'cancel' in sl or 'did not' in sl: return None, True
    if 'done' in sl or 'submission' in sl or 'submitted' in sl or 'complete' in sl: return 'done', False
    if 'off-track' in sl or 'off track' in sl or 'on hold' in sl or 'onhold' in sl: return 'on-hold', False
    if 'on-track' in sl or 'on track' in sl or 'review' in sl or 'quote' in sl: return 'active', False
    return 'planning', False

def build_docs(rows):
    keep, dead = {}, set()
    for i, r in enumerate(rows[1:], start=1):
        vals = [r.get(k, '') for k in range(15)]
        client, event, dl_raw, ptime, designer, mgr, status, platform, lang, link, budget, ptl, eventdate, designs, checklist = vals
        if not client and not event: continue
        st, skip = status_of(status)
        doc_id = 'pl%03d' % (i - 1)
        if skip:
            dead.add(doc_id); continue
        dl, raw = parse_date(dl_raw)
        o = owner_of(mgr)
        notes = []
        if status: notes.append('Pipeline status: ' + status)
        if platform: notes.append('Via: ' + platform)
        if mgr and not o: notes.append('Manager: ' + mgr)
        elif mgr and ('&' in mgr or '/' in mgr): notes.append('Managers: ' + mgr)
        if designer and designer != '-': notes.append('3D: ' + designer)
        if budget and budget not in ('0', 'TBD'): notes.append('Budget: ' + budget)
        if eventdate: notes.append('Event date: ' + eventdate)
        if raw: notes.append('Pitch deadline: ' + raw)
        if lang: notes.append('Language: ' + lang)
        keep[doc_id] = {
            'name': (event or client)[:80], 'client': client[:60], 'deadline': dl,
            'owner': o, 'status': st, 'notes': ' · '.join(notes)[:1500],
            'source': 'Tracker EXP.xlsx / Pipeline',
        }
    return keep, dead

def req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read() or '{}')

def existing_docs():
    docs, token = {}, None
    while True:
        url = f"{BASE}/projects?pageSize=300&key={API_KEY}" + (f"&pageToken={token}" if token else "")
        d = req('GET', url)
        for doc in d.get('documents', []):
            did = doc['name'].rsplit('/', 1)[1]
            flat = {k: v.get('stringValue', '') for k, v in doc.get('fields', {}).items() if 'stringValue' in v}
            docs[did] = flat
        token = d.get('nextPageToken')
        if not token: return docs

def main(path):
    rows = parse_sheet(path)
    keep, dead = build_docs(rows)
    existing = existing_docs()
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    created = updated = deleted = unchanged = 0
    for did, doc in keep.items():
        old = existing.get(did)
        if old and all(old.get(f, '') == doc[f] for f in ['name','client','deadline','owner','status','notes']):
            unchanged += 1; continue
        doc2 = dict(doc); doc2['updatedAt'] = now
        if not old: doc2['id'] = did; doc2['createdAt'] = now
        mask = '&'.join('updateMask.fieldPaths=' + f for f in (SYNC_FIELDS + (['id','createdAt'] if not old else [])))
        body = {'fields': {k: {'stringValue': v} for k, v in doc2.items()}}
        req('PATCH', f"{BASE}/projects/{did}?key={API_KEY}&{mask}", body)
        if old: updated += 1
        else: created += 1
    for did in list(existing):
        if did.startswith('pl') and (did in dead or did not in keep):
            req('DELETE', f"{BASE}/projects/{did}?key={API_KEY}")
            deleted += 1
    print(f"SYNC OK: {created} created, {updated} updated, {deleted} deleted, {unchanged} unchanged, {len(keep)} live rows")

if __name__ == '__main__':
    main(sys.argv[1])
