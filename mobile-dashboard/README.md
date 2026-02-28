# TrackAttendance Mobile Dashboard

Mobile-friendly attendance dashboard with automatic refresh.

## Features

- Auto-refresh every 15 seconds (configurable)
- Mobile-first responsive design
- PWA support (add to home screen)
- Offline indicator
- Cost-effective on Cloud Run (polling, not SSE)

## Setup

### 1. Configure API URL

Edit `index.html` and set your API URL:

```javascript
window.CONFIG = {
    API_URL: 'https://your-api.run.app',
    POLL_INTERVAL: 15000,  // Fallback polling interval
    SHOW_TOAST: true       // Show notification on new scans
};
```

### 2. Deploy to Cloudflare Pages

```bash
# Option 1: Connect GitHub repo
# Go to Cloudflare Pages > Create Project > Connect GitHub

# Option 2: Direct upload
npx wrangler pages deploy .
```

### 3. Add SSE endpoint to API

See `docs/MOBILE_DASHBOARD_PLAN.md` for the API changes needed.

## Project Structure

```
mobile-dashboard/
├── index.html      # Main dashboard page
├── css/
│   └── style.css   # Custom styles
├── js/
│   └── dashboard.js # SSE connection & UI logic
├── manifest.json   # PWA manifest
├── sw.js           # Service worker
├── _headers        # Cloudflare headers
└── icons/          # App icons
```

## Browser Support

- Chrome 52+
- Firefox 52+
- Safari 11+
- Edge 79+

## License

MIT
