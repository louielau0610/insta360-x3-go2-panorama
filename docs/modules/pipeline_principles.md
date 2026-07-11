# Unified Pipeline Principles

The runtime input is BGR, not a DNG. DNG decoding is a slow, photo-only operation and must occur outside the GO2 video path. A live source must provide two calibrated square fisheyes or their left-right side-by-side arrangement.

The panorama is the authoritative full-sphere record. Cubemap faces are an additional perception representation: `F/R/B/L/U/D` covers all directions, whereas front/left/right views omit the rear and polar regions. The wrapper must not discard the panorama when producing faces.

All geometric tables are immutable after construction. `X5CubemapPipeline` creates both the stitch LUT and cubemap sampler once; `process` only remaps, updates or reuses the seam, projects, and optionally encodes. The default seam update interval is three frames; increasing it trades moving-object response for CPU headroom without changing the output coordinate contract. Detection should consume `faces` in memory. JPEG encoding is only for transport or logging because it materially reduces the real-time budget.

The wrapper exposes no DNG decoding, network transport, or robot-body transform. Those responsibilities remain separate so their latency and failure modes do not alter the stitching/cubemap coordinate contract.
