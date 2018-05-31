#!/usr/bin/python3
# Copyright © 2018 Po Huit
# [This program is licensed under the "MIT License"]
# Please see the file LICENSE in the source
# distribution of this software for license terms.

# Make an EVE Planetary Interaction chart.

# https://docs.google.com/document/d/1g03tgHtCoXguI7A42DS18Vozx8LFUHoIC6F_AfLYZ9c/edit

# Location of SDE database.
eveSDE = "sde.sqlite"

import sqlite3

db = sqlite3.connect(eveSDE)

def makeCursor():
    c = db.cursor()
    c.row_factory = sqlite3.Row
    return c

# Collect information about planetary materials from the SDE.
c = makeCursor()

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

for t in range(len(tiers)):
    print("tier", t)
    for m in tiers[t]:
        print(" ", m[0]["typeName"])
