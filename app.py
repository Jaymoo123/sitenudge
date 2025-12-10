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

# V2.0 Launch timestamp (Dec 10, 2025 - Outcome-focused positioning)
V2_LAUNCH = datetime(2025, 12, 10, 12, 0, 0, tzinfo=pytz.UTC)  # Noon UTC on Dec 10

def classify_version(df, v2_launch_time):
    """Add version column: V1.0 (before V2_LAUNCH) or V2.0 (after)"""
    if df.empty or 'started_at' not in df.columns:
        return df
    df = df.copy()
    df['version'] = df['started_at'].apply(lambda x: 'V2.0' if x >= v2_launch_time else 'V1.0')
    return df

# Load data
df_all = fetch_all_sessions()
if df_all.empty:
    st.error("No data available")
    st.stop()

# Add version classification
df_all = classify_version(df_all, V2_LAUNCH)

# Time calculations
now = datetime.now(pytz.UTC)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

# ============== HEADER & FILTERS ==============
st.title("Analytics Dashboard")
st.caption(f"Last updated: {now.strftime('%H:%M:%S')}")
st.markdown("---")

# Primary filters at top
col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

with col1:
    period = st.radio(
        "📅 Time Period",
        ["Today", "Last 7 Days", "Last 30 Days", "All Time"],
        index=3,  # Default to "All Time"
        horizontal=True
    )

with col2:
    # Get unique prices from data
    price_options = ["All Prices"]
    if 'price_shown' in df_all.columns:
        unique_prices = df_all['price_shown'].dropna().unique()
        unique_prices = sorted([p for p in unique_prices if p > 0])
        price_options += [f"${int(p)}" for p in unique_prices]
    
    selected_price = st.selectbox("💰 Price", price_options, index=0)

with col3:
    show_tiktok_only = st.checkbox("TikTok only", value=False)

with col4:
    exclude_bots = st.checkbox("Exclude bots", value=True)

with col5:
    compare = st.checkbox("Compare", value=True)

# Version filter (V1.0 vs V2.0)
st.markdown("---")
col1, col2, col3 = st.columns([1, 2, 2])
with col1:
    version_filter = st.selectbox(
        "🚀 Version",
        ["Both Versions", "V2.0 (Outcome-Focused)", "V1.0 (Feature-Focused)"],
        index=0
    )
with col2:
    if version_filter == "V2.0 (Outcome-Focused)":
        v2_count = len(df_all[df_all['version'] == 'V2.0'])
        st.caption(f"✨ New positioning: '$3k/Month Skill' • {v2_count} sessions • Launched Dec 10")
    elif version_filter == "V1.0 (Feature-Focused)":
        v1_count = len(df_all[df_all['version'] == 'V1.0'])
        st.caption(f"📦 Old positioning: 'Automation Scripts' • {v1_count} sessions • Before Dec 10")
    else:
        v1_count = len(df_all[df_all['version'] == 'V1.0'])
        v2_count = len(df_all[df_all['version'] == 'V2.0'])
        st.caption(f"📊 Compare both: V1.0 ({v1_count}) vs V2.0 ({v2_count}) • Side-by-side analysis")
with col3:
    show_version_comparison = st.checkbox("Show version comparison charts", value=(version_filter == "Both Versions"))

# Test round filter
st.markdown("---")
col1, col2 = st.columns([1, 3])
with col1:
    # Get available test rounds
    test_rounds = {
        "All Rounds": None,
        "Round 2 (Current)": ("headline-001", "social-copy-001", "cta-copy-001"),
        "Round 1 (Completed)": ("hero-price-001", "social-proof-001", "scroll-hook-001"),
    }
    selected_round = st.selectbox("🧪 Test Round", list(test_rounds.keys()), index=0)
with col2:
    if selected_round == "Round 2 (Current)":
        st.caption("📝 Headline: Product vs Pain | ⭐ Social: Total vs Velocity | 🔘 CTA: Action vs Price-in-button")
    elif selected_round == "Round 1 (Completed)":
        st.caption("🦸 Hero: Price visible vs Hook-first | 👥 Social: Hidden vs Visible | 🎣 Scroll: Generic vs Curiosity")

