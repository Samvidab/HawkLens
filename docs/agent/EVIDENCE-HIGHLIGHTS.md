Matterport evidence clarity — Lane B

Selecting a tag or tour-list item keeps the original interactive Showcase view.
Inspection Close-Up or View evidence explicitly opens the original recorded image
in an accessible native dialog; Matterport 3D View returns to the same mounted tour. A separate View evidence button works even when
the SDK is unavailable. The existing panorama link, claim text, verifier note,
Photo taken here marker, and panorama/rotation navigation remain available.
Closing the dialog returns to the tour; Escape closes it and focus returns to
the previous control.

The /media endpoint already returns the original file without resizing or
recompression. All 23 associated recorded images are 2048 × 2048 pixels. The
viewer uses those files directly, fits the full image without CSS upscaling or
blur filters, and offers a scrollable original-size (1:1) view. No generated,
sharpened, reconstructed, or fetched replacement image is used. Source scan
privacy masks or blurred patches remain as recorded; missing original detail
cannot be recovered without inventing content.

Highlights are high-contrast yellow/black ellipses derived from the stored bounding boxes
(or a stored polygon when a valid bounding box is absent). Each mark must refer
to the exact displayed image, that image must belong to the verified claim's
evidence IDs, and coordinates must be finite normalized values in [0, 1]. Boxes
must have positive width and height; polygons must have nonzero area. Invalid
coordinates are rejected, not clamped or replaced. Multiple matching marks are
all displayed rather than guessing which one represents the pin.

An SVG with viewBox 0 0 1 1 sits directly over the rendered image. Ellipse center is ((x0+x1)/2, (y0+y1)/2); radii are (x1-x0)/2 and (y1-y0)/2.
Its bounds exactly match the recorded bounding box; no coordinate or padding is invented.
The overlay and image share exactly the same bounds in fit and original-size
modes. Strokes use non-scaling-stroke to remain visible on resize. Overlays are
hidden until the image loads and removed on load failure. When no valid mark
exists, the viewer says "Exact object location not verified in image."

Image-coordinate validation is not independent verification of the inspector's
annotation accuracy and does not establish a 3D fixture position. Spatial tags
remain observation-location fallbacks.

Read-only audit: 23 tags have recorded-coordinate highlights (26 boxes); zero
current tags require the missing-coordinate fallback. Per-tag image IDs and
coordinates are in evidence-highlight-audit.json. Counts by building:

| Building ID | Tags with highlights | Missing-coordinate fallbacks |
| --- | ---: | ---: |
| 234648 | 2 | 0 |
| 23551 | 5 | 0 |
| 239601 | 3 | 0 |
| 239618 | 2 | 0 |
| 239731 | 2 | 0 |
| 239890 | 4 | 0 |
| 362982 | 5 | 0 |
| 6550930 (7900 Fannin) | 0 | 0 |

Unit verification: 24 tests cover original-image rendering, exact box geometry,
polygon validation, missing/mismatched/malformed coordinates, image failure,
multiple marks, the 23-record audit, and list/tag selection navigation.
Production build passes. Browser verification checks the original image size,
absence of blur filters, and subpixel overlay alignment at fit size, 1:1, and a
smaller viewport while preserving the existing panorama/tag navigation checks.
The browser suite passed across all eight buildings: 23 evidence views and
23 panorama/tag jumps, with zero tags at 7900 Fannin. Screenshots from Paragon
Center I and Denmark House were also visually inspected for image clarity and
object-outline alignment.

Isolated Portfolio preview adaptation: bounding boxes render as ellipses, native-size
images scroll from the left edge, and Escape closes evidence without closing the tour.
These changes do not sharpen, resample, or overwrite any source image.

Regression correction in the isolated preview: removed automatic image opening
from tag selection. Native Showcase camera controls and zoom remain unchanged.
The optional close-up adds wheel/button zoom, drag-to-pan, fit and 1:1 views;
zoom above 100% only magnifies recorded pixels. SVG overlays share image bounds.
