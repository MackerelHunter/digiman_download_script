import geopandas as gpd
import sentinelhub as sh
import rasterio
import numpy as np
import os

### Variables
"""
Set example files for testing purposes,
timeframe, bands of interest, output folder, etc.
"""
SHAPEFILE_PATH = r"M:\IT-Projekte\digiman local\digiman_data\test_shapes\Bergfeld_Schlagkontur\Schlagkontur-Klein.shp"
EXAMPLE_SHP_MANY_FIELDS = r"M:\IT-Projekte\digiman local\digiman_data\test_shapes\Roggenstein_komplett\Roggenstein_komplett.shp"
OUTPUT_FOLDER = r"M:\IT-Projekte\digiman local\digiman_data\test_output"
START_DATE = '2025-07-13'
END_DATE = '2025-07-14'
RESOLUTION = 7  # Meter pro Pixel
BAND_NAMES = ["B01","B02","B03","B04","B05","B06","B07","B08","B8A","B09","B11","B12"]
INPUT_CRS = sh.CRS.UTM_32N

### load shapefile
"""
Read shapefile via geopandas and turn it into geodataframe.
The gdf contains all the information from the shapefile, including
field id etc. Extracts the geometry (coordinate vertices) from the 
gdf. union_all() can create a bounding box (coordinates for rectangle
containing shape) for multipolygons (in case of multiple areas
within a shape). We must turn it into a sh.BBox to use sh.geo_utils,
in case we want to change the coordinate system before the request.
"""
gdf = gpd.read_file(SHAPEFILE_PATH)
gdf = gdf.to_crs(crs=INPUT_CRS.value) # value contains str
geometry = gdf.geometry.union_all()
bbox = sh.BBox(bbox=geometry.bounds, crs=INPUT_CRS)
size = sh.bbox_to_dimensions(bbox, RESOLUTION)

### SentinelHub-Setup
"""
Takes authentification details for sentinhelhub
from the environmental
variables SH_CLIENT_ID and SH_CLIENT_SECRET
"""
config = sh.SHConfig()

### catalog search
""" 
Create iterator containing scenes in the
l2a collection from the 
sentinelhub stac matching the desired timeframe
and location, excluding unnecessary information
"""
catalog = sh.SentinelHubCatalog(config=config)
matching_scenes = catalog.search(
    sh.DataCollection.SENTINEL2_L2A,
    bbox=bbox,
    time=(START_DATE, END_DATE),
    fields={"include": ["id", "properties.datetime"], "exclude": []}
)


"""
Evalscript for sentinelhub request, specifying input
and output and function to be applied
"""
evalscript = """
function setup() {
    return {
        input: [
            "B01","B02","B03","B04","B05","B06","B07","B08","B8A","B09","B11","B12"
        ],
        output: { bands: 13 }
    };
}
function evaluatePixel(sample) {
    return [
        sample.B01, sample.B02, sample.B03, sample.B04, sample.B05, sample.B06, sample.B07,
        sample.B08, sample.B8A, sample.B09, sample.B11, sample.B12
    ];
}
"""
#%% kurze experimente für iterator



#%%
"""
We iterate over every scene, identified by the
scene id.
"""
for scene in matching_scenes:
    """
    We cut off the last 10 characters from the
    datetime string, which contain the time.
    """
    time_str = scene["properties"]["datetime"][:10]
    id = scene["id"]
    
    """
    The Request is fed the evalscript and the input_data string.
    We provide the previously extracted date as the start and finish
    of our time_intervall, so data from the whole day is considered.
    We choose mostRecent as our mosaicking_order, incase the bbox
    overlaps multiple tiles with data from different times
    """

    request = sh.SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            sh.SentinelHubRequest.input_data(
                data_collection=sh.DataCollection.SENTINEL2_L2A,
                time_interval=(time_str, time_str),
                mosaicking_order="mostRecent"
            )
        ],
        responses=[sh.SentinelHubRequest.output_response("default", sh.MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config,
        data_folder=OUTPUT_FOLDER
    )
    
    request.get_data(save_data=True)


#%%
    data_list = request.get_data()
    img = data_list[0]  # Shape: (H, W, Bands)
    height, width, bands = img.shape

    geotransform = bbox.get_transform(width, height)
    crs = bbox.crs.pyproj_crs()

    scene_folder = os.path.join(OUTPUT_FOLDER, time_str)
    os.makedirs(scene_folder, exist_ok=True)

    for band_idx, band_name in enumerate(BAND_NAMES):
        band_data = img[:, :, band_idx].astype(np.float32)

        out_fp = os.path.join(scene_folder, f"{band_name}.tif")

        meta = {
            'driver': 'GTiff',
            'height': height,
            'width': width,
            'count': 1,
            'dtype': 'float32',
            'crs': crs,
            'transform': geotransform
        }

        with rasterio.open(out_fp, 'w', **meta) as dst:
            dst.write(band_data, 1)
