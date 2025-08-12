# app.py
from flask import Flask, render_template_string, request, redirect, url_for
import sqlite3
import re
import urllib.parse
import os

app = Flask(__name__)
DB = 'videos.db'

def init_db():
    """Initialize DB and ensure required columns exist (safe for re-run)."""
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    # create table if missing (includes views column)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            drive_id TEXT NOT NULL,
            uploader TEXT,
            likes INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

    # In case older DB exists without 'views' column, ensure it's present
    cursor.execute("PRAGMA table_info(videos)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'views' not in cols:
        cursor.execute("ALTER TABLE videos ADD COLUMN views INTEGER DEFAULT 0")
        conn.commit()
    conn.close()

# ---------- Helpers ----------
def get_db_conn():
    return sqlite3.connect(DB)

def extract_drive_id(link):
    """Extract drive id from common share link formats."""
    if not link:
        return None
    # Common patterns - Fixed regex patterns
    patterns = [
        r'/d/([a-zA-Z0-9_-]{25,})',              # /d/<id>/ - Google Drive IDs are typically 25+ chars
        r'id=([a-zA-Z0-9_-]{25,})',              # ?id=<id>
        r'drive\.google\.com/open\?id=([A-Za-z0-9_-]{25,})',  # Fixed escaping
        r'file/d/([A-Za-z0-9_-]{25,})',
    ]
    for p in patterns:
        m = re.search(p, link)
        if m:
            return m.group(1)
    # last resort: if link looks like a bare id (must be reasonable length)
    if re.fullmatch(r'[A-Za-z0-9_-]{25,}', link.strip()):
        return link.strip()
    return None

def urlsafe(u):
    return urllib.parse.quote_plus(u) if u else ''

# Add template filters
@app.template_filter('urlencode')
def urlencode_filter(s):
    if s is None:
        return ''
    return urllib.parse.quote_plus(str(s))

# ---------- Routes ----------
@app.route('/', methods=['GET'])
def home():
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'recent')

    conn = get_db_conn()
    c = conn.cursor()

    query = "SELECT id, title, uploader, likes, drive_id, views FROM videos WHERE title LIKE ? OR uploader LIKE ?"
    params = [f"%{search_query}%", f"%{search_query}%"]
    if sort_by == 'likes':
        query += " ORDER BY likes DESC, id DESC"
    else:
        query += " ORDER BY id DESC"

    c.execute(query, params)
    videos = c.fetchall()
    conn.close()

    template = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MGODWILL STREAM</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root{--gold:#FFD700;--gold-dark:#e6c200;--bg:#0e0e0e;--card:#1f1f1f;--muted:#cfcfcf}
    *{box-sizing:border-box}
    body{font-family:Inter,Arial,sans-serif;background:var(--bg);color:white;margin:0}
    #splash{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;background:linear-gradient(180deg, rgba(0,0,0,0.94), rgba(0,0,0,0.88));z-index:9999;transition:opacity .6s}
    .splash-logo{font-weight:900;color:var(--gold);font-size:34px;letter-spacing:1px;animation:logoIn .9s cubic-bezier(.2,.9,.2,1)}
    @keyframes logoIn{0%{opacity:0;transform:translateY(10px) scale(.98)}60%{opacity:1;transform:translateY(-6px) scale(1.02)}100%{transform:translateY(0) scale(1)}}
    .splash-sub{color:var(--muted);margin-top:10px}
    header{background:var(--gold);color:#051014;padding:12px 18px;display:flex;align-items:center;gap:12px;font-weight:800}
    .brand{font-size:20px}
    .container{padding:20px;max-width:1200px;margin:0 auto}
    .topbar{display:flex;gap:12px;align-items:center;margin-bottom:18px;flex-wrap:wrap}
    .btn{background:var(--gold);color:#051014;border:none;padding:9px 14px;border-radius:8px;font-weight:700;cursor:pointer}
    .btn:hover{background:var(--gold-dark)}
    input[type=text],select{padding:9px;border-radius:8px;border:none;outline:none;background:#111;color:white}
    .video-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
    .video-card{background:var(--card);border:1px solid var(--gold);border-radius:10px;overflow:hidden;transition:transform .18s,box-shadow .18s}
    .video-card:hover{transform:translateY(-6px);box-shadow:0 8px 28px rgba(255,215,0,0.06)}
    .video-card img{width:100%;height:150px;object-fit:cover;display:block}
    .video-info{padding:10px}
    .meta{color:var(--muted);font-size:13px;margin-top:6px}
    h2{color:var(--gold);margin:18px 0 8px}
    footer{padding:18px;text-align:center;color:var(--muted);font-size:13px}
    @media (max-width:720px){ .video-grid{grid-template-columns:repeat(2,1fr)} .container{padding:12px} }
  </style>
</head>
<body>
  <div id="splash" aria-hidden="true">
    <div class="splash-logo">MGODWILL STREAM</div>
    <div class="splash-sub">Welcome — loading your gold experience…</div>
  </div>

  <header>
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style="transform:translateY(1px)"><rect x="1" y="3" width="22" height="14" rx="2" fill="#051014"/><path d="M7 9v6l5-3-5-3z" fill="#FFD700"/><rect x="3.5" y="17.5" width="17" height="3" rx="1.5" fill="#051014"/></svg>
    <div class="brand">MGODWILL STREAM</div>
  </header>

  <div class="container">
    <div class="topbar">
      <a href="/upload" class="btn">Upload</a>
      <form method="get" style="display:flex;gap:8px;align-items:center">
        <input type="text" name="search" placeholder="Search title or uploader…" value="{{ request.args.get('search', '') }}">
        <select name="sort">
          <option value="recent" {% if request.args.get('sort','recent')=='recent' %}selected{% endif %}>Most Recent</option>
          <option value="likes" {% if request.args.get('sort')=='likes' %}selected{% endif %}>Most Liked</option>
        </select>
        <button class="btn" type="submit">Search</button>
      </form>
    </div>

    <h2>All Videos</h2>
    {% if videos %}
    <div class="video-grid" id="videoGrid">
      {% for vid in videos %}
      <div class="video-card">
        <a href="/view/{{ vid[0] }}" style="color:inherit;text-decoration:none;display:block">
          <img src="https://drive.google.com/thumbnail?id={{ vid[4] }}" alt="{{ vid[1] }}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQwIiBoZWlnaHQ9IjE1MCIgdmlld0JveD0iMCAwIDI0MCAxNTAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjI0MCIgaGVpZ2h0PSIxNTAiIGZpbGw9IiMxZjFmMWYiLz48dGV4dCB4PSIxMjAiIHk9Ijc1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjY2ZjZmNmIiBmb250LXNpemU9IjE0cHgiPk5vIFRodW1ibmFpbDwvdGV4dD48L3N2Zz4='">
          <div class="video-info">
            <div style="font-weight:700">{{ vid[1] }}</div>
            <div class="meta">by <a href="/channel/{{ (vid[2] or 'Anonymous')|urlencode }}">{{ vid[2] or 'Anonymous' }}</a> • Likes: {{ vid[3] }} • Views: {{ vid[5] }}</div>
          </div>
        </a>
      </div>
      {% endfor %}
    </div>
    {% else %}
      <p style="color:var(--muted)">No videos found.</p>
    {% endif %}

    <h2 style="margin-top:28px">Your Subscriptions (local)</h2>
    <div id="subscribed" style="color:var(--muted);margin-bottom:10px">No subscriptions yet.</div>
    <div id="sub_videos" class="video-grid" style="margin-top:12px"></div>
  </div>

  <footer>MGODWILL STREAM — made with gold ✨</footer>

  <script>
    // Splash hide
    window.addEventListener('load', function() {
      const s = document.getElementById('splash');
      setTimeout(function() { 
        s.style.opacity = 0; 
        setTimeout(function() { s.style.display='none'; }, 600); 
      }, 800);
    });

    // local subs rendering (re-uses server-provided videos)
    let subs = [];
    try {
      subs = JSON.parse(localStorage.getItem('mg_subs') || '[]');
    } catch(e) {
      console.warn('Failed to load subscriptions:', e);
    }
    
    const all_videos = {{ videos | tojson }};
    
    function renderSubs(){
      document.getElementById('subscribed').innerText = subs.length ? subs.join(', ') : 'No subscriptions yet.';
      const sub_videos = document.getElementById('sub_videos');
      sub_videos.innerHTML = '';
      all_videos.forEach(function(vid) {
        const uploader = vid[2] || 'Anonymous';
        if(subs.includes(uploader)){
          const card = document.createElement('div');
          card.className = 'video-card';
          card.innerHTML = 
            '<a href="/view/' + vid[0] + '" style="color:inherit;text-decoration:none;display:block">' +
              '<img src="https://drive.google.com/thumbnail?id=' + vid[4] + '" alt="' + vid[1] + '" onerror="this.src=\'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQwIiBoZWlnaHQ9IjE1MCIgdmlld0JveD0iMCAwIDI0MCAxNTAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjI0MCIgaGVpZ2h0PSIxNTAiIGZpbGw9IiMxZjFmMWYiLz48dGV4dCB4PSIxMjAiIHk9Ijc1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjY2ZjZmNmIiBmb250LXNpemU9IjE0cHgiPk5vIFRodW1ibmFpbDwvdGV4dD48L3N2Zz4=\'">' +
              '<div class="video-info">' +
                '<div style="font-weight:700">' + vid[1] + '</div>' +
                '<div class="meta">by <a href="/channel/' + encodeURIComponent(uploader) + '">' + uploader + '</a> • Likes: ' + vid[3] + ' • Views: ' + vid[5] + '</div>' +
              '</div>' +
            '</a>';
          sub_videos.appendChild(card);
        }
      });
    }
    renderSubs();
  </script>
</body>
</html>
"""
    return render_template_string(template, videos=videos, request=request)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        link = request.form.get('link','').strip()
        name = request.form.get('name','').strip() or None

        # Validate inputs
        if not title:
            return render_template_string(upload_template, error="Title is required.")
        if not link:
            return render_template_string(upload_template, error="Google Drive link is required.")

        drive_id = extract_drive_id(link)
        if not drive_id:
            return render_template_string(upload_template, error='Invalid Google Drive link. Please provide a valid shareable link.')

        # Check for duplicate drive_id
        conn = get_db_conn()
        c = conn.cursor()
        c.execute("SELECT id FROM videos WHERE drive_id = ?", (drive_id,))
        if c.fetchone():
            conn.close()
            return render_template_string(upload_template, error="This video has already been uploaded.")

        c.execute("INSERT INTO videos (title, drive_id, uploader, likes, views) VALUES (?, ?, ?, 0, 0)",
                  (title, drive_id, name))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    return render_template_string(upload_template, error=None)

upload_template = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Upload - MGODWILL STREAM</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body{background:#080808;color:white;font-family:Arial;margin:0;padding:22px}
    .btn{background:#FFD700;color:#051014;border:none;padding:10px 20px;border-radius:6px;font-weight:700;cursor:pointer}
    .error{background:#ff4444;color:white;padding:10px;border-radius:6px;margin-bottom:15px}
    input{width:100%;padding:10px;border-radius:6px;border:none;margin-bottom:10px;background:#333;color:white}
  </style>
</head>
<body>
  <a href="/" style="color:#FFD700;font-weight:800;text-decoration:none">← Back</a>
  <h1 style="color:#FFD700">Upload Video Link</h1>
  {% if error %}
  <div class="error">{{ error }}</div>
  {% endif %}
  <form method="post" style="max-width:760px">
    <label>Title *</label><br>
    <input name="title" required value="{{ request.form.get('title', '') }}"><br>
    <label>Google Drive Shareable Link *</label><br>
    <input name="link" required value="{{ request.form.get('link', '') }}" placeholder="https://drive.google.com/file/d/your-file-id/view"><br>
    <label>Your Name (optional)</label><br>
    <input name="name" value="{{ request.form.get('name', '') }}"><br>
    <button class="btn" type="submit">Upload</button>
  </form>
</body>
</html>
"""

@app.route('/view/<int:vid_id>')
def view(vid_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT title, drive_id, uploader, likes, views FROM videos WHERE id=?", (vid_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return 'Video not found', 404
    title, drive_id, uploader, likes, views = row
    uploader_str = uploader or 'Anonymous'

    # increment view count (atomic-ish)
    c.execute("UPDATE videos SET views = views + 1 WHERE id=?", (vid_id,))
    conn.commit()

    # Get updated view count
    c.execute("SELECT views FROM videos WHERE id=?", (vid_id,))
    updated_views = c.fetchone()[0]

    # 1) videos by same uploader (exclude current)
    watch_next = []
    if uploader:
        c.execute("SELECT id, title, uploader, likes, drive_id, views FROM videos WHERE uploader = ? AND id != ? ORDER BY id DESC LIMIT 10", (uploader, vid_id))
        watch_next = c.fetchall()

    # 2) fill to 10 with recent others (exclude current and already included)
    if len(watch_next) < 10:
        existing_ids = [str(r[0]) for r in watch_next]
        if existing_ids:
            placeholders = ','.join('?' for _ in existing_ids)
            sql = f"SELECT id, title, uploader, likes, drive_id, views FROM videos WHERE id != ? AND id NOT IN ({placeholders}) ORDER BY id DESC LIMIT ?"
            params = [vid_id] + existing_ids + [10 - len(watch_next)]
        else:
            sql = "SELECT id, title, uploader, likes, drive_id, views FROM videos WHERE id != ? ORDER BY id DESC LIMIT ?"
            params = [vid_id, 10 - len(watch_next)]
        c.execute(sql, params)
        watch_next += c.fetchall()

    conn.close()

    # prepare direct stream URL (works sometimes)
    direct_url = f"https://docs.google.com/uc?export=download&id={drive_id}"
    embed_url = f"https://drive.google.com/file/d/{drive_id}/preview"

    template = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{{ title }} - MGODWILL STREAM</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--gold:#FFD700;--gold-dark:#e6c200;--bg:#0b0b0b;--card:#1e1e1e}
  body{background:var(--bg);color:white;font-family:Arial;margin:0}
  header{background:var(--gold);color:#051014;padding:12px 16px;font-weight:800}
  .page{display:flex;gap:18px;padding:18px;max-width:1200px;margin:0 auto;flex-wrap:wrap}
  .main{flex:3;min-width:320px}
  .aside{flex:1;min-width:260px}
  h1{color:var(--gold);margin:0 0 8px}
  .meta{color:#cfcfcf;margin-bottom:10px}
  .video-box{background:#000;border-radius:8px;padding:8px}
  video{width:100%;height:auto;border-radius:6px;background:#000}
  iframe{width:100%;border-radius:6px;border:0;min-height:420px;background:#000}
  .controls{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center}
  .btn{background:var(--gold);color:#051014;border:none;padding:9px 12px;border-radius:8px;font-weight:700;cursor:pointer}
  .video-card{background:var(--card);border:1px solid var(--gold);border-radius:8px;overflow:hidden;margin-bottom:12px;display:flex;gap:8px}
  .video-card img{width:110px;height:70px;object-fit:cover;flex-shrink:0}
  .video-info{padding:8px;font-size:13px}
  .video-info .title{font-weight:700}
  .small{color:#cfcfcf;font-size:12px;margin-top:6px}
  a{color:var(--gold);text-decoration:none}
  @media (max-width:900px){ .page{flex-direction:column} }
</style>
</head>
<body>
  <header><a href="/" style="color:#051014;text-decoration:none;font-weight:800">← MGODWILL STREAM</a></header>

  <div class="page">
    <div class="main">
      <h1>{{ title }}</h1>
      <div class="meta">By <a href="/channel/{{ uploader_str | urlencode }}">{{ uploader_str }}</a> • Likes: <span id="currentLikes">{{ likes }}</span> • Views: {{ updated_views }}</div>

      <div class="video-box" id="playerHolder">
        <!-- We'll try an HTML5 <video> first (direct_url), fallback to iframe if blocked -->
        <video id="htmlPlayer" controls preload="metadata" crossorigin="anonymous" style="display:none"></video>
        <iframe id="iframePlayer" src="{{ embed_url }}" allow="autoplay; encrypted-media" style="display:none"></iframe>
      </div>

      <div class="controls">
        <div>Likes: <span id="likesCount">{{ likes }}</span></div>
        <button class="btn" onclick="like()">👍 Like</button>
        <button class="btn" onclick="toggleSub()" id="subBtn">Subscribe</button>
        <div id="resumeNote" style="color:#cfcfcf;margin-left:8px;font-size:13px"></div>
      </div>
    </div>

    <aside class="aside">
      <h3 style="color:var(--gold);margin-top:0">Watch Next</h3>
      {% for vid in watch_next %}
      <div class="video-card">
        <a href="/view/{{ vid[0] }}" style="display:block"><img src="https://drive.google.com/thumbnail?id={{ vid[4] }}" alt="{{ vid[1] }}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTEwIiBoZWlnaHQ9IjcwIiB2aWV3Qm94PSIwIDAgMTEwIDcwIiBmaWxsPSJub25lIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMTAiIGhlaWdodD0iNzAiIGZpbGw9IiMxZjFmMWYiLz48dGV4dCB4PSI1NSIgeT0iMzUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiNjZmNmY2YiIGZvbnQtc2l6ZT0iMTBweCI+Tm8gVGh1bWJuYWlsPC90ZXh0Pjwvc3ZnPg=='"></a>
        <div class="video-info">
          <a class="title" href="/view/{{ vid[0] }}">{{ vid[1] }}</a>
          <div class="small">by <a href="/channel/{{ (vid[2] or 'Anonymous')|urlencode }}">{{ vid[2] or 'Anonymous' }}</a> • Likes: {{ vid[3] }} • Views: {{ vid[5] }}</div>
        </div>
      </div>
      {% endfor %}
    </aside>
  </div>

<script>
  const vidId = {{ vid_id }};
  const directUrl = "{{ direct_url }}";
  const embedUrl = "{{ embed_url }}";
  const storageKey = 'mg_resume_' + vidId;
  const subsKey = 'mg_subs';
  const uploader = "{{ uploader_str }}";

  const htmlPlayer = document.getElementById('htmlPlayer');
  const iframePlayer = document.getElementById('iframePlayer');
  const resumeNote = document.getElementById('resumeNote');

  // Check subscription status on load
  let subs = [];
  try {
    subs = JSON.parse(localStorage.getItem(subsKey) || '[]');
  } catch(e) {
    console.warn('Failed to load subscriptions:', e);
  }
  
  const subBtn = document.getElementById('subBtn');
  if (subs.includes(uploader)) {
    subBtn.textContent = 'Unsubscribe';
    subBtn.style.background = '#ff4444';
  }

  // Try to use HTML5 <video> with direct download link (may fail if host blocks)
  function tryUseHtml5() {
    htmlPlayer.src = directUrl;
    // attempt to load metadata and play — if loaderror occurs, fallback
    htmlPlayer.addEventListener('loadedmetadata', onMeta);
    htmlPlayer.addEventListener('error', onError);
    // try to show player (browser may block autoplay)
    htmlPlayer.style.display = 'block';
    iframePlayer.style.display = 'none';
    // restore position if present
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try { 
        const time = parseFloat(saved) || 0;
        htmlPlayer.currentTime = time; 
        resumeNote.innerText = 'Resuming from ' + formatTime(time); 
      } catch(e){
        console.warn('Failed to resume:', e);
      }
    }
  }

  function onMeta(){
    resumeNote.style.opacity = '1';
    // periodically save position
    setInterval(function() {
      try {
        if (htmlPlayer.currentTime > 0) {
          localStorage.setItem(storageKey, Math.floor(htmlPlayer.currentTime));
        }
      } catch(e){
        console.warn('Failed to save position:', e);
      }
    }, 2500);
  }

  function onError(){
    // hide html player, show iframe as fallback
    htmlPlayer.style.display = 'none';
    iframePlayer.style.display = 'block';
    // small resume note cannot be supported in iframe preview reliably
    resumeNote.innerText = 'Playback in iframe (resume not supported for Drive preview).';
  }

  // Try to fetch the direct URL HEAD to check if allowed (best-effort)
  fetch(directUrl, { method: 'HEAD', mode: 'cors' }).then(function(resp) {
    // if we get 200-ish, try html5 player
    if (resp.ok) {
      tryUseHtml5();
    } else { 
      htmlPlayer.style.display='none'; 
      iframePlayer.style.display='block'; 
      resumeNote.innerText = 'Fallback to iframe (direct stream not available).'; 
    }
  }).catch(function(err) {
    // likely blocked by CORS or host; fallback to iframe
    htmlPlayer.style.display='none';
    iframePlayer.style.display='block';
    resumeNote.innerText = 'Fallback to iframe (direct stream not available).';
  });

  function formatTime(t){
    t = Number(t);
    if (isNaN(t) || t < 0) return '0:00';
    const s = Math.floor(t % 60).toString().padStart(2,'0');
    const m = Math.floor((t/60)%60);
    const h = Math.floor(t/3600);
    return h ? h + ':' + m.toString().padStart(2,'0') + ':' + s : m + ':' + s;
  }

  function like(){
    fetch('/like/' + vidId, {method:'POST'}).then(function() {
      const el = document.getElementById('likesCount');
      const currentEl = document.getElementById('currentLikes');
      const newCount = parseInt(el.innerText || '0') + 1;
      el.innerText = newCount;
      currentEl.innerText = newCount;
    }).catch(function(err) {
      console.error('Failed to like:', err);
      alert('Failed to like video. Please try again.');
    });
  }

  function toggleSub(){
    try {
      let subs = JSON.parse(localStorage.getItem(subsKey) || '[]');
      if(!subs.includes(uploader)){
        subs.push(uploader);
        localStorage.setItem(subsKey, JSON.stringify(subs));
        subBtn.textContent = 'Unsubscribe';
        subBtn.style.background = '#ff4444';
        alert('Subscribed to ' + uploader);
      } else {
        // unsubscribe
        subs = subs.filter(function(x) {
          return x !== uploader;
        });
        localStorage.setItem(subsKey, JSON.stringify(subs));
        subBtn.