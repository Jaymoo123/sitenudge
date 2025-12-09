import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# Page config
st.set_page_config(
    page_title="SiteNudge Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Premium CSS - Compact
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main .block-container {
        padding: 1.5rem 2rem;
        max-width: 1400px;
    }
    
    h1 { font-weight: 700; font-size: 1.75rem; color: #f8fafc; margin-bottom: 0.25rem; }
    h2 { font-weight: 600; font-size: 1.25rem; color: #e2e8f0; }
    h3 { font-weight: 600; font-size: 1rem; color: #e2e8f0; }
    
    /* Compact metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    
    div[data-testid="stMetric"] label {
        font-size: 0.65rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        color: #64748b;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-size: 0.7rem;
    }
    
    /* Section headers */
    .section-header {
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        color: #475569;
        margin-bottom: 0.75rem;
        margin-top: 0.5rem;
    }
    
    /* Tighter spacing */
    div[data-testid="column"] { padding: 0 0.25rem; }
    
    /* Dividers */
    hr {
        border: none;
        height: 1px;
        background: rgba(148, 163, 184, 0.15);
        margin: 1.25rem 0;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid rgba(148, 163, 184, 0.1);
    }
    
    /* Tables */
    .stDataFrame { font-size: 0.8rem; }
    
    /* Hide branding */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Smaller markdown */
    .stMarkdown p { font-size: 0.85rem; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# Plotly theme
plotly_layout = dict(
    template="plotly_dark",
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="Inter, sans-serif", color="#94a3b8"),
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(gridcolor='rgba(148,163,184,0.1)', zerolinecolor='rgba(148,163,184,0.1)'),
    yaxis=dict(gridcolor='rgba(148,163,184,0.1)', zerolinecolor='rgba(148,163,184,0.1)'),
)

colors = {
    'primary': '#3b82f6',
    'secondary': '#8b5cf6', 
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'info': '#06b6d4',
    'gradient': ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981'],
}

# Supabase connection
@st.cache_resource
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_data(ttl=15)
def fetch_all_sessions():
    response = get_supabase().table('session_sessions').select('*').order('started_at', desc=True).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        df['started_at'] = pd.to_datetime(df['started_at'], utc=True)
        return df
    return pd.DataFrame()

def calculate_metrics(df):
    if df.empty:
        return {'sessions': 0, 'median_time': 0, 'median_scroll': 0, 'total_clicks': 0,
                'clicked_buy': 0, 'initiated_checkout': 0, 'purchased': 0, 'bounce_rate': 0, 'engaged_sessions': 0}
    
    time_col = df.get('time_on_site_sec', pd.Series([0]))
    valid_time = time_col[(time_col > 0) & (time_col <= 1800)]
    scroll_col = df.get('scroll_depth_pct', pd.Series([0]))
    valid_scroll = scroll_col[scroll_col > 0]
    bounces = len(df[(time_col == 0) | (scroll_col == 0)])
    engaged = len(df[(time_col > 10) & (scroll_col > 25)])
    
    return {
        'sessions': len(df),
        'median_time': valid_time.median() if len(valid_time) > 0 else 0,
        'median_scroll': valid_scroll.median() if len(valid_scroll) > 0 else 0,
        'total_clicks': df.get('clicks_total', pd.Series([0])).sum(),
        'clicked_buy': df.get('clicked_buy', pd.Series([0])).sum(),
        'initiated_checkout': df.get('initiated_checkout', pd.Series([0])).sum(),
        'purchased': df.get('purchased', pd.Series([0])).sum(),
        'bounce_rate': (bounces / len(df) * 100) if len(df) > 0 else 0,
        'engaged_sessions': engaged,
    }

def calculate_ab_stats(df, variant_col):
    if variant_col not in df.columns or df.empty:
        return None
    results = []
    for variant in df[variant_col].dropna().unique():
        vdf = df[df[variant_col] == variant]
        m = calculate_metrics(vdf)
        click_rate = (m['clicked_buy'] / m['sessions'] * 100) if m['sessions'] > 0 else 0
        results.append({
            'variant': variant, 'sessions': m['sessions'], 'median_time': m['median_time'],
            'median_scroll': m['median_scroll'], 'clicked_buy': m['clicked_buy'],
            'click_rate': click_rate, 'bounce_rate': m['bounce_rate'], 'engaged': m['engaged_sessions']
        })
    return pd.DataFrame(results)

def calc_delta(current, prev):
    if prev == 0: return None
    return ((current - prev) / prev) * 100

# Load data
df_all = fetch_all_sessions()
if df_all.empty:
    st.error("No data available")
    st.stop()

# Time calculations
now = datetime.now(pytz.UTC)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.markdown("---")
    
    period = st.selectbox("📅 Time Period", 
        ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "All Time"], index=0)
    
    compare = st.checkbox("📊 Compare periods", value=True)
    
    st.markdown("---")
    st.markdown("**Filters**")
    show_tiktok_only = st.checkbox("TikTok only", value=True)
    exclude_bots = st.checkbox("Exclude bots", value=True)
    
    st.markdown("---")
    auto_refresh = st.checkbox("Auto-refresh", value=False)
    if auto_refresh:
        st.caption("Refreshing every 15s")

# Period calculations
periods = {
    "Today": (today_start, now, today_start - timedelta(days=1), today_start),
    "Yesterday": (today_start - timedelta(days=1), today_start, today_start - timedelta(days=2), today_start - timedelta(days=1)),
    "Last 7 Days": (now - timedelta(days=7), now, now - timedelta(days=14), now - timedelta(days=7)),
    "Last 30 Days": (now - timedelta(days=30), now, now - timedelta(days=60), now - timedelta(days=30)),
    "All Time": (df_all['started_at'].min(), now, df_all['started_at'].min(), df_all['started_at'].min()),
}
current_start, current_end, prev_start, prev_end = periods[period]

# Filter data
df_period = df_all[(df_all['started_at'] >= current_start) & (df_all['started_at'] <= current_end)]
df_filtered = df_period.copy()
if exclude_bots: df_filtered = df_filtered[df_filtered['is_bot'] != True]
if show_tiktok_only: df_filtered = df_filtered[df_filtered['utm_source'] == 'tiktok']

df_prev = df_all[(df_all['started_at'] >= prev_start) & (df_all['started_at'] < prev_end)]
if exclude_bots: df_prev = df_prev[df_prev['is_bot'] != True]
if show_tiktok_only: df_prev = df_prev[df_prev['utm_source'] == 'tiktok']

metrics = calculate_metrics(df_filtered)
prev_metrics = calculate_metrics(df_prev)

# ============== HEADER ==============
col1, col2 = st.columns([3, 1])
with col1:
    st.title("Analytics Dashboard")
    filter_tags = []
    if show_tiktok_only: filter_tags.append("TikTok")
    if exclude_bots: filter_tags.append("No Bots")
    st.caption(f"{period} • {' • '.join(filter_tags) if filter_tags else 'All Traffic'} • Updated {now.strftime('%H:%M')}")

# ============== TRAFFIC OVERVIEW ==============
st.markdown('<p class="section-header">Traffic Overview</p>', unsafe_allow_html=True)

total_all = len(df_period)
total_bots = len(df_period[df_period['is_bot'] == True])
total_real = total_all - total_bots
total_tiktok = len(df_period[(df_period['utm_source'] == 'tiktok') & (df_period['is_bot'] != True)])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", f"{total_all:,}", help="All sessions including bots")
c2.metric("Real", f"{total_real:,}", f"{total_bots} bots" if total_bots > 0 else None, delta_color="off")
c3.metric("TikTok", f"{total_tiktok:,}", f"{(total_tiktok/total_real*100):.2f}% of real" if total_real > 0 else None, delta_color="off")
c4.metric("Other", f"{total_real - total_tiktok:,}")
c5.metric("Bot Rate", f"{(total_bots/total_all*100):.2f}%" if total_all > 0 else "0.00%")

# ============== ENGAGEMENT ==============
st.markdown("---")
st.markdown('<p class="section-header">Engagement Metrics</p>', unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6 = st.columns(6)

delta = calc_delta(metrics['sessions'], prev_metrics['sessions']) if compare and period != "All Time" else None
c1.metric("Sessions", f"{metrics['sessions']:,}", f"{delta:+.2f}%" if delta else None)

delta = calc_delta(metrics['median_time'], prev_metrics['median_time']) if compare and period != "All Time" else None
c2.metric("Median Time", f"{metrics['median_time']:.2f}s", f"{delta:+.2f}%" if delta else None)

delta = calc_delta(metrics['median_scroll'], prev_metrics['median_scroll']) if compare and period != "All Time" else None
c3.metric("Median Scroll", f"{metrics['median_scroll']:.2f}%", f"{delta:+.2f}%" if delta else None)

c4.metric("Bounce Rate", f"{metrics['bounce_rate']:.2f}%")

engaged_rate = (metrics['engaged_sessions'] / metrics['sessions'] * 100) if metrics['sessions'] > 0 else 0
c5.metric("Engaged", f"{engaged_rate:.2f}%", help="Sessions with >10s and >25% scroll")

c6.metric("Clicks", f"{int(metrics['total_clicks']):,}")

# ============== CONVERSION FUNNEL ==============
st.markdown("---")
st.markdown('<p class="section-header">Conversion Funnel</p>', unsafe_allow_html=True)

sessions = metrics['sessions']
clicked = int(metrics['clicked_buy'])
checkout = int(metrics['initiated_checkout'])
purchased = int(metrics['purchased'])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sessions", f"{sessions:,}")
c2.metric("Clicked Buy", f"{clicked:,}", f"{(clicked/sessions*100):.2f}%" if sessions > 0 else "0.00%", delta_color="off")
c3.metric("Checkout", f"{checkout:,}", f"{(checkout/sessions*100):.2f}%" if sessions > 0 else "0.00%", delta_color="off")
c4.metric("Purchased", f"{purchased:,}", f"{(purchased/sessions*100):.2f}%" if sessions > 0 else "0.00%", delta_color="off")

# Funnel chart
col1, col2 = st.columns([2, 1])
with col1:
    fig = go.Figure(go.Funnel(
        y=['Sessions', 'Buy Click', 'Checkout', 'Purchase'],
        x=[sessions, clicked, checkout, purchased],
        textinfo="value+percent initial",
        marker=dict(color=[colors['primary'], colors['secondary'], colors['info'], colors['success']]),
        connector=dict(line=dict(color="#334155", width=1))
    ))
    fig.update_layout(**plotly_layout, height=180, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("**Drop-off Rates**")
    if sessions > 0:
        st.markdown(f"Session → Buy: **{(1 - clicked/sessions)*100:.2f}%**")
    if clicked > 0:
        st.markdown(f"Buy → Checkout: **{(1 - checkout/clicked)*100:.2f}%**")
    if checkout > 0:
        st.markdown(f"Checkout → Purchase: **{(1 - purchased/checkout)*100:.2f}%**")

# ============== A/B TESTING ==============
st.markdown("---")
st.markdown('<p class="section-header">A/B Test Results</p>', unsafe_allow_html=True)

tests = [
    ('Hero Section', 'hero_variant'),
    ('Social Proof', 'social_proof_variant'),
    ('Scroll Hook', 'scroll_hook_variant'),
]

cols = st.columns(3)
for i, (name, col) in enumerate(tests):
    with cols[i]:
        st.markdown(f"**{name}**")
        stats = calculate_ab_stats(df_filtered, col)
        
        if stats is None or len(stats) < 2:
            st.caption("Insufficient data")
            continue
        
        control = stats[stats['variant'] == 'control'].iloc[0] if 'control' in stats['variant'].values else None
        test = stats[stats['variant'] == 'test'].iloc[0] if 'test' in stats['variant'].values else None
        
        if control is not None and test is not None:
            lift = ((test['click_rate'] - control['click_rate']) / control['click_rate'] * 100) if control['click_rate'] > 0 else 0
            
            # Metrics comparison
            st.markdown(f"""
            | | Control | Test |
            |---|:---:|:---:|
            | Sessions | {int(control['sessions'])} | {int(test['sessions'])} |
            | Click Rate | {control['click_rate']:.2f}% | {test['click_rate']:.2f}% |
            | Time | {control['median_time']:.2f}s | {test['median_time']:.2f}s |
            | Scroll | {control['median_scroll']:.2f}% | {test['median_scroll']:.2f}% |
            """)
            
            if lift > 5:
                st.success(f"📈 Test winning: +{lift:.2f}%")
            elif lift < -5:
                st.error(f"📉 Control winning: {lift:.2f}%")
            else:
                st.info("⚖️ No clear winner")

# ============== CHARTS ROW ==============
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    st.markdown('<p class="section-header">Sessions Over Time</p>', unsafe_allow_html=True)
    if not df_filtered.empty:
        df_temp = df_filtered.copy()
        df_temp['bucket'] = df_temp['started_at'].dt.floor('H' if period in ['Today', 'Yesterday'] else 'D')
        time_data = df_temp.groupby('bucket').size().reset_index(name='sessions')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=time_data['bucket'], y=time_data['sessions'],
            mode='lines+markers', fill='tozeroy',
            line=dict(color=colors['primary'], width=2),
            marker=dict(size=5),
            fillcolor='rgba(59, 130, 246, 0.1)'
        ))
        fig.update_layout(**plotly_layout, height=220, xaxis_title="", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown('<p class="section-header">Device Breakdown</p>', unsafe_allow_html=True)
    if 'device_type' in df_filtered.columns:
        device_data = df_filtered['device_type'].value_counts()
        fig = go.Figure(go.Pie(
            labels=device_data.index, values=device_data.values,
            hole=0.55, marker=dict(colors=[colors['primary'], colors['secondary'], colors['info']]),
            textinfo='percent+label', textposition='outside',
            textfont=dict(size=11)
        ))
        fig.update_layout(**plotly_layout, height=220, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ============== LOCATIONS & SCROLL ==============
col1, col2 = st.columns(2)

with col1:
    st.markdown('<p class="section-header">Top Locations</p>', unsafe_allow_html=True)
    if 'city' in df_filtered.columns:
        cities = df_filtered[df_filtered['city'].notna() & (df_filtered['city'] != '')]['city'].value_counts().head(6)
        if len(cities) > 0:
            fig = go.Figure(go.Bar(
                x=cities.values, y=cities.index, orientation='h',
                marker=dict(color=colors['primary'])
            ))
            layout = plotly_layout.copy()
            layout['yaxis'] = dict(categoryorder='total ascending', gridcolor='rgba(148,163,184,0.1)')
            fig.update_layout(**layout, height=250)
            st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown('<p class="section-header">Scroll Depth Distribution</p>', unsafe_allow_html=True)
    if 'scroll_depth_pct' in df_filtered.columns:
        scroll_data = df_filtered[df_filtered['scroll_depth_pct'] > 0]['scroll_depth_pct']
        if len(scroll_data) > 0:
            fig = go.Figure(go.Histogram(
                x=scroll_data, nbinsx=10,
                marker=dict(color=colors['secondary'])
            ))
            fig.update_layout(**plotly_layout, height=200, xaxis_title="Scroll %", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

# ============== RECENT SESSIONS ==============
st.markdown("---")
st.markdown('<p class="section-header">Recent Sessions</p>', unsafe_allow_html=True)

if not df_filtered.empty:
    cols = ['started_at', 'device_type', 'city', 'time_on_site_sec', 'scroll_depth_pct', 
            'clicked_buy', 'hero_variant', 'social_proof_variant']
    cols = [c for c in cols if c in df_filtered.columns]
    recent = df_filtered[cols].head(15).copy()
    recent['started_at'] = recent['started_at'].dt.strftime('%H:%M:%S')
    st.dataframe(recent, use_container_width=True, hide_index=True)

# Auto refresh
if auto_refresh:
    import time
    time.sleep(15)
    st.rerun()
