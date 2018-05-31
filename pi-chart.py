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
SIDE = 8.5 * 72
# Aspect ratio of drawing, width / height.
ASPECT = 11.0 / 8.5
# Leading ratio for font
LEADING = 1.8

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

# Abbreviate names for better readability at
# tiny sizes.
def abbrev(name):
    words = name.split()
    nwords = len(words)
    assert nwords > 0
    if nwords == 1:
        return name
    if words[nwords - 1] == "Systems":
        words[nwords - 1] == "S"
        nwords -= 1
    for i in range(nwords - 1):
        words[i] = words[i][0]
    return ' '.join(words)

# Accumulate PI materials in a form
# ready for drawing.
mats = dict()
mat_tiers = [[] for _ in range(len(tiers))]
class Mat(object):
    "PI material in drawing."
    
    def __init__(self, tier, tid, name, inputs):
        self.tier = tier
        self.tid = tid
        self.name = abbrev(name)
        self.inputs = inputs
        self.x = None
        self.y = None

for t in range(len(tiers)):
    for pm, _, inputs  in tiers[t]:
        tid = pm["typeID"]
        mat = Mat(t, tid, pm["typeName"], inputs)
        mats[tid] = mat
        mat_tiers[t].append(mat.tid)

# Set up Cairo for drawing. Origin is in upper-left corner.
height = SIDE
width = round(ASPECT * SIDE)
surface = cairo.SVGSurface("pi-chart.svg", width, height)
ctx = cairo.Context(surface)
ctx.select_font_face("sans-serif",
                     cairo.FontSlant.NORMAL,
                     cairo.FontWeight.BOLD)
font_face = ctx.get_font_face()

# Set up column widths and heights.
col_margin = 0.05 * width
row_margin = 0.05 * height
gutter_width = 0.05 * width
ncols = len(mat_tiers)
row_maxwidth = [None] * ncols
nrow = [None] * ncols
font_height = 0.0
font_ascent = 0.0
for i in range(ncols):
    mat_tier = mat_tiers[i]
    max_width = 0.0
    acc_height = None
    nrow[i] = len(mat_tier)
    for t in mat_tier:
        m = mats[t]
        name = m.name
        extents = ctx.text_extents(name)
        m.width = extents.width
        font_height = max(font_height, extents.height)
        font_ascent = max(font_ascent, -extents.y_bearing)
        max_width = max(max_width, extents.width)
    row_maxwidth[i] = max_width
font_height *= LEADING
total_width = 2.0 * col_margin
total_width += (ncols - 1) * gutter_width
total_width += sum(row_maxwidth)
total_height = 2.0 * row_margin
total_height += max(nrow) * font_height
maxpect = min(width / total_width, height / total_height)
ctx.scale(maxpect, maxpect)
width /= maxpect
height /= maxpect

def draw_rect(ctx, width, height):
    ctx.rel_line_to(0, height)
    ctx.rel_line_to(width, 0)
    ctx.rel_line_to(0, -height)
    ctx.rel_line_to(-width, 0)

# Show a frame.
if False:
    ctx.move_to(col_margin, row_margin)
    draw_rect(ctx, width - 2 * col_margin,
              height - 2 * row_margin)
    ctx.set_source_rgb(0.5, 0.5, 1.0)
    ctx.set_line_width(2)
    ctx.stroke()


# Show column frames.
if False:
    next_x = col_margin
    for i in range(0, ncols):
        col_height = nrow[i] * font_height
        ctx.move_to(next_x, (height - col_height) / 2.0)
        draw_rect(ctx, row_maxwidth[i], col_height)
        next_x += row_maxwidth[i] + gutter_width
    ctx.set_source_rgb(0.5, 0.5, 0.5)
    ctx.set_line_width(2)
    ctx.stroke()

# Show column texts.
x = col_margin
for i in range(0, ncols):
    col_height = nrow[i] * font_height
    y = (height - col_height) / 2.0 + font_ascent
    for mid in mat_tiers[i]:
        m = mats[mid]
        m.x = x
        m.y = y
        ctx.move_to(x, y)
        ctx.show_text(m.name)
        y += font_height
    x += row_maxwidth[i] + gutter_width
ctx.set_source_rgb(0.0, 0.0, 0.0)
ctx.set_line_width(2)
ctx.stroke()

# Show lines.

for i in range(1, ncols):
    for mid in mat_tiers[i]:
        m = mats[mid]
        for iid in m.inputs:
            inp = mats[iid]
            ctx.move_to(m.x, m.y)
            ctx.line_to(inp.x + inp.width, inp.y)
ctx.set_source_rgb(0.25, 0.5, 1.0)
ctx.set_line_width(2)
ctx.stroke()

surface.finish()
