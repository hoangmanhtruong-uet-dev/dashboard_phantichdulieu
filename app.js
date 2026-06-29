// CONFIGURATION: DIRECT CONNECTION TO AI BACKEND
const AI_SERVICE_URL = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

let forecastChart = null;
let segmentChart = null;
let deepForecastChart = null;
let deepSegmentChart = null;
let sentimentSparklineChart = null;

// New Activity Charts
let leadSourceChart = null;
let emailsDayChart = null;
let followUpChart = null;
let salesStatsChart = null;
let callsDayChart = null;
let responseTimeChart = null;

let currentData = [];
let filteredData = [];
let columns = [];
let tablePage = 1;
const TABLE_PAGE_SIZE = 15;
let uploadHistory = JSON.parse(localStorage.getItem('uploadHistory') || '[]');
let currentCategoryFilter = 'all';
let currentSegmentFilter = 'all';
let notifications = [];
let isAIConnected = false;
let activeFilters = { period: 'all', dateFrom: '', dateTo: '', region: 'all', category: 'all' };

document.addEventListener('DOMContentLoaded', () => {
    const loginScreen = document.getElementById('login-screen');
    const mainApp = document.getElementById('main-app');
    const btnLogin = document.getElementById('btn-login');
    const quickLogin = document.getElementById('quick-login');
    const btnLogout = document.getElementById('btn-logout');
    const csvUpload = document.getElementById('csv-upload');
    const tableSearch = document.getElementById('table-search');
    const categoryFilter = document.getElementById('category-filter');
    const btnDemo = document.getElementById('btn-demo');
    const btnExport = document.getElementById('btn-export');
    const btnNotif = document.getElementById('btn-notif');
    const notifPanel = document.getElementById('notif-panel');
    const growthRange = document.getElementById('growth-range');

    // 0. CHECK AI BACKEND HEALTH
    checkAIHealth();

    // 1. AUTH
    const userInp = document.getElementById('username');
    const passInp = document.getElementById('password');
    if(userInp) userInp.value = 'admin';
    if(passInp) passInp.value = '123';

    const handleLogin = () => {
        const user = userInp.value.trim();
        const pass = passInp.value.trim();
        if (user === 'admin' && pass === '123') {
            loginScreen.classList.add('hidden');
            mainApp.classList.remove('hidden');
            showToast('Đăng nhập thành công', 'success', 'ph-shield-check');
        } else {
            showToast('Sai mật khẩu', 'error', 'ph-warning');
        }
    };

    if (btnLogin) btnLogin.addEventListener('click', handleLogin);
    if (quickLogin) quickLogin.addEventListener('click', (e) => { e.preventDefault(); handleLogin(); });

    if (btnLogout) btnLogout.addEventListener('click', () => {
        mainApp.classList.add('hidden');
        loginScreen.classList.remove('hidden');
    });

    // 2. TAB SWITCHING (REFINED WITH AI CALLS)
    const navItems = {
        'nav-overview': 'tab-overview',
        'nav-forecast': 'tab-forecast',
        'nav-activity': 'tab-activity',
        'nav-customers': 'tab-customers'
    };

    Object.keys(navItems).forEach(navId => {
        const item = document.getElementById(navId);
        if (item) {
            item.addEventListener('click', async (e) => {
                e.preventDefault();
                console.log("Switching to tab:", navId);
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
                document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));
                
                const targetTabId = navItems[navId];
                const targetTab = document.getElementById(targetTabId);
                if (targetTab) {
                    targetTab.classList.remove('hidden');
                    if (currentData.length > 0) {
                        if (navId === 'nav-forecast') await renderDeepForecastWithAI();
                        if (navId === 'nav-activity') renderActivityCharts();
                        if (navId === 'nav-customers') await renderDeepCustomersWithAI();
                    }
                }
            });
        }
    });

    // 3. ACTIONS
    if (csvUpload) csvUpload.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) { addToHistory(file.name); processFile(file); }
    });

    if (btnDemo) btnDemo.addEventListener('click', () => loadDemoData());
    if (btnExport) btnExport.addEventListener('click', () => exportToPDF());

    // Notifications
    if (btnNotif && notifPanel) {
        btnNotif.addEventListener('click', (e) => {
            e.stopPropagation();
            notifPanel.classList.toggle('hidden');
            if (!notifPanel.classList.contains('hidden')) {
                const badge = document.querySelector('.notif-badge');
                if (badge) badge.classList.add('hidden');
            }
        });

        document.addEventListener('click', (e) => {
            if (!notifPanel.contains(e.target) && !btnNotif.contains(e.target)) {
                notifPanel.classList.add('hidden');
            }
        });
    }

    // --- FILTER EVENT LISTENERS (event delegation) ---
    const periodChips = document.getElementById('period-chips');
    if (periodChips) periodChips.addEventListener('click', e => {
        const chip = e.target.closest('[data-period]');
        if (!chip) return;
        periodChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeFilters.period = chip.dataset.period;
        applyPeriodPreset(chip.dataset.period);
        applyAllFilters();
    });

    const regionChips = document.getElementById('region-chips');
    if (regionChips) regionChips.addEventListener('click', e => {
        const chip = e.target.closest('[data-region]');
        if (!chip) return;
        regionChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeFilters.region = chip.dataset.region;
        applyAllFilters();
    });

    const categoryChips = document.getElementById('category-chips');
    if (categoryChips) categoryChips.addEventListener('click', e => {
        const chip = e.target.closest('[data-cat]');
        if (!chip) return;
        categoryChips.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeFilters.category = chip.dataset.cat;
        applyAllFilters();
    });

    const dateFrom = document.getElementById('filter-date-from');
    const dateTo   = document.getElementById('filter-date-to');
    if (dateFrom) dateFrom.addEventListener('change', e => {
        activeFilters.dateFrom = e.target.value;
        // Clear period presets
        document.querySelectorAll('#period-chips .chip').forEach(c => c.classList.remove('active'));
        document.querySelector('#period-chips [data-period="all"]')?.classList.add('active');
        activeFilters.period = 'all';
        applyAllFilters();
    });
    if (dateTo) dateTo.addEventListener('change', e => {
        activeFilters.dateTo = e.target.value;
        document.querySelectorAll('#period-chips .chip').forEach(c => c.classList.remove('active'));
        document.querySelector('#period-chips [data-period="all"]')?.classList.add('active');
        activeFilters.period = 'all';
        applyAllFilters();
    });

    const btnReset = document.getElementById('btn-reset-filters');
    if (btnReset) btnReset.addEventListener('click', resetAllFilters);

    // Table search (live filter)
    if (tableSearch) tableSearch.addEventListener('input', () => {
        tablePage = 1;
        applyTableView();
    });
    // Category-filter select in table header
    if (categoryFilter) categoryFilter.addEventListener('change', () => {
        tablePage = 1;
        applyTableView();
    });
    // Pagination click (event delegation)
    const pagContainer = document.getElementById('table-pagination');
    if (pagContainer) pagContainer.addEventListener('click', e => {
        const btn = e.target.closest('[data-page]');
        if (!btn || btn.disabled) return;
        const pg = parseInt(btn.dataset.page);
        if (!isNaN(pg)) { tablePage = pg; applyTableView(); }
        document.getElementById('data-table')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    // Export buttons
    document.getElementById('btn-export-csv')?.addEventListener('click', exportTableCSV);
    document.getElementById('btn-export-excel')?.addEventListener('click', exportTableExcel);
});

// --- CORE AI PIPELINE STABILITY ---

// --- AI HEALTH & RETRY ---

let realtimeInterval = null;

async function checkAIHealth() {
    updateAIStatusBadge('checking');
    try {
        const res = await fetch(`${AI_SERVICE_URL}/health`, {
            method: 'GET',
            mode: 'cors',
            signal: AbortSignal.timeout(5000)
        });
        if (res.ok) {
            isAIConnected = true;
            console.log("AI Backend is ONLINE");
            updateAIStatusBadge('online');
            
            if (!realtimeInterval) {
                showToast('Đã kết nối AI Database Real-time', 'success', 'ph-database');
                fetchRealtimeData();
                realtimeInterval = setInterval(fetchRealtimeData, 10000);
            }
        } else {
            throw new Error(`Status ${res.status}`);
        }
    } catch (err) {
        isAIConnected = false;
        console.warn("AI Backend OFFLINE:", err.message);
        updateAIStatusBadge('offline');
        if (realtimeInterval) {
            clearInterval(realtimeInterval);
            realtimeInterval = null;
        }
        setTimeout(checkAIHealth, 15000);
    }
}

