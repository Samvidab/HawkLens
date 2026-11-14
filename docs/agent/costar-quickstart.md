HackPrinceton 2026 · CoStar track · Matterport
One house, inside and out
Every kind of data a hackathon key reaches, shown for 5836 La Mirada Ave, Los Angeles: the query, a real response, and what it looks like. It mirrors the quickstart notebook section by section.

Notebook (.ipynb)
Script (.py)
models_index.csv
3D tour
Example model
zvKHR9DHNjJ
Address
5836 La Mirada Ave, Los Angeles, CA 90038
Lat, lon
34.0934917, -118.3171000
Inside
1 floor · 19 rooms · 39 panos · defurnished view
Outside
aerial splat · 835 drone photos
Geometry
MatterPak: OBJ mesh + 10.4 M-point cloud
Joins
Homes listing 221139020 · Vexcel by lat/lon
Matterport turns real buildings into 3D digital twins you can measure, search and reimagine. Your hackathon key reaches about 15,000 of them in Houston and Los Angeles. 232 of those also come with an aerial Gaussian splat and the drone photos it was trained from.

This notebook walks through one house, 5836 La Mirada Ave in Los Angeles (model zvKHR9DHNjJ), from the inside out. Each section stands on its own and does one thing: one snippet, one picture. Change MODEL to any other model and run it again.

