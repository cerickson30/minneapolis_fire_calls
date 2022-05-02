import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiPolygon, LineString, Polygon
from datetime import date
import folium

import streamlit as st
from streamlit_folium import st_folium
from htbuilder import HtmlElement, div, ul, li, br, hr, a, p, img, styles, classes, fonts
from htbuilder.units import percent, px
from htbuilder.funcs import rgba, rgb

st.set_page_config(
    page_title='Minneapolis Fire Calls',
    layout="wide",
    initial_sidebar_state="auto",
    menu_items=None)


@st.experimental_memo
# To fix intersecting shapes
def fix_geometry_collection(geom):
    if geom.geom_type == 'GeometryCollection':
        multi_list = []

        for thing in geom:
            if thing.geom_type == 'Polygon':
                multi_list.append(thing)

        return MultiPolygon(multi_list)
    else:
        return geom


@st.experimental_singleton
# Get and preprocess data
def load_data():
    fires = pd.read_csv('combined_fires_for_app.csv')
    fires['alarm_date'] = pd.to_datetime(fires['alarm_date'])
    fires = gpd.GeoDataFrame(fires, geometry=gpd.points_from_xy(fires.longitude, fires.latitude), crs='EPSG:4326')

    districts = gpd.read_file('Fire_Districts.geojson')
    districts = districts.drop(['SHAPE_Length', 'SHAPE_Area'], axis=1).rename(columns={'DISTRICT':'District'})
    station_areas = gpd.read_file('Fire_Stations_Areas.geojson')
    station_areas = station_areas.rename(columns={'STATION':'Station'})[['Station', 'geometry']]
    station_districts = gpd.overlay(station_areas, districts)

    nhoods = gpd.read_file('Minneapolis_Neighborhoods.geojson')
    nhoods = nhoods.rename(columns={'SYMBOL_NAM':'symbol_name', 'BDNAME':'nhood', 'BDNUM':'BDnum'})[['symbol_name', 'nhood', 'BDnum', 'geometry']]
    nhood_districts = gpd.overlay(nhoods, station_districts, keep_geom_type=False)
    nhood_districts['geometry'] = nhood_districts.geometry.apply(fix_geometry_collection)

    return fires, districts, station_districts, nhood_districts


fires, districts, station_districts, nhood_districts = load_data()


# Functions
# Filter data for date range
def filter_fires(fires_gdf, min_date, max_date):
    date_mask = (min_date <= fires_gdf.alarm_date.dt.date) & (fires_gdf.alarm_date.dt.date <= max_date)

    return fires_gdf.loc[date_mask]

# Calculate number of fires within each area
def get_counts(fires_gdf, areas, area_type='District'):
    gdf = gpd.sjoin(areas, fires_gdf)

    counts = gdf.groupby(area_type)[area_type].count()
    counts = pd.DataFrame(counts).rename(columns={area_type:'num_of_fires'}).reset_index()
    return counts

def get_point(geometry):
    if geometry.geom_type == 'Polygon':
        return LineString(list(geometry.exterior.coords[0:2]))
    if geometry.geom_type == 'MultiPolygon':
        return LineString(list(Polygon(geometry.geoms[0]).exterior.coords[0:2]))
    return geometry

