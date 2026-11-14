## How we built it: the agent and data side

**Three CoStar layers, one building at a time.** For each building in an 8-building Houston office portfolio, our agents combine three data layers from the CoStar track:
- **CoStar property records** give each building's type, size, stories and year built. We read the hackathon data kit locally, streaming records instead of loading them whole.
- **Vexcel aerial imagery** gives an orthophoto clipped to each building's roof, fetched by latitude and longitude.
- **Matterport 3D scans** give the panoramas and rooms of our hero building. We join them to CoStar records through the kit's property-to-model table and query them through the Matterport GraphQL Model API.

**An agent team, not a chatbot.** We wired the agents with LangGraph. An orchestrator plans the run and fans out one survey per building, four at a time. Each survey is its own subgraph:
1. A **records agent** turns the CoStar record into a building profile.
2. An **aerial inspector** reads the roof: shape, colour, how much of it is open, shading and existing solar.
3. An **interior inspector** reads the hero's panoramas: lighting, visible HVAC and window type.
4. A **site engineer** applies feasibility rules to propose rooftop solar, LED retrofits and heat pumps, sized to the building.
5. A **verifier** checks every claim before anything is priced.

A quant engine then optimises the portfolio against the owner's carbon target, and a composer builds the owner's workspace from a fixed set of widgets.

**Gemini, through Vertex AI (MLH Gemini track).** Every vision step runs on Gemini through Vertex AI with structured output: the roof inspection, the interior inspection, room labelling and verification. Gemini describes what it sees, as enumerated values, fractions, confidences and boxes on the image, and nothing else. Code computes every area and kilowatt, and the quant engine computes every dollar and tonne. A guardrail rejects any generated sentence containing a number that isn't in the source data.

**A verifier that pushes back.** Each claim goes to the verifier with the image it came from and the inspector's marks drawn on it. The verifier verifies the claim, rejects it, or sends it back with a specific question; for example, it asked whether any photo clearly showed the thermostat the inspector had reported. The inspector re-answers only that question, up to twice, and then the claim is marked unverified. An upgrade enters the optimiser only if the claims behind it are verified. In our final run, 45 of 46 claims were verified, and the verified evidence is what closed the gap to the owner's target.

**Labelling commercial interiors.** Matterport labels rooms in homes but not in offices. Our interior agent labels each room of the hero scan as open office, private office, conference, corridor, lobby, restroom, mechanical/IT, storage or kitchen/break. It judges each room from that room's own panoramas and adds a one-line evidence note, and the verifier checks every label. Matterport sometimes merges a hallway with the offices off it into one "room", so the agent can report a main type plus the other spaces it contains. The labels appear on the floor plan and as pins beside the 3D tour.

**Built to survive the venue Wi-Fi.** Every external call goes through a disk cache: the CoStar kit, Vexcel, Matterport and Gemini. We warm it with one live run, then demo with the cache in read-only mode, so there are no network or model calls on stage. The activity feed is replayed from that real run, including the verifier's send-back.

**What we didn't get to.** Matterport's mesh downloads (MatterPaks) weren't available for our buildings, so the 3D view embeds Matterport's own tour instead. We had no oblique (side-on) imagery, so facades and windows aren't inspected yet.
