import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta
import pytz

# Page config
st.set_page_config(
    page_title="SiteNudge Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-container {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
        border-radius: 10px;
        padding: 15px;
        margin: 5px 0;
    }
    .big-metric {
        font-size: 2.5rem;
        font-weight: 700;
        color: #00d4ff;
    }
    .comparison-up { color: #00ff88; }
    .comparison-down { color: #ff6b6b; }
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #2d4a6f;
    }
</style>
""", unsafe_allow_html=True)

# Supabase connection
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# Fetch all data
@st.cache_data(ttl=10)
def fetch_all_sessions():
    supabase = get_supabase()
    response = supabase.table('session_sessions') \
        .select('*') \
        .order('started_at', desc=True) \
        .execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        df['started_at'] = pd.to_datetime(df['started_at'], utc=True)
        return df
    return pd.DataFrame()

# Calculate metrics for a period
def calculate_metrics(df):
    if df.empty:
        return {
            'sessions': 0,
            'avg_time': 0,
            'avg_scroll': 0,
            'total_clicks': 0,
            'clicked_buy': 0,
            'initiated_checkout': 0,
            'purchased': 0,
        }
    
    return {
        'sessions': len(df),
        'avg_time': df['time_on_site_sec'].mean() if 'time_on_site_sec' in df.columns else 0,
        'avg_scroll': df['scroll_depth_pct'].mean() if 'scroll_depth_pct' in df.columns else 0,
        'total_clicks': df['clicks_total'].sum() if 'clicks_total' in df.columns else 0,
        'clicked_buy': df['clicked_buy'].sum() if 'clicked_buy' in df.columns else 0,
        'initiated_checkout': df['initiated_checkout'].sum() if 'initiated_checkout' in df.columns else 0,
        'purchased': df['purchased'].sum() if 'purchased' in df.columns else 0,
    }

# Sidebar
st.sidebar.title("📊 SiteNudge Analytics")
st.sidebar.markdown("---")

# Time period selector
st.sidebar.subheader("📅 Time Period")
period = st.sidebar.selectbox(
    "Select Period",
    ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Week", "This Month", "All Time"],
    index=0
)

# Comparison period
compare = st.sidebar.checkbox("Compare to previous period", value=True)

st.sidebar.markdown("---")

# Filters
st.sidebar.subheader("🎯 Filters")
show_tiktok_only = st.sidebar.checkbox("TikTok traffic only", value=True)
exclude_bots = st.sidebar.checkbox("Exclude bots", value=True)

# Auto-refresh
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (10s)", value=True)

# Load data
df_all = fetch_all_sessions()

if df_all.empty:
    st.warning("No data available.")
    st.stop()

# Apply filters
df_filtered = df_all.copy()

if exclude_bots:
    df_filtered = df_filtered[df_filtered['is_bot'] != True]

if show_tiktok_only:
    df_filtered = df_filtered[df_filtered['utm_source'] == 'tiktok']

# Calculate date ranges
now = datetime.now(pytz.UTC)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
yesterday_start = today_start - timedelta(days=1)
week_start = today_start - timedelta(days=today_start.weekday())
month_start = today_start.replace(day=1)

# Get current and comparison periods based on selection
if period == "Today":
    current_start = today_start
    current_end = now
    prev_start = yesterday_start
    prev_end = today_start
    period_label = "Today"
    prev_label = "Yesterday"
elif period == "Yesterday":
    current_start = yesterday_start
    current_end = today_start
    prev_start = yesterday_start - timedelta(days=1)
    prev_end = yesterday_start
    period_label = "Yesterday"
    prev_label = "Day Before"
elif period == "Last 7 Days":
    current_start = now - timedelta(days=7)
    current_end = now
    prev_start = now - timedelta(days=14)
    prev_end = now - timedelta(days=7)
    period_label = "Last 7 Days"
    prev_label = "Previous 7 Days"
elif period == "Last 30 Days":
    current_start = now - timedelta(days=30)
    current_end = now
    prev_start = now - timedelta(days=60)
    prev_end = now - timedelta(days=30)
    period_label = "Last 30 Days"
    prev_label = "Previous 30 Days"
elif period == "This Week":
    current_start = week_start
    current_end = now
    prev_start = week_start - timedelta(days=7)
    prev_end = week_start
    period_label = "This Week"
    prev_label = "Last Week"
elif period == "This Month":
    current_start = month_start
    current_end = now
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_start = prev_month_start
    prev_end = month_start
    period_label = "This Month"
    prev_label = "Last Month"
else:  # All Time
    current_start = df_filtered['started_at'].min() if not df_filtered.empty else now - timedelta(days=30)
    current_end = now
    prev_start = current_start
    prev_end = current_start
    period_label = "All Time"
    prev_label = "N/A"
    compare = False

# Filter data by period
df_current = df_filtered[(df_filtered['started_at'] >= current_start) & (df_filtered['started_at'] <= current_end)]
df_prev = df_filtered[(df_filtered['started_at'] >= prev_start) & (df_filtered['started_at'] < prev_end)]

# Calculate metrics
current_metrics = calculate_metrics(df_current)
prev_metrics = calculate_metrics(df_prev)

# Calculate deltas
def calc_delta(current, prev):
    if prev == 0:
        return None
    return ((current - prev) / prev) * 100

# Header
st.title("📈 SiteNudge Analytics")

# Filter status
filter_text = []
if show_tiktok_only:
    filter_text.append("🎵 TikTok Only")
if exclude_bots:
    filter_text.append("🤖 Bots Excluded")
filter_display = " | ".join(filter_text) if filter_text else "All Traffic"

st.caption(f"**{period_label}** | {filter_display} | Last updated: {now.strftime('%H:%M:%S')}")

st.markdown("---")

# Main Metrics Row
st.subheader("📊 Key Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    delta = calc_delta(current_metrics['sessions'], prev_metrics['sessions']) if compare else None
    st.metric(
        "Total Sessions",
        f"{current_metrics['sessions']:,}",
        delta=f"{delta:+.1f}%" if delta else None,
        delta_color="normal"
    )

with col2:
    delta = calc_delta(current_metrics['avg_time'], prev_metrics['avg_time']) if compare else None
    st.metric(
        "Avg Time on Site",
        f"{current_metrics['avg_time']:.1f}s",
        delta=f"{delta:+.1f}%" if delta else None,
        delta_color="normal"
    )

with col3:
    delta = calc_delta(current_metrics['avg_scroll'], prev_metrics['avg_scroll']) if compare else None
    st.metric(
        "Avg Scroll Depth",
        f"{current_metrics['avg_scroll']:.1f}%",
        delta=f"{delta:+.1f}%" if delta else None,
        delta_color="normal"
    )

with col4:
    delta = calc_delta(current_metrics['total_clicks'], prev_metrics['total_clicks']) if compare else None
    st.metric(
        "Total Clicks",
        f"{int(current_metrics['total_clicks']):,}",
        delta=f"{delta:+.1f}%" if delta else None,
        delta_color="normal"
    )

st.markdown("---")

# Conversion Funnel
st.subheader("🎯 Conversion Funnel")

col1, col2, col3, col4 = st.columns(4)

sessions = current_metrics['sessions']
clicked_buy = int(current_metrics['clicked_buy'])
initiated_checkout = int(current_metrics['initiated_checkout'])
purchased = int(current_metrics['purchased'])

# Calculate percentages
pct_clicked_buy = (clicked_buy / sessions * 100) if sessions > 0 else 0
pct_initiated_checkout = (initiated_checkout / sessions * 100) if sessions > 0 else 0
pct_checkout_of_clicks = (initiated_checkout / clicked_buy * 100) if clicked_buy > 0 else 0
pct_purchased = (purchased / sessions * 100) if sessions > 0 else 0

with col1:
    st.metric("Sessions", f"{sessions:,}", help="Total sessions in period")
    st.caption("100% of traffic")

with col2:
    delta = calc_delta(clicked_buy, prev_metrics['clicked_buy']) if compare else None
    st.metric(
        "Clicked Buy", 
        f"{clicked_buy:,}",
        delta=f"{delta:+.1f}%" if delta else None
    )
    st.caption(f"**{pct_clicked_buy:.1f}%** of sessions")

with col3:
    delta = calc_delta(initiated_checkout, prev_metrics['initiated_checkout']) if compare else None
    st.metric(
        "Initiated Checkout", 
        f"{initiated_checkout:,}",
        delta=f"{delta:+.1f}%" if delta else None
    )
    st.caption(f"**{pct_initiated_checkout:.1f}%** of sessions | **{pct_checkout_of_clicks:.1f}%** of buy clicks")

with col4:
    delta = calc_delta(purchased, prev_metrics['purchased']) if compare else None
    st.metric(
        "Purchased", 
        f"{purchased:,}",
        delta=f"{delta:+.1f}%" if delta else None
    )
    st.caption(f"**{pct_purchased:.1f}%** of sessions")

# Funnel visualization
st.markdown("---")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📉 Funnel Visualization")
    
    funnel_data = pd.DataFrame({
        'Stage': ['Sessions', 'Clicked Buy', 'Initiated Checkout', 'Purchased'],
        'Count': [sessions, clicked_buy, initiated_checkout, purchased]
    })
    
    fig = go.Figure(go.Funnel(
        y=funnel_data['Stage'],
        x=funnel_data['Count'],
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(color=['#00d4ff', '#00b4d8', '#0096c7', '#0077b6'])
    ))
    
    fig.update_layout(
        template="plotly_dark",
        height=300,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 Conversion Rates")
    
    st.markdown(f"""
    | Metric | Rate |
    |--------|------|
    | Sessions → Buy Click | **{pct_clicked_buy:.1f}%** |
    | Sessions → Checkout | **{pct_initiated_checkout:.1f}%** |
    | Buy Click → Checkout | **{pct_checkout_of_clicks:.1f}%** |
    | Sessions → Purchase | **{pct_purchased:.1f}%** |
    """)
    
    if compare and prev_metrics['sessions'] > 0:
        prev_pct_clicked = (prev_metrics['clicked_buy'] / prev_metrics['sessions'] * 100)
        change = pct_clicked_buy - prev_pct_clicked
        direction = "📈" if change > 0 else "📉" if change < 0 else "➡️"
        st.caption(f"{direction} Buy click rate: {change:+.1f}pp vs {prev_label}")

# Sessions Over Time
st.markdown("---")
st.subheader("📈 Sessions Over Time")

if not df_current.empty:
    # Determine granularity based on period
    if period in ["Today", "Yesterday"]:
        df_current['time_bucket'] = df_current['started_at'].dt.floor('H')
        time_format = '%H:%M'
    elif period in ["Last 7 Days", "This Week"]:
        df_current['time_bucket'] = df_current['started_at'].dt.floor('D')
        time_format = '%a %d'
    else:
        df_current['time_bucket'] = df_current['started_at'].dt.floor('D')
        time_format = '%b %d'
    
    sessions_over_time = df_current.groupby('time_bucket').agg({
        'session_id': 'count',
        'clicked_buy': 'sum',
        'time_on_site_sec': 'mean'
    }).reset_index()
    sessions_over_time.columns = ['Time', 'Sessions', 'Buy Clicks', 'Avg Time']
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=sessions_over_time['Time'],
        y=sessions_over_time['Sessions'],
        mode='lines+markers',
        name='Sessions',
        line=dict(color='#00d4ff', width=2),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Bar(
        x=sessions_over_time['Time'],
        y=sessions_over_time['Buy Clicks'],
        name='Buy Clicks',
        marker_color='#ff6b6b',
        opacity=0.7
    ))
    
    fig.update_layout(
        template="plotly_dark",
        height=350,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="",
        yaxis_title="Count"
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Recent Sessions Table
st.markdown("---")
st.subheader("📋 Recent Sessions")

display_cols = ['started_at', 'device_type', 'city', 'country', 
                'time_on_site_sec', 'scroll_depth_pct', 'clicks_total', 'clicked_buy', 'initiated_checkout']
display_cols = [c for c in display_cols if c in df_current.columns]

if not df_current.empty:
    recent_df = df_current[display_cols].head(15).copy()
    recent_df['started_at'] = recent_df['started_at'].dt.strftime('%H:%M:%S')
    
    st.dataframe(
        recent_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "started_at": st.column_config.TextColumn("Time"),
            "device_type": st.column_config.TextColumn("Device"),
            "city": st.column_config.TextColumn("City"),
            "country": st.column_config.TextColumn("Country"),
            "time_on_site_sec": st.column_config.NumberColumn("Time (s)", format="%d"),
            "scroll_depth_pct": st.column_config.ProgressColumn("Scroll %", min_value=0, max_value=100),
            "clicks_total": st.column_config.NumberColumn("Clicks"),
            "clicked_buy": st.column_config.CheckboxColumn("Buy Click"),
            "initiated_checkout": st.column_config.CheckboxColumn("Checkout"),
        }
    )
else:
    st.info("No sessions in selected period")

# Auto-refresh
if auto_refresh:
    import time
    time.sleep(10)
    st.rerun()
