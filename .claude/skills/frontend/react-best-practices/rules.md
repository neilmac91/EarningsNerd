# React Best Practices - Complete Rules Reference

57 performance optimization rules for React and Next.js, organized by impact level.

---

## 1. Eliminating Waterfalls (CRITICAL)

**Impact: 2-10× improvement by eliminating sequential async operations**

### 1.1 Defer await until needed

```typescript
// ❌ Incorrect - blocks immediately
async function getData() {
  const data = await fetchData();
  const processed = transform(data);
  return processed;
}

// ✅ Correct - defer await
async function getData() {
  const dataPromise = fetchData();
  // Do other work here
  const data = await dataPromise;
  return transform(data);
}
```

### 1.2 Parallelize independent operations

```typescript
// ❌ Incorrect - sequential
const user = await getUser(id);
const posts = await getPosts(id);
const comments = await getComments(id);

// ✅ Correct - parallel
const [user, posts, comments] = await Promise.all([
  getUser(id),
  getPosts(id),
  getComments(id),
]);
```

### 1.3 Strategic Suspense boundaries

```typescript
// ❌ Incorrect - one boundary blocks everything
<Suspense fallback={<Loading />}>
  <SlowComponent />
  <FastComponent />
</Suspense>

// ✅ Correct - independent boundaries
<Suspense fallback={<Loading />}>
  <SlowComponent />
</Suspense>
<Suspense fallback={<Loading />}>
  <FastComponent />
</Suspense>
```

### 1.4 Prevent waterfall chains in API routes

```typescript
// ❌ Incorrect - waterfall in route handler
export async function GET(request: Request) {
  const user = await db.user.findUnique({ where: { id } });
  const orders = await db.order.findMany({ where: { userId: id } });
  return Response.json({ user, orders });
}

// ✅ Correct - parallel fetching
export async function GET(request: Request) {
  const [user, orders] = await Promise.all([
    db.user.findUnique({ where: { id } }),
    db.order.findMany({ where: { userId: id } }),
  ]);
  return Response.json({ user, orders });
}
```

---

## 2. Bundle Size Optimization (CRITICAL)

**Impact: Improves Time to Interactive and Largest Contentful Paint**

### 2.1 Avoid barrel file imports

```typescript
// ❌ Incorrect - imports entire barrel (200-800ms cost)
import { Button } from '@/components';
import { formatDate } from '@/utils';

// ✅ Correct - direct imports (15-70% faster builds)
import { Button } from '@/components/ui/Button';
import { formatDate } from '@/utils/date';
```

### 2.2 Dynamic imports for heavy components

```typescript
// ❌ Incorrect - always loaded
import { HeavyChart } from './HeavyChart';

// ✅ Correct - loaded on demand
const HeavyChart = dynamic(() => import('./HeavyChart'), {
  loading: () => <ChartSkeleton />,
});
```

### 2.3 Conditional module loading

```typescript
// ❌ Incorrect - always bundled
import { analytics } from 'heavy-analytics-lib';

// ✅ Correct - conditional loading
const analytics = process.env.NODE_ENV === 'production'
  ? await import('heavy-analytics-lib')
  : { track: () => {} };
```

### 2.4 Preload based on user intent

```typescript
// Preload on hover/focus
<Link
  href="/dashboard"
  onMouseEnter={() => router.prefetch('/dashboard')}
>
  Dashboard
</Link>
```

---

## 3. Server-Side Performance (HIGH)

**Impact: Eliminates server-side waterfalls and reduces response times**

### 3.1 Per-request deduplication with React.cache()

```typescript
// ❌ Incorrect - fetches multiple times per request
async function getUser(id: string) {
  return db.user.findUnique({ where: { id } });
}

// ✅ Correct - deduplicated within request
const getUser = cache(async (id: string) => {
  return db.user.findUnique({ where: { id } });
});
```

### 3.2 Cross-request LRU caching

```typescript
import { LRUCache } from 'lru-cache';

const cache = new LRUCache<string, User>({
  max: 500,
  ttl: 1000 * 60 * 5, // 5 minutes
});

async function getUser(id: string) {
  const cached = cache.get(id);
  if (cached) return cached;

  const user = await db.user.findUnique({ where: { id } });
  cache.set(id, user);
  return user;
}
```

