# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 00:42:48 2025

@author: richs

inspired by this project here: 
    https://volatilitysurface.streamlit.app/
"""
#imports
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import timedelta
from scipy.stats import norm
from scipy.optimize import brentq
from scipy.interpolate import griddata
import plotly.graph_objects as go
#end imports


st.title('Implied Volatility Surface')

# Begin functions

def bs_call_no_div(S, K, T, r, sigma):
    N = norm.cdf
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    call_price = S * N(d1) - K * np.exp(-r*T)* N(d2)
    return call_price

def bs_call_div(S, K, T, r, q, sigma):
    N = norm.cdf
    d1 = (np.log(S/K) + (r - q + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma* np.sqrt(T)
    call_price = S*np.exp(-q*T) * N(d1) - K * np.exp(-r*T)* N(d2)
    return call_price

def bs_put_no_div(S, K, T, r, sigma):
    N = norm.cdf
    d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma* np.sqrt(T)
    put_price = K*np.exp(-r*T)*N(-d2) - S*N(-d1)
    return put_price

def bs_put_div(S, K, T, r, q, sigma):
    N = norm.cdf
    d1 = (np.log(S/K) + (r - q + sigma**2/2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma* np.sqrt(T)
    put_price = K*np.exp(-r*T)*N(-d2) - S*np.exp(-q*T)*N(-d1)
    return put_price





def implied_volatility(price, S, K, T, r, q=0):
    if T <= 0 or price <= 0:
        return np.nan

    def objective_function(sigma):
        return bs_call_price(S, K, T, r, sigma, q) - price

    try:
        implied_vol = brentq(objective_function, 1e-6, 5)
    except (ValueError, RuntimeError):
        implied_vol = np.nan

    return implied_vol



# end functions

st.sidebar.header('Model Parameters')
st.sidebar.write('Adjust the parameters for the Black-Scholes model.')

risk_free_rate = st.sidebar.number_input(
    'Risk-Free Rate (e.g., 0.015 for 1.5%)',
    value=0.015,
    format="%.4f"
)

dividend_yield = st.sidebar.number_input(
    'Dividend Yield (e.g., 0.013 for 1.3%)',
    value=0.013,
    format="%.4f"
)

option_type = st.sidebar.selectbox(
    'Option Type (Call || Put)',
    ('Call', 'Put')
)

st.sidebar.header('Visualization Parameters')
y_axis_option = st.sidebar.selectbox(
    'Select Y-axis:',
    ('Strike Price ($)', 'Moneyness')
)

st.sidebar.header('Ticker Symbol')
ticker_symbol = st.sidebar.text_input(
    'Enter Ticker Symbol',
    value='SPY',
    max_chars=10
).upper()

st.sidebar.header('Strike Price Filter Parameters')

min_strike_pct = st.sidebar.number_input(
    'Minimum Strike Price (% of Spot Price)',
    min_value=50.0,
    max_value=199.0,
    value=80.0,
    step=1.0,
    format="%.1f"
)

max_strike_pct = st.sidebar.number_input(
    'Maximum Strike Price (% of Spot Price)',
    min_value=51.0,
    max_value=200.0,
    value=120.0,
    step=1.0,
    format="%.1f"
)

if min_strike_pct >= max_strike_pct:
    st.sidebar.error('Minimum percentage must be less than maximum percentage.')
    st.stop()

ticker = yf.Ticker(ticker_symbol)

today = pd.Timestamp('today').normalize()

try:
    expirations = ticker.options
except Exception as e:
    st.error(f'Error fetching options for {ticker_symbol}: {e}')
    st.stop()

exp_dates = [pd.Timestamp(exp) for exp in expirations if pd.Timestamp(exp) > today + timedelta(days=7)]

if not exp_dates:
    st.error(f'No available option expiration dates for {ticker_symbol}.')
else:
    option_call_data = []
    option_put_data = []

    for exp_date in exp_dates:
        try:
            opt_chain = ticker.option_chain(exp_date.strftime('%Y-%m-%d'))
            calls = opt_chain.calls
            puts = opt_chain.puts
        except Exception as e:
            st.warning(f'Failed to fetch option chain for {exp_date.date()}: {e}')
            continue

        calls = calls[(calls['bid'] > 0) & (calls['ask'] > 0)]
        puts = puts[(puts['bid'] > 0) & (puts['ask'] > 0)]

        for index, row in calls.iterrows():
            strike = row['strike']
            bid = row['bid']
            ask = row['ask']
            mid_price = (bid + ask) / 2

            option_call_data.append({
                'expirationDate': exp_date,
                'strike': strike,
                'bid': bid,
                'ask': ask,
                'mid': mid_price
            })
            
            for index, row in puts.iterrows():
                strike = row['strike']
                bid = row['bid']
                ask = row['ask']
                mid_price = (bid + ask) / 2

                option_put_data.append({
                    'expirationDate': exp_date,
                    'strike': strike,
                    'bid': bid,
                    'ask': ask,
                    'mid': mid_price
                })

    if not option_call_data:
        st.error('No option data available after filtering.')
    else:
        call_options_df = pd.DataFrame(option_call_data)
        put_options_df = pd.DataFrame(option_put_data)

        try:
            spot_history = ticker.history(period='5d')
            if spot_history.empty:
                st.error(f'Failed to retrieve spot price data for {ticker_symbol}.')
                st.stop()
            else:
                spot_price = spot_history['Close'].iloc[-1]
        except Exception as e:
            st.error(f'An error occurred while fetching spot price data: {e}')
            st.stop()

        call_options_df['daysToExpiration'] = (call_options_df['expirationDate'] - today).dt.days
        call_options_df['timeToExpiration'] = call_options_df['daysToExpiration'] / 365
        
        put_options_df['daysToExpiration'] = (put_options_df['expirationDate'] - today).dt.days
        put_options_df['timeToExpiration'] = put_options_df['daysToExpiration'] / 365

        call_options_df = call_options_df[
            (call_options_df['strike'] >= spot_price * (min_strike_pct / 100)) &
            (call_options_df['strike'] <= spot_price * (max_strike_pct / 100))
        ]
        
        put_options_df = put_options_df[
            (put_options_df['strike'] >= spot_price * (min_strike_pct / 100)) &
            (put_options_df['strike'] <= spot_price * (max_strike_pct / 100))
        ]

        call_options_df.reset_index(drop=True, inplace=True)
        put_options_df.reset_index(drop=True, inplace=True)

        with st.spinner('Calculating implied volatility...'):
            options_df['impliedVolatility'] = options_df.apply(
                lambda row: implied_volatility(
                    price=row['mid'],
                    S=spot_price,
                    K=row['strike'],
                    T=row['timeToExpiration'],
                    r=risk_free_rate,
                    q=dividend_yield
                ), axis=1
            )

        options_df.dropna(subset=['impliedVolatility'], inplace=True)

        options_df['impliedVolatility'] *= 100

        options_df.sort_values('strike', inplace=True)

        options_df['moneyness'] = options_df['strike'] / spot_price

        if y_axis_option == 'Strike Price ($)':
            Y = options_df['strike'].values
            y_label = 'Strike Price ($)'
        else:
            Y = options_df['moneyness'].values
            y_label = 'Moneyness (Strike / Spot)'

        X = options_df['timeToExpiration'].values
        Z = options_df['impliedVolatility'].values

        ti = np.linspace(X.min(), X.max(), 50)
        ki = np.linspace(Y.min(), Y.max(), 50)
        T, K = np.meshgrid(ti, ki)

        Zi = griddata((X, Y), Z, (T, K), method='linear')

        Zi = np.ma.array(Zi, mask=np.isnan(Zi))

        fig = go.Figure(data=[go.Surface(
            x=T, y=K, z=Zi,
            colorscale='Viridis',
            colorbar_title='Implied Volatility (%)'
        )])

        fig.update_layout(
            title=f'Implied Volatility Surface for {ticker_symbol} Options',
            scene=dict(
                xaxis_title='Time to Expiration (years)',
                yaxis_title=y_label,
                zaxis_title='Implied Volatility (%)'
            ),
            autosize=False,
            width=900,
            height=800,
            margin=dict(l=65, r=50, b=65, t=90)
        )

        st.plotly_chart(fig)
