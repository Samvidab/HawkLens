Matterport fixture placement audit (Lane B)

The recorder in backend/app/agents/interior.py builds claims from normalized image
marks and creates one pin per evidence panorama (up to its configured limit).
Pin.xyz is copied from PanoramaRef.xyz. It describes the scan origin in the Model
API frame (z up), not the equipment. The equipment widget selects verified
lighting and air-terminal pins, matches their scan positions to panorama IDs,
and supplies the claim evidence to Co2Tour. co2Tags matches that ID to an SDK
sweep in the actual tour. No Model API coordinates are converted to SDK anchors.

Before this fix, Tag.add received the sweep's puck position, an upward decorative
stem, and a label that suggested equipment placement. List clicks explicitly
requested pitch -70. The matterport-ui-co2 branch at c85b9a4 has the same placement
logic; no branch merge or unrelated UI changes were taken. ShowcaseModal exists
on that branch, but does not exist in lane-support.

The read-only audit in fixture-placement-audit.json covers all 23 eligible items:
234648: 2; 23551: 5; 239601: 3; 239618: 2; 239731: 2; 239890: 4;
362982: 5. All have a matching panorama and 2D image marks. Building 6550930
(7900 Fannin) remains valid with zero eligible items.

Verified fixture anchors: 0. Photo taken here fallbacks: 23.

Neither the saved pins nor the normalized face boxes establish a model surface
position. The panorama adapter requests position and skybox URLs, but records
no face-to-Showcase extrinsics. Some pins aggregate multiple marked fixtures.
A bounding-box centre is therefore not a verified fixture surface point.

The installed SDK 1.6.2 exposes Renderer.getWorldPositionData(screenPosition),
which raycasts the rendered model when no height argument is supplied. It can
return a null position when the model has no surface. Its optional height
argument intersects an artificial horizontal plane and is unsuitable here.
Reliable automatic placement still needs a calibrated mapping from each marked
skybox pixel to the live Showcase view, an unambiguous fixture target, and a
model-surface hit validated against that target. This change does not claim
that pipeline is implemented or that a floor or ceiling plane verifies equipment.

Every current marker explicitly says Photo taken here. The original observation
position is preserved without a decorative stem. Selection in the tour and list
both jump to the recorded sweep. Face-0 ceiling evidence selects pitch +90;
horizontal evidence selects a level view at the sweep heading because fixture
yaw is unresolved. These are observation views, not exact equipment framing.
Default tag navigation is disabled to prevent a flight toward the floor marker.
Claims, evidence files, saved demo data, and the other lane are unchanged.

Verification: 14 frontend component tests, production build, and 21 backend
co2_equipment/interior/interior_rooms tests. The Playwright emissions suite passed against a temporary copy of Lane A data
and a read-only cache: all eight live tours reached ready, all 23 markers were
added, and all 23 list clicks reached the SDK-reported target panorama and opened
the matching tag. 7900 Fannin loaded with zero tags. This suite does not assert
Camera.pose or exact fixture framing; screenshots do not establish that the
fixture is centered. Direct in-tour selection is covered by the component test.
