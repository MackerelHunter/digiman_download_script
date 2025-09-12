import pathlib as pl
from functools import partial
import rasterio as rio
import numpy as np
from matplotlib import pyplot as plt
from omnicloudmask import (
    predict_from_load_func,
    load_s2,
)
from s2dl import fetch_single_sentinel_product

import omnicloudmask
omnicloudmask.__version__

exp_path = pl.Path(r"M:\IT-Projekte\digiman local\digiman_data\OCM Experimente")
test_data_dir = pl.Path.cwd() / "Sentinel-2 data"
test_data_dir.mkdir(exist_ok=True, parents=True)

product_id = "S2A_MSIL1C_20230304T020441_N0509_R017_T50HNH_20230304T051523"
scene_dir = test_data_dir / (product_id + ".SAFE")
if not (test_data_dir / (product_id + ".SAFE")).exists():
    fetch_single_sentinel_product(
        product_id,
        test_data_dir,
    )
scene_dir