async function fetchRealtimeData() {
    if (!isAIConnected) return;
    try {
        const anomalyRes = await fetch(`${AI_SERVICE_URL}/api/anomalies`);
        if (anomalyRes.ok) {
            const anomalyData = await anomalyRes.json();
            const banner = document.getElementById('anomaly-container');
            const text = document.getElementById('anomaly-text');
            if (anomalyData.status === 'success' && anomalyData.anomaly) {
                if (banner) {
                    banner.classList.remove('hidden');
                    text.innerHTML = `${anomalyData.message} <button class="btn btn-primary" style="margin-left: 10px; padding: 2px 8px; font-size: 0.8rem;">Xem chi tiết</button>`;
                    banner.style.background = 'rgba(239, 68, 68, 0.15)';
                    banner.style.border = '1px solid rgba(239, 68, 68, 0.3)';
                    banner.style.color = '#f87171';
                }
            } else {
                if (banner) banner.classList.add('hidden');
            }
        }

        const salesRes = await fetch(`${AI_SERVICE_URL}/api/sales/realtime`);
        if (salesRes.ok) {
            const result = await salesRes.json();
            if (result.status === 'success' && result.data.length > 0) {
                const isFirstTime = currentData.length === 0;
                currentData = result.data;
                columns = Object.keys(result.data[0]);
                
                if (isFirstTime) {
                    initDashboard();
                } else {
                    filteredData = [...currentData];
                    runAIAnalytics();
                    applyTableView();
                }
            }
        }
    } catch (err) {
        console.error("Realtime fetch error:", err);
    }
}

function updateAIStatusBadge(state) {
    let badge = document.getElementById('ai-status-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.id = 'ai-status-badge';
        badge.style.cssText = [
            'position:fixed', 'bottom:16px', 'right:16px', 'z-index:9999',
            'display:flex', 'align-items:center', 'gap:6px',
            'padding:6px 12px', 'border-radius:999px',
            'font-size:12px', 'font-weight:600', 'font-family:Outfit,sans-serif',
            'box-shadow:0 4px 15px rgba(0,0,0,0.4)',
            'transition:all 0.4s ease', 'cursor:default',
            'letter-spacing:0.5px'
        ].join(';');
        document.body.appendChild(badge);
    }
    const configs = {
        checking: { bg: 'rgba(30,30,50,0.92)', border: '#6366f1', dot: '#a5b4fc', text: '⚙ Đang kiểm tra AI...' },
        online:   { bg: 'rgba(16,40,30,0.92)', border: '#10b981', dot: '#34d399', text: '● AI Forecast Online' },
        offline:  { bg: 'rgba(40,16,16,0.92)', border: '#ef4444', dot: '#f87171', text: '● Mô phỏng nội bộ' }
    };
    const cfg = configs[state] || configs.offline;
    badge.style.background = cfg.bg;
    badge.style.border = `1px solid ${cfg.border}`;
    badge.style.color = cfg.dot;
    badge.innerHTML = `<span style="font-size:10px">${cfg.text}</span>`;
    badge.title = state === 'online'
        ? 'AI Backend đang hoạt động'
        : 'Đang dùng dự báo tuyến tính nội bộ (không cần server)';
}

/**
 * fetchWithRetry – Exponential backoff (1s, 2s, 4s)
 */
async function fetchWithRetry(url, options, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 8000);
            const response = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timer);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (err) {
            const isLast = i === retries - 1;
            const delay = Math.pow(2, i) * 1000; // 1s, 2s, 4s
            console.warn(`[AI] Lần ${i + 1}/${retries} thất bại: ${err.message}${isLast ? '' : ` – thử lại sau ${delay/1000}s`}`);
            if (isLast) throw err;
            await new Promise(r => setTimeout(r, delay));
        }
    }
}

// --- REAL AI INTEGRATION FUNCTIONS ---

async function renderDeepForecastWithAI() {
    const monthlySales = getMonthlySales();
    if (monthlySales.length === 0) return;

    const apiData = monthlySales.map(m => ({ ds: m.month + "-01", y: parseFloat(m.total) }));

    if (isAIConnected) {
        showToast('AI đang phân tích xu hướng...', 'info', 'ph-sparkle');
        try {
            const result = await fetchWithRetry(`${AI_SERVICE_URL}/forecast`, {
                method: 'POST',
                mode: 'cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(apiData)
            });
            if (result.status === 'success') {
                renderForecastChartDeep(monthlySales, result.forecast);
                showToast('AI dự báo hoàn tất!', 'success', 'ph-check');
                return;
            }
        } catch (err) {
            console.warn("[AI Forecast] Chuyển sang mô phỏng nội bộ:", err.message);
            isAIConnected = false;
            updateAIStatusBadge('offline');
        }
    }

    // --- FALLBACK: Mô phỏng tuyến tính nội bộ (6 tháng) ---
    showToast('Dùng dự báo mô phỏng nội bộ (6 tháng)', 'info', 'ph-chart-line-up');
    const simulatedForecast = calculateSimulatedForecast(monthlySales, 6);
    renderForecastChartDeep(monthlySales, simulatedForecast);
}

async function renderDeepCustomersWithAI() {
    const mapping = calculateRFMDataRaw();
    const apiData = Object.keys(mapping).map(id => ({
        id: String(id),
        frequency: parseInt(mapping[id].count),
        monetary: parseFloat(mapping[id].total)
    }));

    showToast('AI đang phân loại khách hàng...', 'info', 'ph-users-three');

    try {
        const result = await fetchWithRetry(`${AI_SERVICE_URL}/cluster`, {
            method: 'POST',
            mode: 'cors',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(apiData)
        });

        if (result.status === 'success') {
            renderClusterChartDeep(result.clusters);
            showToast('Phân cụm K-Means hoàn tất', 'success', 'ph-users-four');
        }
    } catch (err) {
        console.error("Clustering Error:", err);
        showToast('Dùng phân cụm mặc định.', 'info', 'ph-user');
        renderClusterChartDeepDefault(calculateRFM());
    }
}

function renderForecastChartDeep(history, forecast) {
    const canvas = document.getElementById('forecastChartDeep');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (deepForecastChart) deepForecastChart.destroy();

    const historyLabels = history.map(h => h.month);
    const forecastLabels = forecast.map(f => f.ds);
    const labels = [...historyLabels, ...forecastLabels];

    deepForecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { 
                    label: 'Lịch sử doanh thu', 
                    data: history.map(h => h.total), 
                    borderColor: '#6366f1', 
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                { 
                    label: 'Dự báo từ AI', 
                    data: labels.map((l, i) => i >= history.length ? forecast[i-history.length].yhat : null), 
                    borderColor: '#06b6d4', 
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4
                },
                {
                    label: 'Biên dưới (AI)',
                    data: labels.map((l, i) => i >= history.length ? forecast[i-history.length].yhat_lower : null),
                    borderColor: 'transparent',
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    fill: false,
                    tension: 0.4
                },
                {
                    label: 'Vùng tin cậy (Sai số)',
                    data: labels.map((l, i) => i >= history.length ? forecast[i-history.length].yhat_upper : null),
                    borderColor: 'transparent',
                    backgroundColor: 'rgba(6, 182, 212, 0.15)',
                    pointRadius: 0,
                    fill: '-1',
                    tension: 0.4
                }
            ]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: false, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });

    const baseRevenue = forecast[0]?.yhat || 0;
    const simValue = document.getElementById('sim-value');
    if (simValue) simValue.textContent = Math.round(baseRevenue).toLocaleString('vi-VN') + ' đ';

    // Render Budget Optimization Chart (Prescriptive AI)
    const budgetCtx = document.getElementById('budgetOptimizationChart');
    if (budgetCtx) {
        if (window.budgetChartObj) window.budgetChartObj.destroy();
        window.budgetChartObj = new Chart(budgetCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Lazada', 'Facebook Ads', 'Tiktok Shop', 'Google Ads'],
                datasets: [
                    {
                        label: 'Phân bổ đề xuất (Triệu VNĐ)',
                        data: [60, 45, 30, 15],
                        backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#06b6d4'],
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y', // Horizontal bar chart
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                    y: { grid: { display: false }, ticks: { color: '#e2e8f0', font: { weight: 500 } } }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                // Mock ROI for each channel
                                const rois = [28, 22, 35, 15];
                                return `${ctx.raw} Triệu VNĐ (ROI dự kiến: +${rois[ctx.dataIndex]}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
}

function renderClusterChartDeep(clusters) {
    const canvas = document.getElementById('segmentChartDeep');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (deepSegmentChart) deepSegmentChart.destroy();

    const datasets = [
        { label: 'Nhóm VIP', data: [], backgroundColor: '#6366f1' },
        { label: 'Tiềm năng', data: [], backgroundColor: '#06b6d4' },
        { label: 'Mới', data: [], backgroundColor: '#3b82f6' },
        { label: 'Rời bỏ', data: [], backgroundColor: '#8b5cf6' }
    ];

    clusters.forEach(c => {
        const clusterId = c.cluster % 4; // Ensure it maps to 0-3
        datasets[clusterId].data.push({ x: c.monetary, y: c.frequency, id: c.id });
    });

    deepSegmentChart = new Chart(ctx, {
        type: 'scatter',
        data: { datasets: datasets },
        options: { 
            responsive: true, 
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'Giá trị đơn hàng (Monetary)', color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    title: { display: true, text: 'Tần suất mua (Frequency)', color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', usePointStyle: true } },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            return `KH #${ctx.raw.id}: ${Math.round(ctx.raw.x).toLocaleString('vi-VN')}đ - ${ctx.raw.y} lần`;
                        }
                    }
                }
            }
        }
    });

    const topList = document.getElementById('top-customers-list');
    if (topList) {
        const vips = clusters.filter(c => c.cluster === 0).slice(0, 5);
        topList.innerHTML = vips.map(c => `
            <div class="rec-item">
                <div class="rec-info"><h4>Khách hàng #${c.id}</h4><p>Mức chi tiêu: ${Math.round(c.monetary).toLocaleString()}đ</p></div>
                <div class="trend up">VIP AI</div>
            </div>
        `).join('');
    }
}

