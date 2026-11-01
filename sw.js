// ── 金水 Swimming PWA 輕量防中繼 Service Worker (CWE-668 / ASVS V14.4.1 合規) ──
const CACHE_NAME = 'swim-pwa-cache-v20261101-1145';

// 核心離線離線可用資源清單
const PRECACHE_ASSETS = [
    '/',
    '/index.html',
    '/256split.html',
    '/manifest.json',
    '/chart.min.js',
    '/chartjs-adapter-date-fns.bundle.min.js',
    '/lottie.min.js',
    '/sql-wasm.js',
    '/sql-wasm.wasm',
    '/pdf.min.js',
    '/pdf.worker.min.js',
    '/pdf-lib.min.js'
];

// 安裝階段：快取基本核心框架
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(PRECACHE_ASSETS).catch(err => {
                console.warn('[SW] 部分非關鍵資源快取略過:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

// 啟動階段：清理過期舊快取，防快取污染
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.map(k => {
                    if (k !== CACHE_NAME) {
                        return caches.delete(k);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// 攔截請求階段：Network-First (網路優先) + 敏感路徑強制直通
self.addEventListener('fetch', event => {
    const req = event.request;
    const url = new URL(req.url);

    // 🌐 1. 跨域外部第三方資源 (如 cdn.tailwindcss.com, cdnjs, unpkg, googleapis)
    // 絕不進行 Service Worker 攔截，完全交由瀏覽器原生連線處理，徹底根絕 ERR_ABORTED 導致 CSS/JS 破圖
    if (url.origin !== self.location.origin) {
        return;
    }

    // 🔒 2. 嚴禁快取後端 API 與管理調度中心 (防止 Token 或即時日誌洩漏)
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/int') || req.method !== 'GET') {
        return; // 完全不介入，直接直通網路
    }

    // 3. 網路優先策略 (Network-First with Cache Fallback)
    event.respondWith(
        fetch(req)
            .then(networkResponse => {
                if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        // 僅快取同源靜態檔案
                        if (url.origin === self.location.origin) {
                            cache.put(req, responseClone);
                        }
                    });
                }
                return networkResponse;
            })
            .catch(() => {
                // 網路中斷時自離線快取救援
                return caches.match(req).then(cachedResponse => {
                    if (cachedResponse) return cachedResponse;
                    if (req.mode === 'navigate') {
                        return caches.match('/256split.html') || caches.match('/');
                    }
                    return new Response('離線模式且無快取可用', { status: 503, statusText: 'Service Unavailable' });
                });
            })
    );
});
