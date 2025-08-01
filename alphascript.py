# using stac api
from pystac_client import Client
import pystac

# pandas for geodata (data analaysis)
import geopandas

# working with raster files
import rioxarray

# interacting via http
import requests

# for the polygon
import shapely

# for useful functions concering paths, files, directories
import os

# filename pattern matching
from glob import glob

# truncating file extensions
from pathlib import Path

# for selecting a file from explorer
from tkinter import filedialog, Tk

def get_shapefile_list(starting_dir):
    shapefiles = []
    pattern = "*.shp"
    for dir,_,_ in os.walk(starting_dir):
        shapefiles.extend(glob(os.path.join(dir, pattern)))
    return shapefiles
    
def choose_directory() -> str:
    rootwindow = Tk()
    rootwindow.wm_attributes('-topmost', True)
    rootwindow.withdraw()
    directory = filedialog.askdirectory(
        title="choose_directory")
    return directory

def get_shapefile_from_explorer():
    """
    opens an explorer window,
    user can select a shape file
    """
    rootwindow = Tk()
    rootwindow.wm_attributes('-topmost', True)
    rootwindow.withdraw()
    shapefile= filedialog.askopenfile(
        filetypes=[("shape files", "*.shp")])
    return shapefile

def extract_4326_polygon(shape_filepath: str) -> shapely.Polygon:
    """
    takes a filepath (to a shape file hopefully)
    and reads it as a geodataframe, then turns the crs of the shape into
    4326 (WGS84, latlong-coordinates) and extracts the polygon from the
    geodataframe
    """
    shape_gdf = geopandas.read_file(shape_filepath)
    shape_gdf = shape_gdf.to_crs(4326)
    polygon = shape_gdf.geometry[0]
    return polygon

def create_item_collection(stac_catalogue: str, collection: str, timeframe: str, polygon: shapely.Polygon) -> pystac.ItemCollection:
    """
    takes a couple of parameters and returns a collection of
    stac items matching them
    """
    client = Client.open(stac_catalogue)
    search = client.search(
        max_items=10000,
        collections = collection,
        intersects = polygon,
        datetime = timeframe
        )
    stac_items = search.item_collection()
    return stac_items

def show_item_assets(item: pystac.Item):
    assets = item.assets
    #assets is an attribute of a stac item and a dictionary of asset objects
    for key, asset in assets.items():
        print(f"{key} : {asset.title}")

def get_thumbnail(item: pystac.Item):
    thumbnail_url = item.assets["thumbnail"].href
    data = requests.get(thumbnail_url).content
    thumbnail = open(item.id + "thumbnail" + ".jpg", "wb")
    # wb = write binary
    thumbnail.write(data)
    thumbnail.close()
    
def get_raster_and_clip_and_download(
        shape_name: str,
        band_name: str, 
        item: pystac.Item, 
        polygon: shapely.Polygon
        ):
    """
    takes a band (e.g. red), a polygon in 4326 coords and a stac item,
    opens a raster of that item's band and clips it to the polygon,
    then saves it as a .jp2-file
    """
    band_url = item.assets[band_name].href
    clipped_raster = rioxarray.open_rasterio(
        band_url, masked=True).rio.clip(
            [polygon], crs="4326", from_disk=True)
    # for efficiency clip must directly take the output of
    # open_rasterio and from_disk must be True,
    # use [polygon] because clip expects a list of geometries
    if os.path.exists("./" + shape_name) == False:
        os.mkdir(shape_name)
    item_time = item.datetime.strftime('%Y%m%d')
    clipped_raster.rio.to_raster("./" + shape_name + "/" +
                                 item_time + "_" +
                                 shape_name + "_" + 
                                 band_name + 
                                 ".jp2")

#%%

def lil_test():
    # parameters
    stac_catalogue = "https://earth-search.aws.element84.com/v1"
    collection = "sentinel-2-l2a"
    timeframe = "2025-04-01/2025-04-15"
    
    # get your example item
    os.chdir(choose_directory())
    shape_filepath = get_shapefile_from_explorer().name
    shape_name = Path(shape_filepath).stem
    
    
    polygon = extract_4326_polygon(shape_filepath)
    matching_items = create_item_collection(
        stac_catalogue, collection, timeframe, polygon)
    item = matching_items[0]
    
    # show me the assets of these items
    show_item_assets(item)
    
    # get a thumbnail
    get_thumbnail(item)
    
    # download a full color image of the area
    get_raster_and_clip_and_download(shape_name, "red", item, polygon)

    
def demo():
    # variables
    stac_catalogue = "https://earth-search.aws.element84.com/v1"
    collection = "sentinel-2-l2a"
    timeframe = "2025-04-01/2025-04-15"
    bands_of_interest = ["red", "green", "blue", "nir"]
    
    # workflow
    starting_dir = choose_directory()
    os.chdir(starting_dir)
    shapefiles = get_shapefile_list(starting_dir)
    for shapefile_path in shapefiles:
        shape_name = Path(shapefile_path).stem
        polygon = extract_4326_polygon(shapefile_path)
        matching_items = create_item_collection(
        stac_catalogue, collection, timeframe, polygon)
        for item in matching_items:
            for band in bands_of_interest:
                get_raster_and_clip_and_download(shape_name, band, item, polygon)

demo()

                
