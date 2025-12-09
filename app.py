import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client
from datetime import datetime, timedelta
import pytz
import numpy as np

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
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #2d4a6f;
    }
    .winner { background: linear-gradient(135deg, #1a4d2e 0%, #0d2137 100%) !important; border-color: #2d6f4a !important; }
    .loser { background: linear-gradient(135deg, #4d1a1a 0%, #0d2137 100%) !important; border-color: #6f2d2d !important; }
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

# Calculate metrics for a dataframe
def calculate_metrics(df):
    if df.empty:
        return {
            'sessions': 0, 'avg_time': 0, 'median_time': 0,
            'avg_scroll': 0, 'median_scroll': 0, 'total_clicks': 0,
            'clicked_buy': 0, 'initiated_checkout': 0, 'purchased': 0,
            'sessions_with_time': 0, 'bounce_rate': 0,
        }
    
    time_col = df['time_on_site_sec'] if 'time_on_site_sec' in df.columns else pd.Series([0])
    valid_time = time_col[(time_col > 0) & (time_col <= 1800)]
    
    scroll_col = df['scroll_depth_pct'] if 'scroll_depth_pct' in df.columns else pd.Series([0])
    valid_scroll = scroll_col[scroll_col > 0]
    
    bounces = len(df[(time_col == 0) | (scroll_col == 0)])
    
    return {
        'sessions': len(df),
        'avg_time': valid_time.mean() if len(valid_time) > 0 else 0,
        'median_time': valid_time.median() if len(valid_time) > 0 else 0,
        'avg_scroll': valid_scroll.mean() if len(valid_scroll) > 0 else 0,
        'median_scroll': valid_scroll.median() if len(valid_scroll) > 0 else 0,
        'total_clicks': df['clicks_total'].sum() if 'clicks_total' in df.columns else 0,
        'clicked_buy': df['clicked_buy'].sum() if 'clicked_buy' in df.columns else 0,
        'initiated_checkout': df['initiated_checkout'].sum() if 'initiated_checkout' in df.columns else 0,
        'purchased': df['purchased'].sum() if 'purchased' in df.columns else 0,
        'sessions_with_time': len(valid_time),
        'bounce_rate': (bounces / len(df) * 100) if len(df) > 0 else 0,
    }

# Calculate A/B test stats
def calculate_ab_stats(df, variant_col):
    if variant_col not in df.columns or df.empty:
        return None
    
    results = []
    for variant in df[variant_col].dropna().unique():
        variant_df = df[df[variant_col] == variant]
        metrics = calculate_metrics(variant_df)
        
        click_rate = (metrics['clicked_buy'] / metrics['sessions'] * 100) if metrics['sessions'] > 0 else 0
        checkout_rate = (metrics['initiated_checkout'] / metrics['sessions'] * 100) if metrics['sessions'] > 0 else 0
        
        results.append({
            'variant': variant,
            'sessions': metrics['sessions'],
            'median_time': metrics['median_time'],
            'median_scroll': metrics['median_scroll'],
            'clicked_buy': metrics['clicked_buy'],
            'click_rate': click_rate,
            'checkout_rate': checkout_rate,
            'bounce_rate': metrics['bounce_rate'],
        })
    
    return pd.DataFrame(results)

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

compare = st.sidebar.checkbox("Compare to previous period", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Filters")
show_tiktok_only = st.sidebar.checkbox("TikTok traffic only", value=True)
exclude_bots = st.sidebar.checkbox("Exclude bots", value=True)

st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (10s)", value=False)

# Load data
df_all = fetch_all_sessions()

if df_all.empty:
    st.warning("No data available.")
    st.stop()

# Calculate date ranges
now = datetime.now(pytz.UTC)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
yesterday_start = today_start - timedelta(days=1)
week_start = today_start - timedelta(days=today_start.weekday())
month_start = today_start.replace(day=1)

if period == "Today":
    current_start, current_end = today_start, now
    prev_start, prev_end = yesterday_start, today_start
    period_label, prev_label = "Today", "Yesterday"
elif period == "Yesterday":
    current_start, current_end = yesterday_start, today_start
    prev_start, prev_end = yesterday_start - timedelta(days=1), yesterday_start
    period_label, prev_label = "Yesterday", "Day Before"
elif period == "Last 7 Days":
    current_start, current_end = now - timedelta(days=7), now
    prev_start, prev_end = now - timedelta(days=14), now - timedelta(days=7)
    period_label, prev_label = "Last 7 Days", "Previous 7 Days"
elif period == "Last 30 Days":
    current_start, current_end = now - timedelta(days=30), now
    prev_start, prev_end = now - timedelta(days=60), now - timedelta(days=30)
    period_label, prev_label = "Last 30 Days", "Previous 30 Days"
elif period == "This Week":
    current_start, current_end = week_start, now
    prev_start, prev_end = week_start - timedelta(days=7), week_start
    period_label, prev_label = "This Week", "Last Week"
elif period == "This Month":
    current_start, current_end = month_start, now
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_start, prev_end = prev_month_start, month_start
    period_label, prev_label = "This Month", "Last Month"
else:
    current_start = df_all['started_at'].min() if not df_all.empty else now - timedelta(days=30)
    current_end = now
    prev_start, prev_end = current_start, current_start
    period_label, prev_label = "All Time", "N/A"
    compare = False

# Filter data
df_period_all = df_all[(df_all['started_at'] >= current_start) & (df_all['started_at'] <= current_end)]

df_filtered = df_period_all.copy()
if exclude_bots:
    df_filtered = df_filtered[df_filtered['is_bot'] != True]
if show_tiktok_only:
    df_filtered = df_filtered[df_filtered['utm_source'] == 'tiktok']

df_prev = df_all[(df_all['started_at'] >= prev_start) & (df_all['started_at'] < prev_end)]
if exclude_bots:
    df_prev = df_prev[df_prev['is_bot'] != True]
if show_tiktok_only:
    df_prev = df_prev[df_prev['utm_source'] == 'tiktok']

current_metrics = calculate_metrics(df_filtered)
prev_metrics = calculate_metrics(df_prev)

def calc_delta(current, prev):
    if prev == 0: return None
    return ((current - prev) / prev) * 100

# ===================
# HEADER
# ===================
st.title("📈 SiteNudge Analytics")
st.caption(f"**{period_label}** | Last updated: {now.strftime('%H:%M:%S')}")

# ===================
# TRAFFIC OVERVIEW
# ===================
st.markdown("---")
st.subheader("🔍 Traffic Overview")

total_all = len(df_period_all)
total_bots = len(df_period_all[df_period_all['is_bot'] == True])
total_real = total_all - total_bots
total_tiktok = len(df_period_all[(df_period_all['utm_source'] == 'tiktok') & (df_period_all['is_bot'] != True)])

pct_real = (total_real / total_all * 100) if total_all > 0 else 0
pct_tiktok = (total_tiktok / total_real * 100) if total_real > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Sessions", f"{total_all:,}")
    st.caption("All traffic including bots")
with col2:
    st.metric("Real Sessions", f"{total_real:,}")
    st.caption(f"**{pct_real:.1f}%** of total | {total_bots} bots")
with col3:
    st.metric("TikTok Sessions", f"{total_tiktok:,}")
    st.caption(f"**{pct_tiktok:.1f}%** of real sessions")
with col4:
    other_real = total_real - total_tiktok
    st.metric("Other Sources", f"{other_real:,}")

# ===================
# ENGAGEMENT METRICS
# ===================
st.markdown("---")
st.subheader("📊 Engagement Metrics")
st.caption(f"{'🎵 TikTok Only' if show_tiktok_only else 'All Sources'} | {'🤖 Bots Excluded' if exclude_bots else 'Including Bots'}")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    delta = calc_delta(current_metrics['sessions'], prev_metrics['sessions']) if compare else None
    st.metric("Sessions", f"{current_metrics['sessions']:,}", delta=f"{delta:+.1f}%" if delta else None)

with col2:
    delta = calc_delta(current_metrics['median_time'], prev_metrics['median_time']) if compare else None
    st.metric("Median Time", f"{current_metrics['median_time']:.0f}s", delta=f"{delta:+.1f}%" if delta else None)

with col3:
    delta = calc_delta(current_metrics['median_scroll'], prev_metrics['median_scroll']) if compare else None
    st.metric("Median Scroll", f"{current_metrics['median_scroll']:.0f}%", delta=f"{delta:+.1f}%" if delta else None)

with col4:
    st.metric("Bounce Rate", f"{current_metrics['bounce_rate']:.1f}%")

with col5:
    st.metric("Total Clicks", f"{int(current_metrics['total_clicks']):,}")

# ===================
# CONVERSION FUNNEL
# ===================
st.markdown("---")
st.subheader("🎯 Conversion Funnel")

sessions = current_metrics['sessions']
clicked_buy = int(current_metrics['clicked_buy'])
initiated_checkout = int(current_metrics['initiated_checkout'])
purchased = int(current_metrics['purchased'])

pct_clicked = (clicked_buy / sessions * 100) if sessions > 0 else 0
pct_checkout = (initiated_checkout / sessions * 100) if sessions > 0 else 0
pct_checkout_of_clicks = (initiated_checkout / clicked_buy * 100) if clicked_buy > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Sessions", f"{sessions:,}")
    st.caption("100%")
with col2:
    st.metric("Clicked Buy", f"{clicked_buy:,}")
    st.caption(f"**{pct_clicked:.1f}%** of sessions")
with col3:
    st.metric("Initiated Checkout", f"{initiated_checkout:,}")
    st.caption(f"**{pct_checkout:.1f}%** of sessions")
with col4:
    st.metric("Purchased", f"{purchased:,}")

# Funnel chart
col1, col2 = st.columns([2, 1])
with col1:
    fig = go.Figure(go.Funnel(
        y=['Sessions', 'Clicked Buy', 'Checkout', 'Purchased'],
        x=[sessions, clicked_buy, initiated_checkout, purchased],
        textinfo="value+percent initial",
        marker=dict(color=['#00d4ff', '#00b4d8', '#0096c7', '#0077b6'])
    ))
    fig.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("**Conversion Rates**")
    st.markdown(f"- Sessions → Buy: **{pct_clicked:.1f}%**")
    st.markdown(f"- Sessions → Checkout: **{pct_checkout:.1f}%**")
    st.markdown(f"- Buy → Checkout: **{pct_checkout_of_clicks:.1f}%**")

# ===================
# A/B TESTING RESULTS
# ===================
st.markdown("---")
st.header("🧪 A/B Testing Results")

# Define tests
ab_tests = [
    {'name': 'Hero Section', 'variant_col': 'hero_variant', 'test_id_col': 'hero_test_id', 'icon': '🦸'},
    {'name': 'Social Proof', 'variant_col': 'social_proof_variant', 'test_id_col': 'social_proof_test_id', 'icon': '👥'},
    {'name': 'Scroll Hook', 'variant_col': 'scroll_hook_variant', 'test_id_col': 'scroll_hook_test_id', 'icon': '🎣'},
]

for test in ab_tests:
    st.subheader(f"{test['icon']} {test['name']} Test")
    
    stats = calculate_ab_stats(df_filtered, test['variant_col'])
    
    if stats is None or stats.empty:
        st.info(f"No data for {test['name']} test")
        continue
    
    # Determine winner
    if len(stats) >= 2:
        winner_idx = stats['click_rate'].idxmax()
        winner = stats.loc[winner_idx, 'variant']
    else:
        winner = None
    
    # Display metrics for each variant
    cols = st.columns(len(stats))
    for i, (idx, row) in enumerate(stats.iterrows()):
        with cols[i]:
            is_winner = row['variant'] == winner and len(stats) >= 2
            
            st.markdown(f"### {'🏆 ' if is_winner else ''}{row['variant'].title()}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Sessions", f"{int(row['sessions']):,}")
                st.metric("Click Rate", f"{row['click_rate']:.1f}%")
            with col_b:
                st.metric("Median Time", f"{row['median_time']:.0f}s")
                st.metric("Median Scroll", f"{row['median_scroll']:.0f}%")
    
    # Comparison chart
    if len(stats) >= 2:
        fig = make_subplots(rows=1, cols=3, subplot_titles=('Click Rate %', 'Median Time (s)', 'Median Scroll %'))
        
        colors = ['#00d4ff' if v == 'control' else '#ff6b6b' for v in stats['variant']]
        
        fig.add_trace(go.Bar(x=stats['variant'], y=stats['click_rate'], marker_color=colors, name='Click Rate'), row=1, col=1)
        fig.add_trace(go.Bar(x=stats['variant'], y=stats['median_time'], marker_color=colors, name='Time', showlegend=False), row=1, col=2)
        fig.add_trace(go.Bar(x=stats['variant'], y=stats['median_scroll'], marker_color=colors, name='Scroll', showlegend=False), row=1, col=3)
        
        fig.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Winner callout
        if winner:
            control_rate = stats[stats['variant'] == 'control']['click_rate'].values[0] if 'control' in stats['variant'].values else 0
            test_rate = stats[stats['variant'] == 'test']['click_rate'].values[0] if 'test' in stats['variant'].values else 0
            
            if control_rate > 0 and test_rate > 0:
                lift = ((test_rate - control_rate) / control_rate) * 100
                if lift > 0:
                    st.success(f"📈 **Test variant** is winning with **{lift:+.1f}%** lift in click rate")
                elif lift < 0:
                    st.error(f"📉 **Control variant** is winning. Test has **{lift:.1f}%** lower click rate")
                else:
                    st.info("⚖️ Both variants are performing equally")
    
    st.markdown("---")

# ===================
# DEVICE & LOCATION
# ===================
st.header("📱 Device & Location Breakdown")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Device Types")
    if 'device_type' in df_filtered.columns:
        device_counts = df_filtered['device_type'].value_counts().reset_index()
        device_counts.columns = ['Device', 'Count']
        
        fig = px.pie(device_counts, values='Count', names='Device', 
                     color_discrete_sequence=['#00d4ff', '#ff6b6b', '#feca57'])
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Top Locations")
    if 'city' in df_filtered.columns:
        city_counts = df_filtered[df_filtered['city'].notna() & (df_filtered['city'] != '')]['city'].value_counts().head(8)
        
        fig = px.bar(x=city_counts.values, y=city_counts.index, orientation='h',
                     color=city_counts.values, color_continuous_scale='Viridis')
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0),
                         yaxis={'categoryorder': 'total ascending'}, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

# ===================
# TIME ANALYSIS
# ===================
st.markdown("---")
st.header("⏰ Time Analysis")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Sessions Over Time")
    if not df_filtered.empty:
        if period in ["Today", "Yesterday"]:
            df_filtered['time_bucket'] = df_filtered['started_at'].dt.floor('H')
        else:
            df_filtered['time_bucket'] = df_filtered['started_at'].dt.floor('D')
        
        time_data = df_filtered.groupby('time_bucket').agg({
            'session_id': 'count',
            'clicked_buy': 'sum'
        }).reset_index()
        time_data.columns = ['Time', 'Sessions', 'Buy Clicks']
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=time_data['Time'], y=time_data['Sessions'], mode='lines+markers',
                                 name='Sessions', line=dict(color='#00d4ff')))
        fig.add_trace(go.Bar(x=time_data['Time'], y=time_data['Buy Clicks'], name='Buy Clicks',
                            marker_color='#ff6b6b', opacity=0.7))
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Hour of Day (All Time)")
    if not df_all.empty:
        df_all['hour'] = df_all['started_at'].dt.hour
        hour_data = df_all[df_all['is_bot'] != True].groupby('hour').size().reset_index(name='sessions')
        
        fig = px.bar(hour_data, x='hour', y='sessions', color='sessions',
                     color_continuous_scale='Blues')
        fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=10, b=0),
                         xaxis_title="Hour (UTC)", coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

# ===================
# SCROLL & TIME DISTRIBUTION
# ===================
st.markdown("---")
st.header("📊 Engagement Distribution")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Scroll Depth Distribution")
    if 'scroll_depth_pct' in df_filtered.columns:
        scroll_data = df_filtered[df_filtered['scroll_depth_pct'] > 0]['scroll_depth_pct']
        if len(scroll_data) > 0:
            fig = px.histogram(scroll_data, nbins=10, color_discrete_sequence=['#00d4ff'])
            fig.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=10, b=0),
                             xaxis_title="Scroll Depth %", yaxis_title="Sessions")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No scroll data available")