# Sidebar for advanced settings
with st.sidebar:
    st.markdown("### ⚙️ Advanced Settings")
    st.markdown("---")
    
    auto_refresh = st.checkbox("Auto-refresh (15s)", value=False)
    
    st.markdown("---")
    st.markdown("**Stats**")
    st.caption(f"Total DB rows: {len(df_all):,}")
    st.caption(f"Earliest: {df_all['started_at'].min().strftime('%Y-%m-%d')}")
    st.caption(f"Latest: {df_all['started_at'].max().strftime('%Y-%m-%d')}")

# Period calculations
periods = {
    "Today": (today_start, now, today_start - timedelta(days=1), today_start),
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

# Apply price filter
if selected_price != "All Prices" and 'price_shown' in df_filtered.columns:
    price_value = float(selected_price.replace('$', ''))
    df_filtered = df_filtered[df_filtered['price_shown'] == price_value]

# Apply version filter
if version_filter == "V2.0 (Outcome-Focused)":
    df_filtered = df_filtered[df_filtered['version'] == 'V2.0']
elif version_filter == "V1.0 (Feature-Focused)":
    df_filtered = df_filtered[df_filtered['version'] == 'V1.0']
# If "Both Versions", don't filter - keep all data

# Apply test round filter
selected_test_ids = test_rounds[selected_round]
if selected_test_ids and 'hero_test_id' in df_filtered.columns:
    hero_id, social_id, scroll_id = selected_test_ids
    df_filtered = df_filtered[df_filtered['hero_test_id'] == hero_id]

df_prev = df_all[(df_all['started_at'] >= prev_start) & (df_all['started_at'] < prev_end)]
if exclude_bots: df_prev = df_prev[df_prev['is_bot'] != True]
if show_tiktok_only: df_prev = df_prev[df_prev['utm_source'] == 'tiktok']

# Apply price filter to comparison period too
if selected_price != "All Prices" and 'price_shown' in df_prev.columns:
    price_value = float(selected_price.replace('$', ''))
    df_prev = df_prev[df_prev['price_shown'] == price_value]

# Apply test round filter to comparison period
if selected_test_ids and 'hero_test_id' in df_prev.columns:
    hero_id, social_id, scroll_id = selected_test_ids
    df_prev = df_prev[df_prev['hero_test_id'] == hero_id]

metrics = calculate_metrics(df_filtered)
prev_metrics = calculate_metrics(df_prev)

# ============== TRAFFIC OVERVIEW ==============
st.markdown("---")
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

# ============== VERSION COMPARISON ==============
if show_version_comparison and version_filter == "Both Versions":
    st.markdown("---")
    st.markdown('<p class="section-header">🚀 V1.0 vs V2.0 Comparison</p>', unsafe_allow_html=True)
    
    # Calculate metrics for each version
    df_v1 = df_filtered[df_filtered['version'] == 'V1.0'] if 'version' in df_filtered.columns else pd.DataFrame()
    df_v2 = df_filtered[df_filtered['version'] == 'V2.0'] if 'version' in df_filtered.columns else pd.DataFrame()
    
    if not df_v1.empty and not df_v2.empty:
        metrics_v1 = calculate_metrics(df_v1)
        metrics_v2 = calculate_metrics(df_v2)
        
        # Key comparison metrics
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        # Sessions
        sessions_lift = ((metrics_v2['sessions'] - metrics_v1['sessions']) / metrics_v1['sessions'] * 100) if metrics_v1['sessions'] > 0 else 0
        col1.metric("Sessions", f"V1: {metrics_v1['sessions']:,}\nV2: {metrics_v2['sessions']:,}", f"{sessions_lift:+.1f}%")
        
        # CTR
        ctr_v1 = (metrics_v1['clicked_buy'] / metrics_v1['sessions'] * 100) if metrics_v1['sessions'] > 0 else 0
        ctr_v2 = (metrics_v2['clicked_buy'] / metrics_v2['sessions'] * 100) if metrics_v2['sessions'] > 0 else 0
        ctr_lift = ctr_v2 - ctr_v1
        col2.metric("CTR", f"V1: {ctr_v1:.2f}%\nV2: {ctr_v2:.2f}%", f"{ctr_lift:+.2f}pp")
        
        # Checkout Rate
        checkout_v1 = (metrics_v1['initiated_checkout'] / metrics_v1['sessions'] * 100) if metrics_v1['sessions'] > 0 else 0
        checkout_v2 = (metrics_v2['initiated_checkout'] / metrics_v2['sessions'] * 100) if metrics_v2['sessions'] > 0 else 0
        checkout_lift = checkout_v2 - checkout_v1
        col3.metric("Checkout Rate", f"V1: {checkout_v1:.2f}%\nV2: {checkout_v2:.2f}%", f"{checkout_lift:+.2f}pp")
        
        # Time on Site
        time_lift = metrics_v2['median_time'] - metrics_v1['median_time']
        col4.metric("Median Time", f"V1: {metrics_v1['median_time']:.2f}s\nV2: {metrics_v2['median_time']:.2f}s", f"{time_lift:+.2f}s")
        
        # Scroll Depth
        scroll_lift = metrics_v2['median_scroll'] - metrics_v1['median_scroll']
        col5.metric("Median Scroll", f"V1: {metrics_v1['median_scroll']:.2f}%\nV2: {metrics_v2['median_scroll']:.2f}%", f"{scroll_lift:+.2f}%")
        
        # Purchases
        purchases_v1 = metrics_v1['purchased']
        purchases_v2 = metrics_v2['purchased']
        col6.metric("Purchases", f"V1: {purchases_v1}\nV2: {purchases_v2}", f"+{purchases_v2 - purchases_v1}" if purchases_v2 > purchases_v1 else f"{purchases_v2 - purchases_v1}")
        
        # Comparison charts
        st.markdown("**📊 Side-by-Side Comparison**")
        col1, col2 = st.columns(2)
        
        with col1:
            # CTR Comparison
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='V1.0',
                x=['CTR %'],
                y=[ctr_v1],
                marker_color='#3b82f6',
                text=[f"{ctr_v1:.2f}%"],
                textposition='outside'
            ))
            fig.add_trace(go.Bar(
                name='V2.0',
                x=['CTR %'],
                y=[ctr_v2],
                marker_color='#10b981',
                text=[f"{ctr_v2:.2f}%"],
                textposition='outside'
            ))
            fig.update_layout(**plotly_layout, height=200, title=dict(text="Click-Through Rate Comparison", font=dict(size=12)))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Checkout Rate Comparison
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='V1.0',
                x=['Checkout %'],
                y=[checkout_v1],
                marker_color='#3b82f6',
                text=[f"{checkout_v1:.2f}%"],
                textposition='outside'
            ))
            fig.add_trace(go.Bar(
                name='V2.0',
                x=['Checkout %'],
                y=[checkout_v2],
                marker_color='#10b981',
                text=[f"{checkout_v2:.2f}%"],
                textposition='outside'
            ))
            fig.update_layout(**plotly_layout, height=200, title=dict(text="Checkout Rate Comparison", font=dict(size=12)))
            st.plotly_chart(fig, use_container_width=True)
        
        # Winner callout
        if ctr_v2 > ctr_v1:
            st.success(f"📈 **V2.0 (Outcome-Focused) is winning!** CTR is {ctr_lift:+.2f} percentage points higher ({(ctr_lift/ctr_v1*100):+.1f}% relative improvement)")
        elif ctr_v1 > ctr_v2:
            st.warning(f"📉 V1.0 is performing better. CTR is {abs(ctr_lift):.2f} percentage points higher than V2.0")
        else:
            st.info("⚖️ Both versions performing similarly so far")
    else:
        st.caption("⏳ Not enough data yet for version comparison. Keep monitoring!")

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
fig = go.Figure(go.Funnel(
    y=['Sessions', 'Buy Click', 'Checkout', 'Purchase'],
    x=[sessions, clicked, checkout, purchased],
    textinfo="value+percent initial",
    marker=dict(color=[colors['primary'], colors['secondary'], colors['info'], colors['success']]),
    connector=dict(line=dict(color="#334155", width=1))
))
fig.update_layout(**plotly_layout, height=200, showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ============== TREND ANALYSIS ==============
st.markdown("---")
st.markdown('<p class="section-header">📈 Trend Analysis - Key Metrics Over Time</p>', unsafe_allow_html=True)

if not df_filtered.empty:
    # Prepare data with time buckets
    df_trends = df_filtered.copy()
    time_bucket = 'H' if period == 'Today' else 'D'
    df_trends['bucket'] = df_trends['started_at'].dt.floor(time_bucket)
    
    # Calculate metrics per time bucket
    trend_data = df_trends.groupby('bucket').agg({
        'session_id': 'count',  # Total sessions
        'time_on_site_sec': [
            lambda x: x[(x > 0) & (x <= 1800)].median() if len(x[(x > 0) & (x <= 1800)]) > 0 else 0,
            lambda x: len(x[x > 5]),  # Count of users with >5 sec
            lambda x: len(x[x > 10]),  # Count of users with >10 sec
        ],
        'scroll_depth_pct': [
            lambda x: x[x > 0].median() if len(x[x > 0]) > 0 else 0,
            lambda x: len(x[x > 25]),  # Count of users with >25% scroll
            lambda x: len(x[x > 50]),  # Count of users with >50% scroll
        ],
        'clicks_total': 'sum',
        'clicked_buy': 'sum',
        'initiated_checkout': 'sum',
    }).reset_index()
    
    # Flatten column names
    trend_data.columns = ['date', 'sessions', 'median_time', 'users_5sec', 'users_10sec', 
                          'median_scroll', 'users_25scroll', 'users_50scroll', 
                          'clicks', 'buy_clicks', 'checkouts']
    
    # Calculate rates
    trend_data['ctr'] = (trend_data['buy_clicks'] / trend_data['sessions'] * 100).fillna(0)
    trend_data['checkout_rate'] = (trend_data['checkouts'] / trend_data['buy_clicks'] * 100).fillna(0)
    trend_data['engaged_rate'] = (trend_data['users_10sec'] / trend_data['sessions'] * 100).fillna(0)
    
    # Create 4 rows of 2 columns for 8 charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Sessions Over Time**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['sessions'],
            mode='lines+markers',
            line=dict(color='#3b82f6', width=3),
            marker=dict(size=8, color='#60a5fa'),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.15)',
            hovertemplate='%{y} sessions<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Median Time on Site (seconds)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['median_time'],
            mode='lines+markers',
            line=dict(color='#10b981', width=3),
            marker=dict(size=8, color='#34d399'),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.15)',
            hovertemplate='%{y:.2f}s<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Median Scroll Depth (%)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['median_scroll'],
            mode='lines+markers',
            line=dict(color='#8b5cf6', width=3),
            marker=dict(size=8, color='#a78bfa'),
            fill='tozeroy',
            fillcolor='rgba(139, 92, 246, 0.15)',
            hovertemplate='%{y:.2f}%<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Total Clicks Over Time**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['clicks'],
            mode='lines+markers',
            line=dict(color='#f59e0b', width=3),
            marker=dict(size=8, color='#fbbf24'),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.15)',
            hovertemplate='%{y} clicks<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Buy Button Clicks Over Time**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['buy_clicks'],
            mode='lines+markers',
            line=dict(color='#06b6d4', width=3),
            marker=dict(size=8, color='#22d3ee'),
            fill='tozeroy',
            fillcolor='rgba(6, 182, 212, 0.15)',
            hovertemplate='%{y} buy clicks<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Checkouts Over Time**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['checkouts'],
            mode='lines+markers',
            line=dict(color='#ef4444', width=3),
            marker=dict(size=8, color='#f87171'),
            fill='tozeroy',
            fillcolor='rgba(239, 68, 68, 0.15)',
            hovertemplate='%{y} checkouts<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Click-Through Rate (CTR) %**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['ctr'],
            mode='lines+markers',
            line=dict(color='#ec4899', width=3),
            marker=dict(size=8, color='#f472b6'),
            fill='tozeroy',
            fillcolor='rgba(236, 72, 153, 0.15)',
            hovertemplate='%{y:.2f}%<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Checkout Rate (% of buy clicks)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['checkout_rate'],
            mode='lines+markers',
            line=dict(color='#14b8a6', width=3),
            marker=dict(size=8, color='#2dd4bf'),
            fill='tozeroy',
            fillcolor='rgba(20, 184, 166, 0.15)',
            hovertemplate='%{y:.2f}%<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    # Additional engagement metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Users Who Spend Time (>10 sec)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['users_10sec'],
            mode='lines+markers',
            line=dict(color='#22c55e', width=3),
            marker=dict(size=8, color='#4ade80'),
            fill='tozeroy',
            fillcolor='rgba(34, 197, 94, 0.15)',
            name='Users >10s',
            hovertemplate='%{y} users<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['users_5sec'],
            mode='lines',
            line=dict(color='#86efac', width=2, dash='dash'),
            name='Users >5s',
            hovertemplate='%{y} users<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=True, 
                         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Users Who Scroll (>25% depth)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['users_25scroll'],
            mode='lines+markers',
            line=dict(color='#a855f7', width=3),
            marker=dict(size=8, color='#c084fc'),
            fill='tozeroy',
            fillcolor='rgba(168, 85, 247, 0.15)',
            name='Users >25%',
            hovertemplate='%{y} users<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['users_50scroll'],
            mode='lines',
            line=dict(color='#d8b4fe', width=2, dash='dash'),
            name='Users >50%',
            hovertemplate='%{y} users<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=True,
                         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Engagement Rate (% >10 sec)**")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['engaged_rate'],
            mode='lines+markers',
            line=dict(color='#0ea5e9', width=3),
            marker=dict(size=8, color='#38bdf8'),
            fill='tozeroy',
            fillcolor='rgba(14, 165, 233, 0.15)',
            hovertemplate='%{y:.2f}%<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Quality Score Trend**")
        st.caption("Combined metric: (Engaged Rate × CTR) / 100")
        # Quality score = engagement × conversion
        trend_data['quality_score'] = (trend_data['engaged_rate'] * trend_data['ctr']) / 100
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_data['date'], y=trend_data['quality_score'],
            mode='lines+markers',
            line=dict(color='#f97316', width=3),
            marker=dict(size=8, color='#fb923c'),
            fill='tozeroy',
            fillcolor='rgba(249, 115, 22, 0.15)',
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
        fig.update_layout(**plotly_layout, height=200, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    
    st.caption("💡 Track these trends over time to see if your optimizations and A/B test winners are improving performance")
else:
    st.caption("No data available for trend analysis")

# ============== PRICE TEST RESULTS ==============
st.markdown("---")
st.markdown('<p class="section-header">Price Test Results</p>', unsafe_allow_html=True)

if 'price_shown' in df_filtered.columns:
    # Get price breakdown
    price_stats = df_filtered.groupby('price_shown').agg({
        'session_id': 'count',
        'clicked_buy': 'sum',
        'initiated_checkout': 'sum',
        'purchased': 'sum',
        'time_on_site_sec': 'median',
        'scroll_depth_pct': 'median'
    }).reset_index()
    price_stats.columns = ['Price', 'Sessions', 'Clicked Buy', 'Checkouts', 'Purchases', 'Median Time', 'Median Scroll']
    
    if len(price_stats) > 0:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Price comparison chart
            fig = go.Figure()
            
            for i, row in price_stats.iterrows():
                price = f"${row['Price']:.0f}" if pd.notna(row['Price']) else "Unknown"
                sessions = row['Sessions']
                ctr = (row['Clicked Buy'] / sessions * 100) if sessions > 0 else 0
                
                fig.add_trace(go.Bar(
                    name=price,
                    x=['Sessions', 'CTR %', 'Checkout %'],
                    y=[sessions, ctr, (row['Checkouts'] / sessions * 100) if sessions > 0 else 0],
                    text=[f"{sessions}", f"{ctr:.2f}%", f"{(row['Checkouts'] / sessions * 100):.2f}%" if sessions > 0 else "0%"],
                    textposition='outside',
                    marker_color='#10b981' if row['Price'] == 17 else '#3b82f6'
                ))
            
            fig.update_layout(**plotly_layout, height=220, barmode='group', title=dict(text="Performance by Price Point", font=dict(size=12)))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("**Price Breakdown**")
            for _, row in price_stats.iterrows():
                price = f"${row['Price']:.0f}" if pd.notna(row['Price']) else "Unknown"
                sessions = row['Sessions']
                ctr = (row['Clicked Buy'] / sessions * 100) if sessions > 0 else 0
                purchases = int(row['Purchases'])
                
                st.markdown(f"""
                **{price}**: {sessions} sessions
                - CTR: {ctr:.2f}%
                - Purchases: {purchases}
                """)
    else:
        st.caption("No price data available yet")
else:
    st.caption("Price tracking not yet active - new sessions will include price data")

# ============== A/B TESTING ==============
st.markdown("---")
st.markdown('<p class="section-header">A/B Test Results</p>', unsafe_allow_html=True)

# Test definitions per round
if selected_round == "Round 2 (Current)":
    tests = [
        ('📝 Headline Copy', 'hero_variant', '#3b82f6', '#f59e0b', 'Product Name', 'Pain-Focused'),
        ('⭐ Social Proof Copy', 'social_proof_variant', '#8b5cf6', '#10b981', '"200+ sold"', '"327 this week"'),
        ('🔘 CTA Button Copy', 'scroll_hook_variant', '#06b6d4', '#ef4444', '"Get Instant Access"', '"Download Now - $17"'),
    ]
elif selected_round == "Round 1 (Completed)":
    tests = [
        ('🦸 Hero Layout', 'hero_variant', '#3b82f6', '#f59e0b', 'Price Visible', 'Hook-First'),
        ('👥 Social Proof', 'social_proof_variant', '#8b5cf6', '#10b981', 'Hidden', 'Stars Visible'),
        ('🎣 Scroll Hook', 'scroll_hook_variant', '#06b6d4', '#ef4444', 'Generic', 'Curiosity'),
    ]
else:  # All Rounds
    tests = [
        ('🧪 Hero Test', 'hero_variant', '#3b82f6', '#f59e0b', 'Control', 'Test'),
        ('🧪 Social Proof Test', 'social_proof_variant', '#8b5cf6', '#10b981', 'Control', 'Test'),
        ('🧪 Scroll Hook Test', 'scroll_hook_variant', '#06b6d4', '#ef4444', 'Control', 'Test'),
    ]

for name, variant_col, color1, color2, control_label, test_label in tests:
    stats = calculate_ab_stats(df_filtered, variant_col)
    
    if stats is None or len(stats) < 2:
        continue
    
    control = stats[stats['variant'] == 'control'].iloc[0] if 'control' in stats['variant'].values else None
    test = stats[stats['variant'] == 'test'].iloc[0] if 'test' in stats['variant'].values else None
    
    if control is None or test is None:
        continue
    
    lift = ((test['click_rate'] - control['click_rate']) / control['click_rate'] * 100) if control['click_rate'] > 0 else 0
    
    st.markdown(f"### {name}")
    st.caption(f"**A:** {control_label} vs **B:** {test_label}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Key metrics with descriptive labels
    with col1:
        st.metric(f"A: {control_label[:15]}", f"{int(control['sessions'])} sess")
    with col2:
        st.metric(f"B: {test_label[:15]}", f"{int(test['sessions'])} sess")
    with col3:
        st.metric("A CTR", f"{control['click_rate']:.2f}%")
    with col4:
        st.metric("B CTR", f"{test['click_rate']:.2f}%")
    
    # Charts
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Click Rate comparison
        fig = go.Figure(go.Bar(
            x=[control_label[:12], test_label[:12]],
            y=[control['click_rate'], test['click_rate']],
            marker=dict(color=[color1, color2]),
            text=[f"{control['click_rate']:.2f}%", f"{test['click_rate']:.2f}%"],
            textposition='outside'
        ))
        fig.update_layout(**plotly_layout, height=180, title=dict(text="Click Rate %", font=dict(size=12)))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Time comparison
        fig = go.Figure(go.Bar(
            x=[control_label[:12], test_label[:12]],
            y=[control['median_time'], test['median_time']],
            marker=dict(color=[color1, color2]),
            text=[f"{control['median_time']:.2f}s", f"{test['median_time']:.2f}s"],
            textposition='outside'
        ))
        fig.update_layout(**plotly_layout, height=180, title=dict(text="Median Time (s)", font=dict(size=12)))
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        # Scroll comparison
        fig = go.Figure(go.Bar(
            x=[control_label[:12], test_label[:12]],
            y=[control['median_scroll'], test['median_scroll']],
            marker=dict(color=[color1, color2]),
            text=[f"{control['median_scroll']:.2f}%", f"{test['median_scroll']:.2f}%"],
            textposition='outside'
        ))
        fig.update_layout(**plotly_layout, height=180, title=dict(text="Median Scroll %", font=dict(size=12)))
        st.plotly_chart(fig, use_container_width=True)
    
    # Winner callout
    if lift > 5:
        st.success(f"📈 **{test_label}** winning with +{lift:.2f}% lift in click rate")
    elif lift < -5:
        st.error(f"📉 **{control_label}** winning - {test_label} has {lift:.2f}% lower click rate")
    else:
        st.info("⚖️ **No clear winner yet** - Results within margin")
    
    st.markdown("---")

# ============== CHARTS ROW 1 ==============
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<p class="section-header">Sessions Over Time</p>', unsafe_allow_html=True)
    if not df_filtered.empty:
        df_temp = df_filtered.copy()
        df_temp['bucket'] = df_temp['started_at'].dt.floor('H' if period == 'Today' else 'D')
        
        fig = go.Figure()
        
        # If comparing versions, show both
        if show_version_comparison and version_filter == "Both Versions" and 'version' in df_temp.columns:
            # V1.0 line
            v1_data = df_temp[df_temp['version'] == 'V1.0'].groupby('bucket').size().reset_index(name='sessions')
            if not v1_data.empty:
                fig.add_trace(go.Scatter(
                    x=v1_data['bucket'], y=v1_data['sessions'],
                    mode='lines+markers', fill='tozeroy',
                    name='V1.0 (Feature)',
                    line=dict(color='#3b82f6', width=3),
                    marker=dict(size=8, color='#60a5fa'),
                    fillcolor='rgba(59, 130, 246, 0.15)'
                ))
            
            # V2.0 line
            v2_data = df_temp[df_temp['version'] == 'V2.0'].groupby('bucket').size().reset_index(name='sessions')
            if not v2_data.empty:
                fig.add_trace(go.Scatter(
                    x=v2_data['bucket'], y=v2_data['sessions'],
                    mode='lines+markers', fill='tozeroy',
                    name='V2.0 (Outcome)',
                    line=dict(color='#10b981', width=3),
                    marker=dict(size=8, color='#34d399'),
                    fillcolor='rgba(16, 185, 129, 0.15)'
                ))
        else:
            # Single version
            time_data = df_temp.groupby('bucket').size().reset_index(name='sessions')
            color = '#10b981' if version_filter == "V2.0 (Outcome-Focused)" else '#3b82f6'
            fig.add_trace(go.Scatter(
                x=time_data['bucket'], y=time_data['sessions'],
                mode='lines+markers', fill='tozeroy',
                line=dict(color=color, width=3),
                marker=dict(size=8, color=color),
                fillcolor=f'rgba({16 if color == "#10b981" else 59}, {185 if color == "#10b981" else 130}, {129 if color == "#10b981" else 246}, 0.2)'
            ))
        
        fig.update_layout(**plotly_layout, height=220, showlegend=show_version_comparison and version_filter == "Both Versions")
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown('<p class="section-header">Device Breakdown</p>', unsafe_allow_html=True)
    if 'device_type' in df_filtered.columns:
        device_data = df_filtered['device_type'].value_counts()
        fig = go.Figure(go.Pie(
            labels=device_data.index, values=device_data.values,
            hole=0.5, 
            marker=dict(colors=['#8b5cf6', '#3b82f6', '#06b6d4']),
            textinfo='percent+label', textposition='inside',
            textfont=dict(size=12, color='white')
        ))
        fig.update_layout(**plotly_layout, height=220, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with col3:
    st.markdown('<p class="section-header">Traffic Sources</p>', unsafe_allow_html=True)
    if 'utm_source' in df_period.columns:
        # Get real sessions only
        real_sessions = df_period[df_period['is_bot'] != True]
        source_data = real_sessions['utm_source'].value_counts().head(5)
        
        color_map = {'tiktok': '#ff0050', 'direct': '#10b981', 'google': '#f59e0b'}
        bar_colors = [color_map.get(s, '#64748b') for s in source_data.index]
        
        fig = go.Figure(go.Bar(
            x=source_data.index, y=source_data.values,
            marker=dict(color=bar_colors),
            text=source_data.values, textposition='outside'
        ))
        fig.update_layout(**plotly_layout, height=220)
        st.plotly_chart(fig, use_container_width=True)

# ============== CHARTS ROW 2 ==============
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<p class="section-header">Top Locations</p>', unsafe_allow_html=True)
    if 'city' in df_filtered.columns:
        cities = df_filtered[df_filtered['city'].notna() & (df_filtered['city'] != '')]['city'].value_counts().head(6)
        if len(cities) > 0:
            # Gradient colors
            n = len(cities)
            bar_colors = [f'rgba(59, 130, 246, {0.4 + 0.6*i/n})' for i in range(n)]
            
            fig = go.Figure(go.Bar(
                x=cities.values, y=cities.index, orientation='h',
                marker=dict(color=bar_colors[::-1]),
                text=cities.values, textposition='outside'
            ))
            layout = plotly_layout.copy()
            layout['yaxis'] = dict(categoryorder='total ascending', gridcolor='rgba(148,163,184,0.1)')
            fig.update_layout(**layout, height=220)
            st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown('<p class="section-header">Scroll Depth Distribution</p>', unsafe_allow_html=True)
    if 'scroll_depth_pct' in df_filtered.columns:
        scroll_data = df_filtered[df_filtered['scroll_depth_pct'] > 0]['scroll_depth_pct']
        if len(scroll_data) > 0:
            fig = go.Figure(go.Histogram(
                x=scroll_data, nbinsx=10,
                marker=dict(color='#8b5cf6', line=dict(color='#a78bfa', width=1))
            ))
            fig.update_layout(**plotly_layout, height=220, xaxis_title="Scroll %")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No scroll data")

with col3:
    st.markdown('<p class="section-header">Time on Site Distribution</p>', unsafe_allow_html=True)
    if 'time_on_site_sec' in df_filtered.columns:
        time_data = df_filtered[(df_filtered['time_on_site_sec'] > 0) & (df_filtered['time_on_site_sec'] <= 120)]['time_on_site_sec']
        if len(time_data) > 0:
            fig = go.Figure(go.Histogram(
                x=time_data, nbinsx=12,
                marker=dict(color='#10b981', line=dict(color='#34d399', width=1))
            ))
            fig.update_layout(**plotly_layout, height=220, xaxis_title="Seconds")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No time data")

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