// --- DATA LOGIC (STABLE) ---

// ============================================================
// UP-SELL AI ENGINE
// ============================================================

function generateUpSellRecommendations() {
    const container = document.getElementById('recommendation-list');
    if (!container) return;

    if (!filteredData.length || !columns.length) {
        container.innerHTML = `<div class="upsell-empty"><i class="ph ph-robot"></i>Tải dữ liệu để AI phân tích gợi ý</div>`;
        return;
    }

    const amtCol  = columns.find(c => /amount|salary/i.test(c)) || columns[1];
    const catCol  = columns.find(c => /category/i.test(c));
    const idCol   = columns.find(c => /customerid|^id$/i.test(c)) || columns[0];
    const prodCol = columns.find(c => /product/i.test(c));

    if (!prodCol) {
        container.innerHTML = `<div class="upsell-empty"><i class="ph ph-package"></i>Cần cột 'Product' trong CSV để phân tích</div>`;
        return;
    }

    // Build frequency + revenue maps
    const prodFreq = {}; const prodRevenue = {}; const catRevenue = {};
    const custProds = {};  // customer -> Set of products

    filteredData.forEach(row => {
        const prod = row[prodCol]; if (!prod) return;
        const cat  = row[catCol]  || 'Other';
        const id   = row[idCol]   || 'unknown';
        let amt = parseFloat(String(row[amtCol] || '').replace(/[^0-9.-]/g, '')) || 0;

        prodFreq[prod]    = (prodFreq[prod]    || 0) + 1;
        prodRevenue[prod] = (prodRevenue[prod] || 0) + amt;
        catRevenue[cat]   = (catRevenue[cat]   || 0) + amt;
        if (!custProds[id]) custProds[id] = new Set();
        custProds[id].add(prod);
    });

    const totalRevenue = Object.values(catRevenue).reduce((a,b) => a+b, 0) || 1;
    const totalCusts   = Object.keys(custProds).length || 1;
    const allProds     = Object.keys(prodFreq).sort((a,b) => prodRevenue[b] - prodRevenue[a]);

    // Score each product
    const recommendations = allProds.slice(0, 5).map((prod, rank) => {
        const buyers    = new Set(filteredData.filter(r => r[prodCol] === prod).map(r => r[idCol]));
        const cat       = filteredData.find(r => r[prodCol] === prod)?.[catCol] || 'Other';
        const catShare  = catRevenue[cat] / totalRevenue;
        const popScore  = buyers.size / totalCusts;       // 0-1
        const revScore  = prodRevenue[prod] / totalRevenue; // 0-1
        const rankBonus = (allProds.length - rank) / allProds.length; // 0-1

        // Confidence: weighted blend, capped 45-97
        const raw = 45 + popScore * 25 + revScore * 15 + rankBonus * 12;
        const confidence = Math.min(97, Math.round(raw));
        const confClass  = confidence >= 80 ? 'high' : confidence >= 60 ? 'medium' : 'low';

        const potential  = totalCusts - buyers.size;
        const avgRevenue = Math.round(prodRevenue[prod] / (prodFreq[prod] || 1));

        return { prod, cat, confidence, confClass, buyers: buyers.size, potential, avgRevenue };
    });

    // Render
    container.innerHTML = recommendations.map(r => `
        <div class="upsell-card">
            <div class="upsell-img-wrap">
                <img src="${getProductImage(r.prod, r.cat)}" alt="${r.prod}" loading="lazy"
                     onerror="this.src='https://picsum.photos/seed/${r.prod.length * 13}/62/62'">
                <span class="upsell-cat-badge">${r.cat}</span>
            </div>
            <div class="upsell-info">
                <div class="upsell-name" title="${r.prod}">${r.prod}</div>
                <div class="upsell-meta">
                    <span>💡 ${r.potential} KH tiềm năng</span>
                    <span>~${r.avgRevenue.toLocaleString('vi-VN')}đ</span>
                </div>
                <div class="upsell-confidence-wrap">
                    <div class="upsell-confidence-bar">
                        <div class="upsell-confidence-fill ${r.confClass}" data-w="${r.confidence}"></div>
                    </div>
                    <span class="upsell-confidence-label">${r.confidence}%</span>
                </div>
                <div class="upsell-confidence-text">Độ tin cậy AI</div>
            </div>
        </div>
    `).join('');

    // Animate bars after DOM paint
    requestAnimationFrame(() => {
        container.querySelectorAll('.upsell-confidence-fill[data-w]').forEach(el => {
            el.style.width = el.dataset.w + '%';
        });
    });
}

function getProductImage(product, category) {
    const p = product.toLowerCase();
    // Product keyword → Unsplash photo ID
    if (/iphone|samsung.*phone|điện thoại/i.test(p)) return 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=62&h=62&fit=crop&q=80';
    if (/macbook|laptop|notebook/i.test(p))              return 'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=62&h=62&fit=crop&q=80';
    if (/ipad|tablet/i.test(p))                          return 'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=62&h=62&fit=crop&q=80';
    if (/airpod|headphone|sony.*wh|tai nghe/i.test(p))   return 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=62&h=62&fit=crop&q=80';
    if (/mouse|chuột/i.test(p))                          return 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=62&h=62&fit=crop&q=80';
    if (/keyboard|keychron|bàn phím/i.test(p))           return 'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=62&h=62&fit=crop&q=80';
    if (/chair|ghế/i.test(p))                           return 'https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?w=62&h=62&fit=crop&q=80';
    if (/desk|bàn/i.test(p))                             return 'https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?w=62&h=62&fit=crop&q=80';
    if (/case|ốp/i.test(p))                              return 'https://images.unsplash.com/photo-1553545204-4f7d339aa06a?w=62&h=62&fit=crop&q=80';
    if (/cooling|pad|tản nhiệt/i.test(p))              return 'https://images.unsplash.com/photo-1593640408182-31c228b52a9b?w=62&h=62&fit=crop&q=80';
    if (/asus|rog|gaming/i.test(p))                       return 'https://images.unsplash.com/photo-1587202372634-32705e3bf49c?w=62&h=62&fit=crop&q=80';
    // Fallback by category
    const catMap = {
        'Electronics': 'https://images.unsplash.com/photo-1498049794561-7780e7231661?w=62&h=62&fit=crop&q=80',
        'Accessories': 'https://images.unsplash.com/photo-1491553895911-0055eca6402d?w=62&h=62&fit=crop&q=80',
        'Furniture':   'https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=62&h=62&fit=crop&q=80',
    };
    return catMap[category] || `https://picsum.photos/seed/${product.length * 17}/62/62`;
}

function processFile(file) {
    if (!window.Papa) {
        showToast('Chua tai duoc thu vien doc CSV. Hay refresh trang roi thu lai.', 'error', 'ph-warning');
        return;
    }

    showToast(`Dang doc file ${file.name}...`, 'info', 'ph-file-csv');

    Papa.parse(file, {
        header: true, dynamicTyping: true, skipEmptyLines: true,
        complete: function(results) {
            if (results.errors?.length) {
                console.warn('CSV parse errors:', results.errors);
            }

            const rows = (results.data || []).filter(row =>
                row && Object.values(row).some(value => value !== null && value !== undefined && String(value).trim() !== '')
            );
            const fields = (results.meta.fields || []).filter(Boolean);

            if (!rows.length || !fields.length) {
                showToast('File CSV rong hoac khong co dong tieu de hop le.', 'error', 'ph-warning');
                return;
            }

            currentData = rows;
            columns = fields;
            initDashboard();
            showToast(`Da nap ${rows.length.toLocaleString('vi-VN')} dong du lieu.`, 'success', 'ph-check-circle');
        },
        error: function(error) {
            console.error('CSV parse failed:', error);
            showToast('Khong doc duoc file CSV. Hay kiem tra dinh dang file.', 'error', 'ph-warning');
        }
    });
}

