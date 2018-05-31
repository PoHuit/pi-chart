#!/usr/bin/python3
# Copyright © 2018 Po Huit
# [This program is licensed under the "MIT License"]
# Please see the file LICENSE in the source
# distribution of this software for license terms.

# Make an EVE Planetary Interaction chart.

# https://docs.google.com/document/d/1g03tgHtCoXguI7A42DS18Vozx8LFUHoIC6F_AfLYZ9c/edit

# Location of SDE database.
eveSDE = "sde.sqlite"

# Short side of drawing in pixels.
SIDE = 11*96
# Aspect ratio of drawing, width / height.
ASPECT = 11.0 / 8.5

import sqlite3
import cairo

# Set up SQLite3.
db = sqlite3.connect(eveSDE)
c = db.cursor()
c.row_factory = sqlite3.Row

# Collect information about planetary materials from the SDE.

# Get the marketGroupID for planetary materials.
c.execute("""SELECT marketGroupID FROM invMarketGroups
             WHERE marketGroupName = 'Planetary Materials'""")
pmGroup = c.fetchone()["marketGroupID"]

# Get the marketGroupIDs for the various tiers.
pmTiers = [("R0", "Raw Planetary Materials"),
           ("P1", "Processed Planetary Materials"),
           ("P2", "Refined Planetary Materials"),
           ("P3", "Specialized Planetary Materials"),
           ("P4", "Advanced Planetary Materials")]
pmSubgroup = dict()
for tier in range(len(pmTiers)):
    _, name = pmTiers[tier]
    c.execute("""SELECT marketGroupID FROM invMarketGroups
                 WHERE marketGroupName = ?""", (name,))
    pmSubgroup[tier] = c.fetchone()["marketGroupID"]

# Get planetary materials for each tier.
pms = dict()
for tier in pmSubgroup:
    c.execute("""SELECT * FROM invTypes
                 WHERE marketGroupID = ?""", (pmSubgroup[tier],))
    for pm in c:
        typeID = pm["typeID"]
        pms[typeID] = (tier, pm)

# Debugging: show PM info.
if False:
    for tid in pms:
        (tier, pm) = pms[tid]
        print("tier", tier)
        for k in pm.keys():
            print(k, pm[k])
        print()
    exit(0)

# Process PI schematics.
schtypes = dict()
schs = dict()
for tid in pms:
    # No schematic for R0.
    if pms[tid][0] == 0:
        continue
    c.execute("""SELECT * FROM planetSchematicsTypeMap
                 WHERE typeID = ? AND isInput = 0""", (tid,))
    # There is currently only one way to make each material.
    schtype = c.fetchall()
    assert len(schtype) == 1
    schtype = schtype[0]
    schematicID = schtype["schematicID"]
    c.execute("""SELECT * FROM planetSchematicsTypeMap
                 WHERE schematicID = ? AND isInput = 1""", (schematicID,))
    schinputs = [s["typeID"] for s in c.fetchall()]
    schtypes[tid] = (schtype, schinputs)
    c.execute("""SELECT * FROM planetSchematics
                 WHERE schematicID = ?""", (schematicID,))
    schematics = c.fetchall()
    assert len(schematics) == 1
    schs[schematicID] = schematics[0]

# Debugging: show schematic info
if False:
    for tid in pms:
        (tier, pm) = pms[tid]
        print("name", pm["typeName"])
        print("tier", tier)
        (schtype, schinputs) = schtypes[tid]
        print("schtype")
        for k in schtype.keys():
            print(" ", k, schtype[k])
        print("schinputs", schinputs)
        sch = schs[schtype["schematicID"]]
        print("schtype")
        for k in sch.keys():
            print(" ", k, sch[k])
        print()
    exit(0)

# Consolidate all the retrieved data.
tiers = list()
for t in range(len(pmTiers)):
    mats = list()
    for p in pms:
        (tier, pm) = pms[p]
        if t != tier:
            continue
        if t == 0:
            mats.append((pm, None, []))
            continue
        (schtype, inputs) = schtypes[p]
        mats.append((pm, schtype, inputs))
    mats.sort(key=(lambda info: info[0]["typeName"]))
    tiers += [mats]

# Debugging: show tiers
if False:
    for t in range(len(tiers)):
        print("tier", t)
        for m in tiers[t]:
            print(" ", m[0]["typeName"])
    exit(0)

# Accumulate PI materials in a form
# ready for drawing.
mats = dict()
mat_tiers = [[] for _ in range(len(tiers))]
class Mat(object):
    "PI material in drawing."
    
    def __init__(self, tier, tid, name, inputs):
        self.tier = tier
        self.tid = tid
        self.name = name
        self.inputs = inputs
        self.x = None
        self.y = None

for t in range(len(tiers)):
    for pm, _, inputs  in tiers[t]:
        tid = pm["typeID"]
        mat = Mat(t, tid, pm["typeName"], inputs)
        mats[tid] = mat
        mat_tiers[t].append(mat.tid)

# Set up Cairo for drawing. Origin is in lower-left corner.
# width is ASPECT, Height is 1.0.
height = SIDE
width = round(ASPECT * SIDE)
surface = cairo.SVGSurface("pi-map.svg", width, height)
ctx = cairo.Context(surface)
ctx.scale(height, height)
ctx.select_font_face("sans-serif",
                     cairo.FontSlant.NORMAL,
                     cairo.FontWeight.BOLD)
font_face = ctx.get_font_face()

# Set up column widths and heights.
col_margin = 0.05
row_margin = col_margin
gutter_width = 0.05
ncols = len(mat_tiers)
row_maxwidth = [None] * ncols
nrow = [0] * ncols
name_height = None
font_height = None
for i in range(ncols):
    mat_tier = mat_tiers[i]
    nrow[i] = len(mat_tier)
    max_width = 0.0
    for t in mat_tier:
        name = mats[t].name
        extents = ctx.text_extents(name)
        name_height = extents.x_advance
        font_height = extents.height
        max_width = max(max_width, extents.width)
    row_maxwidth[i] = max_width
total_width = 2.0 * col_margin
total_width += (ncols - 1) * gutter_width
total_width += sum(row_maxwidth)
total_height = 2.0 * row_margin
total_height += max(nrow) * name_height
print(total_width, total_height, font_height)
