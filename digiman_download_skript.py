import geopandas as gpd
from sentinelhub import (MimeType, SHConfig, SentinelHubCatalog, Geometry, DataCollection, SentinelHubRequest)
import os
import shutil
import tarfile
from tkinter import Tk, filedialog, Label, Button
from tkcalendar import DateEntry

### Variablen setzen

# Test-Dateien für schnelle Durchläufe
TEST_INPUT_SHAPE = r"C:\Users\juliu\Daten\HSWT SHK Leßke\digiman_download_script\test_input\b_TUM Freising\Heindlacker\Heindlacker.shp"
TEST_INPUT_FOLDER = r"C:\Users\juliu\Daten\HSWT SHK Leßke\digiman_download_script\test_input"
TEST_OUTPUT_FOLDER = r"C:\Users\juliu\Daten\HSWT SHK Leßke\digiman_download_script\test_output"
TEST_START_DATE = '2024-06-01'
TEST_END_DATE = '2024-06-10'

# Credentials für SentinelHub-Authentifizierung, Überprüfung
config = SHConfig()
print("Client ID aus Environment:", config.sh_client_id)
print("Client Secret aus Environment:", config.sh_client_secret)

### Hilfsfunktionen

# Grafische Ordnerauswahl
def select_folder(title="Ordner auswählen"):
    root = Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    folder_selected = filedialog.askdirectory(title=title, parent=root)
    root.destroy()
    return folder_selected

# Grafische Auswahl eines Start- und Enddatums
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

# Spezifischen Output-Order erstellen
def create_output_dir(input_root, output_root, shapefile_path):
    rel_path = os.path.relpath(shapefile_path, input_root)
    base_path = os.path.splitext(rel_path)[0]
    out_dir = os.path.join(output_root, base_path + "-data")
    return out_dir

# Liste mit Pfaden von Shapefiles in Ordner erstellen
# Shapefiles mit mehr als einem Polygon werden nicht aufgenommen
def find_shapefiles(folder):
    shapefiles = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".shp"):
                shapefiles.append(os.path.join(root, file))
    return shapefiles

# Das vom SentinelHub-Request zurückgegebene .tar-Archiv in den Ordner darüber extrahieren und den "zufällig" benannten Ordner löschen
def extract_and_cleanup_tar(target_folder):
    for root, dirs, files in os.walk(target_folder):
        for file in files:
            if file.endswith(".tar"):
                tar_path = os.path.join(root, file)
                extract_dir = os.path.dirname(root)  # das ist der Datumsordner
                try:
                    with tarfile.open(tar_path) as tar:
                        tar.extractall(path=extract_dir)
                    print(f"✅ Extrahiert: {tar_path}")
                except Exception as e:
                    print(f"❌ Fehler beim Extrahieren von {tar_path}: {e}")
                # Löschen des zufällig benannten Ordners
                try:
                    shutil.rmtree(root)
                    print(f"🧹 Ordner gelöscht: {root}")
                except Exception as e:
                    print(f"⚠️ Fehler beim Löschen von {root}: {e}")

### Sentinelhub-Request

# evalscript (bestimmt Input-Bänder, Output-Dateien und auf ausgeführte Funktion)
# Sammelrequest: Alle Bänder in einem Request
# Alle Bänder als Input (B10 (selten genutzt) nicht von SentinelHub bereitgestellt)
# Alle Bänder als einzelne Outputs, gekennzeichnet durch {}
# evaluatePixel: Nichts weiterverarbeiten, nur 1:1 die Bänder
evalscript = """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"],
      units: "DN"
    }],
    output: [
      { id: "B01", bands: 1, sampleType: "UINT16" },
      { id: "B02", bands: 1, sampleType: "UINT16" },
      { id: "B03", bands: 1, sampleType: "UINT16" },
      { id: "B04", bands: 1, sampleType: "UINT16" },
      { id: "B05", bands: 1, sampleType: "UINT16" },
      { id: "B06", bands: 1, sampleType: "UINT16" },
      { id: "B07", bands: 1, sampleType: "UINT16" },
      { id: "B08", bands: 1, sampleType: "UINT16" },
      { id: "B8A", bands: 1, sampleType: "UINT16" },
      { id: "B09", bands: 1, sampleType: "UINT16" },
      { id: "B11", bands: 1, sampleType: "UINT16" },
      { id: "B12", bands: 1, sampleType: "UINT16" }
    ]
  }
}

function evaluatePixel(sample) {
  return {
    B01: [sample.B01],
    B02: [sample.B02],
    B03: [sample.B03],
    B04: [sample.B04],
    B05: [sample.B05],
    B06: [sample.B06],
    B07: [sample.B07],
    B08: [sample.B08],
    B8A: [sample.B8A],
    B09: [sample.B09],
    B11: [sample.B11],
    B12: [sample.B12],
  };
}
"""