function initDashboard() {
    const loader = document.getElementById('loading-overlay');
    if (loader) loader.classList.remove('hidden');
    setTimeout(() => {
        try {
            const zone = document.getElementById('upload-zone');
            const dash = document.getElementById('dashboard');
            if (zone) zone.classList.add('hidden');
            if (dash) dash.classList.remove('hidden');
            // Reset filters and populate chips from new data
            resetAllFilters(false);
            populateCategoryFilter();
            populateFilterChips();
            filteredData = [...currentData];
            try {
                runAIAnalytics();
            } catch (err) {
                console.error('Analytics render failed:', err);
                showToast('Da nap du lieu, nhung bieu do chua san sang. Hay refresh neu can.', 'error', 'ph-chart-line');
            }
            applyFilters();
        } finally {
            if (loader) loader.classList.add('hidden');
        }
    }, 100);
}

function runAIAnalytics() {
    const monthlySales = getMonthlySales();
    updateForecastChart(monthlySales, calculateForecast(monthlySales));
    const segments = calculateRFM();
    updateSegmentChart(segments);
    generateAIInsights(monthlySales, segments, analyzeSentiment());
    generateUpSellRecommendations();
}

function getMonthlySales() {
    const months = {};
    const dateCol = columns.find(c => c.toLowerCase().includes('date')) || columns[0];
    const amountCol = columns.find(c => c.toLowerCase().includes('amount') || c.toLowerCase().includes('salary')) || columns[1];

    filteredData.forEach(row => {
        if (row[dateCol]) {
            const dateStr = String(row[dateCol]);
            const month = dateStr.includes('-') ? dateStr.substring(0, 7) : 'Unknown';
            // Robust number parsing (handle currency symbols/commas)
            let val = row[amountCol];
            if (typeof val === 'string') {
                val = val.replace(/[^0-9.-]+/g, "");
            }
            months[month] = (months[month] || 0) + (parseFloat(val) || 0);
        }
    });
    return Object.keys(months).sort().map(m => ({ month: m, total: months[m] }));
}

function calculateRFMDataRaw() {
    const customers = {};
    const idCol = columns.find(c => c.toLowerCase().includes('id')) || columns[0];
    const amountCol = columns.find(c => c.toLowerCase().includes('amount') || c.toLowerCase().includes('salary')) || columns[1];
    filteredData.forEach(row => {
        const id = row[idCol];
        if (!id) return;
        if (!customers[id]) customers[id] = { count: 0, total: 0 };
        customers[id].count++;
        let val = row[amountCol];
        if (typeof val === 'string') val = val.replace(/[^0-9.-]+/g, "");
        customers[id].total += (parseFloat(val) || 0);
    });
    return customers;
}

function calculateRFM() {
    const customers = calculateRFMDataRaw();
    const segments = { 'VIP': 0, 'Tiềm năng': 0, 'Sắp rời bỏ': 0, 'Mới': 0 };
    Object.keys(customers).forEach(id => {
        const c = customers[id];
        if (c.total > 50000000) segments['VIP']++;
        else if (c.count > 3) segments['Tiềm năng']++;
        else if (c.count === 1) segments['Mới']++;
        else segments['Sắp rời bỏ']++;
    });
    return segments;
}

function calculateForecast(history) {
    if (history.length < 2) return history[0]?.total || 0;
    const last = history[history.length - 1].total;
    const prev = history[history.length - 2].total;
    return last * (last / (prev || 1));
}

/**
 * calculateSimulatedForecast – Hồi quy tuyến tính đơn giản dự báo N tháng tới.
 * Trả về mảng [{ds, yhat}] tương thích với renderForecastChartDeep.
 */
function calculateSimulatedForecast(history, periods = 6) {
    const n = history.length;
    if (n === 0) return [];
    if (n === 1) {
        return Array.from({ length: periods }, (_, i) => ({
            ds: shiftMonth(history[0].month, i + 1),
            yhat: history[0].total
        }));
    }

    // Tính hệ số hồi quy tuyến tính (Ordinary Least Squares)
    const xMean = (n - 1) / 2;
    const yMean = history.reduce((s, h) => s + h.total, 0) / n;
    let num = 0, den = 0;
    history.forEach((h, i) => {
        num += (i - xMean) * (h.total - yMean);
        den += (i - xMean) ** 2;
    });
    const slope = den === 0 ? 0 : num / den;
    const intercept = yMean - slope * xMean;

    return Array.from({ length: periods }, (_, i) => {
        const x = n + i;
        const yhat = Math.max(0, intercept + slope * x);
        return { 
            ds: shiftMonth(history[n - 1].month, i + 1), 
            yhat: Math.round(yhat),
            yhat_lower: Math.max(0, Math.round(yhat * 0.9)),
            yhat_upper: Math.round(yhat * 1.1)
        };
    });
}

/** Dịch chuyển tháng YYYY-MM sang +offset tháng */
function shiftMonth(yyyymm, offset) {
    const [y, m] = yyyymm.split('-').map(Number);
    const date = new Date(y, m - 1 + offset, 1);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

/**
 * analyzeSentimentDeep: Tính điểm cảm xúc theo từng tháng dựa trên:
 * - Cột Rating (nếu có) chuẩn hóa 0–10
 * - Hoặc xu hướng doanh thu tương đối giữa các tháng
 * Trả về: { monthly: [{month, score}], overall, label, emoji }
 */
function analyzeSentimentDeep(monthlySales) {
    const ratingCol = columns.find(c =>
        /rating|review|score|satisfaction|star/i.test(c)
    );

    let monthly = [];

    if (ratingCol) {
        // Group ratings by month
        const byMonth = {};
        const dateCol = columns.find(c => c.toLowerCase().includes('date')) || columns[0];
        filteredData.forEach(row => {
            const dateStr = String(row[dateCol] || '');
            const month = dateStr.includes('-') ? dateStr.substring(0, 7) : 'Unknown';
            let r = parseFloat(String(row[ratingCol]).replace(/[^0-9.]/g, '')) || null;
            if (r === null) return;
            // Chuẩn hóa về thang 10
            if (r <= 5 && r >= 1) r = r * 2;
            if (!byMonth[month]) byMonth[month] = [];
            byMonth[month].push(Math.min(10, r));
        });
        monthly = Object.keys(byMonth).sort().map(m => ({
            month: m,
            score: parseFloat((byMonth[m].reduce((a, b) => a + b, 0) / byMonth[m].length).toFixed(1))
        }));
    } else {
        // Fallback: dùng biến động doanh thu (tăng = tích cực)
        monthly = monthlySales.map((m, i) => {
            if (i === 0) return { month: m.month, score: 6.5 };
            const prev = monthlySales[i - 1].total || 1;
            const ratio = m.total / prev;
            // ratio 1.2 = tăng 20% → ~8.5, ratio 0.8 = giảm 20% → ~5.0
            const score = Math.min(10, Math.max(2, 5 + (ratio - 1) * 20));
            return { month: m.month, score: parseFloat(score.toFixed(1)) };
        });
    }

    const overall = monthly.length
        ? parseFloat((monthly.reduce((s, m) => s + m.score, 0) / monthly.length).toFixed(1))
        : 6.5;

    const label = overall >= 8 ? 'Rất tích cực'
                : overall >= 6 ? 'Tích cực'
                : overall >= 4 ? 'Trung lập'
                : 'Tiêu cực';

    const emoji = overall >= 8 ? '🤩'
                : overall >= 6 ? '😊'
                : overall >= 4 ? '😐'
                : '😟';

    return { monthly, overall, label, emoji };
}

/**
 * renderSentimentPanel: Vẽ sparkline + tags + progress bar vào KPI card.
 */
let _sentimentSparkChart = null;

function renderSentimentPanel({ monthly, overall, label, emoji }) {
    // 1. Emoji
    const emojiEl = document.getElementById('kpi-sentiment');
    if (emojiEl) emojiEl.textContent = emoji;

    // 2. Score label
    const scoreEl = document.getElementById('sentiment-score');
    if (scoreEl) scoreEl.textContent = `${overall}/10 – ${label}`;

    // 3. Progress bar
    const fill = document.getElementById('sentiment-bar-fill');
    if (fill) {
        const pct = (overall / 10) * 100;
        const cls = overall >= 6 ? 'positive' : overall >= 4 ? 'neutral' : 'negative';
        fill.style.width = `${pct}%`;
        fill.className = `sentiment-score-fill ${cls}`;
    }

    // 4. Sparkline
    const canvas = document.getElementById('sentimentSparkline');
    if (canvas && monthly.length > 1) {
        const ctx = canvas.getContext('2d');
        if (_sentimentSparkChart) _sentimentSparkChart.destroy();

        const grad = ctx.createLinearGradient(0, 0, 0, 48);
        grad.addColorStop(0, 'rgba(99,102,241,0.35)');
        grad.addColorStop(1, 'rgba(99,102,241,0)');

        _sentimentSparkChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: monthly.map(m => m.month.slice(5)), // chỉ hiện MM
                datasets: [{
                    data: monthly.map(m => m.score),
                    borderColor: overall >= 6 ? '#10b981' : overall >= 4 ? '#6366f1' : '#ef4444',
                    backgroundColor: grad,
                    fill: true,
                    tension: 0.45,
                    pointRadius: 0,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 800 },
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { display: false, min: 0, max: 10 }
                }
            }
        });
    }

    // 5. Tags từ khóa
    const tagsEl = document.getElementById('sentiment-tags');
    if (!tagsEl) return;

    const tags = buildSentimentTags(overall);
    tagsEl.innerHTML = tags.map(t =>
        `<span class="s-tag ${t.type}">${t.icon} ${t.text}</span>`
    ).join('');
}

