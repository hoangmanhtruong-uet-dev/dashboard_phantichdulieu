const screens = document.querySelectorAll('.screen');
const navButtons = document.querySelectorAll('.bottom-nav button');
const shell = document.querySelector('.mobile-shell');
const modal = document.getElementById('modal');
const searchOverlay = document.getElementById('search-overlay');
const secondaryContent = document.getElementById('secondary-content');
const secondaryHeader = document.getElementById('secondary-header');
let currentBaseScreen = 'home';
let currentPage = null;
let authSession = null;
let activeImport = null;
let currentWebScreen = 'overview';
const resourceRequests = new window.NexusResource.LatestRequestRegistry();
const resourceQuery = new Map();
const pageHistory = [];
const publicPages = new Set(['splash','onboarding','login','forgot-password','register','reset-password']);

const pageRegistry = {
  'splash': { title: 'Khởi động', type: 'auth', icon: 'ph-chart-polar', headline: 'Biến dữ liệu thành quyết định.', copy: 'Một nơi duy nhất để theo dõi, phân tích và hành động dựa trên dữ liệu.', cta: 'Bắt đầu', next: 'onboarding' },
  'onboarding': { title: 'Giới thiệu', type: 'onboarding' },
  'login': { title: 'Đăng nhập', type: 'form', kicker: 'CHÀO MỪNG TRỞ LẠI', headline: 'Đăng nhập Nexus', fields: ['Email công việc', 'Mật khẩu'], cta: 'Đăng nhập', nextScreen: 'home', link: 'Quên mật khẩu?', linkPage: 'forgot-password', secondaryLink: 'Tạo tài khoản', secondaryLinkPage: 'register' },
  'forgot-password': { title: 'Quên mật khẩu', type: 'form', kicker: 'KHÔI PHỤC TÀI KHOẢN', headline: 'Nhận liên kết đặt lại', fields: ['Email công việc'], cta: 'Gửi liên kết', note: 'Chúng tôi sẽ gửi hướng dẫn khôi phục tới email của bạn.' },
  'register': { title: 'Tạo tài khoản', type: 'form', kicker: 'BẮT ĐẦU VỚI NEXUS', headline: 'Tạo Workspace của bạn', fields: ['Họ và tên', 'Email công việc', 'Tên Workspace', 'Mật khẩu'], cta: 'Tạo tài khoản', link: 'Đã có tài khoản?', linkPage: 'login' },
  'reset-password': { title: 'Đặt lại mật khẩu', type: 'form', kicker: 'BẢO MẬT TÀI KHOẢN', headline: 'Tạo mật khẩu mới', fields: ['Mật khẩu mới'], cta: 'Đặt lại mật khẩu' },
  'revenue': { title: 'Chi tiết doanh thu', type: 'metric', kicker: 'DOANH THU', value: '₫124,592', change: '+12.5%', description: 'Doanh thu tăng mạnh nhờ Organic Search và chiến dịch Summer Sale.', rows: [['Organic Search','₫52,480'],['Direct','₫37,376'],['Paid Social','₫21,181'],['Referral','₫13,555']] },
  'traffic': { title: 'Phân bổ doanh thu', type: 'metric', kicker: 'DOANH THU THEO DANH MỤC', value: '24,892', change: '+9.8%', description: 'Phân bổ doanh thu từ dữ liệu đã nhập trong Workspace.', rows: [] },
  'users': { title: 'Phân tích người dùng', type: 'metric', kicker: 'ACTIVE USERS', value: '42,108', change: '+8.2%', description: 'Tệp người dùng mới tăng, tập trung tại Hà Nội và TP. Hồ Chí Minh.', rows: [['Người dùng mới','28,419'],['Quay lại','13,689'],['Mobile','64%'],['Desktop','31%']] },
  'conversion': { title: 'Chuyển đổi', type: 'metric', kicker: 'CONVERSION RATE', value: '3.42%', change: '−0.5%', description: 'Mobile đang thấp hơn desktop; luồng checkout là điểm cần tối ưu.', rows: [['Xem sản phẩm','100%'],['Thêm giỏ hàng','21.8%'],['Bắt đầu checkout','8.4%'],['Hoàn tất','3.42%']] },
  'insight-detail': { title: 'Chi tiết Insight', type: 'article', tag: 'AI INSIGHT · CƠ HỘI', headline: 'Google Search tạo nhóm khách hàng quay lại tốt nhất', copy: 'Khách hàng đến từ Organic Search có tỷ lệ quay lại trong 30 ngày cao hơn 34%. Giá trị đơn hàng trung bình của nhóm này cũng cao hơn 12%.', bullets: ['Tăng nội dung SEO cho nhóm sản phẩm chủ lực','Tạo remarketing riêng cho khách Organic','Theo dõi cohort trong 30 ngày tới'] },
  'alert-detail': { title: 'Chi tiết cảnh báo', type: 'article', tag: 'NGHIÊM TRỌNG · 10:24', headline: 'Doanh thu giảm bất thường 21%', copy: 'Mức giảm bắt đầu lúc 08:30 và tập trung ở Paid Social. Organic Search vẫn hoạt động bình thường.', bullets: ['Kiểm tra trạng thái Facebook Ads','Đối chiếu thay đổi ngân sách sáng nay','Bật theo dõi mỗi 30 phút'] },
  'reports': { title: 'Báo cáo', type: 'list', kicker: '8 BÁO CÁO', headline: 'Thư viện báo cáo', cta: 'Tạo báo cáo', ctaPage: 'create-report', items: [['Báo cáo hiệu suất Q3','Cập nhật 2 giờ trước','report-detail'],['Dự báo doanh thu tháng 11','Cập nhật hôm qua','report-detail'],['Phân tích Cohort 2026','Cập nhật 3 ngày trước','report-detail']] },
  'report-detail': { title: 'Báo cáo Q3', type: 'report' },
  'create-report': { title: 'Tạo báo cáo', type: 'form', kicker: 'BÁO CÁO MỚI', headline: 'Thiết lập báo cáo', fields: ['Tên báo cáo', 'Khoảng thời gian', 'Nguồn dữ liệu', 'Chỉ số theo dõi'], cta: 'Tạo bản nháp', note: 'Bạn có thể chỉnh sửa bố cục và chia sẻ sau.' },
  'saved-views': { title: 'Chế độ xem đã lưu', type: 'list', kicker: '4 CHẾ ĐỘ XEM', headline: 'Không gian của bạn', items: [['Lưu lượng Mobile Việt Nam','Traffic · Mobile · 7 ngày','traffic'],['Hiệu suất Marketing','Revenue · Campaign · 30 ngày','revenue'],['Người dùng mới','New users · Acquisition','users'],['Checkout Funnel','Conversion · Funnel','conversion']] },
  'data-sources': { title: 'Nguồn dữ liệu', type: 'list', kicker: '3 KẾT NỐI', headline: 'Quản lý dữ liệu', cta: 'Thêm nguồn', ctaPage: 'add-source', items: [['Google Analytics','Đồng bộ 5 phút trước','traffic'],['Facebook Ads','Đồng bộ 12 phút trước','revenue'],['Sales Database','Đồng bộ 1 giờ trước','users']] },
  'add-source': { title: 'Thêm nguồn dữ liệu', type: 'sources' },
  'notifications': { title: 'Thông báo', type: 'list', kicker: 'HÔM NAY', headline: 'Trung tâm thông báo', items: [['Insight mới được phát hiện','Organic Search đang tăng mạnh','insight-detail'],['Báo cáo đã sẵn sàng','Báo cáo Q3 có thể tải xuống','report-detail'],['Cảnh báo doanh thu','Paid Social giảm bất thường','alert-detail']] },
  'global-search': { title: 'Tìm kiếm', type: 'search' },
  'advanced-filter': { title: 'Bộ lọc nâng cao', type: 'filter' },
  'edit-profile': { title: 'Chỉnh sửa hồ sơ', type: 'form', kicker: 'HỒ SƠ CÁ NHÂN', headline: 'Thông tin hiển thị', fields: ['Họ và tên', 'Chức danh', 'Email', 'Số điện thoại'], cta: 'Lưu thay đổi' },
  'account': { title: 'Thông tin tài khoản', type: 'settings', items: [['Họ và tên','Trương Anh'],['Email','truong@nexus.vn'],['Vai trò','Data Analyst'],['Workspace','Nexus Team']] },
  'settings': { title: 'Cài đặt ứng dụng', type: 'settings', items: [['Giao diện','Tự động'],['Ngôn ngữ','Tiếng Việt'],['Đơn vị tiền tệ','VND'],['Tuần bắt đầu','Thứ Hai']] },
  'security': { title: 'Bảo mật', type: 'settings', items: [['Xác thực hai lớp','Đã bật'],['Đổi mật khẩu','Cập nhật 30 ngày trước'],['Thiết bị đăng nhập','2 thiết bị'],['Lịch sử hoạt động','Xem chi tiết']] },
  'support': { title: 'Trợ giúp', type: 'list', kicker: 'NEXUS SUPPORT', headline: 'Chúng tôi có thể giúp gì?', items: [['Hướng dẫn sử dụng','Khám phá các tính năng chính','onboarding'],['Câu hỏi thường gặp','Câu trả lời nhanh cho bạn','support'],['Liên hệ hỗ trợ','Phản hồi trong 24 giờ','support'],['Về Nexus Analytics','Phiên bản UI 1.0','splash']] }
};

const productScreens = [
  ['01','Khởi động','splash'],['02','Giới thiệu','onboarding'],['03','Đăng nhập','login'],['04','Quên mật khẩu','forgot-password'],['05','Tổng quan','home'],['06','Phân tích','analytics'],['07','Chi tiết doanh thu','revenue'],['08','Nguồn truy cập','traffic'],['09','Người dùng','users'],['10','Chuyển đổi','conversion'],['11','Insights','insights'],['12','Chi tiết Insight','insight-detail'],['13','Cảnh báo','alerts'],['14','Chi tiết cảnh báo','alert-detail'],['15','Báo cáo','reports'],['16','Chi tiết báo cáo','report-detail'],['17','Tạo báo cáo','create-report'],['18','Chế độ xem đã lưu','saved-views'],['19','Nguồn dữ liệu','data-sources'],['20','Thêm nguồn dữ liệu','add-source'],['21','Thông báo','notifications'],['22','Tìm kiếm','global-search'],['23','Bộ lọc nâng cao','advanced-filter'],['24','Hồ sơ','profile'],['25','Chỉnh sửa hồ sơ','edit-profile'],['26','Thông tin tài khoản','account'],['27','Cài đặt ứng dụng','settings'],['28','Bảo mật','security'],['29','Trợ giúp','support']
];

function showScreen(name) {
  if (!authSession) return openPage('login');
  currentBaseScreen = name;
  currentPage = null;
  shell.classList.remove('immersive');
  screens.forEach(screen => screen.classList.toggle('active', screen.id === `${name}-screen`));
  navButtons.forEach(button => button.classList.toggle('active', button.dataset.screen === name));
  loadMobileScreen(name);
}

function openDetail(title, description) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-description').textContent = description;
  modal.classList.add('open');
}

function metricChart() {
  return `<div class="detail-chart"><div class="chart-line"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div><div class="chart-days"><span>T2</span><span>T3</span><span>T4</span><span>T5</span><span>T6</span><span>T7</span><span>CN</span></div></div>`;
}

const ingestionFields = [
  ['timestamp','Thời gian','DATE_TIME',true],
  ['revenue','Doanh thu','NUMBER',true],
  ['event_id','Mã sự kiện','STRING',false],
  ['customer_id','Mã khách hàng','STRING',false],
  ['category','Danh mục','STRING',false],
  ['region','Khu vực','STRING',false],
  ['source','Nguồn','STRING',false],
  ['product','Sản phẩm','STRING',false],
  ['currency','Tiền tệ','STRING',false],
  ['is_conversion','Chuyển đổi','BOOLEAN',false]
];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[character]));
}

function canManageIngestion() {
  return ['OWNER','ADMIN'].includes(authSession?.workspace?.role);
}

