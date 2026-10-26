# V5 runtime assets — refined non-pixel 2D

Mode: built-in OpenAI image generation. All runtime images are saved in this project at the following paths, relative to the project root:

| Asset | Prompt specification |
|---|---|
| `assets/painted/student-walk-v5.png` | Original Taiwanese student, natural proportions, matte linen and canvas, flat ink/gouache animation, 4×4 walking atlas, transparent alpha; no pixel art, toy or 3D render. |
| `assets/painted/trees-v5.png` | Four hand-painted camphor, banyan, willow and flamegold silhouettes in a 2×2 transparent atlas, nuanced leaves and muted watercolor; no 3D modeling or pixel grid. |
| `assets/painted/dorm-facades-v5.png` | Four separate building elevations based on official Ren, Shi, Li, Yi photographs; preserve their different tile, window, entrance and stair-screen characteristics, fine ink/watercolor, transparent exterior, no isometric roof planes. Runtime uses Shi, Li, Yi cutouts. |
| `assets/painted/ren-facade-v5.png` | Separate Ren facade based on two official photographs; tile, T-shaped windows, horizontal terracotta courses, AC units, round stair tower and green canopy. Runtime repeats one authored window band to match four visible floors. |
| `assets/painted/room-plans-v5.png` | Four flat overhead furnished room illustrations: official-reference dorm loft-bed/desk arrangement, library, canteen and study room. Shared central walking aisles, matte paper and wood, no pixel or glossy rendered surfaces. |
| `assets/painted/ground-materials-v5.png` | Four hand-painted material swatches: sage grass with dry leaves, worn pedestrian slabs, rounded-stone masonry and muted blue-green freshwater, flat material views with watercolor grain. |

Building reference inputs are identified in `data/dorm_architecture.json`. Official photos remain development references in ignored `work/`, not distributed assets.

All game rendering uses 2D surfaces at native 1280×720 with smooth antialiased fonts and scaling. There is no 3D engine, camera rotation, model, or perspective-scene mode. A drawn facade may retain real curved window shapes, but is placed as flat 2D architecture in the navigable campus.

Original scenes and source from v4 can be recovered from Git's `v4-baseline` tag. They are no longer runtime dependencies. The current game has no ground collectibles, automatic pickups, resource nodes, crafting screen or collection completion target.