/**
 * buildSentimentTags: Tạo danh sách tags dựa trên dữ liệu CSV + ngưỡng điểm
 */
function buildSentimentTags(overall) {
    const tags = [];

    // Tags cố định theo ngưỡng
    if (overall >= 8) {
        tags.push({ text: 'Kỳ vọng cao', type: 'positive', icon: '⬆' });
        tags.push({ text: 'Giới thiệu bạn bè', type: 'positive', icon: '💬' });
        tags.push({ text: 'Mua lại', type: 'positive', icon: '🔄' });
    } else if (overall >= 6) {
        tags.push({ text: 'Hài lòng', type: 'positive', icon: '✔' });
        tags.push({ text: 'Hỗ trợ tốt', type: 'positive', icon: '🏆' });
    } else if (overall >= 4) {
        tags.push({ text: 'Giá hợp lý', type: 'neutral', icon: '➖' });
        tags.push({ text: 'Giao hàng chậm', type: 'negative', icon: '⏱' });
    } else {
        tags.push({ text: 'Cần cải thiện', type: 'negative', icon: '⚠' });
        tags.push({ text: 'Phản hồi xấu', type: 'negative', icon: '🔴' });
    }

    // Tags động từ CSV
    const ratingCol = columns.find(c => /rating|review|score|satisfaction|star/i.test(c));
    if (ratingCol) tags.push({ text: 'Có đánh giá', type: 'neutral', icon: '⭐' });

    const catCol = columns.find(c => c.toLowerCase().includes('category'));
    if (catCol) {
        const topCat = getMostFrequent(filteredData.map(r => r[catCol]).filter(Boolean));
        if (topCat) tags.push({ text: topCat, type: 'neutral', icon: '🏷' });
    }

    return tags.slice(0, 5); // giới hạn 5 tags
}

/** Tìm giá trị xuất hiện nhiều nhất */
function getMostFrequent(arr) {
    const freq = {};
    arr.forEach(v => { freq[v] = (freq[v] || 0) + 1; });
    return Object.keys(freq).sort((a, b) => freq[b] - freq[a])[0] || null;
}

function analyzeSentiment() {
    return { label: 'Tích cực', score: 8.5 };
}

// ============================================================
// FILTERING SYSTEM
// ============================================================

/** Lấy dữ liệu đã lọc theo activeFilters */
function getFilteredData() {
    if (!currentData.length) return [];
    const dateCol = columns.find(c => c.toLowerCase().includes('date')) || columns[0];
    const regionCol = columns.find(c => /region|khu.?v[ựư]c|chi.?nh[aá]nh|branch|city|province/i.test(c));
    const catCol = columns.find(c => c.toLowerCase().includes('category'));

    return currentData.filter(row => {
        // Date filter
        if (activeFilters.dateFrom) {
            const d = new Date(row[dateCol]);
            if (isNaN(d) || d < new Date(activeFilters.dateFrom)) return false;
        }
        if (activeFilters.dateTo) {
            const d = new Date(row[dateCol]);
            if (isNaN(d) || d > new Date(activeFilters.dateTo + 'T23:59:59')) return false;
        }
        // Region filter
        if (activeFilters.region !== 'all' && regionCol) {
            if (row[regionCol] !== activeFilters.region) return false;
        }
        // Category filter
        if (activeFilters.category !== 'all' && catCol) {
            if (row[catCol] !== activeFilters.category) return false;
        }
        return true;
    });
}

/** Áp dụng period preset vào dateFrom/dateTo */
function applyPeriodPreset(period) {
    const now = new Date();
    const dateFromEl = document.getElementById('filter-date-from');
    const dateToEl   = document.getElementById('filter-date-to');
    if (period === 'all') {
        activeFilters.dateFrom = '';
        activeFilters.dateTo = '';
        if (dateFromEl) dateFromEl.value = '';
        if (dateToEl)   dateToEl.value = '';
        return;
    }
    const toStr = now.toISOString().split('T')[0];
    const monthOffsets = { month: 0, quarter: -2, half: -5, year: null };
    let fromDate;
    if (period === 'year') {
        fromDate = new Date(now.getFullYear(), 0, 1);
    } else {
        fromDate = new Date(now.getFullYear(), now.getMonth() + monthOffsets[period], 1);
    }
    const fromStr = fromDate.toISOString().split('T')[0];
    activeFilters.dateFrom = fromStr;
    activeFilters.dateTo   = toStr;
    if (dateFromEl) dateFromEl.value = fromStr;
    if (dateToEl)   dateToEl.value   = toStr;
}

/** Chạy lại toàn bộ dashboard với filteredData */
function applyAllFilters() {
    filteredData = getFilteredData();
    updateFilterBadge();
    if (filteredData.length === 0) {
        showToast('Không có dữ liệu phù hợp với bộ lọc', 'info', 'ph-funnel');
        return;
    }
    runAIAnalytics();
    applyFilters();
    showToast(`Đang hiển thị ${filteredData.length} / ${currentData.length} bản ghi`, 'success', 'ph-funnel-simple');
}

/** Populate region + category chips từ dữ liệu thực */
function populateFilterChips() {
    const regionCol = columns.find(c => /region|khu.?v[ựư]c|chi.?nh[aá]nh|branch|city|province/i.test(c));
    const catCol    = columns.find(c => c.toLowerCase().includes('category'));

    const regionContainer = document.getElementById('region-chips');
    const regionGroup = document.getElementById('region-filter-group');
    const regionSep   = document.getElementById('region-sep');
    if (regionContainer && regionCol) {
        const regions = [...new Set(currentData.map(r => r[regionCol]).filter(Boolean))].sort();
        if (regions.length) {
            regionGroup?.classList.remove('hidden');
            regionSep?.classList.remove('hidden');
            regionContainer.innerHTML =
                `<button class="chip active" data-region="all">Tất cả</button>` +
                regions.map(r => `<button class="chip" data-region="${r}">${r}</button>`).join('');
        } else {
            regionGroup?.classList.add('hidden');
            regionSep?.classList.add('hidden');
        }
    } else {
        regionGroup?.classList.add('hidden');
        regionSep?.classList.add('hidden');
    }

    const catContainer = document.getElementById('category-chips');
    const catGroup = document.getElementById('cat-filter-group');
    const catSep   = document.getElementById('cat-sep');
    if (catContainer && catCol) {
        const cats = [...new Set(currentData.map(r => r[catCol]).filter(Boolean))].sort();
        if (cats.length) {
            catGroup?.classList.remove('hidden');
            catSep?.classList.remove('hidden');
            catContainer.innerHTML =
                `<button class="chip active" data-cat="all">Tất cả</button>` +
                cats.map(c => `<button class="chip" data-cat="${c}">${c}</button>`).join('');
        } else {
            catGroup?.classList.add('hidden');
            catSep?.classList.add('hidden');
        }
    } else {
        catGroup?.classList.add('hidden');
        catSep?.classList.add('hidden');
    }
}

/** Cập nhật badge số bộ lọc đang active */
function updateFilterBadge() {
    let count = 0;
    if (activeFilters.dateFrom || activeFilters.dateTo) count++;
    if (activeFilters.region !== 'all') count++;
    if (activeFilters.category !== 'all') count++;

    const badge   = document.getElementById('filter-active-count');
    const numEl   = document.getElementById('filter-count-num');
    const resetBtn = document.getElementById('btn-reset-filters');

    if (count > 0) {
        badge?.classList.remove('hidden');
        resetBtn?.classList.remove('hidden');
        if (numEl) numEl.textContent = count;
    } else {
        badge?.classList.add('hidden');
        resetBtn?.classList.add('hidden');
    }
}

/** Đặt lại tất cả bộ lọc về mặc định */
function resetAllFilters(reRender = true) {
    activeFilters = { period: 'all', dateFrom: '', dateTo: '', region: 'all', category: 'all' };
    // Reset period chips
    document.querySelectorAll('#period-chips .chip').forEach(c => c.classList.remove('active'));
    document.querySelector('#period-chips [data-period="all"]')?.classList.add('active');
    // Reset date inputs
    const df = document.getElementById('filter-date-from');
    const dt = document.getElementById('filter-date-to');
    if (df) df.value = '';
    if (dt) dt.value = '';
    // Reset region chips
    document.querySelectorAll('#region-chips .chip').forEach(c => c.classList.remove('active'));
    document.querySelector('#region-chips [data-region="all"]')?.classList.add('active');
    // Reset category chips
    document.querySelectorAll('#category-chips .chip').forEach(c => c.classList.remove('active'));
    document.querySelector('#category-chips [data-cat="all"]')?.classList.add('active');
    updateFilterBadge();
    if (reRender && currentData.length) {
        filteredData = [...currentData];
        runAIAnalytics();
        applyFilters();
        showToast('Đã xóa tất cả bộ lọc', 'info', 'ph-funnel-x');
    }
}

