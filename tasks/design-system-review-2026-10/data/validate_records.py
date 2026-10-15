from pathlib import Path
from urllib.parse import unquote
from functools import lru_cache
import re,json,gzip,subprocess
r=Path(__file__).resolve().parents[3];o=r/'tasks/design-system-review-2026-10';archive=r/'.impeccable/critique/2026-10-15T10-26-25Z__frontend-components-ui-index-ts.md'
files=list(o.rglob('*'))+[archive];md=[p for p in files if p.suffix=='.md'];errors=[];links=0;refs=0
sha='1f12fc835fcbf525042473ab0e988b4827734f38'
@lru_cache(maxsize=None)
def source_text(revision, path):
 try:
  return subprocess.check_output(['git','show',f'{revision}:{path}'],cwd=r,text=True,stderr=subprocess.DEVNULL)
 except subprocess.CalledProcessError:
  return None

def anchors(p):
 seen={};out=set()
 for line in p.read_text().splitlines():
  if not re.match(r'^#{1,6} ',line):continue
  h=re.sub(r'^#+ ','',line).strip().lower();h=re.sub(r'<[^>]+>','',h);h=re.sub(r'[^\w\- ]','',h,flags=re.UNICODE).replace(' ','-');n=seen.get(h,0);seen[h]=n+1;out.add(h+('-'+str(n) if n else ''))
 return out
for p in md:
 t=p.read_text()
 if '—' in t:errors.append(f'em dash: {p}')
 for m in re.finditer(r'\[[^\n]*?\]\(([^\n]*?)\)',t):
  target=m[1].strip('<>');links+=1
  if target.startswith('https://github.com/neilmac91/EarningsNerd/blob/'):
   x=target.split('/blob/',1)[1];h,path=x.split('/',1);path,_,frag=path.partition('#');path=unquote(path)
   if h!=sha:errors.append(f'unexpected source SHA {target}')
   frozen=source_text(h,path)
   if frozen is None:errors.append(f'missing source in pinned tree {target}');continue
   if frag.startswith('L'):
    line=int(frag[1:]);refs+=1
    if not 1<=line<=len(frozen.splitlines()):errors.append(f'bad source line {target}')
   continue
  if re.match(r'^[a-z]+:',target):continue
  path,_,frag=target.partition('#');q=(p.parent/unquote(path)).resolve() if path else p
  if not q.exists():errors.append(f'missing link in {p.name}: {target}');continue
  if frag and q.suffix=='.md' and frag not in anchors(q):errors.append(f'missing anchor in {p.name}: {target}')
 # Literal source citations use the review baseline. New record paths use this checkout.
 # Do not validate immutable URL text again against the mutable worktree.
 literal=re.sub(r'\[[^\n]*?\]\([^\n]*?\)', '', t)
 for m in re.finditer(r'(?<![\w/])((?:frontend|backend|docs|tasks|lessons)/[\w./%\[\]-]+\.(?:tsx?|css|json|mjs|js|md|py))(?::(\d+))?',literal):
  path=unquote(m[1]);q=r/path
  content=q.read_text() if path.startswith('tasks/design-system-review-2026-10/') and q.is_file() else source_text(sha,path)
  if content is None:errors.append(f'missing mentioned path {p.name}: {path}');continue
  if m[2] and int(m[2])>len(content.splitlines()):errors.append(f'bad mentioned line {p.name}: {m[0]}')
js=0
for p in files:
 if p.suffix=='.json':json.loads(p.read_text());js+=1
 if p.name.endswith('.json.gz'):
  with gzip.open(p,'rt') as f:json.load(f)
  js+=1
imgs=list((o/'evidence').glob('*'));b=sum(p.stat().st_size for p in imgs)
if b>=2000000:errors.append(f'image budget {b}')
index=json.load(open(o/'data/evidence-index.json'))
for x in index:
 if not (o/x['evidence']).is_file():errors.append('index missing '+x['evidence'])
scopes=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=r,text=True).splitlines()
for l in scopes:
 path=l[3:]
 if not (path.startswith('tasks/design-system-review-2026-10/') or path==str(archive.relative_to(r))):errors.append('scope '+path)
report=(o/'REPORT.md').read_text()
score_sums={}
for heading,next_heading,total in [('### Sameness','### Craft',12),('### Craft','### Impeccable health',20)]:
 section=report.split(heading,1)[1].split(next_heading,1)[0]
 rows=[l for l in section.splitlines() if re.match(r'\| [TC]\d+',l)]
 values=[int(l.split('|')[4 if heading=='### Sameness' else 2].strip()) for l in rows]
 score_sums[heading]=sum(values)
 if sum(values)!=total:errors.append('score total '+heading)
plans={}
for h,n,expected in [('## Distill plan','## Polish plan',6),('## Polish plan','## Clarify plan',9),('## Clarify plan','## Founder decisions',1)]:
 section=report.split(h,1)[1].split(n,1)[0];rows=re.findall(r'^\d+\. \*\*(.+?)\*\*',section,re.M)
 plans[h]={'items':len(rows),'S':sum(', S, routine' in x for x in rows),'M':sum(', M, routine' in x for x in rows)}
 if len(rows)!=expected:errors.append('plan count '+h)
result={'score_sums':score_sums,'plans':plans,'markdown_files' :len(md),'links_checked':links,'immutable_source_line_links':refs,'json_archives_parsed':js,'jpeg_files':len(imgs),'jpeg_bytes':b,'errors':sorted(set(errors))}
print(json.dumps(result,indent=2))
raise SystemExit(bool(errors))
