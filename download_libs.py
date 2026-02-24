import os
import requests

LIB_DIR = "trading-engine/lib"
if not os.path.exists(LIB_DIR):
    os.makedirs(LIB_DIR)

JARS = [
    "https://repo1.maven.org/maven2/com/google/code/gson/gson/2.10.1/gson-2.10.1.jar",
    "https://repo1.maven.org/maven2/com/squareup/okhttp3/okhttp/4.12.0/okhttp-4.12.0.jar",
    "https://repo1.maven.org/maven2/com/squareup/okio/okio/3.6.0/okio-3.6.0.jar",
    "https://repo1.maven.org/maven2/org/jetbrains/kotlin/kotlin-stdlib/1.9.10/kotlin-stdlib-1.9.10.jar",
    "https://repo1.maven.org/maven2/org/slf4j/slf4j-api/2.0.12/slf4j-api-2.0.12.jar",
    "https://repo1.maven.org/maven2/ch/qos/logback/logback-classic/1.4.14/logback-classic-1.4.14.jar",
    "https://repo1.maven.org/maven2/ch/qos/logback/logback-core/1.4.14/logback-core-1.4.14.jar"
]

for url in JARS:
    filename = url.split("/")[-1]
    filepath = os.path.join(LIB_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Downloading {filename}...")
        try:
            r = requests.get(url)
            with open(filepath, "wb") as f:
                f.write(r.content)
            print("Done.")
        except Exception as e:
            print(f"Failed to download {filename}: {e}")
    else:
        print(f"{filename} exists.")
