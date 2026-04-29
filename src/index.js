const HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ChannelGuard - YouTube Channel Risk Scanner</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #0a0a0a;
    color: #fff;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .container { max-width: 640px; text-align: center; }
  h1 { font-size: clamp(2rem, 6vw, 3.5rem); margin-bottom: 1rem; letter-spacing: -0.02em; }
  .accent { color: #00d97e; }
  .tagline { color: #aaa; font-size: 1.1rem; line-height: 1.6; margin-bottom: 2rem; }
  .badge {
    display: inline-block;
    background: rgba(0, 217, 126, 0.1);
    color: #00d97e;
    padding: 6px 14px;
    border-radius: 100px;
    font-size: 0.85rem;
    margin-bottom: 1.5rem;
    border: 1px solid rgba(0, 217, 126, 0.3);
  }
  .footer { margin-top: 3rem; color: #555; font-size: 0.85rem; }
</style>
</head>
<body>
<div class="container">
  <div class="badge">Coming Soon</div>
  <h1>Channel<span class="accent">Guard</span></h1>
  <p class="tagline">Scan any YouTube channel for inauthentic-content risk patterns that trigger YouTube's automated termination policy.</p>
  <p class="footer">A free tool by <a href="https://theoperatorai.io" style="color:#888;">TheOperatorAI</a></p>
</div>
</body>
</html>`;

export default {
  async fetch(request, env, ctx) {
    return new Response(HTML, {
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'public, max-age=300',
      },
    });
  },
};
