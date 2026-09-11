# Source and dependency notes

This is a local research review package. No new GitHub publication occurs in
this batch. Original NHC source response bytes and embedded XML metadata are
preserved in the input archive, including the stated limitations of wind-radii
envelopes. The package does not claim that inclusion in an envelope proves
realized wind at a point. Rendered maps are derived artifacts, not native NHC
graphics. Synthetic fixtures and exercise watch rules are generated here.

Official input directories:

- https://ftp.nhc.noaa.gov/atcf/gis/fst/
- https://ftp.nhc.noaa.gov/atcf/gis/5day/
- https://www.nhc.noaa.gov/archive/2024/al06/al062024.fstadv.005.shtml
- https://www.nhc.noaa.gov/archive/2024/al06/al062024.fstadv.007.shtml

`sources.json` records actual URLs, response hashes, retrieval times and local
reuse. Source metadata is retained as supplied, including its XML encoding and
native sphere CRS. Code and data terms are separate; no rights to third-party
logos, native imagery or unrelated linked materials are asserted here.

External libraries used are Pillow, Shapely, pyproj/PROJ, pyshp, NumPy, Pydantic
and pytest with their dependencies. Exact installed versions are in the resolved
requirements and SOURCE_FREEZE.json. Installed distribution metadata and license
files are exported in THIRD_PARTY_METADATA.json and dependency_licenses/ where
available. No library wheels, model weights, API credentials or external source
repositories are redistributed in the review ZIP.

The renderer uses Pillow's bundled default font; it requires no downloaded font.
The source audit implements its own elementary ray-crossing test. The text
parsers are existing frozen DisasterTrace source files, included verbatim in
the source snapshot. No VersionRAG/STALE/SpaceNet/CyPortQA reproduction is claimed
by this batch.
