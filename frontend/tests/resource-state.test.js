const test = require('node:test');
const assert = require('node:assert/strict');
const { TTLCache, LatestRequestRegistry, buildQuery, loadingState, listState, errorState } = require('../resource-state.js');

test('resource states cover loading, success, empty and error', () => {
  assert.equal(loadingState().status, 'loading');
  assert.equal(listState({data: [], meta: {pagination: {page:1}}}).status, 'empty');
  assert.equal(listState({data: [{id:1}]}).status, 'success');
  assert.equal(errorState(new Error('500')).status, 'error');
});

test('TTL cache expires and invalidates by prefix', () => {
  let now = 100;
  const cache = new TTLCache(() => now);
  cache.set('/api/reports', {data:[1]}, 50);
  assert.deepEqual(cache.get('/api/reports'), {data:[1]});
  now = 151;
  assert.equal(cache.get('/api/reports'), undefined);
  cache.set('/api/a', 1, 50); cache.set('/other', 2, 50);
  cache.invalidate('/api/');
  assert.equal(cache.get('/api/a'), undefined);
  assert.equal(cache.get('/other'), 2);
});

test('query generation is stable and excludes empty values', () => {
  assert.equal(buildQuery({search:'sale', page:2, status:''}), '?page=2&search=sale');
});

test('new request aborts and rejects the stale request', async () => {
  const registry = new LatestRequestRegistry();
  const first = registry.run('reports', signal => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('aborted','AbortError')));
    setTimeout(() => resolve('old'), 30);
  }));
  const second = registry.run('reports', async () => 'new');
  await assert.rejects(first, error => error.code === 'STALE_REQUEST');
  assert.equal(await second, 'new');
});