### Download-Funktion
def download_sentinelhub_bands(shapefile_path, start_date, end_date, input_root, output_root, config):
    
    # Shapefile einlesen
    try:
        gdf = gpd.read_file(shapefile_path).to_crs("EPSG:4326")
    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {shapefile_path}: {e}")
        return
    # Shapefiles mit mehr als einem Polygon werden übersprungen
    if len(gdf) != 1:
        print(f"⚠️ Überspringe {shapefile_path}: enthält {len(gdf)} Features (erwartet 1).")
        return

    # Output-Ordner erstellen
    out_dir = create_output_dir(input_root, output_root, shapefile_path)
    os.makedirs(out_dir, exist_ok=True)
    
    ### SentinelHub-Abfrage
    
    # Polygon aus Shapefile zu SentinelHub-Geometry-Objekt konvertieren
    geometry = Geometry(gdf.geometry[0], crs=4326)

    # SentinelHub Catalog erstellen
    catalog = SentinelHubCatalog(config=config)
    
    # Katalog-Anfrage formulieren
    search_iterator = catalog.search(
        DataCollection.SENTINEL2_L2A,
        geometry=geometry,
        time=(start_date, end_date),
        # Uns interessiert nur das Datum des Items
        fields={
            "include": ["properties.datetime"],
            "exclude": []
        }
    )
    
    # Liste mit Daten der verfügbaren Items erstellen und dabei Uhrzeit (Ab Zeichen 11) abschneiden
    item_date_list = sorted({item['properties']['datetime'][:10] for item in search_iterator})
    
    
    for item_date in item_date_list:
        
        # Ordner für das Datum erstellen
        date_dir = os.path.join(out_dir, item_date)
        os.makedirs(date_dir, exist_ok=True)
        
        # responses-Dictionary für Benennen der TIFFs erstellen (muss genau zu den IDs im evalscript passen
        bands_of_interest = ["B01","B02","B03","B04","B05","B06","B07","B08","B8A","B09","B11","B12"]
        responses = [SentinelHubRequest.output_response(band, MimeType.TIFF) for band in bands_of_interest]
        
        # Zeitinvervall für den Request erstellen
        time_intervall = item_date + "T00:00:00", item_date + "T23:59:59"
        
        # SentinelHub Request erstellen
        request = SentinelHubRequest(
            evalscript=evalscript,
            input_data=[
                SentinelHubRequest.input_data(
                    data_collection=DataCollection.SENTINEL2_L2A,
                    # der SentinelHubRequest braucht einen Intervall für Mosaicking (Zusammensetzen von Bildern von verschiedenen Zeitpunkten)
                    time_interval=(time_intervall)
                )
            ],
            # wir nehmen die Dateinamen aus dem responses-Dictionary
            responses=responses,
            geometry=geometry,
            data_folder=date_dir,
            config=config
        )
        request.get_data(save_data=True)
        extract_and_cleanup_tar(date_dir)
        
def main():
    shapefiles = find_shapefiles(TEST_INPUT_FOLDER)
    for shapefile in shapefiles:
        download_sentinelhub_bands(shapefile, TEST_START_DATE, TEST_END_DATE, TEST_INPUT_FOLDER, TEST_OUTPUT_FOLDER, config)

main()