#	Section	What you get	In the talk
1	Setup and key check	your key works; how many models it sees	15,000 real spaces
2	Find models near a point	a lat/lon lookup over every model (the API has no geo search)	15,000 real spaces
3	Model basics	address, lat/lon, AI summary, property type, the 3D tour	
4	Panoramas	skybox faces, a stitched 360° view, the same room defurnished	We capture; We reimagine
5	Rooms and floor plan	room table, walls drawn from the graph, floor-plan image and DXF	We understand
6	Splat and drone photos	a splat seen from above, the sky, one drone photo, the flight path	We reconstruct
7	The same lot from above	Vexcel aerial imagery under the drone path; the CoStar record	Better together
8	MatterPak: mesh and point cloud	10 M coloured points, read straight out of the zip	We reconstruct
9	Ideas and help	the problems we haven't solved, and who to find	What we haven't solved yet; Find us
Keys. Run /costar-keys in the track Discord. Put the values in environment variables (or your notebook platform's secrets manager, exposed as environment variables) or in a .env file next to the notebook, never in the notebook itself:

Name	What it is	Needed for
MATTERPORT_API_KEY	Matterport "API key" from the keys card	everything
MATTERPORT_API_TOKEN	Matterport "API token" (the secret half)	everything
VEXCEL_API_KEY	Vexcel api_key	section 7
COSTAR_ZIP_PASSWORD	CoStar "Zip password"	section 7 (optional)
COSTAR_KIT_URL or COSTAR_KIT_ZIP	the kit's download link from the CoStar card, or the downloaded zip's path	section 7 (optional)
The whole notebook downloads about 200 MB and takes a few minutes. Everything it saves goes into mp_out/.

1
Setup and key check
One helper, graph(), sends GraphQL to the Model API with your key (HTTP basic auth: the key is the user name, the token the password). The keys only work on production, api.matterport.com. It fails with a plain message if the key is wrong.

Model API POST api.matterport.com/api/models/graph · query · variables {}
Query
{ rootFolder { name modelCountSummary(includeModelsInSubfolders: true)
                 subfolders { results { id name modelCountSummary(includeModelsInSubfolders: true) } } } }
Response (real, trimmed)
{
 "data": {
  "rootFolder": {
   "name": "HackPrinceton 2026",
   "modelCountSummary": 14944,
   "subfolders": {
    "results": [
     {
      "id": "modNEmUQx5D",
      "name": "Commercial Spaces",
      "modelCountSummary": 13014
     },
     {
      "id": "hxR8S1jV8xG",
      "name": "Residential Spaces",
      "modelCountSummary": 1930
     }
    ]
   }
  }
 }
}
The code 2.0 s · 0.0 MB downloaded
Output
Key OK. 'HackPrinceton 2026' holds 14,944 models:
  Commercial Spaces    13,014   (folder modNEmUQx5D)
  Residential Spaces    1,930   (folder hxR8S1jV8xG)
Helpers that later sections share: run this cell once too. After these two cells, every section runs on its own.

The code 0.0 s · 0.0 MB downloaded
2
Find models near a point
The Model API has no geographic search, so this folder ships models_index.csv: one row per model the hackathon keys can see, with its lat/lon, address, segment, the CoStar property id or Homes listing id where known, whether it has a splat, and pano and room counts. near() is a plain distance filter over it, and basemap.json (county lines, city limits and roads) draws the map below. Vexcel takes the same lat/lon, so this is also the bridge between layers.

The code 0.3 s · 0.0 MB downloaded
Output
14,944 models; 232 with a splat
        sid               name     segment splat  pano_count  room_count
zvKHR9DHNjJ 5836 La Mirada Ave residential   yes          39          19
qRFURoCtFoy  6BR, 5BA -1,846SF  commercial    no          26          16
KdCucbSHtZF   2BR, 2BA - 762SF  commercial    no          10           4
HE6AasUmVyN 5BR, 4BA - 1,473SF  commercial    no          18          12
5bM18rdqYt6 4BR, 2BA - 1,161SF  commercial    no          17           8
ioJWQFtzBCY   1BR, 1BA - 477SF  commercial    no           9           4
2ncmRTJs8g2 6BR, 4BA - 1,836SF  commercial    no          21          10
AhTroQ5o2fN 6BR, 3BA - 1,823SF  commercial    no          48          18
hwunjJ37J65 6BR, 4BA - 1,728SF  commercial    no          55          17
jncdtBYm5By 6BR, 4BA - 1,836SF  commercial    no          50          16
saved mp_out/s02_models_map.png  (downloaded so far: 0.0 MB)
Every model with a location, in Los Angeles and Houston: navy commercial, orange residential, over US Census county lines, city limits and primary roads (basemap.json).
Every model with a location, in Los Angeles and Houston: navy commercial, orange residential, over US Census county lines, city limits and primary roads (basemap.json). 2367×1036
3
Model basics
The basics of a model: its address and lat/lon, an AI-written summary, the property type Matterport's vision models assigned, and counts of what's inside. A public or unlisted model also plays in the Showcase 3D viewer, which you can embed with an iframe (or script with the Showcase SDK).

Model API POST api.matterport.com/api/models/graph · Basics · variables {"id": "zvKHR9DHNjJ"}
Query
query Basics($id: ID!) { model(id: $id) {
  id name description created visibility
  address { address locality administrativeArea postalCode }
  geolocation { lat long }
  generatedDescription { summary }
  propertyClassifications { classification type }
  floors { id label } rooms { id } panoLocations { id }
  image { url }
} }
Response (real, trimmed)
{
 "data": {
  "model": {
   "id": "zvKHR9DHNjJ",
   "name": "5836 La Mirada Ave",
   "description": "3BD, 2BA - 1,628 SF - Home staged for open house; No exterior scans per agent; Cars in driveway; Tv on in living room & candles lit in living room and throughout house; Some curtains closed/set by age…",
   "created": "2026-11-09T23:16:37Z",
   "visibility": "public",
   "address": {
    "address": "5836 La Mirada Ave, Los Angeles, CA, 90038, US",
    "locality": "Los Angeles",
    "administrativeArea": "CA",
    "postalCode": "90038"
   },
   "geolocation": {
    "lat": "34.0934917",
    "long": "-118.3171000"
   },
   "propertyClassifications": [
    {
     "classification": "living_space",
     "type": "vision"
    }
   ],
   "floors": [
    {
     "id": "tsmq1wak12rhgn0mawksxcwcd",
     "label": "Floor 1"
    }
   ],
   "rooms": [
    {
     "id": "n2yqr30509t7i8whfdf2htwic"
    },
    {
     "id": "peina19mpqedsku6a3huu38md"
    },
    {
     "id": "613htqkzf66zz7hf7n8kzszed"
    },
    "… 16 more"
   ],
   "panoLocations": [
    {
     "id": "d279g7xebr6dyraxsf95h6qfa"
    },
    {
     "id": "i2e531d27m54g8xf8fqm0mm6b"
    },
    {
     "id": "sa0ccfc88azxsste162hiipwd"
    },
    "… 36 more"
   ],
   "image": {
    "url": "https://cdn-2.matterport.com/apifs/models/zvKHR9DHNjJ/images/BYWkQ7bRoRC/09.16.2026_07.22.10.jpg?…"
   }
  }
 }
}
The code 0.5 s · 0.9 MB downloaded
Output
5836 La Mirada Ave  (zvKHR9DHNjJ, public)
5836 La Mirada Ave, Los Angeles, CA, 90038, US
lat/lon 34.0934917, -118.3171
1 floor(s), 19 rooms, 39 panoramas; property type: ['living_space']

AI summary: none for this model (90% of models have one, but only 70 of the 232 splat models; ai_summary in models_index.csv says which, e.g. BxUNr6KdqyL)
Capture notes: 3BD, 2BA - 1,628 SF - Home staged for open house; No exterior scans per agent; Cars in driveway; Tv on in living room & candles lit in living room and throughout house; Some curtains closed/set by agent asked to not adjust; Some lights/lamps out throughout house; could not access side patios from dining room door; no back door scans to avoid backyard and cat outside from coming in; side hallway door to be kept closed by kitchen
saved mp_out/s03_preview.jpg  (downloaded so far: 0.9 MB)
3D tour: https://my.matterport.com/show/?…
The model's preview image, from image { url }.
The model's preview image, from image { url }. 3034×1707
4
Panoramas
Every scan position (a "pano") is a 360° photo stored as a skybox: six square cube faces, 0 up, 1–4 around the horizon, 5 down. Ask for 2k (2048 px) or 4k faces. The links are signed and expire, so query again for fresh ones.

Models in this set also carry a defurnished view: the same panoramas with the furniture removed by Matterport's generative models. It is a separate view of the model; query it by its own id with the same fields.

Model API POST api.matterport.com/api/models/graph · Panos · variables {"id": "zvKHR9DHNjJ"}
Query
query Panos($id: ID!) { model(id: $id) {
  panoLocations { id label position { x y z } skybox(resolution: "2k") { status children } }
  view(type: "matterport.model.defurnished") { id }
} }
Response (real, trimmed)
{
 "data": {
  "model": {
   "panoLocations": [
    {
     "id": "d279g7xebr6dyraxsf95h6qfa",
     "label": "22",
     "position": {
      "x": -11.874,
      "y": -5.135,
      "z": 1.475
     },
     "skybox": {
      "status": "available",
      "children": [
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/pan/2k/~/1f1c124fa6ff470382b787dfcaf981d4_skybox0.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/pan/2k/~/1f1c124fa6ff470382b787dfcaf981d4_skybox1.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/pan/2k/~/1f1c124fa6ff470382b787dfcaf981d4_skybox2.jpg?…",
       "… 3 more"
      ]
     }
    },
    {
     "id": "i2e531d27m54g8xf8fqm0mm6b",
     "label": "13",
     "position": {
      "x": -9.904,
      "y": -4.384,
      "z": 1.473
     },
     "skybox": {
      "status": "available",
      "children": [
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/dbc7a932e1c44db48c32891894b1f4b1/pan/2k/~/d6d5dc0ef9d943089e2956534be2cfc6_skybox0.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/dbc7a932e1c44db48c32891894b1f4b1/pan/2k/~/d6d5dc0ef9d943089e2956534be2cfc6_skybox1.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/dbc7a932e1c44db48c32891894b1f4b1/pan/2k/~/d6d5dc0ef9d943089e2956534be2cfc6_skybox2.jpg?…",
       "… 3 more"
      ]
     }
    },
    {
     "id": "sa0ccfc88azxsste162hiipwd",
     "label": "36",
     "position": {
      "x": 0.479,
      "y": 2.668,
      "z": 1.52
     },
     "skybox": {
      "status": "available",
      "children": [
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/pan/2k/~/9d41ef08a215480fb931083e397241ef_skybox0.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/pan/2k/~/9d41ef08a215480fb931083e397241ef_skybox1.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/pan/2k/~/9d41ef08a215480fb931083e397241ef_skybox2.jpg?…",
       "… 3 more"
      ]
     }
    },
    "… 36 more"
   ],
   "view": {
    "id": "ew3wiyc2wzr94eymaex3kqd5a"
   }
  }
 }
}
Model API POST api.matterport.com/api/models/graph · Panos · variables {"id": "ew3wiyc2wzr94eymaex3kqd5a"}
Query
query Panos($id: ID!) { model(id: $id) {
  panoLocations { id label position { x y z } skybox(resolution: "2k") { status children } }
  view(type: "matterport.model.defurnished") { id }
} }
Response (real, trimmed)
{
 "data": {
  "model": {
   "panoLocations": [
    {
     "id": "d279g7xebr6dyraxsf95h6qfa",
     "label": "22",
     "position": {
      "x": -11.874,
      "y": -5.135,
      "z": 1.475
     },
     "skybox": {
      "status": "available",
      "children": [
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/1f1c124fa6ff470382b787dfcaf981d4_skybox0.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/1f1c124fa6ff470382b787dfcaf981d4_skybox1.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/1f1c124fa6ff470382b787dfcaf981d4_skybox2.jpg?…",
       "… 3 more"
      ]
     }
    },
    {
     "id": "i2e531d27m54g8xf8fqm0mm6b",
     "label": "13",
     "position": {
      "x": -9.904,
      "y": -4.384,
      "z": 1.473
     },
     "skybox": {
      "status": "available",
      "children": [
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/d6d5dc0ef9d943089e2956534be2cfc6_skybox0.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/d6d5dc0ef9d943089e2956534be2cfc6_skybox1.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/d6d5dc0ef9d943089e2956534be2cfc6_skybox2.jpg?…",
       "… 3 more"
      ]
     }
    },
    {
     "id": "sa0ccfc88azxsste162hiipwd",
     "label": "36",
     "position": {
      "x": 0.479,
      "y": 2.668,
      "z": 1.52
     },
     "skybox": {
      "status": "available",
      "children": [
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/9d41ef08a215480fb931083e397241ef_skybox0.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/9d41ef08a215480fb931083e397241ef_skybox1.jpg?…",
       "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/overlay/fcde7493ddd4486eb3c39c05d3be6349/pan/2k/~/9d41ef08a215480fb931083e397241ef_skybox2.jpg?…",
       "… 3 more"
      ]
     }
    },
    "… 36 more"
   ],
   "view": {
    "id": "ew3wiyc2wzr94eymaex3kqd5a"
   }
  }
 }
}
The code 3.1 s · 5.4 MB downloaded
Output
39 panos; pano 6 (5ef86yc9eazqtcm82ar3irfqa) at {'x': -4.544435501098633, 'y': -0.3194575011730194, 'z': 1.509665608406067} (metres, model frame, z up)
saved mp_out/s04_skybox_faces.jpg  (downloaded so far: 4.7 MB)
saved mp_out/s04_equirect.jpg  (downloaded so far: 4.7 MB)
defurnished view id: ew3wiyc2wzr94eymaex3kqd5a
saved mp_out/s04_furnished_vs_defurnished.jpg  (downloaded so far: 6.2 MB)
The six faces stitched into one equirectangular panorama by equirect().
The six faces stitched into one equirectangular panorama by equirect(). 2048×1024
Top: the dining room as scanned. Bottom: the same pano from the defurnished view.
Top: the dining room as scanned. Bottom: the same pano from the defurnished view. 2048×2048
Pano 6's six skybox faces, laid out as a cross (face 1 in the middle, 0 above, 5 below).
Pano 6's six skybox faces, laid out as a cross (face 1 in the middle, 0 above, 5 below). 2048×1536
Look around
pano 6, 4096 × 2048
As scanned
Defurnished
Open the 360° viewer (3 MB)
Drag to look around, scroll to zoom.

5
Rooms and floor plan
Matterport segments each floor into rooms, classifies them (bedroom, kitchen, ...) and measures them. The walls come as a graph: vertices (2D points in metres) joined by edges, and each room's boundary is a loop of those edges. Below, the plan is drawn from that graph alone, then the same walls, and the position of every scan, are laid over Matterport's own photogrammetric floor plan using the image's origin (metres) and resolution (pixels per metre). The schematic plan also comes as a DXF for CAD tools.

Model API POST api.matterport.com/api/models/graph · Rooms · variables {"id": "zvKHR9DHNjJ"}
Query
query Rooms($id: ID!) { model(id: $id) {
  floors { id label vertices { id position { x y } } edges { id type thickness vertices { id } } }
  rooms { id floor { id } classifications { label confidence } boundary { edges { id } }
          dimensions(units: metric) { areaFloor width depth height } }
  assets { floorplans(provider: "matterport") { format flags url width height resolution origin { x y } } }
  panoLocations { label position { x y } }
} }
Response (real, trimmed)
{
 "data": {
  "model": {
   "floors": [
    {
     "id": "tsmq1wak12rhgn0mawksxcwcd",
     "label": "Floor 1",
     "vertices": [
      {
       "id": "m2rbsc4q2irhtbzk9akrmpn9d",
       "position": {
        "x": 2.803,
        "y": 4.912
       }
      },
      {
       "id": "ptwkaizdqzpek7n4ezaickh7c",
       "position": {
        "x": -10.57,
        "y": -5.766
       }
      },
      {
       "id": "s2u1m04skz64zy8rz497qkmad",
       "position": {
        "x": -10.576,
        "y": -2.763
       }
      },
      "… 46 more"
     ],
     "edges": [
      {
       "id": "etr47kkxw2pznh8574m8krq7c",
       "type": "wall",
       "thickness": 0.16,
       "vertices": [
        {
         "id": "9dzbpzahrdsur94x9b2ranzab"
        },
        {
         "id": "g0gyifch9a79wzw2zfgs140yb"
        }
       ]
      },
      {
       "id": "itducxpy0t5rz42autw6nq2na",
       "type": "wall",
       "thickness": 0.28,
       "vertices": [
        {
         "id": "bkdr5gsww0ik3skb6crtpmmed"
        },
        {
         "id": "f5hqr2egpsmzmfkxifds3n01b"
        }
       ]
      },
      {
       "id": "ktt8adpt2x0fhdagu178w2n8d",
       "type": "wall",
       "thickness": 0.16,
       "vertices": [
        {
         "id": "5d45kb826m2ek5zq07bpkrfrb"
        },
        {
         "id": "xyr7r5ts3rn0uaa550mcx7prb"
        }
       ]
      },
      "… 61 more"
     ]
    }
   ],
   "rooms": [
    {
     "id": "n2yqr30509t7i8whfdf2htwic",
     "floor": {
      "id": "tsmq1wak12rhgn0mawksxcwcd"
     },
     "classifications": [
      {
       "label": "Void",
       "confidence": 1.0
      }
     ],
     "boundary": {
      "edges": [
       {
        "id": "wutab26i2mbc319xyd46qm2ub"
       },
       {
        "id": "afg9cuxp68sf39tx3pspsbnac"
       },
       {
        "id": "p76bcufk68rub7276sntidcca"
       },
       "… 3 more"
      ]
     }
    },
    {
     "id": "peina19mpqedsku6a3huu38md",
     "floor": {
      "id": "tsmq1wak12rhgn0mawksxcwcd"
     },
     "classifications": [
      {
       "label": "Void",
       "confidence": 1.0
      }
     ],
     "boundary": {
      "edges": [
       {
        "id": "337tbxz1b7hse1c39a5gqrm5b"
       },
       {
        "id": "dd1xaz815mtxicfygai5n4uec"
       },
       {
        "id": "5d9k9acsu897p32mnmaf92m1d"
       },
       "… 1 more"
      ]
     }
    },
    {
     "id": "613htqkzf66zz7hf7n8kzszed",
     "floor": {
      "id": "tsmq1wak12rhgn0mawksxcwcd"
     },
     "classifications": [
      {
       "label": "Dining Room",
       "confidence": 1.0
      }
     ],
     "boundary": {
      "edges": [
       {
        "id": "itducxpy0t5rz42autw6nq2na"
       },
       {
        "id": "uaxr3sbdung4egmy7ghwynekd"
       },
       {
        "id": "hkpe74gzwzaq97excwmuyhy5b"
       },
       "… 5 more"
      ]
     },
     "dimensions": {
      "areaFloor": 22.709,
      "width": 4.4,
      "depth": 4.84,
      "height": 2.68
     }
    },
    "… 16 more"
   ],
   "assets": {
    "floorplans": [
     {
      "format": "jpg",
      "flags": [
       "photogramy"
      ],
      "url": "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/render/colorplan_000.jpg?…",
      "width": 1903,
      "height": 1289,
      "resolution": 100.0,
      "origin": {
       "x": -13.781,
       "y": -7.021
      }
     },
     {
      "format": "png",
      "flags": [
       "photogramy",
       "alpha"
      ],
      "url": "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/render/colorplan_alpha_000.png?…",
      "width": 1763,
      "height": 1149,
      "resolution": 100.0,
      "origin": {
       "x": -13.08,
       "y": -6.321
      }
     },
     {
      "format": "jpg",
      "flags": [
       "photogramy",
       "colored_rooms"
      ],
      "url": "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/render/colorplan_room_000.jpg?…",
      "width": 1903,
      "height": 1289,
      "resolution": 100.0,
      "origin": {
       "x": -13.781,
       "y": -7.021
      }
     },
     "… 5 more"
    ]
   },
   "panoLocations": [
    {
     "label": "22",
     "position": {
      "x": -11.874,
      "y": -5.135
     }
    },
    {
     "label": "13",
     "position": {
      "x": -9.904,
      "y": -4.384
     }
    },
    {
     "label": "36",
     "position": {
      "x": 0.479,
      "y": 2.668
     }
    },
    "… 36 more"
   ]
  }
 }
}
The code 1.4 s · 1.1 MB downloaded
Output
id        label  area_m2  width_m  depth_m  height_m
cdz3fkt38kae7tapstpt0eaeb  Living Room    28.87     5.04     5.70      2.67
613htqkzf66zz7hf7n8kzszed  Dining Room    22.71     4.40     4.84      2.68
tt6gm2a0463x9wmnx7rn6gugc      Bedroom    17.18     4.07     3.99         -
xy2x8mpaaqknp7q2c3nnbw1ma  Living Room    14.78     3.82     3.70      2.72
h26t7ky77ew74yb0pg8qqf5rd      Bedroom    13.82     3.32     3.95         -
3m54yff1z7crxaywd8if9rb0d      Kitchen    13.28     4.79     3.00      2.72
a5f9age4zzxewres6iqux2emc (unlabelled)    12.86     1.84        -         -
2qdmc5i9byxi79ry1pxdkqzea  Dining Room    11.08     3.47     2.87      2.72
m8npxsuk79xy21dd09x9wtped (unlabelled)     8.62        -        -      2.52
19ab05tns5h6y4qm42esqqpea     Bathroom     7.88     1.93     2.88      2.73
b4qtykzcazp4iumkamm7y7h2b       Closet     4.21     0.99     3.72         -
ediidma5zg15dufx3n0qyq21a     Bathroom     3.58     2.25        -         -
wbpb7dkfuwnikd1kq2a9hz70a      Hallway     3.03     2.78     0.88      2.72
n81qfe51azs8iexnbqwspye6c      Hallway     2.29     1.46     1.33      2.73
kuc0fpmsgqxff63egrxrycfud      Hallway     2.09     1.78     1.04      2.72
3ygfq6yfyyw3hi9x7u5rm2iqa     Bathroom     1.16        -        -         -
b2kez6wsw32fm2x3ui593u3hc (unlabelled)     0.10        -        -         -

49 wall vertices, 64 wall edges; total labelled area 168 m²
saved mp_out/s05_floorplan_drawn.png  (downloaded so far: 0.0 MB)
saved mp_out/s05_floorplan_matterport.jpg  (downloaded so far: 1.1 MB)
DXF saved: mp_out/zvKHR9DHNjJ_floorplan.dxf (open it in any CAD tool, or with the ezdxf package)
Drawn from the wall graph alone: walls are edges between vertices; rooms are loops of edges, labelled with their classification and area.
Drawn from the wall graph alone: walls are edges between vertices; rooms are loops of edges, labelled with their classification and area. 1267×911
Matterport's photogrammetric floor plan, placed by its origin and resolution, with the wall graph in orange and all 39 scan positions; pano 6, the dining room of section 4, is ringed.
Matterport's photogrammetric floor plan, placed by its origin and resolution, with the wall graph in orange and all 39 scan positions; pano 6, the dining room of section 4, is ringed. 1239×884
Explore the plan
click a room; dots are scan positions (pano 6 is ringed)
Click a room on the plan.

6
Splat and drone photos
For 232 models, a drone flew around the property and those photos trained a 3D Gaussian splat of the outside. The hackathon site serves each file through a short-lived signed link: SITE/resources/<sid>/<file> answers with a redirect to the file, and SITE/api/models/<sid> lists the drone photos. splat.ply is the standard "INRIA" layout: one 68-byte record per Gaussian with its centre, colour (f_dc_*), opacity, scale and rotation. Z is up and the units are roughly metres.

The splat's frame is local to the property and not aligned to north; the drone photos' GPS (below) gives you the georeference. These files are big (this one is 553 MB), but the Gaussians are stored in no spatial order, so the first few percent of the file is a fair sample of the whole scene. We read only the first 60 MB with an HTTP range request. Set SPLAT_MB = None for the full file.

The code 7.3 s · 62.9 MB downloaded
Output
residential model, splat 553 MB, 835 drone photos
read 925,207 of 8,136,303 Gaussians (11%); median z 2.9 m
saved mp_out/s06_splat_topdown.jpg  (downloaded so far: 70.2 MB)
saved mp_out/s06_envmap.jpg  (downloaded so far: 70.2 MB)
The splat's sky cubemap (px nx py ny pz nz), 128 px per face.
The splat's sky cubemap (px nx py ny pz nz), 128 px per face. 768×128
The aerial splat from straight above, rendered from the first 60 MB of splat.ply (11% of its Gaussians).
The aerial splat from straight above, rendered from the first 60 MB of splat.ply (11% of its Gaussians). 400×400
Each drone photo carries its GPS position and gimbal angles in the JPEG's XMP block, which sits in the first 48 KB of the file. So the whole flight path costs one small range request per photo, and we download a full 20 MB photo only for the one that looks most directly at the house.

Model API POST api.matterport.com/api/models/graph · query · variables {"id": "zvKHR9DHNjJ"}
Query
query($id: ID!) { model(id: $id) { geolocation { lat long } } }
Response (real, trimmed)
{
 "data": {
  "model": {
   "geolocation": {
    "lat": "34.0934917",
    "long": "-118.3171000"
   }
  }
 }
}
The code 15.2 s · 26.5 MB downloaded
Output
167 photos sampled; altitude above take-off 9-94 m
DJI_20260915135040_0281_D.JPG: 6144x4096, 37 m up, 73 m away, gimbal yaw -153°, pitch -21°
saved mp_out/s06_drone_photo.jpg  (downloaded so far: 96.7 MB)
saved mp_out/s06_flight_path.png  (downloaded so far: 96.7 MB)
The drone photo whose camera points most directly at the house, picked from its XMP gimbal angles.
The drone photo whose camera points most directly at the house, picked from its XMP gimbal angles. 1600×1067
The drone flight, from one 48 KB range request per photo, in metres from the model's lat/lon.
The drone flight, from one 48 KB range request per photo, in metres from the model's lat/lon. 927×781
Fly around the splat
400,000 Gaussians, thinned from the full file
Open the splat viewer (12.8 MB)
Drag to orbit, right-drag to pan, scroll to zoom. Rendered with gaussian-splats-3d.

7
The same lot from above
Vexcel flies its own aircraft over the same cities. One call clips their latest orthophoto (7.5 cm per pixel) to a square around the model's lat/lon. The drone path from section 6 is drawn on top, so the three layers line up: the Matterport model's position, the drone that flew the splat, and Vexcel's view from above. Vexcel's own tutorial and Python quickstart (linked from the Vexcel keys card in Discord) go much further: parcels, roof attributes, obliques, object detection and embedding search.

The hackathon Vexcel keys cover Houston and Los Angeles only; anywhere else answers 403.

Model API POST api.matterport.com/api/models/graph · query · variables {"id": "zvKHR9DHNjJ"}
Query
query($id: ID!) { model(id: $id) { geolocation { lat long } } }
Response (real, trimmed)
{
 "data": {
  "model": {
   "geolocation": {
    "lat": "34.0934917",
    "long": "-118.3171000"
   }
  }
 }
}
Vexcel post https://api.vexcelgroup.com/v2/ortho/extract · HTTP 200
Request body (key goes in the X-API-KEY header)
{
 "wkt": "POLYGON((-118.31785932808691 34.092862882177506,-118.31634067191308 34.092862882177506,-118.31634067191308 34.094120517822496,-118.31785932808691 34.094120517822496,-118.31785932808691 34.092862882177506))",
 "srid": 4326,
 "layer": "urban,urban-r,wide-area,urban-g",
 "crop": "bounding_box",
 "image-format": "jpeg",
 "destination-dimensions": "1400,1400",
 "attribution": "false"
}
Response
<image/jpeg, 825,753 bytes>
The code 1.7 s · 0.8 MB downloaded
Output
saved mp_out/s07_vexcel_ortho_drone.jpg  (downloaded so far: 97.5 MB)
Vexcel's ortho of the lot, with the drone photo positions and the Matterport model's lat/lon.
Vexcel's ortho of the lot, with the drone photo positions and the Matterport model's lat/lon. 1041×1050
The CoStar kit (link and zip password on the CoStar keys card) holds the property and listing records. A residential model's Homes listing id (homes_listing_id in the index) joins to residential-listings.csv; a commercial model's CoStar property id joins to the commercial records. The kit is 160 MB, but a zip keeps its table of contents at the end, so with range requests we read just the one file we need. This step is skipped when the CoStar settings aren't set.

Not yet tested. We wrote this cell against the kit's file list, but haven't yet run it with the real zip password, so the join itself is unverified. If it fails, tell us in the track channel.

The code 0.0 s · 0.0 MB downloaded
Output
CoStar kit not configured (COSTAR_ZIP_PASSWORD plus COSTAR_KIT_URL or COSTAR_KIT_ZIP); skipped.
8
MatterPak: mesh and point cloud
A MatterPak is the model's geometry as one zip: a textured OBJ mesh, a coloured point cloud (cloud.xyz, one x y z r g b line per point, metres, Z up, in the same frame as the panos and the wall graph) and floor-plan renders. The API hands out a signed link. It is unlocked for the 232 splat models and is being unlocked for the rest of the hackathon org; a model where it is still locked says so below.

We list the zip's contents without downloading it, then stream just the point cloud (about 100 MB compressed) and keep every 10th point.

Model API POST api.matterport.com/api/models/graph · MatterPak · variables {"id": "zvKHR9DHNjJ"}
Query
query MatterPak($id: ID!) { model(id: $id) {
  bundle(id: "mp:matterpak") { availability }
  assets { resources(format: "matterpak") { status filename url } }
} }
Response (real, trimmed)
{
 "data": {
  "model": {
   "bundle": {
    "availability": "unlocked"
   },
   "assets": {
    "resources": [
     {
      "status": "available",
      "filename": "mp_matterpak_5836-La-Mirada-Ave_zvKHR9DHNjJ.zip",
      "url": "https://cdn-2.matterport.com/models/fd453824d49b4ddd9d7b207747dea986/assets/bundles/aec.zip?…"
     },
     {
      "status": "unavailable",
      "filename": "mp_obj_5836-La-Mirada-Ave_zvKHR9DHNjJ.zip"
     },
     {
      "status": "unavailable",
      "filename": "mp_obj-low-res_5836-La-Mirada-Ave_zvKHR9DHNjJ.zip"
     }
    ]
   }
  }
 }
}
The code 13.4 s · 100.7 MB downloaded
Output
mp_matterpak_5836-La-Mirada-Ave_zvKHR9DHNjJ.zip: 138 MB
  cloud.xyz                                        412.5 MB  (97.7 MB zipped)
  c4210c3617d648aab3191a5dc5560f8b.obj              26.5 MB  (7.4 MB zipped)
  c4210c3617d648aab3191a5dc5560f8b_017.jpg           1.3 MB  (1.3 MB zipped)
  c4210c3617d648aab3191a5dc5560f8b_024.jpg           1.1 MB  (1.1 MB zipped)
  colorplan_000.jpg                                  1.1 MB  (1.1 MB zipped)
  c4210c3617d648aab3191a5dc5560f8b_019.jpg           1.0 MB  (1.0 MB zipped)
  colorplan.pdf                                      1.0 MB  (1.0 MB zipped)
  c4210c3617d648aab3191a5dc5560f8b_012.jpg           1.0 MB  (1.0 MB zipped)
kept 1,039,630 points (every 10th); extent [17.6 11.3  5.6] m
saved mp_out/s08_point_cloud.jpg  (downloaded so far: 198.2 MB)

Total downloaded by this notebook: 198 MB
The MatterPak point cloud (every 10th point), from above with the ceiling cut away, and as an oblique cut-away.
The MatterPak point cloud (every 10th point), from above with the ceiling cut away, and as an oblique cut-away. 1773×854
Walk the point cloud
400,000 points
cut at
Open the point-cloud viewer (3.6 MB)
Drag to orbit, scroll to zoom; the slider removes everything above a height.

9
Ideas and help
What we haven't solved yet. These are real problems on our team's board. Pick one, build it this weekend, and come show us.

#	Problem	Data to start from
1	Understand commercial spaces. We've focused on homes; offices, shops and warehouses have room types we don't label yet.	sections 2 and 5 on a commercial model (segment == commercial)
2	Find and count amenities. Spot every gym, pool, lounge and laundry in a space, place it, count it.	panoramas (4), rooms (5), point cloud (8)
3	Agentic annotation. An agent that walks a space and labels what it finds.	panoramas and their positions (4), rooms (5)
4	Search inside panoramas and meshes. Find spaces by what's in them: "sunlit kitchen with an island".	skybox faces (4), mesh (8)
5	Splats as an in-between representation. The 3D format between photos and everything else.	splat and drone photos (6)
6	Refurnish: restage a room. Put furniture back into an empty room, in a new style.	furnished and defurnished panoramas (4)
Several of these would shine inside the 3D tour itself, with the Showcase SDK. And two ideas across the track's layers: create Gaussian splats from Vexcel's aerial imagery, and learn to predict CoStar listing amenities from the Matterport models of the same places.

Where to look.

The hackathon site: the Model Playground (GraphiQL with your key), the API reference, the splat dataset, and this page.
Model API reference: https://matterport.github.io/developer-docs/api/ · Showcase SDK: https://matterport.github.io/developer-docs/overview/
models_index.csv and AGENTS.md (for your coding agent), next to this notebook.
Find us. Ask in #costar-group on Discord or with /ask-costar, or find us at the CoStar track: Azwad Sabik, Ilia Glazkov, Lucas Hayne, Olaf Brandt, Ted Weidling (the API) and Guillermo Bruce (on Discord). Lucas is the one to ask about semantic search. Help us Matterport the world this weekend.

·
Run time and size
One run of the notebook for this model, on a laptop with a fast connection (45 s and 198 MB in all). The page itself loads none of that: its viewers load on demand.

#	Section	Seconds	MB downloaded
1	Setup and key check	2.0	0.0
2	Find models near a point	0.3	0.0
3	Model basics	0.5	0.9
4	Panoramas	3.1	5.4
5	Rooms and floor plan	1.4	1.1
6	Splat and drone photos	22.5	89.4
7	The same lot from above	1.7	0.8
8	MatterPak: mesh and point cloud	13.4	100.7
Generated by workshop/matterport/tools/build_reference.py from one run of matterport_quickstart.py with a hackathon key, 2026-11-13 14:57 EST. Responses are real and trimmed; signed links have their tokens removed, and no key appears on this page. Hackathon use only.
One house, inside and out
contents
Setup and key check
Find models near a point
Model basics
Panoramas
Rooms and floor plan
Splat and drone photos
The same lot from above
MatterPak: mesh and point cloud
Ideas and help
Run time and size