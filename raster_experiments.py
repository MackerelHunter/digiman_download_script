### Rasterio-Experimente

import geopandas as gpd
import pathlib as pl
import rasterstats as rs
import time
import rasterio as rio

"""
Pfade auf Laptop
"""
# shapefile_pathstring = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\rasterio_tests\R02_ab_TUM Freising\radarfeld_pixelpolygons.shp"
# shapefile_path = pl.Path(shapefile_pathstring)
# tif_pathstring = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\rasterio_tests\radarfeld_pixelpolygons\2025-06-23\S2A_MSIL2A_20250623T101041_N0511_R022_T32UPU_20250623T135215_B02.tif"
# #tif_pathstring = r"C:\Users\juliu\Daten\IT-Projekte\Digiman\data\rasterio_tests\freising felder geclipped\2025-06-23\S2A_MSIL2A_20250623T101041_N0511_R022_T32UPU_20250623T135215_B02.tif"
# tif_path = pl.Path(tif_pathstring)

"""
Pfade auf PC
"""
shapefile_pathstring = r"M:\IT-Projekte\digiman local\digiman_data\Schlagkonturen\R02_ab_TUM Freising\pixel shapes\tum_freising_süd_pixels.shp"
shapefile_path = pl.Path(shapefile_pathstring)
tif_pathstring = r"M:\IT-Projekte\digiman local\digiman_data\tests zu pixelshapes\pixel shape tifs\tum_freising_süd_pixels\2025-06-23\S2A_MSIL2A_20250623T101041_N0511_R022_T32UPU_20250623T135215_B02.tif"
tif_path = pl.Path(tif_pathstring)
tif_12_canal_pathstring = r"M:\IT-Projekte\digiman local\digiman_data\tests zu pixelshapes\pixel shape tifs\tum_freising_süd_pixels_12_canal\2025-06-21\226471cb9d74222958ed9927340dae6e\response.tiff"
tif_12canal_path = pl.Path(tif_12_canal_pathstring)


pixelpolygon_gdf = gpd.read_file(shapefile_path)

"""
Mit rasterstats: 51s für Freising Süd
"""
# start = time.time()
# test = rs.zonal_stats(pixelpolygon_gdf, tif_path)
# end = time.time()
# rasterstats_time = (end - start)
# print(rasterstats_time)

"""
Mit rasterio.sample: 3s für Freising Süd?
Kontrolle: Ist der gleiche Wert wie in QGIS an der x,y-Position
"""
start = time.time()
rio_raster = rio.open(tif_12canal_path)
pixelpolygon_gdf["B01"] = None
for i in range(len(pixelpolygon_gdf.geometry)):
    pixelpolygon = pixelpolygon_gdf.geometry[i]
    x, y = pixelpolygon.centroid.x, pixelpolygon.centroid.y
    row, col = rio_raster.index(x, y)
    for band in range(1):
        value = rio_raster.read()[band, row, col]
        print(f"x: {x}, y: {y}, value of band {i+1}: {value}")
        pixelpolygon_gdf.B01[i] = value
    
print(time.time() - start)

test2 = rio_raster.read(2)
