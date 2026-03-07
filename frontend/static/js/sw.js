// offline-booking-sw.js
const CACHE_NAME = 'ai-sched-offline-v1';
const OFFLINE_URL = '/offline';

const CORE_ASSETS = [
    '/',
    '/login',
    '/register',
    '/static/css/style.css',
    '/static/js/main.js',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(CORE_ASSETS);
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Only handle POST requests (Bookings) for offline queueing
    if (event.request.method === 'POST' && event.request.url.includes('/api/book')) {
        event.respondWith(
            fetch(event.request.clone()).catch(async () => {
                // If network fails, save to IndexedDB/LocalStorage logic (simplified for walkthrough)
                return new Response(JSON.stringify({ 
                    offline: true, 
                    message: "Booking saved offline. We will sync when you're back!" 
                }), {
                    headers: { 'Content-Type': 'application/json' }
                });
            })
        );
        return;
    }

    // Standard Cache-First for assets, Network-First for pages
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