function ingestionWorkspace(compact = false) {
  const allowed = canManageIngestion();
  return `<section class="ingestion-workspace ${compact ? 'compact' : ''}">
    <input class="ingestion-file-input" type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden>
    <div class="ingestion-upload-card">
      <span><i class="ph-fill ph-file-arrow-up"></i></span>
      <div><b>Tải tệp CSV hoặc XLSX</b><small>Tối đa 10 MB · 100.000 dòng · tệp được kiểm tra trước khi nhập</small></div>
      <button class="${compact ? 'primary-button' : 'dark-button'}" data-action="choose-import-file" ${allowed ? '' : 'disabled'}>Chọn tệp</button>
    </div>
    ${allowed ? '' : '<p class="ingestion-permission"><i class="ph ph-lock"></i> Chỉ Owner hoặc Admin có thể nhập dữ liệu.</p>'}
    <div class="ingestion-status" role="status"></div>
    <div class="ingestion-preview"></div>
    <div class="ingestion-history"><p class="loading-state">Đang tải lịch sử nhập...</p></div>
  </section>`;
}

function renderPage(page) {
  if (page === 'ui-map') return `<div class="secondary-heading"><p class="eyebrow">MOBILE DESIGN SYSTEM</p><h1>29 màn hình UI</h1><p>Mở từng màn hình để kiểm tra giao diện và luồng điều hướng.</p></div><div class="ui-map">${productScreens.map(([number,title,key]) => `<button data-route="${key}"><span>${number}</span><b>${title}</b><i class="ph ph-caret-right"></i></button>`).join('')}</div>`;
  const config = pageRegistry[page];
  if (!config) return '';
  if (config.type === 'auth') return `<div class="auth-view"><span class="auth-logo"><i class="ph-fill ${config.icon}"></i></span><div><p class="eyebrow">NEXUS ANALYTICS</p><h1>${config.headline}</h1><p>${config.copy}</p><button class="primary-button" data-route="${config.next}">${config.cta}</button></div></div>`;
  if (config.type === 'onboarding') return `<div class="onboarding-view"><div class="onboarding-art"><i class="ph-fill ph-chart-line-up"></i><i class="ph-fill ph-sparkle"></i><i class="ph-fill ph-database"></i></div><p class="eyebrow">MỌI DỮ LIỆU · MỘT NƠI</p><h1>Hiểu doanh nghiệp trong vài giây</h1><p>Theo dõi chỉ số, nhận Insight từ AI và hành động ngay khi có biến động.</p><div class="onboarding-dots"><i></i><i></i><i></i></div><button class="primary-button" data-route="login">Tiếp tục</button></div>`;
  if (config.type === 'form') return `<div class="secondary-heading"><p class="eyebrow">${config.kicker}</p><h1>${config.headline}</h1>${config.note ? `<p>${config.note}</p>` : ''}</div><form class="mobile-form">${config.fields.map((field,index) => { const passwordField = field.toLowerCase().includes('khẩu'); const emailField = field.toLowerCase().includes('email'); return `<label>${field}<div><input type="${passwordField ? 'password' : emailField ? 'email' : 'text'}" autocomplete="${passwordField ? (currentPage === 'login' ? 'current-password' : 'new-password') : emailField ? 'email' : 'off'}" placeholder="${index ? `Nhập ${field.toLowerCase()}` : field}"/><i class="ph ph-${passwordField ? 'lock' : 'pencil-simple'}"></i></div></label>`; }).join('')}<p class="form-status" role="status"></p><button type="button" class="primary-button" ${config.nextScreen ? `data-screen="${config.nextScreen}"` : ''}>${config.cta}</button>${config.link ? `<button type="button" class="form-link" data-route="${config.linkPage}">${config.link}</button>` : ''}${config.secondaryLink ? `<button type="button" class="form-link" data-route="${config.secondaryLinkPage}">${config.secondaryLink}</button>` : ''}</form>`;
  if (['users','insight-detail','alert-detail'].includes(page)) return blockedMarkup(page === 'users' ? 'Backend chưa có mô hình sự kiện người dùng để cung cấp chỉ số này.' : 'Backend chưa có endpoint chi tiết; nội dung từ danh sách vẫn xem được trong hộp thoại.');
  if (['reports','saved-views','data-sources'].includes(page)) return `<div class="secondary-heading"><p class="eyebrow">DỮ LIỆU WORKSPACE</p><h1>${config.headline}</h1></div>${config.cta ? `<button class="create-button" data-route="${config.ctaPage}"><i class="ph ph-plus"></i>${config.cta}</button>` : ''}${resourceToolbar(page)}<div class="page-list resource-host" data-resource-host="${page}">${skeletonMarkup(3)}</div>`;
  if (page === 'global-search') return `<div class="standalone-search"><i class="ph ph-magnifying-glass"></i><input data-resource-search="global-search" placeholder="Tìm báo cáo, chế độ xem, nguồn dữ liệu..." autofocus></div><p class="group-label">KẾT QUẢ TỪ WORKSPACE</p><div class="page-list resource-host" data-resource-host="global-search">${emptyMarkup('Nhập từ khóa để tìm kiếm dữ liệu thật.')}</div>`;
  if (page === 'account') return `<div class="secondary-heading"><p class="eyebrow">NEXUS ACCOUNT</p><h1>Thông tin tài khoản</h1></div>${skeletonMarkup(4)}`;
  if (['notifications','report-detail'].includes(page)) return blockedMarkup(page === 'notifications' ? 'Trung tâm thông báo chưa có API.' : 'Chi tiết và xuất báo cáo chưa có API.');
  if (['settings','security'].includes(page)) return `<div class="secondary-heading"><p class="eyebrow">CHƯA CÓ BACKEND</p><h1>${config.title}</h1></div>${blockedMarkup('Các cấu hình này chỉ được hiển thị để giữ nguyên UI; chưa thể lưu hoặc thay đổi.')}`;
  if (config.type === 'metric') return `<div class="secondary-heading"><p class="eyebrow">${config.kicker}</p><h1>—</h1><span class="trend up">API</span><p>Dữ liệu theo Workspace đang được tải.</p></div>${skeletonMarkup(2)}<div class="detail-rows">${skeletonMarkup(3)}</div>`;
  if (config.type === 'article') return `<article class="article-view"><span class="article-icon"><i class="ph-fill ph-sparkle"></i></span><p class="eyebrow">${config.tag}</p><h1>${config.headline}</h1><p>${config.copy}</p><h3>Đề xuất hành động</h3>${config.bullets.map((item,index) => `<div class="recommendation"><b>0${index+1}</b><span>${item}</span></div>`).join('')}<button class="primary-button">Tạo nhiệm vụ theo dõi</button></article>`;
  if (config.type === 'list') return `<div class="secondary-heading"><p class="eyebrow">${config.kicker}</p><h1>${config.headline}</h1></div>${config.cta ? `<button class="create-button" data-route="${config.ctaPage}"><i class="ph ph-plus"></i>${config.cta}</button>` : ''}<div class="page-list">${config.items.map(([title,subtitle,target]) => `<button data-route="${target}"><span class="page-list-icon"><i class="ph ph-file-text"></i></span><span><b>${title}</b><small>${subtitle}</small></span><i class="ph ph-caret-right"></i></button>`).join('')}</div>`;
  if (config.type === 'report') return `<div class="report-cover"><p class="eyebrow">01/07 — 30/09/2026</p><h1>Báo cáo hiệu suất Q3</h1><span class="pill">Đã hoàn tất</span></div><div class="report-kpis"><article><small>DOANH THU</small><b>₫342K</b><em>+14.2%</em></article><article><small>NGƯỜI DÙNG</small><b>128K</b><em>+8.7%</em></article></div>${metricChart()}<button class="primary-button"><i class="ph ph-download-simple"></i> Xuất PDF</button>`;
  if (config.type === 'sources') return `<div class="secondary-heading"><p class="eyebrow">NHẬP DỮ LIỆU THẬT</p><h1>Thêm nguồn dữ liệu</h1><p>Hiện hỗ trợ tệp CSV và Excel. Các kết nối bên ngoài sẽ được mở ở giai đoạn sau.</p></div><div class="source-grid"><button disabled><b class="google">G</b><span>Google Analytics</span><small>Sắp có</small></button><button disabled><b class="facebook"><i class="ph-fill ph-facebook-logo"></i></b><span>Facebook Ads</span><small>Sắp có</small></button><button disabled><b class="email"><i class="ph-fill ph-database"></i></b><span>PostgreSQL</span><small>Sắp có</small></button><button class="active-source" data-action="choose-import-file"><b><i class="ph-fill ph-file-csv"></i></b><span>CSV / Excel</span><small>Đang hỗ trợ</small></button></div>${ingestionWorkspace(true)}`;
  if (config.type === 'filter') return `<div class="secondary-heading"><p class="eyebrow">TÙY CHỈNH DỮ LIỆU</p><h1>Bộ lọc nâng cao</h1></div><div class="filter-form"><label>Khoảng thời gian<select data-analytics-days><option value="7">7 ngày qua</option><option value="30">30 ngày qua</option><option value="90">90 ngày qua</option><option value="custom">Tùy chỉnh</option></select></label><div class="filter-date-range"><label>Từ ngày<input type="date" data-analytics-date-from></label><label>Đến ngày<input type="date" data-analytics-date-to></label></div><label>Nguồn dữ liệu<select disabled title="Chưa có API lọc theo data source"><option>Tất cả nguồn</option></select></label><p class="blocked-note">Lọc theo kênh và thiết bị đang BLOCKED vì backend chưa có event dimensions.</p><p class="form-status" role="status"></p><button class="primary-button" data-action="apply-analytics-filter">Áp dụng bộ lọc</button></div>`;
  if (config.type === 'settings') return `<div class="secondary-heading"><p class="eyebrow">NEXUS ACCOUNT</p><h1>${config.title}</h1></div><div class="settings-detail">${config.items.map(([label,value]) => `<button><span><small>${label}</small><b>${value}</b></span><i class="ph ph-caret-right"></i></button>`).join('')}</div>`;
  return '';
}

function openPage(page, addHistory = true) {
  if (!authSession && !publicPages.has(page)) page = 'login';
  if (['home','analytics','insights','alerts','profile'].includes(page)) return showScreen(page);
  if (addHistory && currentPage) pageHistory.push(currentPage);
  currentPage = page;
  const config = pageRegistry[page];
  secondaryHeader.textContent = page === 'ui-map' ? 'UI Map' : config?.title || 'Chi tiết';
  secondaryContent.innerHTML = renderPage(page);
  screens.forEach(screen => screen.classList.toggle('active', screen.id === 'secondary-screen'));
  navButtons.forEach(button => button.classList.remove('active'));
  shell.classList.toggle('immersive', ['splash','onboarding','login','forgot-password','register','reset-password'].includes(page));
  secondaryContent.scrollTop = 0;
  if (page === 'add-source') loadImportHistory();
  loadSecondaryResource(page);
}

function goBack() {
  if (pageHistory.length) return openPage(pageHistory.pop(), false);
  showScreen(currentBaseScreen || 'home');
}

