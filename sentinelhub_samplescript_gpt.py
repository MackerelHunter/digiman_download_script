import geopandas as gpd
import sentinelhub as sh
import pathlib as pl
import shutil
import tarfile
import numpy as np

### Helper functions
"""
A callable for the bbox edge rounding.
"""
def round_coordinates(x: float, y: float):
    x = np.round(x, -1)
    y = np.round(y, -1)
    return x, y

### Variables
"""
Set example files for testing purposes,
timeframe, bands of interest, output folder, etc.
You should paste the filepaths after the r, which denotes
a raw string (helps with the backslashes). Resolution
should be 10 (m/px), which is the highest available.
"""
INPUT_FOLDER = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\test_input"
OUTPUT_FOLDER = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\test_output"
START_DATE = '2025-06-23'
END_DATE = '2025-06-23'
RESOLUTION = 10  # Meter pro Pixel
BAND_NAMES = ["B02", "B03", "B04"]

"""
Create Path-Objects.
Find all shapefiles within the starting directory and create a list of them
"""
inputfolder_path = pl.Path(INPUT_FOLDER)
outputfolder_path = pl.Path(OUTPUT_FOLDER)
shapefile_list = inputfolder_path.glob("*/*.shp")

### SentinelHub-Setup
"""
Takes authentification details for sentinhelhub
from the environmental
variables SH_CLIENT_ID and SH_CLIENT_SECRET
"""
config = sh.SHConfig()

"""
Evalscript for sentinelhub request, specifying input
and output and function to be applied. Is given an 
array of strings specifying the bands we want (not arbitrary).
Output an array of javascript objects (denoted by {}),
specifying AT LEAST the number of bands.
evaluatePixel takes as a parameter a single pixel from our scene
(handled by the POST-Request) and MUST return an array of values,
not objects.
"""
evalscript = """
function setup() {
    return {
        input: [{
            bands: ["B02","B03","B04"],
            units: "DN"
        }],
        output: [
            {id : "B02", bands : 1, sampleType: "UINT16"},
            {id : "B03", bands : 1, sampleType: "UINT16"},
            {id : "B04", bands : 1, sampleType: "UINT16"}
            ]
    };
}
function evaluatePixel(sample) {
    return {
        B02 : [sample.B02],
        B03 : [sample.B03],
        B04 : [sample.B04]
        }
}
"""

"""
responses is an array of strings to be used in the
POST-Request, specifying the name and filetype of the
responses. the name must match an id from the output
section of the evalscript. The output_response function
generates such a string for us. We don't have to use all
outputs from the evalscript. Thus the evalscript can provide
all bands, but we could create a separate response for each one.
"""
responses = [
    sh.SentinelHubRequest.output_response("B02", sh.MimeType.TIFF),
    sh.SentinelHubRequest.output_response("B03", sh.MimeType.TIFF),
    sh.SentinelHubRequest.output_response("B04", sh.MimeType.TIFF),
    ]