with col2:
    st.subheader("Time on Site Distribution")
    if 'time_on_site_sec' in df_filtered.columns:
        time_data = df_filtered[(df_filtered['time_on_site_sec'] > 0) & (df_filtered['time_on_site_sec'] <= 300)]['time_on_site_sec']
        if len(time_data) > 0:
            fig = px.histogram(time_data, nbins=15, color_discrete_sequence=['#ff6b6b'])
            fig.update_layout(template="plotly_dark", height=250, margin=dict(l=0, r=0, t=10, b=0),
                             xaxis_title="Time (seconds)", yaxis_title="Sessions")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No time data available")

# ===================
# RECENT SESSIONS
# ===================
st.markdown("---")
st.header("📋 Recent Sessions")

display_cols = ['started_at', 'utm_source', 'device_type', 'city', 'time_on_site_sec', 
                'scroll_depth_pct', 'clicked_buy', 'hero_variant', 'social_proof_variant']
display_cols = [c for c in display_cols if c in df_filtered.columns]

if not df_filtered.empty:
    recent_df = df_filtered[display_cols].head(20).copy()
    recent_df['started_at'] = recent_df['started_at'].dt.strftime('%H:%M:%S')
    st.dataframe(recent_df, use_container_width=True, hide_index=True)
else:
    st.info("No sessions in selected period")

# Auto-refresh
if auto_refresh:
    import time
    time.sleep(10)
    st.rerun()
