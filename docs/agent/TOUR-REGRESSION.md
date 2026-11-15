Showcase regression correction in the isolated preview

Before: selecting a tag called setEvidenceIndex(i), opening a native modal and
making the underlying interactive Showcase inaccessible until dismissed.
After: tag selection only navigates the existing Showcase sweep and opens the tag.
Inspection Close-Up / View evidence is explicit. Returning to Matterport 3D View
closes only the evidence dialog; the Showcase iframe remains mounted, with its
sweep, camera rotation and zoom preserved. No fixture framing was invented.

The image viewer supports fit, original 1:1, button and wheel zoom, and drag panning.
Zoom beyond 100% magnifies existing pixels, without enhancing or generating detail.
The same original image and normalized SVG ellipses share bounds during every
zoom/pan. Ellipse bounds derive directly from the recorded boxes. Existing source
annotation errors and privacy masking remain; see PREVIEW-EVIDENCE-QA.md.

Verification: 235 frontend tests, 23 relevant backend tests and production build
passed. Browser checks covered all 8 tours (7-building suite plus focused Fannin
check), native camera wheel zoom/drag, all 23 list/tag navigation selections,
26 recorded highlights at fit/1:1/resize/zoom/pan, and unchanged iframe/camera state
on return from close-ups. Fannin has zero tags. Direct tag selection is covered
by the component test. No uncaught browser page errors; Matterport logs XR policy
messages. Earlier browser retries addressed a navigation timeout, non-atomic
geometry measurements during recentering, and Fannin's introductory overlay.
Original survey data/cache hashes and the saved preview plan remained unchanged.