### 3.3 Minimize serialization at RSC boundaries

```typescript
// ❌ Incorrect - passes entire object
async function Page() {
  const data = await fetchLargeDataset();
  return <ClientComponent data={data} />;
}

// ✅ Correct - pass only needed data
async function Page() {
  const data = await fetchLargeDataset();
  return <ClientComponent summary={data.summary} count={data.items.length} />;
}
```

### 3.4 Use after() for non-blocking operations

```typescript
import { after } from 'next/server';

export async function POST(request: Request) {
  const data = await request.json();
  const result = await processData(data);

  // Non-blocking analytics after response
  after(async () => {
    await analytics.track('data_processed', { id: result.id });
  });

  return Response.json(result);
}
```

### 3.5 Authenticate Server Actions like API routes

```typescript
'use server';

export async function updateProfile(data: FormData) {
  const session = await getSession();
  if (!session) {
    throw new Error('Unauthorized');
  }

  // Proceed with authenticated action
}
```

---

## 4. Client-Side Data Fetching (MEDIUM-HIGH)

**Impact: Reduces redundant network requests**

### 4.1 SWR for automatic deduplication

```typescript
// ❌ Incorrect - manual fetching
const [data, setData] = useState(null);
useEffect(() => {
  fetch('/api/data').then(r => r.json()).then(setData);
}, []);

// ✅ Correct - SWR handles deduplication
const { data } = useSWR('/api/data', fetcher);
```

### 4.2 Passive event listeners for scrolling

```typescript
// ❌ Incorrect - blocks scrolling
element.addEventListener('scroll', handler);

// ✅ Correct - passive listener
element.addEventListener('scroll', handler, { passive: true });
```

### 4.3 Deduplicate global event listeners

```typescript
// ❌ Incorrect - listener per component instance
useEffect(() => {
  window.addEventListener('resize', handleResize);
  return () => window.removeEventListener('resize', handleResize);
}, []);

// ✅ Correct - shared subscription
const size = useSyncExternalStore(
  subscribeToResize,
  getWindowSize,
  getServerSize
);
```

---

## 5. Re-render Optimization (MEDIUM)

**Impact: Reduces unnecessary re-renders and wasted computation**

### 5.1 Calculate derived state during rendering

```typescript
// ❌ Incorrect - effect for derived state
const [items, setItems] = useState([]);
const [total, setTotal] = useState(0);
useEffect(() => {
  setTotal(items.reduce((sum, i) => sum + i.price, 0));
}, [items]);

// ✅ Correct - calculate during render
const [items, setItems] = useState([]);
const total = items.reduce((sum, i) => sum + i.price, 0);
```

### 5.2 Use functional setState updates

```typescript
// ❌ Incorrect - stale closure risk
const increment = () => setCount(count + 1);

// ✅ Correct - functional update
const increment = () => setCount(c => c + 1);
```

### 5.3 Use lazy state initialization

```typescript
// ❌ Incorrect - runs every render
const [data] = useState(expensiveComputation());

// ✅ Correct - runs once
const [data] = useState(() => expensiveComputation());
```

### 5.4 Extract to memoized components

```typescript
// ❌ Incorrect - re-renders with parent
function Parent() {
  const [count, setCount] = useState(0);
  return (
    <div>
      <button onClick={() => setCount(c => c + 1)}>{count}</button>
      <ExpensiveList items={items} />
    </div>
  );
}

// ✅ Correct - memoized child
const MemoizedList = memo(ExpensiveList);
function Parent() {
  const [count, setCount] = useState(0);
  return (
    <div>
      <button onClick={() => setCount(c => c + 1)}>{count}</button>
      <MemoizedList items={items} />
    </div>
  );
}
```

### 5.5 Narrow effect dependencies

```typescript
// ❌ Incorrect - runs on any user change
useEffect(() => {
  document.title = user.name;
}, [user]);

// ✅ Correct - only when name changes
useEffect(() => {
  document.title = user.name;
}, [user.name]);
```

### 5.6 Use transitions for non-urgent updates

```typescript
const [isPending, startTransition] = useTransition();

function handleSearch(query: string) {
  // Urgent: update input
  setQuery(query);

  // Non-urgent: update results
  startTransition(() => {
    setResults(filterResults(query));
  });
}
```