function populateCategoryFilter() {
    const categoryCol = columns.find(c => c.toLowerCase().includes('category'));
    if (!categoryCol) return;
    const categories = [...new Set(currentData.map(r => r[categoryCol]))].filter(Boolean);
    const filter = document.getElementById('category-filter');
    if (filter) filter.innerHTML = '<option value="all">Tất cả danh mục</option>' + categories.map(c => `<option value="${c}">${c}</option>`).join('');
}

function generateAIInsights(monthlySales, segments, _sentiment) {
    if (!monthlySales || monthlySales.length === 0) return;

    const kf = document.getElementById('kpi-forecast');
    const kr = document.getElementById('kpi-revenue');
    const kv = document.getElementById('kpi-vips');

    const currentMonthRevenue = monthlySales[monthlySales.length - 1].total;
    const forecastedRevenue = calculateForecast(monthlySales);

    if(kf) kf.textContent = Math.round(forecastedRevenue).toLocaleString('vi-VN') + ' đ';
    if(kr) kr.textContent = Math.round(currentMonthRevenue).toLocaleString('vi-VN') + ' đ';
    if(kv) kv.textContent = segments['VIP'] || 0;

    // Sentiment KH chi tiết
    const sentimentData = analyzeSentimentDeep(monthlySales);
    renderSentimentPanel(sentimentData);

    // Update Activity KPIs (Syncing both tabs)
    updateActivityKPIs(currentMonthRevenue, forecastedRevenue, segments);
}

function updateActivityKPIs(rev, fore, segments) {
    const activityTab = document.getElementById('tab-activity');
    if (!activityTab) return;

    // Number of Emails (simulated based on transaction count)
    const emailValue = activityTab.querySelector('.kpi-card:nth-child(1) .value');
    if (emailValue) emailValue.textContent = currentData.length * 5;

    // Number of Calls
    const callValue = activityTab.querySelector('.kpi-card:nth-child(2) .value');
    if (callValue) callValue.textContent = currentData.length * 3;

    // Number of Meetings
    const meetValue = activityTab.querySelector('.kpi-card:nth-child(3) .value');
    if (meetValue) meetValue.textContent = Math.round(currentData.length * 1.2);

    // Response Rate (Simulated based on sentiment/rating)
    const respValue = activityTab.querySelector('.kpi-card:nth-child(4) .value');
    if (respValue) respValue.textContent = "88%";

    // Conversion
    const convValue = activityTab.querySelector('.kpi-card:nth-child(5) .value');
    if (convValue) convValue.textContent = "32";

    // Success Rate
    const succValue = activityTab.querySelector('.kpi-card:nth-child(6) .value');
    if (succValue) succValue.textContent = "65%";
}

function updateForecastChart(history, forecast) {
    const ctx = document.getElementById('forecastChart');
    if (!ctx) return;
    if (!window.Chart) {
        console.warn('Chart.js is not loaded; skipping forecast chart.');
        return;
    }
    if (forecastChart) forecastChart.destroy();
    forecastChart = new Chart(ctx, {
        type: 'line',
        data: { labels: history.map(h => h.month), datasets: [{ label: 'Doanh thu', data: history.map(h => h.total), borderColor: '#6366f1' }] },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

function updateSegmentChart(segments) {
    const ctx = document.getElementById('segmentChart');
    if (!ctx) return;
    if (!window.Chart) {
        console.warn('Chart.js is not loaded; skipping segment chart.');
        return;
    }
    if (segmentChart) segmentChart.destroy();
    segmentChart = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: Object.keys(segments), datasets: [{ data: Object.values(segments), backgroundColor: ['#6366f1', '#06b6d4', '#3b82f6', '#8b5cf6'] }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '70%' }
    });
}

function applyFilters() {
    tablePage = 1;
    applyTableView();
}

/** Apply search + category filter on top of filteredData, then render */
function applyTableView() {
    const q = document.getElementById('table-search')?.value.trim().toLowerCase() || '';
    const cat = document.getElementById('category-filter')?.value || 'all';
    const catCol = columns.find(c => c.toLowerCase().includes('category'));
    let d = filteredData;
    if (cat !== 'all' && catCol) d = d.filter(r => r[catCol] === cat);
    if (q) d = d.filter(r => columns.some(c => String(r[c] ?? '').toLowerCase().includes(q)));
    renderTable(d);
}

function renderTable(data) {
    const header = document.getElementById('table-header');
    const body   = document.getElementById('table-body');
    if (!header || !body || !columns?.length) return;

    const statusCol = columns.find(c => /^status$|tr[aạ]ng.?th[aá]i/i.test(c));
    const addVirtual = !statusCol;

    // Header
    header.innerHTML = columns.map(c => `<th>${c}</th>`).join('') +
        (addVirtual ? '<th>Trạng thái</th>' : '');

    // Pagination
    const total = data.length;
    const totalPages = Math.max(1, Math.ceil(total / TABLE_PAGE_SIZE));
    tablePage = Math.min(tablePage, totalPages);
    const start = (tablePage - 1) * TABLE_PAGE_SIZE;
    const pageData = data.slice(start, start + TABLE_PAGE_SIZE);

    // Rows
    body.innerHTML = pageData.map(row => {
        const cells = columns.map(col => {
            const val = row[col] ?? '';
            if (col === statusCol) {
                const s = getStatusInfo(String(val));
                return `<td><span class="status-badge ${s.cls}">${s.label}</span></td>`;
            }
            return `<td>${val}</td>`;
        }).join('');
        const vs = addVirtual ? (() => { const s = getRowStatus(row); return `<td><span class="status-badge ${s.cls}">${s.label}</span></td>`; })() : '';
        return `<tr>${cells}${vs}</tr>`;
    }).join('');

    // Footer info
    const infoEl = document.getElementById('table-info');
    if (infoEl) {
        if (total === 0) {
            infoEl.innerHTML = '<em>Không có dữ liệu</em>';
        } else {
            const end = Math.min(start + TABLE_PAGE_SIZE, total);
            infoEl.innerHTML = `Hiển thị <strong>${start + 1}–${end}</strong> / <strong>${total}</strong> đơn hàng`;
        }
    }
    renderPagination(totalPages);
}

function getRowStatus(row) {
    const rCol = columns.find(c => /rating|review|score|star/i.test(c));
    if (rCol) {
        const r = parseFloat(row[rCol]) || 0;
        if (r >= 4) return { label: 'Hoàn thành', cls: 'completed' };
        if (r === 3) return { label: 'Đang xử lý', cls: 'processing' };
        return { label: 'Đã hủy', cls: 'cancelled' };
    }
    const seed = String(row[columns[0]] || '').charCodeAt(0) % 3;
    return [{ label: 'Hoàn thành', cls: 'completed' }, { label: 'Đang xử lý', cls: 'processing' }, { label: 'Đã hủy', cls: 'cancelled' }][seed];
}

function getStatusInfo(val) {
    if (/hoàn.?thành|complete|done|delivered|success/i.test(val)) return { label: 'Hoàn thành', cls: 'completed' };
    if (/xử.?lý|processing|pending|in.?progress/i.test(val))   return { label: 'Đang xử lý', cls: 'processing' };
    if (/hủy|cancel|reject|failed/i.test(val))                  return { label: 'Đã hủy', cls: 'cancelled' };
    return { label: val, cls: 'processing' };
}

function renderPagination(totalPages) {
    const el = document.getElementById('table-pagination');
    if (!el) return;
    if (totalPages <= 1) { el.innerHTML = ''; return; }

    const range = getPaginationRange(tablePage, totalPages);
    const prev = `<button class="page-btn" data-page="${tablePage - 1}" ${tablePage === 1 ? 'disabled' : ''}><i class="ph ph-caret-left"></i></button>`;
    const next = `<button class="page-btn" data-page="${tablePage + 1}" ${tablePage === totalPages ? 'disabled' : ''}><i class="ph ph-caret-right"></i></button>`;
    const mid  = range.map(p => p === '...'
        ? `<span class="page-ellipsis">…</span>`
        : `<button class="page-btn${p === tablePage ? ' active' : ''}" data-page="${p}">${p}</button>`
    ).join('');
    el.innerHTML = prev + mid + next;
}

function getPaginationRange(cur, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    if (cur <= 4)         return [1,2,3,4,5,'...',total];
    if (cur >= total - 3) return [1,'...',total-4,total-3,total-2,total-1,total];
    return [1,'...',cur-1,cur,cur+1,'...',total];
}

function exportTableCSV() {
    if (!filteredData.length) return showToast('Không có dữ liệu', 'info', 'ph-warning');
    const statusCol = columns.find(c => /^status$|tr[aạ]ng.?th[aá]i/i.test(c));
    const hdrs = statusCol ? columns : [...columns, 'Trạng thái'];
    const rows = [hdrs.join(',')];
    filteredData.forEach(row => {
        const vals = columns.map(c => `"${String(row[c] ?? '').replace(/"/g, '""')}"`);
        if (!statusCol) vals.push(`"${getRowStatus(row).label}"`);
        rows.push(vals.join(','));
    });
    const blob = new Blob(['\uFEFF' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `orders_${new Date().toISOString().slice(0,10)}.csv` });
    a.click(); URL.revokeObjectURL(a.href);
    showToast('Xuất CSV thành công!', 'success', 'ph-file-csv');
}

function exportTableExcel() {
    if (!filteredData.length) return showToast('Không có dữ liệu', 'info', 'ph-warning');
    if (typeof XLSX === 'undefined') return showToast('Thư viện XLSX chưa tải', 'info', 'ph-spinner');
    const statusCol = columns.find(c => /^status$|tr[aạ]ng.?th[aá]i/i.test(c));
    const hdrs = statusCol ? columns : [...columns, 'Trạng thái'];
    const wsData = [hdrs, ...filteredData.map(row => {
        const vals = columns.map(c => row[c] ?? '');
        if (!statusCol) vals.push(getRowStatus(row).label);
        return vals;
    })];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(wsData), 'Orders');
    XLSX.writeFile(wb, `orders_${new Date().toISOString().slice(0,10)}.xlsx`);
    showToast('Xuất Excel thành công!', 'success', 'ph-file-xls');
}

