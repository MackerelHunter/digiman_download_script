#%% imports

from pystac_client import Client
import geopandas
import rioxarray
import os
from shapely.geometry import shape
from shapely.geometry import Point
from shapely.ops import transform
import shapely
import json
import utm
import requests

# for selecting a file from explorer
from PIL import ImageTk, Image
from tkinter import *
from tkinter import filedialog, Tk
#%% taking care of the shape file

# read shape file (crs is automatically detected)
# open an explorer dialog
rootwindow = Tk()
rootwindow.wm_attributes('-topmost', True)
rootwindow.withdraw()
shapefile_path = filedialog.askopenfile(
    initialdir="~",
    title="open your shapefile"
    )
hausfeld_shapefile = geopandas.read_file(shapefile_path.name)

# change crs to 4326 (wgs84), the only accepted by client search
hausfeld_in_4326 = hausfeld_shapefile.to_crs(4326)

# my polygon
hausfeld_polygon = hausfeld_in_4326.geometry[0]

# method to flip x and y coordinates
def flip(x, y):
    return y, x

# shapely transform method applying flip to my polygon
# hausfeld_polygon = transform(flip, hausfeld_polygon)
print(hausfeld_polygon)

#%% stac client action

stac_catalogue = "https://earth-search.aws.element84.com/v1"
collection = "sentinel-2-l2a"
timeframe = "2025-04/2025-05"

# new stac clien initialized
client = Client.open(stac_catalogue)

# creating search, expecting polygon with wgs84 coordinates
# returns Item_Search instance, a deferred query to a stac search endpoint
# only once a method is called to iterate through the resulting items is the
# api call made
search = client.search(
    max_items=10,
    collections = collection,
    intersects = hausfeld_polygon,
    datetime = timeframe
    )

# returns number of matches, does not work with all apis
print(search.matched())

# makes the api call and returns an iterable ItemCollection instance
# containing stac items
stac_items = search.item_collection()

#%% lets check the assets

# assets is an attribute of a stac item and a dictionary of asset objects
# lets create a dictionary of the first stac item
# also show me the type of assets we have
assets_n1 = stac_items[1].assets
for key, asset in assets_n1.items():
    print(f"{key} : {asset.title}")


#%% download a thumbnail

thumbnail_url = (assets_n1["thumbnail"].href)

# download the data via the requests package
data = requests.get(thumbnail_url).content

# we create a new image with that name and wb = write binary to it
image = open('test.jpg', 'wb')
image.write(data)
image.close()

#%% download rgb bands

# get the bands urls
# see the assets name from above
red_href = assets_n1["red"].href
green_href = assets_n1["green"].href
blue_href = assets_n1["blue"].href

# get the rasters and directly clip them to save ram
# use [hausfeld_polygon] because clip expects a list
# of geometries
red_hausfeld = rioxarray.open_rasterio(red_href, masked=True).rio.clip([hausfeld_polygon], from_disk=True)

green = rioxarray.open_rasterio(green_href)
green.rio.to_raster("green.jp2")
blue = rioxarray.open_rasterio(blue_href)



visual = rioxarray.open_rasterio(assets_n1["visual"].href)
visual_to_shape = visual.rio.clip([hausfeld_polygon], crs="4326")
visual_to_shape.rio.to_raster("visual_to_shape.jp2")

# test-polygon (trying to find something that overlaps)
visual.rio.crs
