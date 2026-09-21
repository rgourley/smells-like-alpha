# Third-party notices

The code in this repo is MIT licensed (see LICENSE). It builds on the work below.

## Brain wiring: MaleCNS v1.0

`data/circuit/` and `viewer/model/brain/` are made from the MaleCNS v1.0 connectome by FlyEM at HHMI Janelia, Google Research and the Cambridge Connectomics Group, https://male-cns.janelia.org. License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/.

Berg S. et al. Sexual dimorphism in the complete connectome of the *Drosophila* male central nervous system. 2025. bioRxiv 2025.10.09.680999.

Changes: `data/circuit/` keeps the 7,443 neurons of the olfactory pathway and the connections among them. `viewer/model/brain/` holds simplified neuropil meshes.

## Neuron model: Shiu et al.

The equations and parameters in `flybrain/brain.py` follow the model code of Shiu P. K. et al., "A *Drosophila* computational brain model reveals sensorimotor processing", Nature 634, 210–219 (2024), https://github.com/philshiu/Drosophila_brain_model.

```
MIT License

Copyright (c) 2023 Philip Shiu and Nico Spiller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Fly body: NeuroMechFly

`viewer/model/body.bin`, `body.json` and `rig.json` are made from the meshes and joint data of NeuroMechFly (flygym), Neuroengineering Laboratory, EPFL, https://github.com/NeLy-EPFL/flygym. License: Apache-2.0, in `viewer/model/LICENSE-flygym.txt`. Changes: the 39 meshes are packed into one indexed file (`scripts/build_body_pack.py`), colored as a male *Drosophila melanogaster*, and posed by the viewer.

## Table, floor and room light: Poly Haven

`viewer/model/table/` and `viewer/textures/` are from Poly Haven, https://polyhaven.com (wooden_table_02, diagonal_parquet, lythwood_room). License: CC0. Changes: the floor texture and the room-light panorama are reduced in size (`scripts/build_room_light.py`), and the backdrop is a blurred crop of the panorama.

## three.js

`viewer/vendor/` holds three.js r128 and its GLTF and RGBE loaders, https://threejs.org. License: MIT, Copyright 2010-2021 three.js authors.

## Simulator

Brian2 is installed as a dependency and is not included here. Stimberg M., Brette R., Goodman D. F. M. Brian 2, an intuitive and efficient neural simulator. eLife 8, e47314 (2019).
