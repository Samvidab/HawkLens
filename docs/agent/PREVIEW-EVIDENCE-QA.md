Evidence QA in the isolated Portfolio preview

All 8 tours loaded; all 23 inspection selections opened original 2048 x 2048 images.
The 26 SVG ellipses match the recorded box bounds at fit size, native CSS-pixel size,
and resized viewports. HTTP image bytes match the copied cached files. This validates
rendering and provenance, not the correctness of the source annotations.

Visual findings, with source coordinates preserved:
- Legacy Pointe (362982), item 2, image mpp_FNC3RNdVtoP_c2imx9e9feimyn9nahcpnwb4b_1:
  the box labelled "vav diffuser" surrounds a red device visibly labelled FIRE.
- Legacy Pointe (362982), item 0, image mpp_FNC3RNdVtoP_2e2ns4efqhq5z11efebehq7qd_1:
  the box labelled "fluorescent troffer" surrounds an apparently blank ceiling region.
- Paragon Center I (239601), item 2, image mpp_FTkFHSZ4isL_uzpe2t8y4m2pyc2988nrrtykb_0:
  the diffuser-labelled boxes surround small round fixtures; their identification is uncertain.
- Several images contain existing blur/privacy masking. Original detail cannot be recovered
  by the viewer. No sharpening, generated detail, coordinate corrections, claim changes,
  or fixture positions were introduced.

Saved verifier statuses are shown as recorded. These examples need source-data review;
it would be inaccurate to claim every outline identifies the correct equipment.

Matterport emitted XR permission messages and several internal fetch errors despite all
8 tours reaching ready and all 23 panorama/tag checks passing. No uncaught page errors.
Real target-slider optimization from 40% to 20% also passed against a separate disposable
backend/data copy, leaving the main preview plan 91235cb8b3dd intact.
