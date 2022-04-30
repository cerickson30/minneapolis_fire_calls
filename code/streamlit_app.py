import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiPolygon, LineString, Polygon
from datetime import date, datetime
import folium
from streamlit_folium import st_folium



# Get and preprocess data
cols_to_drop = ['number', 'street', 'st_type', 'st_suffix', 'addr_2', 'apt_room', 'xst_prefix', 'xstreet', 'xst_type', 'xst_suffix']
cols_to_drop.extend(['inci_no', 'inci_type', 'descript', 'alarms', 'confirmed_fire', 'alm_date', 'clr_date', 'complete', 'station'])
fires = pd.read_csv('../data/confirmed_fires.csv').drop(cols_to_drop, axis=1)

fires['alarm_datetime'] = pd.to_datetime(fires['alarm_datetime'])
fires['clear_datetime'] = pd.to_datetime(fires['clear_datetime'])

fires_gdf = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs='EPSG:4326')
fires_gdf.drop(['latitude', 'longitude'], axis=1, inplace=True)


# Shapes
def fix_geometry_collection(geom):
    if geom.geom_type == 'GeometryCollection':
        multi_list = []

        for thing in geom:
            if thing.geom_type == 'Polygon':
                multi_list.append(thing)

        return MultiPolygon(multi_list)
    else:
        return geom



districts = gpd.read_file('../data/Fire_Districts.geojson')
districts = districts.drop(['SHAPE_Length', 'SHAPE_Area'], axis=1).rename(columns={'DISTRICT':'District'})
station_areas = gpd.read_file('../data/Fire_Stations_Areas.geojson')
station_areas = station_areas.rename(columns={'STATION':'Station'})[['Station', 'geometry']]
station_districts = gpd.overlay(station_areas, districts)

nhoods = gpd.read_file('../data/Minneapolis_Neighborhoods.geojson')
nhoods = nhoods.rename(columns={'SYMBOL_NAM':'symbol_name', 'BDNAME':'nhood', 'BDNUM':'BDnum'})[['symbol_name', 'nhood', 'BDnum', 'geometry']]
nhood_districts = gpd.overlay(nhoods, station_districts, keep_geom_type=False)
nhood_districts['geometry'] = nhood_districts.geometry.apply(fix_geometry_collection)

# Functions

def filter_fires(df, min_date, max_date):
    df['alarm_datetime'] = pd.to_datetime(df['alarm_datetime'])
    df['clear_datetime'] = pd.to_datetime(df['clear_datetime'])

    date_mask = (min_date <= df.alarm_datetime.dt.date) & (df.alarm_datetime.dt.date <= max_date)

    return df.loc[date_mask]

def get_counts(filtered_fires, areas, area_type='District'):
    gdf = gpd.sjoin(areas, filtered_fires)

    counts = gdf.groupby(area_type)[area_type].count()
    counts = pd.DataFrame(counts).rename(columns={area_type:'num_of_fires'}).reset_index()
    return counts

def get_point(geometry):
    if geometry.geom_type == 'Polygon':
        return LineString(list(geometry.exterior.coords[0:2]))
    if geometry.geom_type == 'MultiPolygon':
        return LineString(list(Polygon(geometry.geoms[0]).exterior.coords[0:2]))
    return geometry

def map_fire_counts(filtered_fires, areas, area_type='District'):
    areas_with_counts = areas.merge(get_counts(filtered_fires, areas, area_type), on=area_type)

    if area_type == 'District':
        tooltip_fields = ['District', 'num_of_fires']
        tooltip_aliases = ['District:', 'Number of Fires:']
    elif area_type == 'Station':
        tooltip_fields = ['Station', 'District', 'num_of_fires']
        tooltip_aliases = ['Station:', 'District:', 'Number of Fires:']
    elif area_type == 'nhood':
        tooltip_fields = ['nhood', 'Station', 'District', 'num_of_fires']
        tooltip_aliases = ['Neighborhood:', 'Station:', 'District:', 'Number of Fires:']

    zero_holder = {area_type:'zero_holder',
        'geometry':[get_point(areas_with_counts.geometry.iloc[0])], 
        'num_of_fires':[0]}
    areas_with_counts = pd.concat([areas_with_counts, gpd.GeoDataFrame(zero_holder)], ignore_index=True)

    m = folium.Map(location=[44.9772995, -93.2654692], zoom_start=12)

    folium.Choropleth(
        geo_data = areas_with_counts,
        data = areas_with_counts,
        columns=[area_type, 'num_of_fires'],
        key_on=f'feature.properties.{area_type}',
        fill_color='YlOrRd'
        ).add_to(m)

    areas = folium.GeoJson(
        areas_with_counts,
        style_function = lambda feature: {
            'fillOpacity': 0,
            'weight': 0
        }
        )
    areas.add_child(
        folium.features.GeoJsonTooltip(
            fields = tooltip_fields,
            aliases = tooltip_aliases
        )
    )

    areas.add_to(m)

    return m




# Streamlit stuff

years = sorted(fires['alarm_datetime'].dt.year.unique(), reverse=True)
year_choice = st.sidebar.selectbox('Select a year:', years)

left_date = fires.loc[fires.alarm_datetime.dt.year == year_choice].alarm_datetime.min().date()
right_date = fires.loc[fires.alarm_datetime.dt.year == year_choice].alarm_datetime.max().date()
min_date, max_date = st.sidebar.slider('Select a date range:', left_date, right_date, value=(left_date, right_date), format='MMM D')

chart_choice = st.sidebar.radio('', ['Fire Locations', 'Fires by District', 'Fires by Fire Station', 'Fires by Neighborhood'])

filtered_fires = filter_fires(fires_gdf, min_date, max_date)
num_fires = len(filtered_fires)

st.markdown('# Minneapolis Fire Calls')
if min_date == max_date:
    date_str = min_date.strftime('%B %d, %Y')
    st.markdown(f'#### The Minneapolis Fire Department responded to {num_fires} calls with confirmed fires on {date_str}.')
else:
    min_date_str = min_date.strftime('%B %d, %Y')
    max_date_str = max_date.strftime('%B %d, %Y')
    st.markdown(f'#### The Minneapolis Fire Department responded to {num_fires} calls with confirmed fires between {min_date_str} and {max_date_str}.')





if chart_choice == 'Fire Locations':
    df = filter_fires(fires, min_date, max_date)
    st.map(df.loc[~df.latitude.isna()], width=600, height=735)
elif chart_choice == 'Fires by District':
    m = map_fire_counts(filtered_fires, districts, 'District')
    # call to render Folium map in Streamlit
    st_folium(m, width=600, height=735)
elif chart_choice == 'Fires by Fire Station':
    m = map_fire_counts(filtered_fires, station_districts, 'Station')
    # call to render Folium map in Streamlit
    st_folium(m, width=600, height=735)
elif chart_choice == 'Fires by Neighborhood':
    m = map_fire_counts(filtered_fires, nhood_districts, 'nhood')
    # call to render Folium map in Streamlit
    st_folium(m, width=600, height=735)

st.markdown('Data accessed from [Open Data Minneapolis](https://opendata.minneapolismn.gov/) on April 22, 2022.')