### Iterate over found shapefiles
for shapefile_path in shapefile_list:
    
    ### Get coordinates etc.
    """
    Read shapefile via geopandas and turn it into geodataframe.
    The gdf contains all the information from the shapefile, including
    field id etc. Extracts the geometry (coordinate vertices) from the 
    gdf. union_all() can create a bounding box (coordinates for rectangle
    containing shape) for multipolygons (in case of multiple areas
    within a shape). We must turn it into a sh.BBox for the POST-Request.
    Create a buffer around the bbox of 10%. Round the buffered coordinates
    to get pixel size of exactly 10m x 10m.
    bbox_to_dimensions generates an appriate pixel width and height for
    our output according to our specified resolution (seemingly higher
    resolution than 10m/px from copernicus browser is due to interpolation).
    We cannot find out whether the coordinate system is LongLat or UTM,
    so we assume that the gdf has a coordinate system set.
    """
    gdf = gpd.read_file(shapefile_path)
    if (gdf.crs.to_epsg() == 4326):
        crs_code = gdf.estimate_utm_crs().to_epsg()
        gdf = gdf.to_crs(crs=crs_code)
    else:
        crs_code = gdf.crs.to_epsg()
    geometry = gdf.geometry.union_all()
    bbox_unrounded = sh.BBox(bbox=geometry.bounds, crs=sh.CRS(crs_code))
    bbox = bbox_unrounded.apply(round_coordinates)
    print(shapefile_path.name, " : ", bbox.__str__())
    size = sh.bbox_to_dimensions(bbox, RESOLUTION)
    
    ### Create directories and get names
    """
    Get the relative path of the shapefile starting from the
    input folder, including the file name with extension.
    Make an output folder path out of the output base folder,
    the parent folder of the shapefile and the shapefile name.
    Create the necessary directories.
    
    If shapefiles are already in subdirectories named after them, 
    this will create another subdirectory of the same name,
    e.g. "lager/lager/2025-04-31/.."
    """
    shapefile_relpath= shapefile_path.relative_to(inputfolder_path)
    shapefile_folder_path = outputfolder_path.joinpath(
        shapefile_relpath.parent, shapefile_relpath.stem)
    shapefile_folder_path.mkdir(parents = True, exist_ok = True)
    """
    Get the name of the greatest parent folder containing the shapefile,
    which is hopefully named after the betrieb. This is later used for
    renaming the output
    """
    shapefile_betrieb_name = shapefile_relpath.parts[0]
    
    ### Find matching scenes
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
    Control output
    """
    print(shapefile_path.name, ": Matches für ", START_DATE, " bis ",
          END_DATE, " : ", len(list(matching_scenes)))
    for scene in matching_scenes:
        print(scene["id"])
    
    """
    Keep track of scenes already downloaded to avoid duplicates,
    where a shape is within two different, overlapping tiles,
    leading to two scenes for a single day.
    """
    downloaded_scene_dates = []
    ### Iterate over scenes
    for scene in matching_scenes:
        """
        Trim the last 10 characters from the
        datetime string, which contain the time.
        id could be used later.
        """
        date_str = scene["properties"]["datetime"][:10]
        scene_id = scene["id"]
        
        if date_str not in downloaded_scene_dates:
            """
            Create folder for that date as subdirectory for the betrieb
            """
            datefolder_path = pl.Path(shapefile_folder_path).joinpath(date_str)
            datefolder_path.mkdir(parents = True, exist_ok = True)
            
            ### Create SentinelHub request
            """
            The Request is fed the evalscript and the input_data string.
            We provide the previously extracted date as the start and finish
            of our time_intervall, so data from the whole day is considered.
            We choose mostRecent as our mosaicking_order, incase the bbox
            overlaps multiple tiles with data from different times.
            """
            request = sh.SentinelHubRequest(
                evalscript=evalscript,
                input_data=[
                    sh.SentinelHubRequest.input_data(
                        data_collection=sh.DataCollection.SENTINEL2_L2A,
                        time_interval=(date_str, date_str),
                        mosaicking_order="mostRecent"
                    )
                ],
                responses=responses,
                bbox=bbox,
                size=size,
                config=config,
                data_folder=datefolder_path
            )
            request.save_data()
            
            """
            Move the response.tar one level up, out of the folder named
            after the hash (works via rename()). Delete the hash named folder.
            Extract the tar. Delete the tar.
            """
            response_tar_path = next(datefolder_path.rglob("*.tar"))
            tmp_response_tar_path = response_tar_path
            new_tar_path = datefolder_path.joinpath(response_tar_path.name)
            response_tar_path.rename(new_tar_path)
            
            shutil.rmtree(tmp_response_tar_path.parent)
            with tarfile.open(new_tar_path, "r") as tar:
                tar.extractall(datefolder_path)
            new_tar_path.unlink()
            """
            Rename the tifs according to the scene id and the band id
            """
            print("test")
            tif_paths = datefolder_path.glob("*.tif")
            for tif_path in tif_paths:
                new_filename = (scene_id + "_" + tif_path.name)
                new_path = tif_path.parent.joinpath(new_filename)
                tif_path.rename(new_path)
        """
        Add this date to the already downloaded dates to avoid
        downloading from more than one scene for a single day
        """
        downloaded_scene_dates.append(date_str)
            
