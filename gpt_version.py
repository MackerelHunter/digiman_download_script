import os
import geopandas as gpd
import rioxarray
from pystac_client import Client
from planetary_computer import sign
from tkinter import Tk, filedialog, Button
from tkcalendar import DateEntry
from tqdm import tqdm
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def select_folder(title="Ordner auswählen"):
    root = Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    folder_selected = filedialog.askdirectory(title=title, parent=root)
    root.destroy()
    return folder_selected

def get_date(title="Datum auswählen"):
    from tkinter import Label
    root = Tk()
    root.title(title)
    root.attributes('-topmost', True)

    Label(root, text=title, font=("Arial", 12)).pack(padx=10, pady=(10, 0))

    cal = DateEntry(root, width=12, background='darkblue',
                    foreground='white', borderwidth=2, date_pattern='dd.mm.yyyy')
    cal.pack(padx=10, pady=10)

    selected_date = []

    def on_ok():
        selected_date.append(cal.get_date())
        root.destroy()

    Button(root, text="OK", command=on_ok).pack(pady=(0, 10))
    root.mainloop()

    return selected_date[0] if selected_date else None

def get_feld_id(gdf, shapefile_path):
    for key in ['fid', 'FeldID', 'ID']:
        if key in gdf.columns:
            val = str(gdf.iloc[0][key])
            return val.replace(" ", "_")
    return os.path.splitext(os.path.basename(shapefile_path))[0]

def create_output_dir(input_root, output_root, shapefile_path, date_obj):
    rel_path = os.path.relpath(shapefile_path, input_root)
    base_path = os.path.splitext(rel_path)[0]
    date_str = date_obj.strftime("%Y%m%d")
    out_dir = os.path.join(output_root, base_path + "-data", date_str)
    return out_dir

def download_band(band_code, href, out_path, gdf, shapefile_path, date_str):
    try:
        print(f"⬇️ {os.path.basename(out_path)}")
        da = rioxarray.open_rasterio(href, masked=True).squeeze()
        clipped = da.rio.clip(gdf.geometry.values, gdf.crs, drop=True)
        clipped.rio.to_raster(out_path)
    except Exception as e:
        print(f"⚠️ Fehler bei {band_code} ({shapefile_path}): {e}")

def download_stac_images(shapefile_path, start_date, end_date, input_root, output_root):
    try:
        gdf = gpd.read_file(shapefile_path).to_crs("EPSG:4326")
    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {shapefile_path}: {e}")
        return

    if len(gdf) != 1:
        print(f"⚠️ Überspringe {shapefile_path}: enthält {len(gdf)} Features (erwartet 1).")
        return
    
    geom = gdf.geometry[0]

    search = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1").search(
        collections=["sentinel-2-l2a"],
        datetime=f"{start_date}/{end_date}",
        intersects=geom
    )

    items = list(search.items())
    if not items:
        print(f"⚠️ Keine Szenen für {shapefile_path} gefunden.")
        return

    print(f"ℹ️ Gefundene Szenen für {os.path.basename(shapefile_path)}:")
    for item in items:
        print(f"   - {item.id} vom {item.datetime.date()}")

    feld_id = get_feld_id(gdf, shapefile_path)
    betrieb = os.path.normpath(shapefile_path).split(os.sep)[len(os.path.normpath(input_root).split(os.sep))]
    betrieb = betrieb.replace(" ", "_")

    for item in tqdm(items, desc=f"{os.path.basename(shapefile_path)}", leave=False):
        signed_item = sign(item)
        date_obj = item.datetime.date()
        date_str = date_obj.strftime("%Y%m%d")

        print(f"⬇️ Download der Szene {item.id} vom {date_obj}")

        out_dir = create_output_dir(input_root, output_root, shapefile_path, date_obj)
        os.makedirs(out_dir, exist_ok=True)

        bands_to_download = {
            key: asset for key, asset in signed_item.assets.items()
            if key.startswith("B") and hasattr(asset, "href")
        }

        planned_downloads = []
        for band_code, asset in bands_to_download.items():
            band_code_lower = band_code.lower()
            tif_name = f"{betrieb}-{feld_id}-{date_str}-{band_code_lower}.tif"
            tif_name = tif_name.replace(" ", "_")
            out_path = os.path.join(out_dir, tif_name)
            if not os.path.exists(out_path):
                planned_downloads.append((band_code_lower, asset.href, out_path))

        if not planned_downloads:
            print("   ✔️ Alle Bänder für diese Szene sind bereits vorhanden, überspringe.")
            continue

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(download_band, band_code, href, out_path, gdf, shapefile_path, date_str)
                for band_code, href, out_path in planned_downloads
            ]
            for future in as_completed(futures):
                pass

def find_shapefiles(folder):
    shapefiles = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".shp"):
                shapefiles.append(os.path.join(root, file))
    return shapefiles

def main():
    print("📂 Bitte Eingabe-Ordner mit Shapefiles wählen...")
    input_root = select_folder("Input-Ordner auswählen")
    if not input_root:
        print("❌ Kein Eingabeordner gewählt, Programm beendet.")
        return

    print("📁 Bitte Ausgabe-Ordner auswählen...")
    output_root = select_folder("Output-Ordner auswählen")
    if not output_root:
        print("❌ Kein Ausgabeordner gewählt, Programm beendet.")
        return

    print("📅 Startdatum auswählen...")
    start_date = get_date("Startdatum")
    print("📅 Enddatum auswählen...")
    end_date = get_date("Enddatum")
    if not start_date or not end_date:
        print("❌ Kein Zeitraum gewählt, Programm beendet.")
        return

    print(f"ℹ️ Ausgewählter Zeitraum: {start_date.strftime('%d.%m.%Y')} bis {end_date.strftime('%d.%m.%Y')}")
    print(f"ℹ️ Eingabeordner: {input_root}")
    print(f"ℹ️ Ausgabeordner: {output_root}")

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    shapefiles = find_shapefiles(input_root)
    print(f"🔍 Gefundene Shapefiles: {len(shapefiles)}")

    for shp in tqdm(shapefiles, desc="🔄 Verarbeitung", unit="Shape"):
        download_stac_images(shp, start_date_str, end_date_str, input_root, output_root)

if __name__ == "__main__":
    main()