### 5.7 Use useRef for transient values

```typescript
// ❌ Incorrect - causes re-render
const [intervalId, setIntervalId] = useState(null);

// ✅ Correct - no re-render
const intervalIdRef = useRef(null);
```

---

## 6. Rendering Performance (MEDIUM)

**Impact: Reduces browser rendering workload**

### 6.1 CSS content-visibility for long lists

```css
/* 10× faster initial render for 1000+ items */
.list-item {
  content-visibility: auto;
  contain-intrinsic-size: 0 50px;
}
```

### 6.2 Hoist static JSX elements

```typescript
// ❌ Incorrect - recreated each render
function Component() {
  const header = <header>Static Header</header>;
  return <div>{header}</div>;
}

// ✅ Correct - hoisted outside
const header = <header>Static Header</header>;
function Component() {
  return <div>{header}</div>;
}
```

### 6.3 Use explicit conditional rendering

```typescript
// ❌ Incorrect - always evaluates
{condition && <Component />}

// ✅ Correct - explicit
{condition ? <Component /> : null}
```

### 6.4 Optimize SVG precision

```xml
<!-- ❌ Incorrect - excessive precision -->
<path d="M10.123456789 20.987654321..." />

<!-- ✅ Correct - 1 decimal place (use SVGO) -->
<path d="M10.1 21..." />
```

---

## 7. JavaScript Performance (LOW-MEDIUM)

**Impact: Micro-optimizations for hot code paths**

### 7.1 Use Set/Map for O(1) lookups

```typescript
// ❌ Incorrect - O(n) lookup
const isSelected = selectedIds.includes(id);

// ✅ Correct - O(1) lookup
const selectedSet = new Set(selectedIds);
const isSelected = selectedSet.has(id);
```

### 7.2 Build index maps for repeated lookups

```typescript
// ❌ Incorrect - O(n) per lookup = O(n²) total
items.forEach(item => {
  const user = users.find(u => u.id === item.userId);
});

// ✅ Correct - O(1) per lookup = O(n) total
const userMap = new Map(users.map(u => [u.id, u]));
items.forEach(item => {
  const user = userMap.get(item.userId);
});
```

### 7.3 Early return from functions

```typescript
// ❌ Incorrect - always runs full function
function process(data) {
  let result = null;
  if (data) {
    result = expensiveOperation(data);
  }
  return result;
}

// ✅ Correct - early return
function process(data) {
  if (!data) return null;
  return expensiveOperation(data);
}
```

### 7.4 Cache property access in loops

```typescript
// ❌ Incorrect - property access each iteration
for (let i = 0; i < array.length; i++) { }

// ✅ Correct - cached length
for (let i = 0, len = array.length; i < len; i++) { }
```

### 7.5 Use toSorted() for immutability

```typescript
// ❌ Incorrect - mutates original
const sorted = items.sort((a, b) => a.id - b.id);

// ✅ Correct - immutable
const sorted = items.toSorted((a, b) => a.id - b.id);
```

---

## 8. Advanced Patterns (LOW)

**Impact: Prevents duplicate initialization and stale closures**

### 8.1 Initialize app once, not per mount

```typescript
// ❌ Incorrect - initializes on every mount
useEffect(() => {
  initializeAnalytics();
}, []);

// ✅ Correct - module-level initialization
let initialized = false;
function useAnalytics() {
  if (!initialized) {
    initializeAnalytics();
    initialized = true;
  }
}
```

### 8.2 Store event handlers in refs

```typescript
// ❌ Incorrect - stale closure
const handleClick = useCallback(() => {
  console.log(count);
}, [count]);

// ✅ Correct - always fresh
const countRef = useRef(count);
countRef.current = count;
const handleClick = useCallback(() => {
  console.log(countRef.current);
}, []);
```

---

## Summary Statistics

| Optimization | Impact |
|-------------|--------|
| Barrel imports | 200-800ms per import, 15-70% faster builds with direct imports |
| SVG precision | Significant file size reduction with SVGO |
| content-visibility | 10× faster initial render for 1000-item lists |
| Map vs Array lookup | 1M operations → 2K operations |
| Functional setState | Prevents stale closure bugs |

---

*Source: Vercel Engineering, January 2026*
