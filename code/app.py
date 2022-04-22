import streamlit as st
import pandas as pd
import os
import re



# Get the data
fires = pd.DataFrame()
pathname = '../data'

for filename in os.listdir(pathname):
    if os.path.isfile(os.path.join(pathname, filename)) and 'Confirmed' in filename:
        if os.path.splitext(filename)[1] == '.csv':
            fires = pd.concat([fires, pd.read_csv(os.path.join(pathname, filename))], ignore_index=True)

fires = fires.drop('OBJECTID', axis=1).drop_duplicates()


# Some simple cleaning
def strip_time(entry):
    m = re.match('(\d{4}/\d{2}/\d{2})', entry)
    return m.group(1)

fires['confirmed_fire'] = True
fires['alarm_datetime'] = fires.apply(lambda row: strip_time(row.alm_date) + ' ' + row.alm_time, axis=1)
fires['clear_datetime'] = fires.apply(lambda row: strip_time(row.clr_date) + ' ' + row.clr_time, axis=1)

fires['alarm_datetime'] = pd.to_datetime(fires['alarm_datetime'])
fires['clear_datetime'] = pd.to_datetime(fires['clear_datetime'])

fires = fires.drop(['alm_time', 'clr_time'], axis=1)

years = fires['alarm_datetime'].dt.year.unique()
year_choice = st.sidebar.selectbox('', years)
df = fires.loc[fires.alarm_datetime.dt.year == year_choice]


st.markdown('# Minneapolis Fire Calls')
st.markdown(f'Fire calls responded to by the Minneapolis Fire Department with a confirmed fire in year {year_choice}')

st.map(df)

st.markdown('Data from accessed from [Open Data Minneapolis](https://opendata.minneapolismn.gov/) on April 22, 2022.')