#!/usr/bin/env bash
# Holt Ampeln für die Region Leipzig. Probiert nacheinander mehrere Quellen.
set -u
BBOX="${BBOX:-12.15,51.20,12.62,51.48}"
UA="Gruenwelle-Ampeldaten/1.0 (+https://github.com/DMS314/Gruenwelle)"

try_pbf () {
  local url="$1"
  echo "Versuche $url"
  code=$(curl -sSL --retry 2 --retry-delay 10 -A "$UA" -o src.osm.pbf -w '%{http_code}' "$url") || code="curl-fehler"
  echo "  HTTP $code, Größe $(stat -c %s src.osm.pbf 2>/dev/null || echo 0) Bytes"
  [ "$code" = "200" ] || return 1
  osmium extract -b "$BBOX" src.osm.pbf -o region.osm.pbf --overwrite || return 1
  osmium tags-filter region.osm.pbf n/highway=traffic_signals n/crossing=traffic_signals -o sig.osm.pbf --overwrite || return 1
  osmium export sig.osm.pbf -f geojsonseq --add-unique-id=type_id -o sig.geojsonseq --overwrite || return 1
  python3 tools/build_signals.py sig.geojsonseq signals.json "$BBOX"
}

try_overpass () {
  local url="$1"
  IFS=, read -r W S E N <<< "$BBOX"
  local q="[out:json][timeout:180];(node[\"highway\"=\"traffic_signals\"]($S,$W,$N,$E);node[\"crossing\"=\"traffic_signals\"]($S,$W,$N,$E););out body;"
  echo "Versuche Overpass $url"
  code=$(curl -sS --max-time 240 -A "$UA" -o sig.json -w '%{http_code}' --data-urlencode "data=$q" "$url") || code="curl-fehler"
  echo "  HTTP $code"
  [ "$code" = "200" ] || return 1
  python3 tools/build_signals.py sig.json signals.json "$BBOX"
}

try_pbf https://download.geofabrik.de/europe/germany/sachsen-latest.osm.pbf && exit 0
try_pbf https://download.bbbike.org/osm/bbbike/Leipzig/Leipzig.osm.pbf && exit 0
try_overpass https://overpass-api.de/api/interpreter && exit 0
try_overpass https://overpass.private.coffee/api/interpreter && exit 0
echo "Alle Quellen fehlgeschlagen"; exit 1
