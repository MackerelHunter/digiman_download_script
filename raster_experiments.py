### Rasterio-Experimente

import geopandas as gpd
import pathlib as pl
import rasterstats as rs
import time

shapefile_pathstring = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\rasterio_tests\R02_ab_TUM Freising\radarfeld_pixelpolygons.shp"
shapefile_path = pl.Path(shapefile_pathstring)
tif_pathstring = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\rasterio_tests\radarfeld_pixelpolygons\2025-06-23\S2A_MSIL2A_20250623T101041_N0511_R022_T32UPU_20250623T135215_B02.tif"
#tif_pathstring = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\rasterio_tests\freising felder geclipped\2025-06-23\S2A_MSIL2A_20250623T101041_N0511_R022_T32UPU_20250623T135215_B02.tif"
tif_path = pl.Path(tif_pathstring)

pixelpolygon_gdf = gpd.read_file(shapefile_path)

start = time.time()
test = rs.zonal_stats(pixelpolygon_gdf, tif_path,stats="mean")
end = time.time()
rasterstats_time = (end - start)
print(rasterstats_time)