const webPages = {
  realtime: ['Phân tích thời gian thực','Theo dõi hoạt động người dùng ngay lúc này','pulse'],
  funnel: ['Phân tích Funnel','Theo dõi hành trình chuyển đổi từ truy cập đến mua hàng','funnel'],
  explorer: ['Khám phá dữ liệu','Tự do kết hợp dimensions và metrics để tìm câu trả lời','explorer'],
  insights: ['AI Insights','Những phát hiện quan trọng được Nexus AI đề xuất','insights'],
  journey: ['Hành trình người dùng','Quan sát các bước người dùng đi qua trước khi chuyển đổi','journey'],
  retention: ['Retention','Đo lường khả năng người dùng quay lại theo thời gian','retention'],
  segmentation: ['Phân khúc người dùng','Tạo và so sánh các nhóm người dùng theo hành vi','table'],
  cohort: ['Phân tích Cohort','So sánh hành vi của các nhóm người dùng theo thời gian','cohort'],
  'revenue-analysis': ['Phân tích doanh thu','Đánh giá xu hướng và động lực tăng trưởng doanh thu','revenue'],
  anomaly: ['Phát hiện bất thường','Theo dõi tự động các biến động vượt ngoài dự kiến','anomaly'],
  alerts: ['Cảnh báo','Thiết lập và quản lý các cảnh báo dữ liệu','alerts'],
  forecast: ['Dự báo','Dự đoán doanh thu và hành vi dựa trên dữ liệu lịch sử','forecast'],
  reports: ['Quản lý Báo cáo','Tạo, theo dõi và xuất các báo cáo phân tích','reports'],
  dashboards: ['Dashboards','Quản lý các dashboard phục vụ từng mục tiêu','dashboards'],
  builder: ['Dashboard Builder','Kéo thả widget để xây dashboard riêng','builder'],
  sources: ['Nguồn dữ liệu','Quản lý và theo dõi trạng thái các nguồn kết nối','sources'],
  events: ['Sự kiện','Theo dõi sự kiện và thuộc tính được gửi về hệ thống','events'],
  saved: ['Chế độ xem đã lưu','Truy cập nhanh các cấu hình phân tích thường dùng','dashboards'],
  quality: ['Chất lượng dữ liệu','Giám sát độ đầy đủ, tính chính xác và độ trễ dữ liệu','quality'],
  export: ['Xuất dữ liệu','Quản lý lịch sử và trạng thái các tác vụ xuất dữ liệu','export'],
  members: ['Thành viên','Quản lý thành viên và quyền truy cập Workspace','members'],
  activity: ['Nhật ký hoạt động','Theo dõi thay đổi quan trọng trong Workspace','activity'],
  settings: ['Cài đặt hệ thống','Quản lý tài khoản, tích hợp và API key','settings']
};

const webKpis = (items) => `<div class="reference-kpis">${items.map(([label,value,change]) => `<article><small>${label}</small><h2>${value}</h2><span class="${change?.startsWith('-') ? 'bad' : ''}">${change || ''}</span></article>`).join('')}</div>`;
const webHeading = (title,description,action='Xuất dữ liệu') => {
  const create = ['Tạo báo cáo','Tạo cảnh báo'].includes(action);
  const refresh = action === 'Làm mới';
  const importFile = action === 'Nhập từ tệp';
  const invite = action === 'Mời thành viên';
  const disabled = !create && !refresh && !importFile && !invite;
  const attribute = create ? 'data-action="focus-create-resource"' : refresh ? 'data-action="refresh-web-resource"' : importFile ? 'data-action="choose-import-file"' : invite ? 'data-action="focus-member-invite"' : 'disabled';
  return `<div class="reference-heading"><div><h1>${title}</h1><p>${description}</p></div><div><button class="soft-button" disabled title="Dùng bộ lọc dữ liệu bên dưới"><i class="ph ph-calendar-blank"></i> Khoảng thời gian</button><button class="dark-button" ${attribute} ${disabled ? 'title="Backend chưa hỗ trợ thao tác này"' : ''}><i class="ph ${refresh ? 'ph-arrow-clockwise' : create ? 'ph-plus' : 'ph-download-simple'}"></i> ${action}</button></div></div>`;
};
const miniTable = (rows) => `<div class="reference-table"><table><thead><tr><th>TÊN</th><th>TRẠNG THÁI</th><th>NGƯỜI DÙNG</th><th>CHUYỂN ĐỔI</th><th></th></tr></thead><tbody>${rows.map(([name,status,users,rate]) => `<tr><td><b>${name}</b></td><td><span class="status-pill">${status}</span></td><td>${users}</td><td>${rate}</td><td><i class="ph ph-dots-three"></i></td></tr>`).join('')}</tbody></table></div>`;

function renderWebPage(key) {
  const [title,description,type] = webPages[key];
  if (type === 'members') return `${webHeading(title,description,'Mời thành viên')}<div class="member-invite"><input type="email" placeholder="email@company.com"><select><option>VIEWER</option><option>ANALYST</option><option>ADMIN</option></select><button class="dark-button" data-action="invite-member">Gửi lời mời</button><span role="status"></span></div><div class="reference-table" id="workspace-members"><p class="loading-state">Đang tải thành viên...</p></div>`;
  if (type === 'reports') return `${webHeading(title,description,'Tạo báo cáo')}<form class="web-create-form" data-create-resource="report"><input name="name" placeholder="Tên báo cáo" required><select name="report_type"><option value="performance">Hiệu suất</option><option value="cohort">Cohort</option><option value="custom">Tùy chỉnh</option></select><button class="dark-button" type="submit">Tạo bản nháp</button><span role="status"></span></form><div class="web-resource-controls">${resourceToolbar('web-reports')}</div><div class="resource-host web-resource-host" data-resource-host="web-reports">${skeletonMarkup(4)}</div>`;
  if (type === 'alerts') return `${webHeading(title,description,'Tạo cảnh báo')}<form class="web-create-form" data-create-resource="alert"><input name="title" placeholder="Tên cảnh báo" required><input name="description" placeholder="Mô tả" required><select name="severity"><option value="medium">Theo dõi</option><option value="high">Nghiêm trọng</option><option value="low">Thấp</option></select><button class="dark-button" type="submit">Tạo cảnh báo</button><span role="status"></span></form><div class="web-resource-controls">${resourceToolbar('web-alerts')}</div><div class="resource-host web-resource-host" data-resource-host="web-alerts">${skeletonMarkup(4)}</div>`;
  if (['insights','pulse','funnel','cohort','revenue'].includes(type)) return `${webHeading(title,description,'Làm mới')}<div class="web-resource-controls">${type === 'insights' ? resourceToolbar('web-insights') : dateToolbar(`web-${type}`)}</div><div class="resource-host web-resource-host" data-resource-host="web-${type}">${skeletonMarkup(4)}</div>`;
  if (type === 'sources') return `${webHeading(title,'Tải CSV/XLSX, kiểm tra dữ liệu và theo dõi từng lần nhập','Nhập từ tệp')}<div class="web-resource-controls">${resourceToolbar('web-sources')}</div><div class="resource-host web-resource-host" data-resource-host="web-sources">${skeletonMarkup(3)}</div>${ingestionWorkspace(false)}`;
  if (['dashboards','builder','table','journey','retention','forecast','events','quality','export','activity','settings','explorer','anomaly'].includes(type)) return `${webHeading(title,description,'Chưa khả dụng')}${blockedMarkup('Backend chưa có capability tương ứng. Màn hình được giữ nguyên trong điều hướng nhưng mọi thao tác giả đã bị khóa.')}`;
  if (type === 'pulse') return `${webHeading(title,description,'Tạm dừng')} ${webKpis([['ĐANG HOẠT ĐỘNG','1,284','+12.4%'],['SỰ KIỆN / PHÚT','3,821','+8.1%'],['DOANH THU 30 PHÚT','₫12,840','+18.3%'],['CHUYỂN ĐỔI','3.82%','-0.2%']])}<div class="reference-grid wide"><article class="reference-card"><h3>Hoạt động trong 30 phút gần nhất</h3><div class="reference-bars">${[35,48,42,66,52,81,74,96,86,70,92,78].map(v=>`<i style="height:${v}%"></i>`).join('')}</div></article><article class="reference-card"><h3>Hoạt động gần đây</h3><div class="live-feed"><p><i></i><span><b>purchase_completed</b><small>Hà Nội · 10 giây trước</small></span></p><p><i></i><span><b>checkout_started</b><small>TP.HCM · 24 giây trước</small></span></p><p><i></i><span><b>product_viewed</b><small>Đà Nẵng · 41 giây trước</small></span></p></div></article></div>`;
  if (type === 'funnel') return `${webHeading(title,description,'Tạo Funnel')}${webKpis([['TỶ LỆ HOÀN TẤT','12.5%','+2.4%'],['THỜI GIAN TB','8m 42s','-1.1%'],['ĐIỂM RƠI LỚN NHẤT','Giỏ hàng',''],['TỔNG NGƯỜI DÙNG','58K','+5.8%']])}<article class="reference-card funnel-card"><h3>Users theo bước chuyển đổi</h3><div class="funnel-visual"><span style="width:92%">Truy cập · 124,592</span><span style="width:76%">Xem sản phẩm · 94,018</span><span style="width:59%">Thêm giỏ hàng · 52,809</span><span style="width:43%">Bắt đầu checkout · 28,420</span><span style="width:29%">Hoàn tất · 15,574</span></div></article>`;
  if (type === 'retention') return `${webHeading(title,description)}${webKpis([['DAY 1 RETENTION','61%','+2.4%'],['DAY 7 RETENTION','32%','-1.1%'],['DAY 14 RETENTION','24%','+0.5%'],['DAY 30 RETENTION','18%','+3.2%']])}<article class="reference-card retention-card"><h3>Retention theo thời gian</h3><div class="retention-lines"><i></i><i></i><i></i><i></i></div><div class="chart-labels"><span>Ngày 0</span><span>Ngày 7</span><span>Ngày 14</span><span>Ngày 21</span><span>Ngày 30</span></div></article><div class="info-banner"><i class="ph-fill ph-lightbulb"></i><div><b>Thông tin chi tiết</b><p>Organic Search có Day-30 Retention cao hơn 18% so với mức trung bình.</p></div></div>`;
  if (type === 'cohort') return `${webHeading(title,description)}${webKpis([['COHORT TỐT NHẤT','T4/W2','+12.5%'],['RETENTION TRUNG BÌNH','18.4%','+2.1%'],['THAY ĐỔI KỲ TRƯỚC','+5.2%',''],['USER PHÂN TÍCH','12.4K','']])}<article class="reference-card"><h3>Retention theo Cohort</h3><div class="cohort-grid">${Array.from({length:48},(_,i)=>`<span style="opacity:${Math.max(.15,1-(i%8)*.11)}">${i%8===0?'100%':Math.max(12,58-(i%8)*7)+'%'}</span>`).join('')}</div></article>`;
  if (type === 'insights') return `${webHeading(title,description,'Hỏi Nexus AI')}<div class="ai-hero"><i class="ph-fill ph-sparkle"></i><div><small>ĐIỂM NỔI BẬT HÔM NAY</small><h2>Traffic từ Organic Search tăng mạnh trong 7 ngày qua</h2><p>Nexus AI phát hiện mức tăng 23%, đóng góp thêm khoảng ₫18.4K doanh thu.</p></div><button>Khám phá nguyên nhân</button></div><div class="web-section-grid"><article><i class="ph ph-trend-up"></i><h3>Cơ hội tăng trưởng</h3><p>Summer Sale đang có ROAS tốt hơn 32% so với dự kiến.</p></article><article><i class="ph ph-warning"></i><h3>Mobile cần chú ý</h3><p>Bounce rate tăng 9% tại trang checkout.</p></article><article><i class="ph ph-users"></i><h3>Nhóm khách hàng mới</h3><p>Khách Organic có khả năng quay lại cao hơn 34%.</p></article></div>`;
  if (['dashboards','reports'].includes(type)) { const cards = type==='reports' ? [['Báo cáo doanh thu Q3','revenue-analysis'],['Phân tích người dùng','segmentation'],['Báo cáo Cohort','cohort'],['Dự báo tháng 11','forecast']] : [['Marketing Overview','overview'],['Executive Dashboard','revenue-analysis'],['Product Analytics','funnel'],['Conversion Dashboard','journey'],['Revenue Performance','revenue-analysis'],['User Acquisition','segmentation']]; return `${webHeading(title,description,type==='reports'?'Tạo báo cáo':'Tạo Dashboard')}<div class="dashboard-gallery">${cards.map(([name,target],i)=>`<button data-web-screen="${target}"><div class="gallery-preview p${i%3+1}"><i></i><i></i><i></i><span></span></div><b>${name}</b><small>Cập nhật hôm nay</small><i class="ph ph-dots-three"></i></button>`).join('')}</div>`; }
  if (type === 'sources') return `${webHeading(title,'Tải CSV/XLSX, kiểm tra dữ liệu và theo dõi từng lần nhập','Nhập từ tệp')}${ingestionWorkspace(false)}`;
  if (type === 'quality') return `${webHeading(title,description,'Làm mới')}${webKpis([['ĐIỂM CHẤT LƯỢNG','94/100','+3'],['VẤN ĐỀ ĐANG MỞ','2','-1'],['NGUỒN CẦN CHÚ Ý','1',''],['ĐỘ TRỄ','0.3%','']])}<div class="reference-grid wide"><article class="reference-card"><h3>Điểm chất lượng dữ liệu theo thời gian</h3>${metricChart()}</article><article class="reference-card"><h3>Vấn đề cần xử lý</h3><div class="issue"><b>Facebook Ads đồng bộ chậm</b><p>Dữ liệu chậm hơn bình thường 45 phút.</p></div><div class="issue soft"><b>Thiếu trường campaign_id</b><p>1.2% bản ghi trong 24 giờ qua.</p></div></article></div>`;
  if (['table','events','export','activity','alerts','anomaly'].includes(type)) return `${webHeading(title,description,type==='alerts'?'Tạo cảnh báo':'Tạo mới')}${webKpis([['TỔNG','24,502','+4.2%'],['ĐANG HOẠT ĐỘNG','12,183','+8.1%'],['CẦN CHÚ Ý','4','-2'],['CẬP NHẬT HÔM NAY','128','+12%']])}${miniTable([['Organic Search','Hoạt động','8,421','4.82%'],['Paid Social','Hoạt động','6,294','3.91%'],['Email Campaign','Theo dõi','4,105','3.24%'],['Referral','Hoạt động','2,890','2.81%']])}`;
  if (type === 'builder') return `${webHeading(title,description,'Lưu Dashboard')}<div class="builder-layout"><aside><p>THÀNH PHẦN</p><button><i class="ph ph-number-square-one"></i>KPI</button><button><i class="ph ph-chart-line"></i>Line chart</button><button><i class="ph ph-chart-bar"></i>Bar chart</button><button><i class="ph ph-table"></i>Table</button></aside><div class="builder-canvas"><div class="builder-kpis">${webKpis([['REVENUE','124.5K',''],['USERS','45,210',''],['CONVERSION','3.2%','']])}</div><div class="drop-zone"><i class="ph ph-plus"></i><p>Kéo thành phần vào đây</p></div></div><aside class="properties"><p>THUỘC TÍNH</p><label>Tiêu đề<input value="Marketing Performance"></label><label>Nguồn<select><option>Google Analytics</option></select></label></aside></div>`;
  if (type === 'explorer') return `${webHeading(title,description,'Lưu chế độ xem')}<div class="explorer-layout"><aside class="reference-card"><h3>Cấu hình truy vấn</h3><label>Dimensions<select><option>Source / Medium</option></select></label><label>Metrics<select><option>Active users</option></select></label><button class="dark-button">Chạy truy vấn</button></aside><article class="reference-card"><h3>Sessions theo ngày</h3><div class="reference-bars">${[30,46,38,67,55,83,72,95].map(v=>`<i style="height:${v}%"></i>`).join('')}</div></article></div>`;
  if (['journey','revenue','forecast'].includes(type)) return `${webHeading(title,description)}${webKpis([['TỔNG','124,592','+12.5%'],['TRUNG BÌNH','12,549','+4.2%'],['DỰ BÁO','₫104,320','+8.5%'],['ĐỘ TIN CẬY','92%','']])}<article class="reference-card"><h3>${type==='journey'?'Luồng người dùng chính':'Xu hướng theo thời gian'}</h3>${type==='journey'?'<div class="journey-flow"><span>Landing page</span><i></i><span>Product</span><i></i><span>Cart</span><i></i><span>Purchase</span></div>':metricChart()}</article>`;
  return `${webHeading(title,description)}<div class="web-section-grid"><article><i class="ph ph-user"></i><h3>Hồ sơ cá nhân</h3><p>Quản lý thông tin hiển thị và vai trò.</p></article><article><i class="ph ph-key"></i><h3>Bảo mật & API</h3><p>Quản lý mật khẩu, 2FA và API key.</p></article><article><i class="ph ph-bell"></i><h3>Thông báo</h3><p>Tùy chỉnh cảnh báo email và push.</p></article></div>`;
}

