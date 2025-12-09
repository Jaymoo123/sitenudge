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

# Custom CSS for dark theme
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #0f3460;
    }
    .big-number {
        font-size: 2.5rem;
        font-weight: 700;
        color: #00d4ff;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stMetric {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #0f3460;
    }
</style>
""", unsafe_allow_html=True)

# Supabase connection
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# Fetch data with caching (short TTL for real-time feel)
@st.cache_data(ttl=10)  # Refresh every 10 seconds
def fetch_sessions(hours_back: int = 24):
    supabase = get_supabase()
    cutoff = (datetime.now(pytz.UTC) - timedelta(hours=hours_back)).isoformat()
    
    response = supabase.table('session_sessions') \
        .select('*') \
        .gte('started_at', cutoff) \
        .order('started_at', desc=True) \
        .execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        df['started_at'] = pd.to_datetime(df['started_at'])
        return df
    return pd.DataFrame()

@st.cache_data(ttl=10)
def fetch_all_sessions():
    supabase = get_supabase()
    response = supabase.table('session_sessions') \
        .select('*') \
        .order('started_at', desc=True) \
        .execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        df['started_at'] = pd.to_datetime(df['started_at'])
        return df
    return pd.DataFrame()

# Sidebar
st.sidebar.title("📊 SiteNudge Analytics")
st.sidebar.markdown("---")

# Time range selector
time_range = st.sidebar.selectbox(
    "Time Range",
    ["Last Hour", "Last 6 Hours", "Last 24 Hours", "Last 7 Days", "All Time"],
    index=2
)

# Auto-refresh toggle
auto_refresh = st.sidebar.checkbox("Auto-refresh (10s)", value=True)
if auto_refresh:
    st.sidebar.caption("🔄 Data refreshes automatically")

# Filter options
st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
exclude_bots = st.sidebar.checkbox("Exclude bots", value=True)
source_filter = st.sidebar.multiselect(
    "Traffic Source",
    ["tiktok", "direct", "organic"],
    default=[]
)

# Load data based on time range
hours_map = {
    "Last Hour": 1,
    "Last 6 Hours": 6,
    "Last 24 Hours": 24,
    "Last 7 Days": 168,
    "All Time": None
}

if time_range == "All Time":
    df = fetch_all_sessions()
else:
    df = fetch_sessions(hours_map[time_range])

# Apply filters
if not df.empty:
    if exclude_bots:
        df = df[df['is_bot'] != True]
    
    if source_filter:
        df = df[df['utm_source'].isin(source_filter)]

# Main content
st.title("📈 Live Analytics Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Showing: {time_range}")

if df.empty:
    st.warning("No data available for the selected time range.")
    st.stop()

# Key Metrics Row
col1, col2, col3, col4, col5 = st.columns(5)

total_sessions = len(df)
tiktok_sessions = len(df[df['utm_source'] == 'tiktok'])
avg_time = df['time_on_site_sec'].mean() if 'time_on_site_sec' in df.columns else 0
buy_clicks = df['clicked_buy'].sum() if 'clicked_buy' in df.columns else 0
conversion_rate = (buy_clicks / total_sessions * 100) if total_sessions > 0 else 0

with col1:
    st.metric("Total Sessions", f"{total_sessions:,}")

with col2:
    st.metric("TikTok Sessions", f"{tiktok_sessions:,}")

with col3:
    st.metric("Avg Time (sec)", f"{avg_time:.1f}")

with col4:
    st.metric("Buy Clicks", f"{int(buy_clicks):,}")

with col5:
    st.metric("Click Rate", f"{conversion_rate:.1f}%")

st.markdown("---")

# Charts Row 1
col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Sessions Over Time")
    
    # Group by hour or minute depending on time range
    if time_range in ["Last Hour", "Last 6 Hours"]:
        df['time_bucket'] = df['started_at'].dt.floor('5min')
        time_label = "Time (5-min intervals)"
    else:
        df['time_bucket'] = df['started_at'].dt.floor('H')
        time_label = "Time (hourly)"
    
    sessions_over_time = df.groupby('time_bucket').size().reset_index(name='sessions')
    
    fig = px.line(
        sessions_over_time, 
        x='time_bucket', 
        y='sessions',
        markers=True,
        color_discrete_sequence=['#00d4ff']
    )
    fig.update_layout(
        xaxis_title=time_label,
        yaxis_title="Sessions",
        template="plotly_dark",
        height=350,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🎯 Traffic Sources")
    
    source_counts = df['utm_source'].value_counts().reset_index()
    source_counts.columns = ['source', 'count']
    
    fig = px.pie(
        source_counts, 
        values='count', 
        names='source',
        color_discrete_sequence=px.colors.sequential.Plasma_r,
        hole=0.4
    )
    fig.update_layout(
        template="plotly_dark",
        height=350,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

# Charts Row 2
col1, col2 = st.columns(2)

with col1:
    st.subheader("📱 Device Breakdown")
    
    device_counts = df['device_type'].value_counts().reset_index()
    device_counts.columns = ['device', 'count']
    
    fig = px.bar(
        device_counts, 
        x='device', 
        y='count',
        color='device',
        color_discrete_sequence=['#00d4ff', '#ff6b6b', '#feca57']
    )
    fig.update_layout(
        xaxis_title="Device",
        yaxis_title="Sessions",
        template="plotly_dark",
        height=300,
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🌍 Top Locations")
    
    if 'city' in df.columns:
        city_counts = df[df['city'].notna() & (df['city'] != '')]['city'].value_counts().head(10).reset_index()
        city_counts.columns = ['city', 'count']
        
        fig = px.bar(
            city_counts, 
            x='count', 
            y='city',
            orientation='h',
            color='count',
            color_continuous_scale='Viridis'
        )
        fig.update_layout(
            xaxis_title="Sessions",
            yaxis_title="",
            template="plotly_dark",
            height=300,
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            yaxis={'categoryorder': 'total ascending'}
        )
        st.plotly_chart(fig, use_container_width=True)

# A/B Test Results
st.markdown("---")
st.subheader("🧪 A/B Test Results")

ab_col1, ab_col2, ab_col3 = st.columns(3)

def calculate_ab_stats(df, variant_col, test_name):
    if variant_col not in df.columns:
        return None
    
    stats = df.groupby(variant_col).agg({
        'session_id': 'count',
        'clicked_buy': 'sum',
        'time_on_site_sec': 'mean'
    }).reset_index()
    stats.columns = ['variant', 'sessions', 'clicks', 'avg_time']
    stats['click_rate'] = (stats['clicks'] / stats['sessions'] * 100).round(1)
    return stats

with ab_col1:
    st.markdown("**Hero Test**")
    hero_stats = calculate_ab_stats(df, 'hero_variant', 'Hero')
    if hero_stats is not None and not hero_stats.empty:
        for _, row in hero_stats.iterrows():
            st.metric(
                f"{row['variant'].title()}",
                f"{row['click_rate']}% CTR",
                f"{int(row['sessions'])} sessions"
            )

with ab_col2:
    st.markdown("**Social Proof Test**")
    sp_stats = calculate_ab_stats(df, 'social_proof_variant', 'Social Proof')
    if sp_stats is not None and not sp_stats.empty:
        for _, row in sp_stats.iterrows():
            st.metric(
                f"{row['variant'].title()}",
                f"{row['click_rate']}% CTR",
                f"{int(row['sessions'])} sessions"
            )

with ab_col3:
    st.markdown("**Scroll Hook Test**")
    sh_stats = calculate_ab_stats(df, 'scroll_hook_variant', 'Scroll Hook')
    if sh_stats is not None and not sh_stats.empty:
        for _, row in sh_stats.iterrows():
            st.metric(
                f"{row['variant'].title()}",
                f"{row['click_rate']}% CTR",
                f"{int(row['sessions'])} sessions"
            )

# Recent Sessions Table
st.markdown("---")
st.subheader("📋 Recent Sessions")

# Select columns to display
display_cols = ['started_at', 'utm_source', 'device_type', 'city', 'country', 
                'time_on_site_sec', 'scroll_depth_pct', 'clicked_buy', 'hero_variant']
display_cols = [c for c in display_cols if c in df.columns]

recent_df = df[display_cols].head(20).copy()
recent_df['started_at'] = recent_df['started_at'].dt.strftime('%H:%M:%S')

st.dataframe(
    recent_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "started_at": st.column_config.TextColumn("Time"),
        "utm_source": st.column_config.TextColumn("Source"),
        "device_type": st.column_config.TextColumn("Device"),
        "city": st.column_config.TextColumn("City"),
        "country": st.column_config.TextColumn("Country"),
        "time_on_site_sec": st.column_config.NumberColumn("Time (s)"),
        "scroll_depth_pct": st.column_config.ProgressColumn("Scroll %", min_value=0, max_value=100),
        "clicked_buy": st.column_config.CheckboxColumn("Clicked Buy"),
        "hero_variant": st.column_config.TextColumn("Hero"),
    }
)

# Auto-refresh mechanism
if auto_refresh:
    import time
    time.sleep(10)
    st.rerun()

