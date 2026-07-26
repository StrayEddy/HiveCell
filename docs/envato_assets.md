# Licensed city assets — "One Night" real-look render

The photoreal night-street dressing (`HC_REAL=1`) uses **KitBash3D** models from
**Envato Elements**. They are covered by the Envato Elements subscription license,
are **not redistributable**, and are gitignored (`assets/envato/`). Rebuild them
from the Elements `.zip` downloads with `blender/prepare_envato.sh`.

All items are one coherent KitBash family (Manhattan + Storefronts + City Streets
+ City Cars): real-world metric scale, Z-up, base at z=0 — the same units as the
hero cell, so they drop straight onto the street plane.

## Download list (elements.envato.com, logged in → download .zip into ~/Downloads)

Skyline (behind the hive):
- https://elements.envato.com/kitbash-manhattan-skyscraper-c-ADWX3PN
- https://elements.envato.com/kitbash-manhattan-upscale-hotel-ZCGJSUS

Street-level facades (flank the hive):
- https://elements.envato.com/kitbash-storefronts-book-store-GYX68X2
- https://elements.envato.com/kitbash-storefronts-minimart-groceries-M26VQQU
- https://elements.envato.com/kitbash-storefronts-st-noelle-bistro-AZJZHXZ

Street kit (lamp, sidewalk tiles, props, signals) — note a couple of Envato
titles are mislabelled: "city-sidewalk-b" is actually a building (BldgMD_K) and
"sidewalk-trash-can" is a small building (BldgSM_O):
- https://elements.envato.com/kitbash-city-streets-lamp-f-S9RFQZJ
- https://elements.envato.com/kitbash-city-streets-city-sidewalk-b-ABWQMAV
- https://elements.envato.com/kitbash-city-streets-sidewalk-a-FUKUZVU
- https://elements.envato.com/kitbash-city-streets-sidewalk-b-WMDAFKH
- https://elements.envato.com/kitbash-city-streets-sidewalk-c-X82ZHZC
- https://elements.envato.com/kitbash-city-streets-fire-hydrant-a-F59DD6Y
- https://elements.envato.com/kitbash-city-streets-newspaper-stand-a-KMH2BUU
- https://elements.envato.com/kitbash-city-streets-sidewalk-trash-can-VFMLELC
- https://elements.envato.com/kitbash-city-streets-bus-stop-a-SMSBJB6
- https://elements.envato.com/kitbash-city-streets-traffic-lights-b-6M94ZJ2
- https://elements.envato.com/kitbash-city-streets-crossing-signal-BZY2EL3

Vehicles:
- https://elements.envato.com/kitbash-city-cars-sedan-YEWY7H4
- https://elements.envato.com/kitbash-city-cars-mid-size-suv-XNEZ3J8
- https://elements.envato.com/kitbash-city-cars-city-bus-9NK8LWD

## Rebuild

```
./blender/prepare_envato.sh              # extract ~/Downloads/kitbash-*.zip + fix textures
HC_REAL=1 HC_STILL=120,700 ./blender/render_narrative.sh   # look-check a couple of stills
```

The `.blend`s reference a shared `KB3DTextures/4k/` library the Elements download
omits; `prepare_envato.sh` repoints every image to the flattened copy shipped
beside each blend, or they render magenta.