function showWebScreen(key) {
  if (!authSession) return openPage('login');
  if (key === 'members' && !['OWNER','ADMIN'].includes(authSession.workspace.role)) return showWebScreen('overview');
  currentWebScreen = key;
  document.querySelectorAll('.web-panel').forEach(panel => panel.classList.toggle('active', panel.id === (key === 'overview' ? 'overview-web-panel' : 'dynamic-web-panel')));
  document.querySelectorAll('[data-web-screen]').forEach(button => button.classList.toggle('active', button.dataset.webScreen === key));
  if (key !== 'overview') document.getElementById('dynamic-web-panel').innerHTML = renderWebPage(key);
  if (key === 'members') loadWorkspaceMembers();
  if (key === 'sources') loadImportHistory();
  loadWebResource(key);
  document.querySelector('.web-content').scrollTop = 0;
}

const NexusAPI = window.NexusAPI;

function skeletonMarkup(count = 3) {
  return `<div class="resource-skeleton" aria-label="Đang tải">${Array.from({length: count}, () => '<i></i>').join('')}</div>`;
}

function emptyMarkup(message = 'Chưa có dữ liệu phù hợp.') {
  return `<div class="resource-state empty"><i class="ph ph-database"></i><b>Chưa có dữ liệu</b><p>${escapeHtml(message)}</p></div>`;
}

function errorMarkup(error, key) {
  return `<div class="resource-state error"><i class="ph ph-warning-circle"></i><b>Không thể tải dữ liệu</b><p>${escapeHtml(error?.message || 'Đã xảy ra lỗi.')}</p><button data-resource-retry="${escapeHtml(key)}">Thử lại</button></div>`;
}

function blockedMarkup(message) {
  return `<div class="resource-state blocked"><i class="ph ph-lock-key"></i><b>BLOCKED</b><p>${escapeHtml(message)}</p></div>`;
}

function resourceToolbar(key) {
  const filter = key.includes('alerts')
    ? '<select data-resource-filter><option value="">Tất cả</option><option value="unread_only=true">Chưa đọc</option><option value="severity=high">Nghiêm trọng</option></select>'
    : key.includes('reports')
      ? '<select data-resource-filter><option value="">Mọi trạng thái</option><option value="status=ready">Sẵn sàng</option><option value="status=draft">Bản nháp</option></select>'
      : key.includes('import-history')
        ? '<select data-resource-filter><option value="">Mọi trạng thái</option><option value="status=COMPLETED">Hoàn tất</option><option value="status=FAILED">Thất bại</option><option value="status=PROCESSING">Đang xử lý</option></select>'
      : key.includes('sources')
        ? '<select data-resource-filter><option value="">Mọi trạng thái</option><option value="status=connected">Đã kết nối</option><option value="status=completed">Hoàn tất</option><option value="status=warning">Cần chú ý</option></select>'
        : key.includes('saved')
          ? '<select data-resource-filter><option value="">Tất cả</option><option value="is_favorite=true">Yêu thích</option></select>' : '';
  return `<div class="resource-toolbar" data-resource-controls="${key}"><label><i class="ph ph-magnifying-glass"></i><input data-resource-search="${key}" placeholder="Tìm kiếm..."></label>${filter}<select data-resource-sort><option value="desc">Mới nhất</option><option value="asc">Cũ nhất</option></select></div>`;
}

function dateToolbar(key) {
  return `<div class="resource-toolbar date-toolbar" data-resource-controls="${key}"><select data-resource-days><option value="7">7 ngày</option><option value="30">30 ngày</option><option value="90">90 ngày</option></select><label>Từ<input type="date" data-resource-date-from></label><label>Đến<input type="date" data-resource-date-to></label><button data-resource-retry="${key}"><i class="ph ph-arrow-clockwise"></i> Làm mới</button></div>`;
}

function queryFor(key) {
  if (!resourceQuery.has(key)) resourceQuery.set(key, { page: 1, page_size: 10, sort_order: 'desc' });
  return resourceQuery.get(key);
}

function analyticsQuery(key, fallbackDays) {
  const query = queryFor(key);
  return query.date_from && query.date_to
    ? {date_from: query.date_from, date_to: query.date_to}
    : {days: query.days || fallbackDays};
}

function pagerMarkup(key, pagination) {
  if (!pagination || pagination.total_pages <= 1) return '';
  return `<nav class="resource-pager" aria-label="Phân trang"><button data-resource-page="${key}" data-page="${pagination.page - 1}" ${pagination.page <= 1 ? 'disabled' : ''}><i class="ph ph-caret-left"></i></button><span>Trang ${pagination.page} / ${pagination.total_pages} · ${pagination.total} mục</span><button data-resource-page="${key}" data-page="${pagination.page + 1}" ${pagination.page >= pagination.total_pages ? 'disabled' : ''}><i class="ph ph-caret-right"></i></button></nav>`;
}

function resourceHosts(key) {
  return [...document.querySelectorAll(`[data-resource-host="${key}"]`)];
}

function setResourceHtml(key, html) {
  resourceHosts(key).forEach(host => { host.innerHTML = html; });
}

function formatDate(value) {
  if (!value) return 'Chưa cập nhật';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('vi-VN');
}

function mobileRows(key, items) {
  if (key === 'reports') return items.map(item => `<button disabled><span class="page-list-icon"><i class="ph ph-file-text"></i></span><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.report_type)} · ${escapeHtml(item.status)} · ${formatDate(item.updated_at)}</small></span><span class="status-pill">${escapeHtml(item.status)}</span></button>`).join('');
  if (key === 'saved-views') return items.map(item => `<button data-route="${({traffic:'traffic',revenue:'revenue',funnel:'conversion'})[item.view_type] || 'users'}"><span class="page-list-icon"><i class="ph ph-bookmark-simple"></i></span><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.description)} · ${escapeHtml(item.view_type)}</small></span>${item.is_favorite ? '<i class="ph-fill ph-star"></i>' : '<i class="ph ph-caret-right"></i>'}</button>`).join('');
  if (key === 'data-sources') return items.map(item => `<button disabled><span class="page-list-icon"><i class="ph ph-database"></i></span><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.source_type)} · ${formatDate(item.last_sync || item.last_import_at)}</small></span><span class="status-pill">${escapeHtml(item.health_status || item.status)}</span></button>`).join('');
  return '';
}