def map_fire_counts(fires_gdf, areas, area_type='District'):
    areas_with_counts = areas.merge(get_counts(fires_gdf, areas, area_type), on=area_type)

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

    if area_type == 'nhood':
        merged_data = areas.overlay(fires_gdf, keep_geom_type=False)
        mask = [nhood not in merged_data.nhood.unique() for nhood in nhood_districts.nhood.unique()]
        missing_nhoods = nhood_districts.nhood.unique()[mask]
        if len(missing_nhoods) != 0:
            mask = nhood_districts.nhood.apply(lambda x: x in missing_nhoods)
            areas_with_counts = pd.concat([areas_with_counts, nhood_districts.loc[mask]])
            areas_with_counts['num_of_fires'] = areas_with_counts.num_of_fires.fillna(0)
            
    areas = folium.GeoJson(
        areas_with_counts,
        style_function = lambda feature: {
            'fillOpacity': 0,
            'color': 'black',
            'weight': 1
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


def map_fire_locations(fires_gdf):
    minneapolis_boundary = gpd.read_file('Minneapolis_City_boundary.geojson')

    m = folium.Map(location=[44.9772995, -93.2654692], zoom_start=12, prefer_canvas=True)

    boundary = folium.GeoJson(
        minneapolis_boundary,
        style_function = lambda feature: {
            'fillOpacity': 0,
            'color': 'black',
            'weight': 2
    }
    )
    boundary.add_to(m)

    for ix, row in fires_gdf.loc[~fires_gdf.latitude.isna()].iterrows():
        folium.CircleMarker(location = [row['latitude'], row['longitude']], radius=1.5, color='red', opacity=0.6).add_to(m)

    return m




# Streamlit stuff
st.title('Minneapolis Fire Calls')

years = sorted(fires['alarm_date'].dt.year.unique(), reverse=True)
year_choice = st.sidebar.selectbox('Select a year:', years)

left_date = fires.loc[fires.alarm_date.dt.year == year_choice].alarm_date.min().date()
right_date = fires.loc[fires.alarm_date.dt.year == year_choice].alarm_date.max().date()
min_date, max_date = st.sidebar.slider('Select a date range:', left_date, right_date, value=(left_date, right_date), format='MMM D')

chart_choice = st.sidebar.radio('', ['Fire Locations', 'Fires by District', 'Fires by Fire Station', 'Fires by Neighborhood'])

filtered_fires = filter_fires(fires, min_date, max_date)
num_fires = len(filtered_fires)

if min_date == max_date:
    date_str = min_date.strftime('%B %d, %Y')
    st.markdown(f'#### The Minneapolis Fire Department responded to {num_fires} calls with confirmed fires on {date_str}.')
else:
    min_date_str = min_date.strftime('%B %d, %Y')
    max_date_str = max_date.strftime('%B %d, %Y')
    st.markdown(f'#### The Minneapolis Fire Department responded to {num_fires} calls with confirmed fires between {min_date_str} and {max_date_str}.')





if chart_choice == 'Fire Locations':
    m = map_fire_locations(filtered_fires)
    # call to render Folium map in Streamlit
    st_folium(m, width=600, height=735)
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

st.markdown('Data accessed from [Open Data Minneapolis](https://opendata.minneapolismn.gov/) on May 1, 2022.')




# For the custom footer in Streamlit app
def image(src_as_string, **style):
    return img(src=src_as_string, style=styles(**style))


def link(link, text, **style):
    return a(_href=link, _target="_blank", style=styles(**style))(text)


def layout(*args):

    style = """
    <style>
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
    </style>
    """

    style_div = styles(
        left=0,
        bottom=0,
        margin=px(0, 0, 0, 0),
        width=percent(100),
        text_align="center",
        height="60px",
        opacity=0.7,
    )

    style_hr = styles(
    )

    body = p()
    foot = div(style=style_div)(hr(style=style_hr), body)

    st.markdown(style, unsafe_allow_html=True)

    for arg in args:
        if isinstance(arg, str):
            body(arg)
        elif isinstance(arg, HtmlElement):
            body(arg)

    st.markdown(str(foot), unsafe_allow_html=True)


def footer(author_name="Craig Erickson", author_url="https://cerickson30.github.io"):
    myargs = [
        "Made with Python 3.8 ",
        link("https://www.python.org/", image('https://i.imgur.com/ml09ccU.png',
        	width=px(18), height=px(18), margin= "0em")),
        " and Streamlit ",
        link("https://streamlit.io/", image('https://docs.streamlit.io/logo.svg',
        	width=px(24), height=px(25), margin= "0em")),
        " by ",
        link(author_url, author_name, color="#ff0000"),
        br(),
    ]
    layout(*myargs)


footer()