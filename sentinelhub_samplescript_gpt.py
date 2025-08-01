import geopandas as gpd
from sentinelhub import (
    SHConfig, CRS, BBox, bbox_to_dimensions,
    SentinelHubRequest, SentinelHubCatalog,
    DataCollection, MimeType, Geometry
)
import rasterio
import numpy as np
import os

# ==== Konfiguration ====
SHAPEFILE_PATH = r"C:\Users\juliu\Daten\HSWT SHK Leßke\digiman_download_script\test_input\b_TUM Freising\Heindlacker\Heindlacker.shp"
OUTPUT_FOLDER = r"C:\Users\juliu\Daten\HSWT SHK Leßke\digiman_download_script\test_output"
START_DATE = '2024-06-01'
END_DATE = '2024-06-30'
RESOLUTION = 10  # Meter pro Pixel

# ==== Sentinel Hub Setup ====
config = SHConfig()

print("Client ID aus Environment:", config.sh_client_id)
print("Client Secret aus Environment:", config.sh_client_secret)

# ==== Shapefile laden ====
gdf = gpd.read_file(SHAPEFILE_PATH)
geometry = gdf.geometry.unary_union
bbox = BBox(bbox=geometry.bounds, crs=CRS.WGS84)
geom = Geometry(geometry, crs=CRS.WGS84)

# ==== Katalogabfrage ====
catalog = SentinelHubCatalog(config=config)
search_iterator = catalog.search(
    DataCollection.SENTINEL2_L2A,
    bbox=bbox,
    time=(START_DATE, END_DATE),
    fields={"include": ["id", "properties.datetime"], "exclude": []}
)

scenes = list(search_iterator)
print(f"Gefundene Szenen: {len(scenes)}")

# ==== Evalscript (alle Bänder) ====
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

band_names = ["B01","B02","B03","B04","B05","B06","B07","B08","B8A","B09","B11","B12"]

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

for i, scene in enumerate(scenes):
    time_str = scene["properties"]["datetime"][:10]

    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(time_str, time_str),
                mosaicking_order="mostRecent"
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=bbox_to_dimensions(bbox, RESOLUTION),
        config=config
    )

    data_list = request.get_data()
    img = data_list[0]  # Shape: (H, W, Bands)
    height, width, bands = img.shape

    geotransform = bbox.get_transform(width, height)
    crs = bbox.crs.pyproj_crs()

    scene_folder = os.path.join(OUTPUT_FOLDER, time_str)
    os.makedirs(scene_folder, exist_ok=True)

    for band_idx, band_name in enumerate(band_names):
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

    print(f"[{i+1}/{len(scenes)}] Alle Bänder gespeichert für {time_str}")

print("✅ Alle Bilder und Bänder gespeichert.")