function webTable(items, columns) {
  return `<div class="reference-table"><table><thead><tr>${columns.map(column => `<th>${column.label}</th>`).join('')}</tr></thead><tbody>${items.map(item => `<tr>${columns.map(column => `<td>${column.render ? column.render(item) : escapeHtml(item[column.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function webRows(key, items) {
  if (key === 'web-reports') return webTable(items, [
    {label:'BÁO CÁO',render:item=>`<b>${escapeHtml(item.name)}</b>`}, {label:'LOẠI',key:'report_type'},
    {label:'TRẠNG THÁI',render:item=>`<span class="status-pill">${escapeHtml(item.status)}</span>`}, {label:'CẬP NHẬT',render:item=>formatDate(item.updated_at)}
  ]);
  if (key === 'web-alerts') return webTable(items, [
    {label:'CẢNH BÁO',render:item=>`<b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.description)}</small>`}, {label:'MỨC ĐỘ',key:'severity'},
    {label:'TRẠNG THÁI',render:item=>item.is_read ? 'Đã đọc' : 'Chưa đọc'}, {label:'THỜI GIAN',render:item=>formatDate(item.created_at)}
  ]);
  if (key === 'web-insights') return `<div class="web-section-grid">${items.map(item => `<article><i class="ph ${item.insight_type === 'warning' ? 'ph-warning' : 'ph-trend-up'}"></i><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.description)}</p><span class="status-pill">${escapeHtml(item.change_value || item.severity)}</span></article>`).join('')}</div>`;
  if (key === 'web-sources') return webTable(items, [
    {label:'NGUỒN',render:item=>`<b>${escapeHtml(item.name)}</b>`}, {label:'LOẠI',key:'source_type'},
    {label:'TRẠNG THÁI',render:item=>`<span class="status-pill">${escapeHtml(item.health_status || item.status)}</span>`}, {label:'BẢN GHI',render:item=>String(item.event_count || 0)}, {label:'LẦN NHẬP CUỐI',render:item=>formatDate(item.last_import_at || item.last_sync)}
  ]);
  return '';
}

const listResourceApi = {
  reports: query => NexusAPI.reports(query),
  'saved-views': query => NexusAPI.savedViews(query),
  'data-sources': query => NexusAPI.dataSources(query),
  'web-reports': query => NexusAPI.reports(query),
  'web-alerts': query => NexusAPI.alerts(query),
  'web-insights': query => NexusAPI.insights(query),
  'web-sources': query => NexusAPI.dataSources(query)
};

function reloadResource(key, force = false) {
  if (listResourceApi[key]) return loadListResource(key, force);
  if (key === 'global-search') return loadGlobalSearch(force);
  if (key === 'mobile-alerts') return loadMobileAlerts(force);
  if (key === 'mobile-insights') return loadMobileInsights(force);
  if (key === 'mobile-analytics') return loadMobileAnalytics(force);
  if (key === 'account') return loadAccount(force);
  if (key === 'edit-profile') return loadEditProfile(force);
  if (key === 'import-history') return loadImportHistory(force);
  if (key === 'overview') return loadBackendData(7, force);
  if (key.startsWith('metric-')) return loadMetricPage(key.slice(7), force);
  if (key.startsWith('web-')) {
    const match = Object.entries(webPages).find(([,config]) => config[2] === key.slice(4));
    if (match) return loadWebResource(match[0], force);
  }
}

async function loadListResource(key, force = false) {
  const api = listResourceApi[key];
  if (!api || !resourceHosts(key).length) return;
  setResourceHtml(key, skeletonMarkup(key.startsWith('web-') ? 4 : 3));
  try {
    const query = {...queryFor(key)};
    const response = await resourceRequests.run(key, signal => api(query, {signal, force}));
    const state = window.NexusResource.listState(response);
    if (state.status === 'empty') return setResourceHtml(key, emptyMarkup());
    const rows = key.startsWith('web-') ? webRows(key, state.items) : mobileRows(key, state.items);
    setResourceHtml(key, rows + pagerMarkup(key, state.pagination));
  } catch (error) {
    if (error?.code !== 'STALE_REQUEST') setResourceHtml(key, errorMarkup(error, key));
  }
}

async function loadGlobalSearch(force = false) {
  const key = 'global-search';
  if (!resourceHosts(key).length) return;
  const search = queryFor(key).search || '';
  if (search.length < 2) return setResourceHtml(key, emptyMarkup('Nhập ít nhất 2 ký tự để tìm kiếm.'));
  setResourceHtml(key, skeletonMarkup(3));
  try {
    const [reports, views, sources] = await resourceRequests.run(key, signal => Promise.all([
      NexusAPI.reports({search,page_size:5},{signal,force}), NexusAPI.savedViews({search,page_size:5},{signal,force}), NexusAPI.dataSources({search,page_size:5},{signal,force})
    ]));
    const groups = [
      ['BÁO CÁO', reports.data, item => `<button disabled><span class="page-list-icon"><i class="ph ph-file-text"></i></span><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.report_type)} · ${escapeHtml(item.status)}</small></span></button>`],
      ['CHẾ ĐỘ XEM', views.data, item => mobileRows('saved-views',[item])],
      ['NGUỒN DỮ LIỆU', sources.data, item => mobileRows('data-sources',[item])]
    ];
    const html = groups.filter(([,items]) => items.length).map(([label,items,render]) => `<p class="group-label">${label}</p>${items.map(render).join('')}`).join('');
    setResourceHtml(key, html || emptyMarkup(`Không tìm thấy kết quả cho “${search}”.`));
  } catch (error) {
    if (error?.code !== 'STALE_REQUEST') setResourceHtml(key, errorMarkup(error,key));
  }
}

async function loadWebGlobalSearch(force = false) {
  const search = queryFor('web-global-search').search || '';
  const dynamic = document.getElementById('dynamic-web-panel');
  if (search.length < 2) return;
  document.querySelectorAll('.web-panel').forEach(panel => panel.classList.toggle('active', panel === dynamic));
  document.querySelectorAll('[data-web-screen]').forEach(button => button.classList.remove('active'));
  dynamic.innerHTML = `${webHeading('Tìm kiếm Workspace',`Kết quả thật cho “${escapeHtml(search)}”`,'Chưa khả dụng')}<div class="resource-host web-search-results" data-resource-host="web-global-search">${skeletonMarkup(4)}</div>`;
  try {
    const [reports, views, sources] = await resourceRequests.run('web-global-search', signal => Promise.all([
      NexusAPI.reports({search,page_size:10},{signal,force}), NexusAPI.savedViews({search,page_size:10},{signal,force}), NexusAPI.dataSources({search,page_size:10},{signal,force})
    ]));
    const rows = [
      ...reports.data.map(item=>({kind:'Báo cáo',name:item.name,status:item.status})),
      ...views.data.map(item=>({kind:'Chế độ xem',name:item.name,status:item.view_type})),
      ...sources.data.map(item=>({kind:'Nguồn dữ liệu',name:item.name,status:item.health_status || item.status}))
    ];
    setResourceHtml('web-global-search', rows.length ? webTable(rows,[{label:'LOẠI',key:'kind'},{label:'TÊN',render:item=>`<b>${escapeHtml(item.name)}</b>`},{label:'TRẠNG THÁI',render:item=>`<span class="status-pill">${escapeHtml(item.status)}</span>`}]) : emptyMarkup(`Không tìm thấy kết quả cho “${search}”.`));
  } catch (error) { if (error?.code !== 'STALE_REQUEST') setResourceHtml('web-global-search',errorMarkup(error,'web-global-search')); }
}

async function loadMobileScreen(name) {
  if (name === 'analytics') return loadMobileAnalytics();
  if (name === 'insights') return loadMobileInsights();
  if (name === 'alerts') return loadMobileAlerts();
}

async function loadMobileAnalytics(force = false) {
  const host = document.querySelector('#analytics-screen .screen-scroll');
  if (!host) return;
  host.classList.add('is-loading');
  setText('#analytics-screen .analysis-card h2', '—');
  const initialList = document.querySelector('#analytics-screen .channel-list');
  if (initialList) initialList.innerHTML = skeletonMarkup(3);
  try {
    const response = await resourceRequests.run('mobile-analytics', signal => NexusAPI.revenue(analyticsQuery('mobile-analytics',30),{signal,force}));
    const daily = response.data.daily || [];
    const total = daily.reduce((sum,row) => sum + Number(row.revenue || 0), 0);
    setText('#analytics-screen .analysis-card h2', formatCurrency(total));
    const bars = document.querySelector('#analytics-screen .mini-bars');
    if (bars) {
      const recent = daily.slice(-7); const max = Math.max(...recent.map(row => Number(row.revenue || 0)), 1);
      bars.innerHTML = recent.map(row => `<i style="height:${Math.max(8, Number(row.revenue || 0) / max * 100)}%" title="${escapeHtml(row.label)}"></i>`).join('');
    }
    const groups = response.data.by_category || [];
    const list = document.querySelector('#analytics-screen .channel-list');
    if (list) list.innerHTML = groups.length ? groups.map((row,index) => `<button data-page="revenue"><span class="channel-icon ${index%2?'facebook':'google'}">${escapeHtml(String(row.name || '?').slice(0,1))}</span><span><b>${escapeHtml(row.name)}</b><small>Dữ liệu đã nhập</small></span><strong>${formatCurrency(row.revenue)}</strong><i class="ph ph-caret-right"></i></button>`).join('') : emptyMarkup();
  } catch (error) {
    if (error?.code !== 'STALE_REQUEST') host.insertAdjacentHTML('afterbegin', errorMarkup(error,'mobile-analytics'));
  } finally { host.classList.remove('is-loading'); }
}

async function loadMobileInsights(force = false) {
  const host = document.querySelector('#insights-screen .screen-scroll');
  if (!host) return;
  host.innerHTML = skeletonMarkup(4);
  try {
    const response = await resourceRequests.run('mobile-insights', signal => NexusAPI.insights({page_size:20},{signal,force}));
    if (!response.data.length) return void (host.innerHTML = emptyMarkup());
    const [featured,...items] = response.data;
    host.innerHTML = `<div class="page-heading compact"><div><p class="eyebrow">DỮ LIỆU WORKSPACE</p><h1>Insights</h1></div><span class="pill">${response.meta.pagination.total}</span></div><article class="featured-insight"><span><i class="ph-fill ph-sparkle"></i></span><p>${escapeHtml(featured.insight_type)}</p><h2>${escapeHtml(featured.title)}</h2><button data-action="detail" data-title="${escapeHtml(featured.title)}" data-description="${escapeHtml(featured.description)}">Xem phân tích <i class="ph ph-arrow-right"></i></button></article><div class="insight-timeline">${items.map(item => `<button class="timeline-item" data-action="detail" data-title="${escapeHtml(item.title)}" data-description="${escapeHtml(item.description)}"><i class="ph-fill ${item.insight_type==='warning'?'ph-warning':'ph-lightbulb'}"></i><span><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.description)}</small></span><em>${escapeHtml(item.change_value || item.severity)}</em></button>`).join('')}</div>`;
  } catch (error) { if (error?.code !== 'STALE_REQUEST') host.innerHTML = errorMarkup(error,'mobile-insights'); }
}

async function loadMobileAlerts(force = false) {
  const host = document.querySelector('#alerts-screen .alert-list');
  if (!host) return;
  host.innerHTML = skeletonMarkup(3);
  try {
    const response = await resourceRequests.run('mobile-alerts', signal => NexusAPI.alerts({page_size:20},{signal,force}));
    if (!response.data.length) return void (host.innerHTML = emptyMarkup());
    host.innerHTML = response.data.map(item => `<article class="alert ${escapeHtml(item.severity)}"><span><i class="ph-fill ${item.severity==='high'?'ph-warning-octagon':'ph-info'}"></i></span><div><p class="alert-tag">${escapeHtml(item.severity.toUpperCase())} · ${formatDate(item.created_at)}</p><h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.description)}</p><button data-action="detail" data-title="${escapeHtml(item.title)}" data-description="${escapeHtml(item.description)}">Xem chi tiết</button>${!item.is_read && ['OWNER','ADMIN','ANALYST'].includes(authSession?.workspace?.role) ? `<button class="mark-read" data-alert-read="${item.id}">Đánh dấu đã đọc</button>` : ''}</div></article>`).join('');
  } catch (error) { if (error?.code !== 'STALE_REQUEST') host.innerHTML = errorMarkup(error,'mobile-alerts'); }
}

async function loadSecondaryResource(page) {
  if (listResourceApi[page]) return loadListResource(page);
  if (page === 'global-search') return;
  if (page === 'account') return loadAccount();
  if (page === 'edit-profile') return loadEditProfile();
  if (['revenue','traffic','conversion'].includes(page)) return loadMetricPage(page);
}

async function loadAccount(force = false) {
  try {
    const response = await resourceRequests.run('account', signal => NexusAPI.profile({signal,force}));
    if (currentPage !== 'account') return;
    const item = response.data;
    secondaryContent.innerHTML = `<div class="secondary-heading"><p class="eyebrow">NEXUS ACCOUNT</p><h1>Thông tin tài khoản</h1></div><div class="settings-detail">${[['Họ và tên',item.full_name],['Email',item.email],['Vai trò',item.role],['Workspace',item.workspace]].map(([label,value]) => `<div class="settings-readonly"><span><small>${label}</small><b>${escapeHtml(value)}</b></span></div>`).join('')}</div>`;
  } catch (error) { if (error?.code !== 'STALE_REQUEST') secondaryContent.innerHTML = errorMarkup(error,'account'); }
}

async function loadEditProfile(force = false) {
  try {
    const response = await resourceRequests.run('edit-profile', signal => NexusAPI.profile({signal,force}));
    if (currentPage !== 'edit-profile') return;
    const values = [response.data.full_name,response.data.job_title,response.data.email,response.data.phone];
    secondaryContent.querySelectorAll('.mobile-form input').forEach((input,index) => { input.value = values[index] || ''; });
  } catch (error) {
    const status = secondaryContent.querySelector('.form-status');
    if (status && error?.code !== 'STALE_REQUEST') status.textContent = error.message;
  }
}

async function loadMetricPage(page, force = false) {
  secondaryContent.classList.add('is-loading');
  try {
    let response;
    if (page === 'revenue') response = await resourceRequests.run('metric-revenue', signal => NexusAPI.revenue({days:30},{signal,force}));
    if (page === 'traffic') response = await resourceRequests.run('metric-traffic', signal => NexusAPI.overview({days:30},{signal,force}));
    if (page === 'conversion') response = await resourceRequests.run('metric-conversion', signal => NexusAPI.funnel({days:30},{signal,force}));
    if (currentPage !== page || !response) return;
    if (page === 'revenue') {
      const total = response.data.daily.reduce((sum,row) => sum + Number(row.revenue || 0), 0);
      setText('#secondary-content .secondary-heading h1', formatCurrency(total));
      const rows = response.data.by_category || [];
      const container = secondaryContent.querySelector('.detail-rows');
      if (container) container.innerHTML = rows.length ? rows.map(row => `<div><span>${escapeHtml(row.name)}</span><b>${formatCurrency(row.revenue)}</b></div>`).join('') : emptyMarkup();
    } else if (page === 'traffic') {
      setText('#secondary-content .secondary-heading h1', formatCompactNumber(response.data.summary.sessions));
      const container = secondaryContent.querySelector('.detail-rows');
      if (container) container.innerHTML = response.data.traffic_sources.map(row => `<div><span>${escapeHtml(row.name)}</span><b>${row.share}%</b></div>`).join('');
    } else {
      setText('#secondary-content .secondary-heading h1', `${response.data.completion_rate}%`);
      const container = secondaryContent.querySelector('.detail-rows');
      if (container) container.innerHTML = response.data.steps.map(row => `<div><span>${escapeHtml(row.name)}</span><b>${row.rate}% · ${formatCompactNumber(row.users)}</b></div>`).join('');
    }
  } catch (error) {
    if (error?.code !== 'STALE_REQUEST') secondaryContent.insertAdjacentHTML('afterbegin', errorMarkup(error,`metric-${page}`));
  } finally { secondaryContent.classList.remove('is-loading'); }
}

function webMetricHtml(title, kpis, content) {
  return `${webKpis(kpis)}<article class="reference-card">${title ? `<h3>${escapeHtml(title)}</h3>` : ''}${content}</article>`;
}

async function loadWebResource(key, force = false) {
  const type = webPages[key]?.[2];
  const resourceKey = `web-${type}`;
  if (listResourceApi[resourceKey]) return loadListResource(resourceKey, force);
  const host = resourceHosts(resourceKey)[0];
  if (!host || !['pulse','funnel','cohort','revenue'].includes(type)) return;
  host.innerHTML = skeletonMarkup(4);
  try {
    let response;
    if (type === 'pulse') response = await resourceRequests.run(resourceKey, signal => NexusAPI.realtime({}, {signal,force}));
    if (type === 'funnel') response = await resourceRequests.run(resourceKey, signal => NexusAPI.funnel(analyticsQuery(resourceKey,7),{signal,force}));
    if (type === 'cohort') response = await resourceRequests.run(resourceKey, signal => NexusAPI.cohort({signal,force}));
    if (type === 'revenue') response = await resourceRequests.run(resourceKey, signal => NexusAPI.revenue(analyticsQuery(resourceKey,30),{signal,force}));
    if (type === 'pulse') {
      const rows = response.data || [];
      const total = rows.reduce((sum,row) => sum + Number(row.Amount || 0),0);
      host.innerHTML = rows.length ? webMetricHtml('Giao dịch gần nhất', [['GIAO DỊCH',formatCompactNumber(rows.length),''],['DOANH THU',formatCurrency(total),''],['KHÁCH HÀNG',formatCompactNumber(new Set(rows.map(row=>row.CustomerID)).size),'']], webTable(rows.slice(0,10), [{label:'MÃ ĐƠN',key:'OrderID'},{label:'DANH MỤC',key:'Category'},{label:'KHU VỰC',key:'Region'},{label:'GIÁ TRỊ',render:item=>formatCurrency(item.Amount)},{label:'THỜI GIAN',render:item=>formatDate(item.OrderDate)}])) : emptyMarkup();
    } else if (type === 'funnel') {
      const data = response.data;
      host.innerHTML = webMetricHtml('Users theo bước chuyển đổi', [['TỶ LỆ HOÀN TẤT',`${data.completion_rate}%`,''],['TỔNG TRUY CẬP',formatCompactNumber(data.steps[0]?.users || 0),''],['HOÀN TẤT',formatCompactNumber(data.steps.at(-1)?.users || 0),'']], `<div class="funnel-visual">${data.steps.map(step=>`<span style="width:${Math.max(step.rate,22)}%">${escapeHtml(step.name)} · ${formatCompactNumber(step.users)} · ${step.rate}%</span>`).join('')}</div>`);
    } else if (type === 'cohort') {
      const data = response.data;
      host.innerHTML = webMetricHtml('Retention theo Cohort', [['COHORT',String(data.cohorts.length),''],['NGƯỜI DÙNG',formatCompactNumber(data.cohorts.reduce((sum,row)=>sum+row.users,0)),'']], `<div class="cohort-grid">${data.cohorts.flatMap(row=>row.retention.map(value=>`<span style="opacity:${Math.max(.15,value/100)}">${value}%</span>`)).join('')}</div>`);
    } else {
      const data = response.data; const total = data.daily.reduce((sum,row)=>sum+Number(row.revenue||0),0);
      host.innerHTML = webMetricHtml('Doanh thu theo ngày', [['TỔNG DOANH THU',formatCurrency(total),''],['ĐƠN HÀNG',formatCompactNumber(data.daily.reduce((sum,row)=>sum+Number(row.orders||0),0)),''],['KHU VỰC',String(data.by_region.length),'']], `<div class="reference-bars">${data.daily.slice(-14).map(row=>`<i style="height:${Math.max(6,Number(row.revenue||0)/(Math.max(...data.daily.map(item=>Number(item.revenue||0)),1))*100)}%" title="${escapeHtml(row.label)} · ${formatCurrency(row.revenue)}"></i>`).join('')}</div>`);
    }
  } catch (error) { if (error?.code !== 'STALE_REQUEST') host.innerHTML = errorMarkup(error,resourceKey); }
}

function statusLabel(status) {
  return ({UPLOADED:'Đã tải lên',PREVIEWED:'Đã xem trước',VALIDATING:'Đang kiểm tra',PROCESSING:'Đang nhập',COMPLETED:'Hoàn tất',FAILED:'Thất bại',CANCELLED:'Đã hủy'})[status] || status;
}

function setIngestionStatus(message, kind = '') {
  document.querySelectorAll('.ingestion-status').forEach(container => {
    container.className = `ingestion-status ${kind}`;
    container.innerHTML = message ? `<i class="ph ${kind === 'error' ? 'ph-warning-circle' : kind === 'success' ? 'ph-check-circle' : 'ph-spinner-gap'}"></i><span>${escapeHtml(message)}</span>` : '';
  });
}

function suggestedColumn(field, columns) {
  const aliases = {
    timestamp: ['timestamp','created_at','date','datetime','order_date','time'], revenue: ['revenue','amount','sales','total','value'],
    event_id: ['event_id','order_id','id'], customer_id: ['customer_id','user_id','client_id'], category: ['category','type'],
    region: ['region','country','location'], source: ['source','channel'], product: ['product','product_name','item'],
    currency: ['currency','currency_code'], is_conversion: ['is_conversion','converted','conversion']
  };
  const normalize = value => value.toLowerCase().replace(/[^a-z0-9]/g, '');
  const normalized = new Map(columns.map(column => [normalize(column), column]));
  return (aliases[field] || []).map(alias => normalized.get(normalize(alias))).find(Boolean) || '';
}

function renderImportPreview(payload) {
  const preview = payload.preview;
  const columns = preview.columns || [];
  const headers = columns.map(column => `<th>${escapeHtml(column)}<small>${escapeHtml(preview.inferred_types?.[column] || 'STRING')}</small></th>`).join('');
  const rows = (preview.rows || []).slice(0, 5).map(row => `<tr>${columns.map(column => `<td>${escapeHtml(row[column])}</td>`).join('')}</tr>`).join('');
  const mappings = ingestionFields.map(([field,label,type,required]) => {
    const suggested = suggestedColumn(field, columns);
    return `<label><span>${label}${required ? ' *' : ''}</span><select data-canonical="${field}" data-type="${type}" ${required ? 'required' : ''}><option value="">${required ? 'Chọn cột' : 'Không nhập'}</option>${columns.map(column => `<option value="${escapeHtml(column)}" ${column === suggested ? 'selected' : ''}>${escapeHtml(column)}</option>`).join('')}</select></label>`;
  }).join('');
  const content = `<div class="ingestion-steps"><b class="done">1 Tải lên</b><b class="done">2 Xem trước</b><b>3 Ánh xạ</b><b>4 Nhập</b></div>
    <div class="preview-summary"><span><b>${preview.row_count}</b>dòng</span><span><b>${preview.column_count}</b>cột</span><span><b>${preview.formula_cells_ignored || 0}</b>công thức bỏ qua</span></div>
    <div class="preview-table"><table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div>
    <form class="mapping-form"><div class="mapping-heading"><div><h3>Ánh xạ cột</h3><p>Hai trường có dấu * là bắt buộc. Dữ liệu sai kiểu sẽ không bị tự động ép.</p></div></div><div class="mapping-grid">${mappings}</div><label class="partial-option"><input type="checkbox" name="allow_partial"> Nhập các dòng hợp lệ và giữ lại lỗi để kiểm tra</label><button type="button" class="dark-button" data-action="run-file-import">Kiểm tra & nhập dữ liệu</button></form>`;
  document.querySelectorAll('.ingestion-preview').forEach(container => { container.innerHTML = content; });
}

function renderImportErrors(items) {
  if (!items?.length) return '';
  return `<div class="import-errors"><h3>Chi tiết lỗi</h3>${items.slice(0, 20).map(error => `<p><b>Dòng ${error.row_number}</b><span>${escapeHtml(error.field)} · ${escapeHtml(error.code)}</span><small>${escapeHtml(error.message)}</small></p>`).join('')}</div>`;
}

async function handleImportFile(file) {
  if (!file) return;
  setIngestionStatus(`Đang tải ${file.name} lên máy chủ...`);
  document.querySelectorAll('.ingestion-preview').forEach(container => { container.innerHTML = ''; });
  try {
    const uploaded = await NexusAPI.uploadDataset(file);
    activeImport = uploaded.data.job;
    setIngestionStatus('Đã tải lên. Đang đọc cấu trúc và tạo bản xem trước...');
    const previewed = await NexusAPI.previewImport(activeImport.id);
    activeImport = previewed.data.job;
    renderImportPreview(previewed.data);
    setIngestionStatus(`Đã kiểm tra ${previewed.data.preview.row_count} dòng. Hãy xác nhận ánh xạ cột.`, 'success');
  } catch (error) {
    setIngestionStatus(error.message, 'error');
    await loadImportHistory();
  }
}

async function submitImport(trigger) {
  if (!activeImport) return;
  const form = trigger.closest('.mapping-form');
  const fields = [...form.querySelectorAll('select[data-canonical]')].filter(select => select.value).map(select => ({ source_column: select.value, canonical_field: select.dataset.canonical, data_type: select.dataset.type }));
  const requiredMissing = [...form.querySelectorAll('select[required]')].some(select => !select.value);
  if (requiredMissing) return setIngestionStatus('Hãy ánh xạ đủ trường Thời gian và Doanh thu.', 'error');
  trigger.disabled = true;
  setIngestionStatus('Đang kiểm tra từng dòng và nhập dữ liệu...');
  try {
    const response = await NexusAPI.runImport(activeImport.id, { display_name: activeImport.original_filename.replace(/\.[^.]+$/, ''), allow_partial: form.querySelector('[name="allow_partial"]').checked, fields });
    activeImport = response.data.job;
    if (activeImport.status === 'COMPLETED') {
      setIngestionStatus(`Hoàn tất: ${activeImport.valid_rows} dòng hợp lệ, ${activeImport.invalid_rows} dòng lỗi.`, 'success');
    } else {
      const errors = await NexusAPI.importErrors(activeImport.id);
      setIngestionStatus(`Nhập thất bại: ${activeImport.invalid_rows} dòng không hợp lệ.`, 'error');
      document.querySelectorAll('.ingestion-preview').forEach(container => { container.insertAdjacentHTML('beforeend', renderImportErrors(errors.data.items)); });
    }
    await loadImportHistory();
  } catch (error) {
    setIngestionStatus(error.message, 'error');
  } finally {
    trigger.disabled = false;
  }
}

async function loadImportHistory(force = false) {
  const containers = document.querySelectorAll('.ingestion-history');
  if (!containers.length) return;
  if (!canManageIngestion()) {
    containers.forEach(container => { container.innerHTML = blockedMarkup('Chỉ Owner hoặc Admin có thể xem lịch sử nhập dữ liệu.'); });
    return;
  }
  containers.forEach(container => { container.innerHTML = skeletonMarkup(3); });
  try {
    const response = await resourceRequests.run('import-history', signal => NexusAPI.importJobs(queryFor('import-history'), {signal,force}));
    const jobs = response.data || [];
    const html = `<div class="history-heading"><h3>Lịch sử nhập</h3><small>${response.meta.pagination.total} lần nhập</small></div>${resourceToolbar('import-history')}${jobs.length ? `<div class="history-table"><table><thead><tr><th>Tệp</th><th>Ngày tải</th><th>Trạng thái</th><th>Hợp lệ / lỗi</th></tr></thead><tbody>${jobs.map(job => `<tr><td><b>${escapeHtml(job.original_filename)}</b><small>${escapeHtml(job.uploader_name || '')}</small></td><td>${new Date(job.created_at).toLocaleString('vi-VN')}</td><td><span class="job-status ${job.status.toLowerCase()}">${statusLabel(job.status)}</span></td><td>${job.valid_rows || 0} / ${job.invalid_rows || 0}</td></tr>`).join('')}</tbody></table></div>${pagerMarkup('import-history',response.meta.pagination)}` : emptyMarkup('Chưa có lần nhập dữ liệu nào.')}`;
    containers.forEach(container => { container.innerHTML = html; });
  } catch (error) {
    if (error?.code !== 'STALE_REQUEST') containers.forEach(container => { container.innerHTML = errorMarkup(error,'import-history'); });
  }
}

async function loadWorkspaceMembers() {
  const container = document.getElementById('workspace-members');
  if (!container) return;
  try {
    const response = await NexusAPI.members();
    container.innerHTML = `<table><thead><tr><th>THÀNH VIÊN</th><th>EMAIL</th><th>VAI TRÒ</th><th>THAM GIA</th></tr></thead><tbody>${response.data.map(member => `<tr><td><b>${member.full_name}</b></td><td>${member.email}</td><td><span class="status-pill">${member.role}</span></td><td>${new Date(member.joined_at).toLocaleDateString('vi-VN')}</td></tr>`).join('')}</tbody></table>`;
  } catch (error) {
    container.innerHTML = `<p class="loading-state">${error.status === 403 ? 'Bạn không có quyền quản lý thành viên.' : 'Không thể tải thành viên.'}</p>`;
  }
}

function formatCompactNumber(value) {
  return new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatCurrency(value) {
  return `₫${formatCompactNumber(value)}`;
}

function setText(selector, value) {
  const element = document.querySelector(selector);
  if (element) element.textContent = value;
}

function applyOverviewData(payload) {
  const summary = payload.summary;
  setText('#home-screen .hero-card h2', formatCurrency(summary.revenue));
  setText('#home-screen .hero-card .trend', `${summary.revenue_change >= 0 ? '+' : ''}${summary.revenue_change}%`);
  setText('#home-screen .metric-card:nth-child(1) h3', formatCompactNumber(summary.users));
  setText('#home-screen .metric-card:nth-child(1) .metric-change', `${summary.users_change >= 0 ? '+' : ''}${summary.users_change}%`);
  setText('#home-screen .metric-card:nth-child(2) h3', `${summary.conversion}%`);
  setText('#home-screen .metric-card:nth-child(2) .metric-change', `${summary.conversion_change >= 0 ? '+' : ''}${summary.conversion_change}%`);
  setText('.alert-nav b', summary.unread_alerts);

  const webValues = [formatCurrency(summary.revenue), formatCompactNumber(summary.users), `${summary.conversion}%`, formatCompactNumber(summary.sessions)];
  document.querySelectorAll('#overview-web-panel .web-kpi-grid article').forEach((card, index) => {
    const heading = card.querySelector('h2');
    if (heading) heading.textContent = webValues[index];
  });
  const webChanges = [summary.revenue_change, summary.users_change, summary.conversion_change, summary.sessions_change];
  document.querySelectorAll('#overview-web-panel .web-kpi-grid article').forEach((card, index) => {
    const change = card.querySelector('span');
    if (change) change.textContent = `${webChanges[index] >= 0 ? '+' : ''}${webChanges[index]}%`;
  });

  const traffic = payload.traffic_sources;
  setText('#home-screen .traffic-block .section-title h2', 'Doanh thu theo danh mục');
  setText('#home-screen .traffic-block .section-title p', 'Dữ liệu đã nhập trong Workspace');
  setText('#overview-web-panel .source-card .web-card-title h2', 'Doanh thu theo danh mục');
  setText('#overview-web-panel .source-card .web-card-title p', 'Phân bổ theo dữ liệu đã nhập');
  document.querySelectorAll('#home-screen .legend p').forEach((row, index) => {
    row.hidden = !traffic[index];
    if (!traffic[index]) return;
    row.childNodes.forEach(node => { if (node.nodeType === Node.TEXT_NODE) node.textContent = traffic[index].name; });
    const value = row.querySelector('b');
    if (value) value.textContent = `${traffic[index].share}%`;
  });
  setText('#home-screen .donut strong', formatCompactNumber(summary.sessions));

  const mobileAttention = document.querySelector('#home-screen .section-block');
  if (mobileAttention) {
    mobileAttention.querySelectorAll('.insight-card,.resource-state').forEach(item => item.remove());
    const items = payload.attention || [];
    if (!items.length) mobileAttention.insertAdjacentHTML('beforeend', emptyMarkup());
    else mobileAttention.insertAdjacentHTML('beforeend', items.slice(0,3).map(item => `<button class="insight-card" data-action="detail" data-title="${escapeHtml(item.title)}" data-description="${escapeHtml(item.description)}"><span class="insight-icon ${item.severity === 'warning' ? 'warning' : 'positive'}"><i class="ph-fill ${item.severity === 'warning' ? 'ph-warning-circle' : 'ph-sparkle'}"></i></span><span class="insight-copy"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.description)}</small></span><span>${escapeHtml(item.change_value || item.severity)}</span><i class="ph ph-caret-right"></i></button>`).join(''));
  }

  const attention = document.querySelector('#overview-web-panel .attention-card');
  if (attention) {
    attention.innerHTML = `<div class="web-card-title"><div><h2>Điểm cần chú ý</h2><p>Dữ liệu từ Workspace</p></div><button data-web-screen="insights">Xem tất cả</button></div>${(payload.attention || []).length ? payload.attention.slice(0,3).map(item => `<div class="web-insight ${item.severity === 'warning' ? 'warning-bg' : 'success-bg'}"><i class="ph-fill ph-sparkle"></i><div><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.description)}</small></div><strong>${escapeHtml(item.change_value || '')}</strong></div>`).join('') : emptyMarkup()}`;
  }
  const campaign = document.querySelector('#overview-web-panel .campaign-card');
  if (campaign) campaign.innerHTML = `<div class="web-card-title"><div><h2>Chiến dịch hàng đầu</h2><p>Chưa có API campaign</p></div></div>${blockedMarkup('Backend chưa có mô hình chiến dịch; không hiển thị số liệu giả.')}`;

  const values = (payload.trend || []).map(row => Number(row.value ?? row.revenue ?? 0));
  const svg = document.querySelector('#overview-web-panel .web-line-chart svg');
  if (svg && values.length) {
    const max = Math.max(...values,1); const min = Math.min(...values,0); const span = Math.max(max-min,1);
    const points = values.map((value,index) => `${values.length === 1 ? 350 : index/(values.length-1)*700} ${210-(value-min)/span*180}`);
    const line = `M${points.join(' L')}`;
    const paths = svg.querySelectorAll('path');
    if (paths[0]) paths[0].setAttribute('d', `${line} L700 230 L0 230Z`);
    if (paths[1]) paths[1].setAttribute('d', line);
  }
  const mobileSvg = document.querySelector('#home-screen .hero-chart');
  if (mobileSvg && values.length) {
    const max = Math.max(...values,1); const min = Math.min(...values,0); const span = Math.max(max-min,1);
    const points = values.map((value,index) => `${values.length === 1 ? 160 : index/(values.length-1)*320} ${96-(value-min)/span*82}`);
    const line = `M${points.join(' L')}`;
    const paths = mobileSvg.querySelectorAll('path');
    if (paths[0]) paths[0].setAttribute('d', `${line} L320 106 L0 106Z`);
    if (paths[1]) paths[1].setAttribute('d', line);
  }
  document.querySelectorAll('#overview-web-panel .web-source-content p').forEach((row,index) => {
    row.hidden = !traffic[index];
    if (!traffic[index]) return;
    row.childNodes.forEach(node => { if (node.nodeType === Node.TEXT_NODE) node.textContent = traffic[index].name; });
    const value = row.querySelector('b'); if (value) value.textContent = `${traffic[index].share}%`;
  });
  setText('#overview-web-panel .web-donut b', formatCompactNumber(summary.sessions));
  const sourceDetail = document.querySelector('#overview-web-panel .source-card [data-web-screen]');
  if (sourceDetail) sourceDetail.dataset.webScreen = 'revenue-analysis';
  document.querySelector('#overview-web-panel .revenue-card .web-card-title button')?.setAttribute('disabled','');
}

async function loadBackendData(days = 7, force = false) {
  setText('#home-screen .hero-card h2', '—');
  setText('#home-screen .metric-card:nth-child(1) h3', '—');
  setText('#home-screen .metric-card:nth-child(2) h3', '—');
  document.querySelector('#home-screen .section-block')?.querySelectorAll('.insight-card').forEach(item => item.remove());
  const homeAttention = document.querySelector('#home-screen .section-block');
  if (homeAttention && !homeAttention.querySelector('.resource-skeleton')) homeAttention.insertAdjacentHTML('beforeend', skeletonMarkup(2));
  const campaign = document.querySelector('#overview-web-panel .campaign-card');
  if (campaign) campaign.innerHTML = skeletonMarkup(2);
  try {
    const response = await resourceRequests.run('overview', signal => NexusAPI.bootstrap(days, {signal,force}));
    const data = response.data;
    applyOverviewData(data.overview.data || data.overview);
    setText('#profile-screen .profile-hero h1', data.profile.full_name);
    setText('#profile-screen .profile-hero p', `${data.profile.job_title} · ${data.profile.workspace}`);
    setText('.web-user b', data.profile.full_name);
    setText('.web-user small', data.profile.job_title);
    document.documentElement.dataset.api = 'connected';
    document.querySelectorAll('#home-screen .resource-skeleton').forEach(item => item.remove());
  } catch (error) {
    if (error?.code === 'STALE_REQUEST') return;
    document.documentElement.dataset.api = 'offline';
    document.querySelectorAll('#home-screen .resource-skeleton').forEach(item => item.remove());
    const mobile = document.querySelector('#home-screen .screen-scroll');
    const desktop = document.querySelector('#overview-web-panel');
    if (mobile && !mobile.querySelector('.api-load-error')) mobile.insertAdjacentHTML('afterbegin', `<div class="api-load-error">${errorMarkup(error,'overview')}</div>`);
    if (desktop && !desktop.querySelector('.api-load-error')) desktop.insertAdjacentHTML('afterbegin', `<div class="api-load-error">${errorMarkup(error,'overview')}</div>`);
  }
}

async function handleBackendForm(button) {
  const form = button.closest('.mobile-form');
  if (!form) return false;
  const values = [...form.querySelectorAll('input')].map(input => input.value.trim());
  const status = form.querySelector('.form-status');
  if (status) status.textContent = '';
  try {
    if (currentPage === 'login') {
      await NexusAPI.login({ email: values[0], password: values[1], redirect_to: '/' });
      authSession = (await NexusAPI.session()).data;
      document.body.classList.remove('auth-required');
      showScreen('home');
      await loadBackendData();
      return true;
    }
    if (currentPage === 'register') {
      await NexusAPI.register({ full_name: values[0], email: values[1], workspace_name: values[2], password: values[3] });
      authSession = (await NexusAPI.session()).data;
      document.body.classList.remove('auth-required');
      showScreen('home');
      await loadBackendData();
      return true;
    }
    if (currentPage === 'forgot-password') {
      await NexusAPI.forgotPassword({ email: values[0] });
      if (status) status.textContent = 'Nếu tài khoản tồn tại, hướng dẫn đặt lại mật khẩu đã được chuẩn bị.';
      return true;
    }
    if (currentPage === 'reset-password') {
      const token = new URLSearchParams(location.search).get('reset_token') || '';
      await NexusAPI.resetPassword({ token, password: values[0] });
      if (status) status.textContent = 'Đã đặt lại mật khẩu. Hãy đăng nhập lại.';
      setTimeout(() => openPage('login'), 700);
      return true;
    }
    if (currentPage === 'create-report') {
      await NexusAPI.createReport({ name: values[0] || 'Báo cáo chưa đặt tên', report_type: values[2] || 'custom' });
      button.textContent = 'Đã tạo bản nháp';
      setTimeout(() => openPage('reports'), 400);
      return true;
    }
    if (currentPage === 'edit-profile') {
      await NexusAPI.updateProfile({ full_name: values[0] || 'Trương Anh', job_title: values[1] || 'Data Analyst', email: values[2] || 'truong@nexus.vn', phone: values[3] || '', workspace: 'Nexus Team' });
      button.textContent = 'Đã lưu thay đổi';
      await loadBackendData();
      return true;
    }
  } catch (error) {
    if (status) status.textContent = error.message;
    else button.textContent = 'Không thể lưu — thử lại';
    return true;
  }
  return false;
}

document.addEventListener('click', event => {
  const webPeriod = event.target.closest('#overview-web-panel .web-period button');
  if (webPeriod && !webPeriod.disabled) {
    const label = webPeriod.textContent.trim();
    if (label.includes('Tùy chỉnh')) return;
    document.querySelectorAll('#overview-web-panel .web-period button').forEach(button => button.classList.toggle('active',button === webPeriod));
    loadBackendData(label.includes('Hôm nay') ? 1 : label.includes('30') ? 30 : 7);
    return;
  }
  const importAction = event.target.closest('[data-action="choose-import-file"]');
  if (importAction) {
    event.preventDefault();
    const workspace = importAction.closest('.ingestion-workspace') || document.querySelector('.ingestion-workspace');
    workspace?.querySelector('.ingestion-file-input')?.click();
    return;
  }
  const runImportAction = event.target.closest('[data-action="run-file-import"]');
  if (runImportAction) {
    event.preventDefault();
    submitImport(runImportAction);
    return;
  }
  const backendButton = event.target.closest('.mobile-form .primary-button');
  if (backendButton && ['login','register','forgot-password','reset-password','create-report','edit-profile'].includes(currentPage)) {
    event.preventDefault();
    handleBackendForm(backendButton);
    return;
  }
  const retry = event.target.closest('[data-resource-retry]');
  if (retry) {
    event.preventDefault();
    reloadResource(retry.dataset.resourceRetry, true);
    return;
  }
  const pager = event.target.closest('[data-resource-page]');
  if (pager && !pager.disabled) {
    event.preventDefault();
    const key = pager.dataset.resourcePage;
    queryFor(key).page = Number(pager.dataset.page);
    reloadResource(key);
    return;
  }
  const markRead = event.target.closest('[data-alert-read]');
  if (markRead) {
    event.preventDefault();
    markRead.disabled = true;
    NexusAPI.markAlertRead(Number(markRead.dataset.alertRead)).then(() => loadMobileAlerts(true)).catch(error => { markRead.disabled = false; markRead.textContent = error.message; });
    return;
  }
  const webTrigger = event.target.closest('[data-web-screen]');
  if (webTrigger) return showWebScreen(webTrigger.dataset.webScreen);
  const route = event.target.closest('[data-route]');
  if (route) return openPage(route.dataset.route);
  const page = event.target.closest('[data-page]');
  if (page) return openPage(page.dataset.page);
  const nav = event.target.closest('[data-screen]');
  if (nav) return showScreen(nav.dataset.screen);
  const trigger = event.target.closest('[data-action]');
  if (!trigger) return;
  const action = trigger.dataset.action;
  if (action === 'apply-analytics-filter') {
    const box = trigger.closest('.filter-form');
    const days = box.querySelector('[data-analytics-days]').value;
    const from = box.querySelector('[data-analytics-date-from]').value;
    const to = box.querySelector('[data-analytics-date-to]').value;
    const status = box.querySelector('[role="status"]');
    const query = queryFor('mobile-analytics');
    if (days === 'custom') {
      if (!from || !to || from > to) { status.textContent = 'Hãy chọn khoảng ngày hợp lệ.'; return; }
      query.date_from = from; query.date_to = to; delete query.days;
    } else {
      query.days = Number(days); delete query.date_from; delete query.date_to;
    }
    showScreen('analytics');
    return;
  }
  if (action === 'logout') {
    NexusAPI.logout().finally(() => { authSession = null; document.body.classList.add('auth-required'); openPage('login'); });
  }
  if (action === 'invite-member') {
    const box = trigger.closest('.member-invite');
    const email = box.querySelector('input').value.trim();
    const role = box.querySelector('select').value;
    const message = box.querySelector('[role="status"]');
    NexusAPI.inviteMember({ email, role }).then(result => { message.textContent = `Đã tạo lời mời. Mã: ${result.data.invitation_token}`; }).catch(error => { message.textContent = error.message; });
  }
  if (action === 'focus-create-resource') document.querySelector('.web-create-form input')?.focus();
  if (action === 'focus-member-invite') document.querySelector('.member-invite input')?.focus();
  if (action === 'refresh-web-resource') loadWebResource(currentWebScreen, true);
  if (action === 'detail') openDetail(trigger.dataset.title, trigger.dataset.description);
  if (action === 'close') modal.classList.remove('open');
  if (action === 'search') openPage('global-search');
  if (action === 'close-search') searchOverlay.classList.remove('open');
  if (action === 'back') goBack();
  if (action === 'secondary-menu') openPage('ui-map');
  if (['home', 'analytics', 'insights', 'alerts', 'profile'].includes(action)) showScreen(action);
});

document.addEventListener('submit', async event => {
  const form = event.target.closest('[data-create-resource]');
  if (!form) return;
  event.preventDefault();
  const message = form.querySelector('[role="status"]');
  const button = form.querySelector('button[type="submit"]');
  if (!['OWNER','ADMIN','ANALYST'].includes(authSession?.workspace?.role)) {
    message.textContent = 'Vai trò Viewer chỉ có quyền xem.';
    return;
  }
  button.disabled = true;
  message.textContent = 'Đang lưu...';
  try {
    if (form.dataset.createResource === 'report') {
      await NexusAPI.createReport({name: form.elements.name.value.trim(), report_type: form.elements.report_type.value});
      form.reset(); await loadListResource('web-reports', true);
    } else {
      await NexusAPI.createAlert({title: form.elements.title.value.trim(), description: form.elements.description.value.trim(), severity: form.elements.severity.value});
      form.reset(); await loadListResource('web-alerts', true);
    }
    message.textContent = 'Đã lưu thành công.';
  } catch (error) { message.textContent = error.message; }
  finally { button.disabled = false; }
});

document.addEventListener('change', event => {
  if (event.target.matches('.ingestion-file-input')) {
    handleImportFile(event.target.files?.[0]);
    event.target.value = '';
    return;
  }
  const controls = event.target.closest('[data-resource-controls]');
  if (!controls) return;
  const key = controls.dataset.resourceControls;
  const query = queryFor(key);
  if (event.target.matches('[data-resource-filter]')) {
    ['status','severity','unread_only','is_favorite'].forEach(name => delete query[name]);
    const [name,value] = event.target.value.split('=');
    if (name && value) query[name] = value;
  }
  if (event.target.matches('[data-resource-sort]')) query.sort_order = event.target.value;
  if (event.target.matches('[data-resource-days]')) {
    query.days = Number(event.target.value); delete query.date_from; delete query.date_to;
    controls.querySelectorAll('input[type="date"]').forEach(input => { input.value = ''; });
  }
  if (event.target.matches('[data-resource-date-from]')) query.date_from = event.target.value;
  if (event.target.matches('[data-resource-date-to]')) query.date_to = event.target.value;
  query.page = 1;
  if ((query.date_from && !query.date_to) || (!query.date_from && query.date_to)) return;
  reloadResource(key);
});

let resourceSearchTimer = null;
document.addEventListener('input', event => {
  if (event.target.matches('.web-search input')) {
    queryFor('web-global-search').search = event.target.value.trim();
    clearTimeout(resourceSearchTimer);
    resourceSearchTimer = setTimeout(() => loadWebGlobalSearch(),250);
    return;
  }
  const input = event.target.closest('[data-resource-search]');
  if (!input) return;
  const key = input.dataset.resourceSearch;
  const query = queryFor(key);
  query.search = input.value.trim();
  query.page = 1;
  clearTimeout(resourceSearchTimer);
  resourceSearchTimer = setTimeout(() => reloadResource(key), 250);
});

document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => {
  if (button.dataset.period === 'Tùy chỉnh') return openPage('advanced-filter');
  document.querySelectorAll('[data-period]').forEach(item => item.classList.remove('selected'));
  button.classList.add('selected');
  document.querySelector('.hero-card .muted').textContent = `so với ${button.dataset.period.toLowerCase()}`;
  const selectedDays = button.dataset.period === 'Hôm nay' ? 1 : button.dataset.period === '30 ngày qua' ? 30 : 7;
  loadBackendData(selectedDays);
}));

modal.addEventListener('click', event => { if (event.target === modal) modal.classList.remove('open'); });

async function initializeAuth() {
  try {
    authSession = (await NexusAPI.session()).data;
    document.body.classList.remove('auth-required');
    const memberNav = document.querySelector('[data-web-screen="members"]');
    if (memberNav) memberNav.hidden = !['OWNER','ADMIN'].includes(authSession.workspace.role);
    document.querySelectorAll('.web-actions button').forEach(button => { button.disabled = true; button.title = 'Backend chưa hỗ trợ thao tác này'; });
    const customPeriod = [...document.querySelectorAll('#overview-web-panel .web-period button')].find(button => button.textContent.includes('Tùy chỉnh'));
    if (customPeriod) { customPeriod.disabled = true; customPeriod.title = 'Dùng bộ lọc ngày tại các màn phân tích'; }
    await loadBackendData();
  } catch (_error) {
    authSession = null;
    document.body.classList.add('auth-required');
    openPage(new URLSearchParams(location.search).has('reset_token') ? 'reset-password' : 'login');
  }
}

initializeAuth();
