-- For documentation of Lua tag transformations, see docs/lua.md.

-- Objects with any of the following keys will be treated as polygon
polygon_keys = {
    'aeroway',
    'amenity',
    'building',
    'harbour',
    'historic',
    'landuse',
    'leisure',
    'man_made',
    'military',
    'natural',
    'office',
    'place',
    'power',
    'public_transport',
    'shop',
    'sport',
    'tourism',
    'water',
    'waterway',
    'wetland'
}

-- Filtering on nodes, ways, and relations
function filter_tags_generic(keyvalues, numberofkeys)
    if keyvalues['wikidata'] then
      return 0, keyvalues
    else
      return 1, {}
    end
end

-- Filtering on nodes
function filter_tags_node (keyvalues, numberofkeys)
    return filter_tags_generic(keyvalues, numberofkeys)
end

-- Filtering on relations
function filter_basic_tags_rel (keyvalues, numberofkeys)
    -- Filter out objects that are filtered out by filter_tags_generic
    filter, keyvalues = filter_tags_generic(keyvalues, numberofkeys)
    if filter == 1 then
        return filter, keyvalues
    end

    -- -- Filter out all relations except route, multipolygon and boundary relations
    -- if ((keyvalues["type"] ~= "route") and (keyvalues["type"] ~= "multipolygon") and (keyvalues["type"] ~= "boundary")) then
    --     filter = 1
    --     return filter, keyvalues
    -- end

    return filter, keyvalues
end

-- Filtering on ways
function filter_tags_way (keyvalues, numberofkeys)
    filter = 0  -- Will object be filtered out?
    polygon = 0 -- Will object be treated as polygon?
    roads = 0   -- Will object be added to planet_osm_roads?

    -- Filter out objects that are filtered out by filter_tags_generic
    filter, keyvalues = filter_tags_generic(keyvalues, numberofkeys)
    if filter == 1 then
        return filter, keyvalues, polygon, roads
    end

    -- Treat objects with a key in polygon_keys as polygon
    for i,k in ipairs(polygon_keys) do
        if keyvalues[k] then
            polygon=1
            break
        end
    end

    -- Treat objects tagged as area=yes, area=1, or area=true as polygon,
    -- and treat objects tagged as area=no, area=0, or area=false not as polygon
    if ((keyvalues["area"] == "yes") or (keyvalues["area"] == "1") or (keyvalues["area"] == "true")) then
        polygon = 1;
    elseif ((keyvalues["area"] == "no") or (keyvalues["area"] == "0") or (keyvalues["area"] == "false")) then
        polygon = 0;
    end

    return filter, keyvalues, polygon, roads
end

function filter_tags_relation_member (keyvalues, keyvaluemembers, roles, membercount)
    filter = 0     -- Will object be filtered out?
    linestring = 0 -- Will object be treated as linestring?
    polygon = 0    -- Will object be treated as polygon?
    roads = 0      -- Will object be added to planet_osm_roads?
    membersuperseded = {}
    for i = 1, membercount do
        membersuperseded[i] = 0 -- Will member be ignored when handling areas?
    end

    type = keyvalues["type"]

    -- Remove type key
    keyvalues["type"] = nil

    -- Relations with type=boundary are treated as linestring
    if (type == "boundary") then
        linestring = 1
    end
    -- Relations with type=multipolygon and boundary=* are treated as linestring
    if ((type == "multipolygon") and keyvalues["boundary"]) then
        linestring = 1
    -- For multipolygons...
    elseif (type == "multipolygon") then
        -- Treat as polygon
        polygon = 1
        polytagcount = 0;
        -- Count the number of polygon tags of the object
        for i,k in ipairs(polygon_keys) do
            if keyvalues[k] then
                polytagcount = 1
                break
            end
        end
        -- If there are no polygon tags, add tags from all outer elements to the multipolygon itself
        if (polytagcount == 0) then
            for i = 1,membercount do
                if (roles[i] == "outer") then
                    for k,v in pairs(keyvaluemembers[i]) do
                        keyvalues[k] = v
                    end
                end
            end

            f, keyvalues = filter_tags_generic(keyvalues, 1)
            -- check again if there are still polygon tags left
            polytagcount = 0
            for i,k in ipairs(polygon_keys) do
                if keyvalues[k] then
                    polytagcount = 1
                    break
                end
            end
            if polytagcount == 0 then
                filter = 1
            end
        end
        -- For any member of the multipolygon, set membersuperseded to 1 (i.e. don't deal with it as area as well),
        -- except when the member has a key/value combination such that
        --   1) the key occurs in generic_keys
        --   2) the key/value combination is not also a key/value combination of the multipolygon itself
        for i = 1,membercount do
            superseded = 1
            for k,v in pairs(keyvaluemembers[i]) do
                if ((keyvalues[k] == nil) or (keyvalues[k] ~= v)) then
                    superseded = 0;
                    break
                end
            end
            membersuperseded[i] = superseded
        end
    end

    return filter, keyvalues, membersuperseded, linestring, polygon, roads
end
