import streamlit as st
import pandas as pd
import os
import re
from datetime import date, datetime



# Get the data
fires = pd.DataFrame()
pathname = '../data'

# for filename in os.listdir(pathname):
#     if os.path.isfile(os.path.join(pathname, filename)) and 'Confirmed' in filename:
#         if os.path.splitext(filename)[1] == '.csv':
#             fires = pd.concat([fires, pd.read_csv(os.path.join(pathname, filename))], ignore_index=True)

# fires = fires.drop('OBJECTID', axis=1).drop_duplicates()

fires = pd.read_csv('../data/confirmed_fires.csv')


# # Some simple cleaning
# def strip_time(entry):
#     m = re.match('(\d{4}/\d{2}/\d{2})', entry)
#     return m.group(1)

# fires['confirmed_fire'] = True
# fires['alarm_datetime'] = fires.apply(lambda row: strip_time(row.alm_date) + ' ' + row.alm_time, axis=1)
# fires['clear_datetime'] = fires.apply(lambda row: strip_time(row.clr_date) + ' ' + row.clr_time, axis=1)

fires['alarm_datetime'] = pd.to_datetime(fires['alarm_datetime'])
fires['clear_datetime'] = pd.to_datetime(fires['clear_datetime'])

# fires = fires.drop(['alm_time', 'clr_time'], axis=1)

years = sorted(fires['alarm_datetime'].dt.year.unique(), reverse=True)
year_choice = st.sidebar.selectbox('Select a year:', years)

min_date = fires.loc[fires.alarm_datetime.dt.year == year_choice].alarm_datetime.min().date()
max_date = fires.loc[fires.alarm_datetime.dt.year == year_choice].alarm_datetime.max().date()
min_date, max_date = st.sidebar.slider('Select a date range:', min_date, max_date, value=(min_date, max_date),
        format='MMM d')

date_mask = (min_date <= fires.alarm_datetime.dt.date) & (fires.alarm_datetime.dt.date <= max_date)
df = fires.loc[date_mask]

num_fires = len(df)

st.markdown('# Minneapolis Fire Calls')
if min_date == max_date:
    date_str = min_date.strftime('%B %d, %Y')
    st.markdown(f'#### The Minneapolis Fire Department responded to {num_fires} calls with confirmed fires on {date_str}.')
else:
    min_date_str = min_date.strftime('%B %d, %Y')
    max_date_str = max_date.strftime('%B %d, %Y')
    st.markdown(f'#### The Minneapolis Fire Department responded to {num_fires} calls with confirmed fires between {min_date_str} and {max_date_str}.')

st.map(df.loc[~df.latitude.isna()])

st.markdown('Data from accessed from [Open Data Minneapolis](https://opendata.minneapolismn.gov/) on April 22, 2022.')