function loadDemoData() {
    fetch('sales_data.csv').then(res => res.text()).then(text => {
        Papa.parse(text, { header: true, dynamicTyping: true, complete: function(r) { currentData = r.data; columns = r.meta.fields; initDashboard(); } });
    });
}

function showToast(m, t, i) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${t}`;
    toast.innerHTML = `<i class="ph ${i}"></i> <span>${m}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 400); }, 3000);

    // Đồng bộ với notification panel
    addNotification(m, t, i);
}

function addNotification(m, t, i) {
    notifications.unshift({ message: m, type: t, icon: i, time: new Date() });
    if (notifications.length > 20) notifications.pop();
    renderNotifications();
}

function renderNotifications() {
    const list = document.getElementById('notif-list');
    const badge = document.querySelector('.notif-badge');
    const panel = document.getElementById('notif-panel');
    if (!list) return;

    if (notifications.length === 0) {
        list.innerHTML = '<div class="notif-empty">Không có thông báo mới</div>';
        if (badge) badge.classList.add('hidden');
        return;
    }

    // Cập nhật số lượng thông báo chưa đọc
    if (badge && panel && panel.classList.contains('hidden')) {
        badge.textContent = notifications.length > 9 ? '9+' : notifications.length;
        badge.classList.remove('hidden');
    }

    list.innerHTML = notifications.map(n => `
        <div class="notif-item ${n.type === 'error' ? 'important' : ''}">
            <div style="display: flex; gap: 8px; align-items: start;">
                <div style="font-size: 1.2rem; color: ${n.type === 'error' ? '#ef4444' : n.type === 'success' ? '#10b981' : '#6366f1'}">
                    <i class="ph ${n.icon}"></i>
                </div>
                <div>
                    <div style="margin-bottom: 4px;">${n.message}</div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">${n.time.toLocaleTimeString('vi-VN')}</div>
                </div>
            </div>
        </div>
    `).join('');
}

function addToHistory(f) { console.log("Added to history:", f); }

function renderClusterChartDeepDefault(s) {
    const canvas = document.getElementById('segmentChartDeep');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (deepSegmentChart) deepSegmentChart.destroy();
    deepSegmentChart = new Chart(ctx, { type: 'polarArea', data: { labels: Object.keys(s), datasets: [{ data: Object.values(s), backgroundColor: ['#6366f1', '#06b6d4', '#3b82f6', '#8b5cf6'] }] }, options: { responsive: true, maintainAspectRatio: false } });
}

function renderActivityCharts() {
    showToast('Đang đồng bộ dữ liệu hoạt động...', 'info', 'ph-arrows-clockwise');

    // --- DYNAMIC LOGIC BASED ON CSV (uses filteredData) ---
    const customerCounts = {};
    filteredData.forEach(row => {
        const id = row.CustomerID;
        if (id) customerCounts[id] = (customerCounts[id] || 0) + 1;
    });

    let recurring = 0;
    let newCust = 0;
    Object.values(customerCounts).forEach(count => {
        if (count > 1) recurring++;
        else newCust++;
    });

    const dayOfWeekData = [0, 0, 0, 0, 0, 0, 0]; // Sun-Sat
    filteredData.forEach(row => {
        const date = new Date(row.OrderDate);
        if (!isNaN(date.getTime())) {
            dayOfWeekData[date.getDay()]++;
        }
    });
    // Shift so Mon is first: [Mon, Tue, Wed, Thu, Fri, Sat, Sun]
    const shiftedDays = [...dayOfWeekData.slice(1), dayOfWeekData[0]];

    // --- CHART INITIALIZATION ---

    // 1. Lead Source Analysis (Pie) - Premium Colors
    const lsCtx = document.getElementById('leadSourceChart').getContext('2d');
    if (leadSourceChart) leadSourceChart.destroy();
    leadSourceChart = new Chart(lsCtx, {
        type: 'pie',
        data: {
            labels: ['Google Ads', 'Direct', 'Social Media', 'Referral', 'Email'],
            datasets: [{
                data: [40, 20, 25, 10, 5],
                backgroundColor: ['#06b6d4', '#6366f1', '#f59e0b', '#10b981', '#ef4444'],
                borderWidth: 2,
                borderColor: '#0f1117'
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            plugins: { 
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Outfit' }, usePointStyle: true } },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            if (label) label += ': ';
                            if (context.parsed !== null) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((context.parsed / total) * 100) + '%';
                                label += context.parsed + ' (' + percentage + ')';
                            }
                            return label;
                        }
                    }
                }
            } 
        }
    });

    // 2. Emails Sent per Day (Bar) - Matching Cyan
    const edCtx = document.getElementById('emailsDayChart').getContext('2d');
    if (emailsDayChart) emailsDayChart.destroy();
    emailsDayChart = new Chart(edCtx, {
        type: 'bar',
        data: {
            labels: ['M', 'T', 'W', 'T', 'F', 'S', 'S'],
            datasets: [{
                label: 'Emails',
                data: shiftedDays.map(v => v * 12 + 5), // Simulated based on order volume
                backgroundColor: '#06b6d4',
                borderRadius: 8,
                hoverBackgroundColor: '#22d3ee'
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { 
                y: { display: false }, 
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } } 
            },
            plugins: { legend: { display: false } }
        }
    });

    // 3. Follow-up Sessions (Horizontal Bar)
    const fsCtx = document.getElementById('followUpChart').getContext('2d');
    if (followUpChart) followUpChart.destroy();
    followUpChart = new Chart(fsCtx, {
        type: 'bar',
        data: {
            labels: ['Intro', 'Demo', 'Proposal', 'Closing'],
            datasets: [{
                label: 'Sessions',
                data: [recurring * 5, recurring * 3, recurring * 2, recurring],
                backgroundColor: '#6366f1',
                borderRadius: 8
            }]
        },
        options: { 
            indexAxis: 'y', 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { 
                x: { display: false }, 
                y: { grid: { display: false }, ticks: { color: '#94a3b8' } } 
            },
            plugins: { legend: { display: false } }
        }
    });

    // 4. New vs Recurring Stats (Doughnut) - Dynamic
    const ssCtx = document.getElementById('salesStatsChart').getContext('2d');
    if (salesStatsChart) salesStatsChart.destroy();
    salesStatsChart = new Chart(ssCtx, {
        type: 'doughnut',
        data: {
            labels: ['New Customers', 'Recurring'],
            datasets: [{
                data: [newCust, recurring],
                backgroundColor: ['#06b6d4', '#f59e0b'],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            cutout: '75%', 
            plugins: { 
                legend: { position: 'bottom', labels: { color: '#94a3b8', usePointStyle: true } } 
            } 
        }
    });

    // 5. Calls per Day (Bar) - Matching Orange
    const cdCtx = document.getElementById('callsDayChart').getContext('2d');
    if (callsDayChart) callsDayChart.destroy();
    callsDayChart = new Chart(cdCtx, {
        type: 'bar',
        data: {
            labels: ['M', 'T', 'W', 'T', 'F', 'S', 'S'],
            datasets: [{
                label: 'Calls',
                data: shiftedDays.map(v => v * 8 + 3),
                backgroundColor: '#f59e0b',
                borderRadius: 8
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { 
                y: { display: false }, 
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } } 
            },
            plugins: { legend: { display: false } }
        }
    });

    // 6. Response Time (Area Line) - Gradient
    const rtCtx = document.getElementById('responseTimeChart').getContext('2d');
    if (responseTimeChart) responseTimeChart.destroy();
    
    const gradient = rtCtx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.3)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0)');

    responseTimeChart = new Chart(rtCtx, {
        type: 'line',
        data: {
            labels: ['1h', '2h', '3h', '4h', '5h', '6h', '7h'],
            datasets: [{
                label: 'Avg Response (min)',
                data: [15, 22, 18, 30, 25, 35, 28],
                borderColor: '#06b6d4',
                backgroundColor: gradient,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#06b6d4'
            }]
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            scales: { 
                y: { display: false }, 
                x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } } 
            },
            plugins: { legend: { display: false } }
        }
    });

    // 7. Staff Performance (Radar/Bar) - Dummy data for empty state
    let spCtx = document.getElementById('staffPerformanceChart');
    if (spCtx) {
        if (window.staffPerformanceChartObj) window.staffPerformanceChartObj.destroy();
        window.staffPerformanceChartObj = new Chart(spCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Alice', 'Bob', 'Charlie', 'David'],
                datasets: [
                    { label: 'Cuộc gọi', data: [45, 30, 60, 25], backgroundColor: '#6366f1' },
                    { label: 'Email', data: [80, 50, 90, 40], backgroundColor: '#06b6d4' },
                    { label: 'Gặp mặt', data: [15, 10, 20, 5], backgroundColor: '#f59e0b' }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, grid: { display: false }, ticks: { color: '#94a3b8' } },
                    y: { stacked: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } }
                },
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#94a3b8', usePointStyle: true, boxWidth: 8 } }
                }
            }
        });
    }

    // 8. Audit Log Dummy Data
    const auditLog = document.getElementById('audit-log');
    if (auditLog) {
        auditLog.innerHTML = `
            <div style="display:flex; gap:12px; margin-bottom:12px; align-items:flex-start;">
                <div style="width:32px; height:32px; border-radius:50%; background:rgba(16,185,129,0.1); color:#10b981; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><i class="ph-fill ph-check-circle"></i></div>
                <div>
                    <p style="margin:0; font-size:0.9rem; color:#e2e8f0;"><strong>Admin</strong> đã tải lên dữ liệu sales_data.csv</p>
                    <span style="font-size:0.75rem; color:#94a3b8;">Vừa xong</span>
                </div>
            </div>
            <div style="display:flex; gap:12px; margin-bottom:12px; align-items:flex-start;">
                <div style="width:32px; height:32px; border-radius:50%; background:rgba(99,102,241,0.1); color:#6366f1; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><i class="ph-fill ph-robot"></i></div>
                <div>
                    <p style="margin:0; font-size:0.9rem; color:#e2e8f0;"><strong>AI Forecast</strong> hoàn tất phân tích dự báo</p>
                    <span style="font-size:0.75rem; color:#94a3b8;">2 phút trước</span>
                </div>
            </div>
            <div style="display:flex; gap:12px; margin-bottom:12px; align-items:flex-start;">
                <div style="width:32px; height:32px; border-radius:50%; background:rgba(6,182,212,0.1); color:#06b6d4; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><i class="ph-fill ph-envelope-simple"></i></div>
                <div>
                    <p style="margin:0; font-size:0.9rem; color:#e2e8f0;"><strong>Hệ thống</strong> gửi 125 email tự động</p>
                    <span style="font-size:0.75rem; color:#94a3b8;">15 phút trước</span>
                </div>
            </div>
            <div style="display:flex; gap:12px; margin-bottom:0; align-items:flex-start;">
                <div style="width:32px; height:32px; border-radius:50%; background:rgba(245,158,11,0.1); color:#f59e0b; display:flex; align-items:center; justify-content:center; flex-shrink:0;"><i class="ph-fill ph-warning-circle"></i></div>
                <div>
                    <p style="margin:0; font-size:0.9rem; color:#e2e8f0;"><strong>Cảnh báo:</strong> Tỷ lệ phản hồi giảm 5%</p>
                    <span style="font-size:0.75rem; color:#94a3b8;">1 giờ trước</span>
                </div>
            </div>
        `;
        auditLog.style.overflowY = 'auto';
        auditLog.style.maxHeight = '260px';
    }
}

