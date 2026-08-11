(function createNexusResourceState(global) {
  class StaleRequestError extends Error {
    constructor() {
      super('A newer request replaced this response');
      this.name = 'StaleRequestError';
      this.code = 'STALE_REQUEST';
    }
  }

  class TTLCache {
    constructor(now = () => Date.now()) {
      this.now = now;
      this.values = new Map();
    }

    get(key) {
      const entry = this.values.get(key);
      if (!entry) return undefined;
      if (entry.expiresAt <= this.now()) {
        this.values.delete(key);
        return undefined;
      }
      return entry.value;
    }

    set(key, value, ttlMs) {
      if (ttlMs > 0) this.values.set(key, { value, expiresAt: this.now() + ttlMs });
      return value;
    }

    invalidate(prefix = '') {
      for (const key of this.values.keys()) {
        if (!prefix || key.startsWith(prefix)) this.values.delete(key);
      }
    }

    clear() {
      this.values.clear();
    }
  }

  class LatestRequestRegistry {
    constructor() {
      this.active = new Map();
      this.sequence = 0;
    }

    async run(key, task) {
      this.cancel(key);
      const controller = new AbortController();
      const token = ++this.sequence;
      this.active.set(key, { controller, token });
      try {
        const value = await task(controller.signal);
        if (this.active.get(key)?.token !== token) throw new StaleRequestError();
        return value;
      } catch (error) {
        if (controller.signal.aborted && error?.name === 'AbortError') throw new StaleRequestError();
        throw error;
      } finally {
        if (this.active.get(key)?.token === token) this.active.delete(key);
      }
    }

    cancel(key) {
      const current = this.active.get(key);
      if (current) current.controller.abort();
      this.active.delete(key);
    }

    cancelAll() {
      for (const key of [...this.active.keys()]) this.cancel(key);
    }
  }

  function buildQuery(parameters = {}) {
    const query = new URLSearchParams();
    Object.keys(parameters).sort().forEach(key => {
      const value = parameters[key];
      if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
    });
    const text = query.toString();
    return text ? `?${text}` : '';
  }

  function loadingState() {
    return { status: 'loading', items: [], error: null };
  }

  function listState(envelope) {
    const items = envelope?.data;
    if (!Array.isArray(items)) throw new TypeError('Expected a list API envelope');
    return {
      status: items.length ? 'success' : 'empty',
      items,
      pagination: envelope.meta?.pagination || null,
      error: null
    };
  }

  function errorState(error) {
    return { status: 'error', items: [], error };
  }

  const exported = {
    TTLCache, LatestRequestRegistry, StaleRequestError, buildQuery,
    loadingState, listState, errorState
  };
  global.NexusResource = exported;
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
})(typeof window !== 'undefined' ? window : globalThis);
