import os
import geopandas as gpd
from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox, DataCollection, bbox_to_dimensions
from tkinter import Tk, filedialog, Button, Label
from tkcalendar import DateEntry
from tqdm import tqdm
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# GUI-Funktionen für Ordner- und Datumsauswahl
def select_folder(title="Ordner auswählen"):
    root = Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    folder_selected = filedialog.askdirectory(title=title, parent=root)
    root.destroy()
    return folder_selected

def get_date(title="Datum auswählen"):
    root = Tk()
    root.title(title)
    root.attributes('-topmost', True)
    Label(root, text=title, font=("Arial", 12)).pack(padx=10, pady=(10, 0))
    cal = DateEntry(root, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='dd.mm.yyyy')
    cal.pack(padx=10, pady=10)
    selected_date = []

    def on_ok():
        selected_date.append(cal.get_date())
        root.destroy()

    Button(root, text="OK", command=on_ok).pack(pady=(0, 10))
    root.mainloop()
    return selected_date[0] if selected_date else None

# Hilfsfunktion: Feld-ID aus Shapefile holen (für Dateinamen)
def get_feld_id(gdf, shapefile_path):
    for key in ['fid', 'FeldID', 'ID']:
        if key in gdf.columns:
            val = str(gdf.iloc[0][key])
            return val.replace(" ", "_")
    return os.path.splitext(os.path.basename(shapefile_path))[0]

# Hilfsfunktion: Ausgabepfad erstellen
def create_output_dir(input_root, output_root, shapefile_path):
    rel_path = os.path.relpath(shapefile_path, input_root)
    base_path = os.path.splitext(rel_path)[0]
    out_dir = os.path.join(output_root, base_path + "-data")
    return out_dir

# Download-Funktion für Sentinel Hub
def download_sentinelhub_bands(shapefile_path, start_date, end_date, input_root, output_root, config):
    try:
            
        gdf = gpd.read_file(shapefile_path).to_crs("EPSG:4326")
    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {shapefile_path}: {e}")
        return

    if len(gdf) != 1:
        print(f"⚠️ Überspringe {shapefile_path}: enthält {len(gdf)} Features (erwartet 1).")
        return

    geom = gdf.geometry[0]
    bbox = BBox(bbox=geom.bounds, crs=CRS.WGS84)

    # Pixelgröße in Metern
    resolution = 10
    size = bbox_to_dimensions(bbox, resolution=resolution)

    feld_id = get_feld_id(gdf, shapefile_path)
    betrieb = os.path.normpath(shapefile_path).split(os.sep)[len(os.path.normpath(input_root).split(os.sep))]
    betrieb = betrieb.replace(" ", "_")

    out_dir = create_output_dir(input_root, output_root, shapefile_path)
    os.makedirs(out_dir, exist_ok=True)

    # Bänder, die heruntergeladen werden sollen
    bands = ["B02", "B03", "B04", "B08"]  # Blau, Grün, Rot, NIR

    # Für jeden Band ein Request erstellen und ausführen
    for band in bands:
        date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        tif_name = f"{betrieb}-{feld_id}-{date_str}-{band.lower()}.tif"
        out_path = os.path.join(out_dir, tif_name)

        if os.path.exists(out_path):
            print(f"✔️ {os.path.basename(out_path)} existiert bereits, überspringe.")
            continue

        evalscript = f"""
        //VERSION=3
        function setup() {{
            return {{
                input: ["{band}"],
                output: {{ bands: 1, sampleType: "UINT16" }}
            }};
        }}

        function evaluatePixel(sample) {{
            return [sample.{band}];
        }}
        """

        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            )],
            responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
            bbox=bbox,
            size=size,
            config=config,
            data_folder=out_dir
        )

        print(f"⬇️ Lade Band {band} für {os.path.basename(shapefile_path)} herunter...")
        try:
            data = request.get_data(save_data=True)  # speichert TIFF in out_dir
        except Exception as e:
            print(f"⚠️ Fehler beim Download von Band {band}: {e}")

    print(f"✅ Download für {os.path.basename(shapefile_path)} abgeschlossen.")

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
    if end_date < start_date:
        print("❌ Enddatum liegt vor Startdatum, Programm beendet.")
        return

    print(f"ℹ️ Zeitraum: {start_date.strftime('%d.%m.%Y')} bis {end_date.strftime('%d.%m.%Y')}")
    print(f"ℹ️ Eingabeordner: {input_root}")
    print(f"ℹ️ Ausgabeordner: {output_root}")

    # Sentinel Hub Config aus Umgebungsvariablen oder config.json laden
    config = SHConfig()
    if not config.sh_client_id or not config.sh_client_secret:
        print("❌ Sentinel Hub Client ID und Secret fehlen. Bitte in config.json oder Umgebungsvariablen hinterlegen.")
        return

    shapefiles = find_shapefiles(input_root)
    print(f"🔍 Gefundene Shapefiles: {len(shapefiles)}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(download_sentinelhub_bands, shp, start_date, end_date, input_root, output_root, config) for shp in shapefiles]
        for future in tqdm(as_completed(futures), total=len(futures), desc="🔄 Bearbeitung"):
            pass

if __name__ == "__main__":
    main()