function exportToPDF() { 
    showToast('Đang tạo báo cáo PDF chuyên nghiệp...', 'info', 'ph-spinner');
    const element = document.getElementById('dashboard');
    const opt = {
      margin:       0.2,
      filename:     `DataInsight_Executive_Report_${new Date().toISOString().slice(0,10)}.pdf`,
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true, logging: false, backgroundColor: '#0f1117' },
      jsPDF:        { unit: 'in', format: 'a3', orientation: 'landscape' }
    };
    
    html2pdf().set(opt).from(element).save().then(() => {
        showToast('Đã tải xuống báo cáo PDF!', 'success', 'ph-check-circle');
    });
}

// --- CONVERSATIONAL BI (CHAT VỚI DỮ LIỆU) ---
document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chat-input');
    const btnSend = document.getElementById('btn-chat-send');
    const chatBody = document.getElementById('chat-body');

    function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        // Thêm tin nhắn của User
        const userMsg = document.createElement('div');
        userMsg.className = 'chat-message user';
        userMsg.innerHTML = `<div class="msg-bubble">${text}</div>`;
        chatBody.appendChild(userMsg);
        chatInput.value = '';
        chatBody.scrollTop = chatBody.scrollHeight;

        // Loading indicator
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'chat-message ai';
        loadingMsg.innerHTML = `<div class="msg-bubble"><span class="ph-spinner ph-spin" style="font-size: 1.2rem;"></span> Đang suy nghĩ...</div>`;
        chatBody.appendChild(loadingMsg);
        chatBody.scrollTop = chatBody.scrollHeight;

        // Gọi API Gemini từ backend
        fetch(`${AI_SERVICE_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        })
        .then(res => res.json())
        .then(data => {
            chatBody.removeChild(loadingMsg);
            const aiMsg = document.createElement('div');
            aiMsg.className = 'chat-message ai';
            aiMsg.innerHTML = `<div class="msg-bubble">${data.reply ? data.reply.replace(/\\n/g, '<br>') : 'Không có phản hồi.'}</div>`;
            chatBody.appendChild(aiMsg);
            chatBody.scrollTop = chatBody.scrollHeight;
        })
        .catch(err => {
            chatBody.removeChild(loadingMsg);
            const aiMsg = document.createElement('div');
            aiMsg.className = 'chat-message ai';
            
            // Fallback mock nếu backend chưa mở hoặc lỗi
            let responseText = "Xin lỗi, tôi chưa hiểu ý bạn.";
            const lower = text.toLowerCase();
            if (lower.includes('vùng') && lower.includes('thấp')) {
                responseText = "Theo dữ liệu hiện tại, vùng <strong>Đà Nẵng</strong> đang có doanh thu thấp nhất trong kỳ.";
            } else if (lower.includes('tăng trưởng') || lower.includes('dự báo')) {
                responseText = "Thuật toán dự báo doanh thu tháng tới có thể đạt <strong>tăng trưởng 8.4%</strong>.";
            } else {
                responseText = `Lỗi kết nối AI Backend (${err.message}). Vui lòng khởi động backend để dùng Gemini.`;
            }

            aiMsg.innerHTML = `<div class="msg-bubble">${responseText}</div>`;
            chatBody.appendChild(aiMsg);
            chatBody.scrollTop = chatBody.scrollHeight;
        });
    }

    if (btnSend) btnSend.addEventListener('click', sendChatMessage);
    if (chatInput) chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    // --- CUSTOMIZABLE LAYOUT (DRAG AND DROP) ---
    // Make Grid Rows sortable
    const sortableConfigs = {
        animation: 150,
        ghostClass: 'sortable-ghost',
        handle: '.card-header, .kpi-meta, h3', // Kéo bằng header
        easing: "cubic-bezier(1, 0, 0, 1)"
    };

    setTimeout(() => {
        const visualRow = document.querySelector('.visual-row');
        if (visualRow && typeof Sortable !== 'undefined') {
            Sortable.create(visualRow, sortableConfigs);
        }

        const activityRows = document.querySelectorAll('.activity-row');
        activityRows.forEach(row => {
            if (typeof Sortable !== 'undefined') Sortable.create(row, sortableConfigs);
        });
        
        const kpiGrid = document.querySelector('.kpi-grid');
        if (kpiGrid && typeof Sortable !== 'undefined') {
            Sortable.create(kpiGrid, sortableConfigs);
        }
    }, 1000); // Chờ DOM render xong biểu đồ
});
