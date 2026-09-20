# The smell circuit

`neurons.parquet` has 7,443 neurons: `body_id`, `type`, `cls`. `edges.parquet` has the 1,138,899 connections among them: `pre`, `post` (body ids) and `weight`, the synapse count, negative when the connection is inhibitory.

Source: MaleCNS v1.0, FlyEM at HHMI Janelia, Google Research and the Cambridge Connectomics Group, https://male-cns.janelia.org, CC BY 4.0. `scripts/build_circuit.py` makes these files from the full release.
