const test = require('node:test');
const assert = require('node:assert/strict');
global.NexusResource = require('../resource-state.js');
const { ApiClient, NexusApiError, assertListEnvelope } = require('../api-client.js');

function response(status, payload, contentType = 'application/json') {
  return { ok: status >= 200 && status < 300, status, headers: {get: () => contentType}, json: async () => payload };
}

test('typed list response validates pagination contract', () => {
  const valid = {success:true,data:[],meta:{pagination:{page:1,page_size:10,total:0,total_pages:0}}};
  assert.equal(assertListEnvelope(valid), valid);
  assert.throws(() => assertListEnvelope({success:true,data:{}}), NexusApiError);
  assert.throws(() => assertListEnvelope({success:true,data:[],meta:{pagination:{page:'1'}}}), NexusApiError);
});

test('GET uses TTL cache and force bypasses it', async () => {
  let calls = 0;
  const client = new ApiClient({fetch: async () => { calls += 1; return response(200,{success:true,data:{value:calls}}); }});
  assert.equal((await client.get('/api/profile')).data.value, 1);
  assert.equal((await client.get('/api/profile')).data.value, 1);
  assert.equal((await client.get('/api/profile',{force:true})).data.value, 2);
  assert.equal(calls, 2);
});

for (const status of [400,401,403,404,409,500]) {
  test(`API ${status} is exposed as a typed frontend error`, async () => {
    const client = new ApiClient({fetch: async () => response(status,{success:false,error:{code:`E_${status}`,message:`status ${status}`}})});
    await assert.rejects(client.get('/api/auth/login'), error => error instanceof NexusApiError && error.status === status && error.code === `E_${status}`);
  });
}

test('network failure becomes NETWORK_ERROR and AbortError remains cancellable', async () => {
  const offline = new ApiClient({fetch: async () => { throw new Error('offline'); }});
  await assert.rejects(offline.get('/api/auth/login'), error => error.code === 'NETWORK_ERROR');
  const aborted = new ApiClient({fetch: async () => { throw new DOMException('aborted','AbortError'); }});
  await assert.rejects(aborted.get('/api/auth/login'), error => error.name === 'AbortError');
});
