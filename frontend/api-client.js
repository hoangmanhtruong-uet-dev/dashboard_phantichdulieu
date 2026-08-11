(function createNexusApiClient(global) {
  /** @typedef {{page:number,page_size:number,total:number,total_pages:number}} NexusPagination */
  /** @typedef {{success:true,data:unknown,meta?:{pagination?:NexusPagination,query?:object}}} NexusApiEnvelope */
  /** @typedef {{page?:number,page_size?:number,search?:string,sort_by?:string,sort_order?:'asc'|'desc',[key:string]:unknown}} NexusListQuery */
  const { TTLCache, buildQuery } = global.NexusResource;

  class NexusApiError extends Error {
    constructor(message, options = {}) {
      super(message);
      this.name = 'NexusApiError';
      this.code = options.code || 'INTERNAL_ERROR';
      this.status = options.status || 0;
      this.details = options.details;
    }
  }

  function assertEnvelope(payload) {
    if (!payload || payload.success !== true || !Object.hasOwn(payload, 'data')) {
      throw new NexusApiError('Nexus API trả về dữ liệu không hợp lệ', { code: 'INVALID_API_RESPONSE' });
    }
    return payload;
  }

  function assertListEnvelope(payload) {
    const envelope = assertEnvelope(payload);
    if (!Array.isArray(envelope.data)) {
      throw new NexusApiError('Nexus API trả về danh sách không hợp lệ', { code: 'INVALID_API_RESPONSE' });
    }
    const pagination = envelope.meta?.pagination;
    if (pagination && !['page', 'page_size', 'total', 'total_pages'].every(key => Number.isInteger(pagination[key]))) {
      throw new NexusApiError('Metadata phân trang không hợp lệ', { code: 'INVALID_API_RESPONSE' });
    }
    return envelope;
  }

  class ApiClient {
    constructor(options = {}) {
      this.baseUrl = (options.baseUrl ?? global.NEXUS_CONFIG?.apiBaseUrl ?? '').replace(/\/$/, '');
      this.getAccessToken = options.getAccessToken || (() => null);
      this.fetch = options.fetch || global.fetch.bind(global);
      this.cache = options.cache || new TTLCache();
      this.defaultCacheTtl = options.defaultCacheTtl ?? 15000;
    }

    cookie(name) {
      const cookieText = global.document?.cookie || '';
      const item = cookieText.split('; ').find(value => value.startsWith(`${name}=`));
      return item ? decodeURIComponent(item.slice(name.length + 1)) : null;
    }

    invalidate(prefix = '/api/') {
      this.cache.invalidate(`${this.baseUrl}${prefix}`);
    }

    async request(path, options = {}) {
      const method = options.method || 'GET';
      const cacheKey = `${this.baseUrl}${path}`;
      const cacheTtl = options.cacheTtl ?? (method === 'GET' ? this.defaultCacheTtl : 0);
      if (method === 'GET' && !options.force) {
        const cached = this.cache.get(cacheKey);
        if (cached !== undefined) return cached;
      }
      const token = this.getAccessToken();
      const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
      const headers = { Accept: 'application/json', ...(options.body && !isFormData ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) };
      if (token) headers.Authorization = `Bearer ${token}`;
      if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        const csrf = this.cookie('nexus_csrf_token');
        if (csrf) headers['X-CSRF-Token'] = csrf;
      }
      let response;
      try {
        response = await this.fetch(cacheKey, { credentials: 'same-origin', ...options, method, headers });
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        throw new NexusApiError('Không thể kết nối tới Nexus API', { code: 'NETWORK_ERROR' });
      }

      const canRefresh = path === '/api/auth/session' || !path.startsWith('/api/auth/');
      if (response.status === 401 && !options._retried && canRefresh) {
        const refreshed = await this.fetch(`${this.baseUrl}/api/auth/refresh`, {
          method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'X-CSRF-Token': this.cookie('nexus_csrf_token') || '' }
        });
        if (refreshed.ok) return this.request(path, { ...options, _retried: true });
      }
      const contentType = response.headers.get('content-type') || '';
      const payload = contentType.includes('application/json') ? await response.json() : null;
      if (!response.ok || payload?.success === false) {
        const apiError = payload?.error || {};
        throw new NexusApiError(apiError.message || `API request failed (${response.status})`, {
          code: apiError.code || 'INTERNAL_ERROR', status: response.status, details: apiError.details
        });
      }
      const envelope = assertEnvelope(payload);
      if (method === 'GET') this.cache.set(cacheKey, envelope, cacheTtl);
      else this.invalidate();
      return envelope;
    }

    get(path, options = {}) { return this.request(path, { ...options, method: 'GET' }); }
    post(path, body, options = {}) { return this.request(path, { ...options, method: 'POST', body: JSON.stringify(body) }); }
    postForm(path, body, options = {}) { return this.request(path, { ...options, method: 'POST', body }); }
    put(path, body, options = {}) { return this.request(path, { ...options, method: 'PUT', body: JSON.stringify(body) }); }
    patch(path, body, options = {}) { return this.request(path, { ...options, method: 'PATCH', ...(body === undefined ? {} : { body: JSON.stringify(body) }) }); }
  }

  const client = new ApiClient();
  const list = (path, query = {}, options = {}) => client.get(`${path}${buildQuery(query)}`, options).then(assertListEnvelope);
  global.NexusApiError = NexusApiError;
  global.NexusAPI = {
    client,
    session: options => client.get('/api/auth/session', { cacheTtl: 5000, ...options }),
    register: payload => client.post('/api/auth/register', payload),
    login: payload => client.post('/api/auth/login', payload),
    logout: () => client.post('/api/auth/logout', {}),
    forgotPassword: payload => client.post('/api/auth/forgot-password', payload),
    resetPassword: payload => client.post('/api/auth/reset-password', payload),
    workspaces: options => list('/api/workspaces', {}, options),
    switchWorkspace: workspace_id => client.post('/api/workspaces/switch', { workspace_id }),
    members: options => client.get('/api/workspaces/current/members', options),
    inviteMember: payload => client.post('/api/workspaces/current/invitations', payload),
    bootstrap: (days, options) => client.get(`/api/bootstrap?days=${days}`, options),
    overview: (query = {}, options) => client.get(`/api/dashboard/overview${buildQuery(query)}`, options),
    revenue: (query = {}, options) => client.get(`/api/analytics/revenue${buildQuery(query)}`, options),
    funnel: (query = {}, options) => client.get(`/api/analytics/funnel${buildQuery(query)}`, options),
    cohort: options => client.get('/api/analytics/cohort', options),
    realtime: (query = {}, options) => client.get(`/api/sales/realtime${buildQuery(query)}`, options),
    insights: (query = {}, options) => list('/api/insights', query, options),
    alerts: (query = {}, options) => list('/api/alerts', query, options),
    reports: (query = {}, options) => list('/api/reports', query, options),
    dataSources: (query = {}, options) => list('/api/data-sources', query, options),
    savedViews: (query = {}, options) => list('/api/saved-views', query, options),
    profile: options => client.get('/api/profile', options),
    createReport: payload => client.post('/api/reports', payload),
    createAlert: payload => client.post('/api/alerts', payload),
    createSource: payload => client.post('/api/data-sources', payload),
    updateProfile: payload => client.put('/api/profile', payload),
    markAlertRead: id => client.patch(`/api/alerts/${id}/read`),
    ingestionSchema: options => client.get('/api/ingestion/schema', options),
    uploadDataset: file => { const body = new FormData(); body.append('file', file); return client.postForm('/api/ingestion/uploads', body); },
    previewImport: (id, sheet_name = null) => client.post(`/api/ingestion/jobs/${encodeURIComponent(id)}/preview`, { sheet_name }),
    runImport: (id, payload) => client.post(`/api/ingestion/jobs/${encodeURIComponent(id)}/import`, payload),
    importJobs: (query = {}, options) => list('/api/ingestion/jobs', query, options),
    importErrors: (id, query = {}, options) => client.get(`/api/ingestion/jobs/${encodeURIComponent(id)}/errors${buildQuery(query)}`, options)
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = { ApiClient, NexusApiError, assertEnvelope, assertListEnvelope };
})(typeof window !== 'undefined' ? window : globalThis);
