-- Migration: 0002_canvas_layers
-- Purpose: Add canvas mapping tables for interactive SLD topology and floor plan navigation
-- Date: 2026-04-11
-- Depends on: 0001_initial.sql

BEGIN;

-- ============================================================
-- 1. Canvas — top-level container for each visual view
-- ============================================================
CREATE TABLE assets.canvas (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT        UNIQUE NOT NULL,
    name            TEXT        NOT NULL,
    description     TEXT,
    svg_path        TEXT        NOT NULL,
    width           INT         NOT NULL,
    height          INT         NOT NULL,
    default_zoom    REAL        NOT NULL DEFAULT 1.0,
    min_zoom        REAL        NOT NULL DEFAULT 0.2,
    max_zoom        REAL        NOT NULL DEFAULT 5.0,
    version         INT         NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE assets.canvas IS 'Top-level visual canvas. One row per interactive view (SLD topology, floor plan).';

-- ============================================================
-- 2. Canvas Layer — toggleable groups within a canvas
-- ============================================================
CREATE TABLE assets.canvas_layer (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    canvas_id           UUID        NOT NULL REFERENCES assets.canvas(id) ON DELETE CASCADE,
    code                TEXT        NOT NULL,
    name                TEXT        NOT NULL,
    description         TEXT,
    z_order             INT         NOT NULL DEFAULT 0,
    visible_by_default  BOOLEAN     NOT NULL DEFAULT true,
    min_zoom_visible    REAL,
    max_zoom_visible    REAL,
    style               JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canvas_id, code)
);

COMMENT ON TABLE assets.canvas_layer IS 'Toggleable layer within a canvas. Controls visibility, z-order, and LOD thresholds.';
CREATE INDEX idx_canvas_layer_canvas ON assets.canvas_layer(canvas_id);

-- ============================================================
-- 3. Canvas Hotspot — clickable region linked to an asset
-- ============================================================
CREATE TABLE assets.canvas_hotspot (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    layer_id        UUID        NOT NULL REFERENCES assets.canvas_layer(id) ON DELETE CASCADE,
    asset_id        UUID,
    asset_type      TEXT,
    label           TEXT        NOT NULL,
    shape           TEXT        NOT NULL CHECK (shape IN ('rect', 'circle', 'polygon', 'path', 'line')),
    geometry        JSONB       NOT NULL,
    anchor_x        REAL        NOT NULL,
    anchor_y        REAL        NOT NULL,
    style_default   JSONB       NOT NULL DEFAULT '{}',
    style_active    JSONB       NOT NULL DEFAULT '{}',
    style_selected  JSONB       NOT NULL DEFAULT '{}',
    nav_targets     JSONB       NOT NULL DEFAULT '[]',
    tooltip_template TEXT,
    sort_order      INT         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE assets.canvas_hotspot IS 'Clickable/hoverable region on a canvas layer, linked to an asset in the registry.';
CREATE INDEX idx_hotspot_layer       ON assets.canvas_hotspot(layer_id);
CREATE INDEX idx_hotspot_asset       ON assets.canvas_hotspot(asset_id, asset_type);
CREATE INDEX idx_hotspot_layer_order ON assets.canvas_hotspot(layer_id, sort_order);

-- ============================================================
-- 4. Canvas Nav Route — cross-canvas drill-through links
-- ============================================================
CREATE TABLE assets.canvas_nav_route (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    from_canvas_id  UUID        NOT NULL REFERENCES assets.canvas(id) ON DELETE CASCADE,
    from_hotspot_id UUID        REFERENCES assets.canvas_hotspot(id) ON DELETE SET NULL,
    to_canvas_id    UUID        NOT NULL REFERENCES assets.canvas(id) ON DELETE CASCADE,
    to_hotspot_id   UUID        REFERENCES assets.canvas_hotspot(id) ON DELETE SET NULL,
    to_zoom         REAL,
    label           TEXT        NOT NULL,
    icon            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE assets.canvas_nav_route IS 'Defines navigation links between canvases (e.g. SLD breaker → floor plan location).';
CREATE INDEX idx_nav_from ON assets.canvas_nav_route(from_canvas_id, from_hotspot_id);
CREATE INDEX idx_nav_to   ON assets.canvas_nav_route(to_canvas_id, to_hotspot_id);

-- ============================================================
-- 5. Seed: Two canvases
-- ============================================================
INSERT INTO assets.canvas (code, name, description, svg_path, width, height, default_zoom)
VALUES
    ('sld_topology', 'SLD Topology',
     'Electrical single-line distribution diagram derived from 643.E.300. Shows transformer → main boards → breakers → distribution boards.',
     'canvases/sld_topology.svg', 2400, 1600, 1.0),

    ('floor_plan', 'Mall Floor Plan',
     'Physical floor plan of Kingswalk Mall derived from 2239-100-0-Overall Floor Plan-Rev H. Shows tenant zones, MB rooms, DB positions.',
     'canvases/floor_plan.svg', 3200, 2400, 0.5);

-- ============================================================
-- 6. Seed: Layers for SLD Topology canvas
-- ============================================================
INSERT INTO assets.canvas_layer (canvas_id, code, name, z_order, visible_by_default, min_zoom_visible, style)
SELECT c.id, v.code, v.name, v.z_order, v.visible_by_default, v.min_zoom_visible, v.style::jsonb
FROM assets.canvas c,
(VALUES
    ('transformer',       'Transformer',        10, true,  NULL, '{"fill": "#4A90D9", "stroke": "#2C5F8A", "strokeWidth": 2}'),
    ('main_boards',       'Main Boards',        20, true,  NULL, '{"fill": "#2E7D32", "stroke": "#1B5E20", "strokeWidth": 2}'),
    ('breakers',          'Breakers',           30, true,  1.5,  '{"fill": "#66BB6A", "stroke": "#388E3C", "strokeWidth": 1}'),
    ('cables',            'Cable Runs',         5,  true,  NULL, '{"stroke": "#757575", "strokeWidth": 1.5, "strokeDasharray": "4 2"}'),
    ('measuring_devices', 'Measuring Devices',  25, false, 2.0,  '{"fill": "#7B1FA2", "stroke": "#4A148C", "strokeWidth": 1}'),
    ('alarms',            'Active Alarms',      99, true,  NULL, '{"fill": "#D32F2F", "opacity": 0.8}')
) AS v(code, name, z_order, visible_by_default, min_zoom_visible, style)
WHERE c.code = 'sld_topology';

-- ============================================================
-- 7. Seed: Layers for Floor Plan canvas
-- ============================================================
INSERT INTO assets.canvas_layer (canvas_id, code, name, z_order, visible_by_default, min_zoom_visible, style)
SELECT c.id, v.code, v.name, v.z_order, v.visible_by_default, v.min_zoom_visible, v.style::jsonb
FROM assets.canvas c,
(VALUES
    ('building_shell',      'Building Structure',    1,  true,  NULL, '{"fill": "none", "stroke": "#424242", "strokeWidth": 2}'),
    ('tenant_zones',        'Tenant Zones',          10, true,  NULL, '{"fill": "#C8E6C9", "stroke": "#66BB6A", "strokeWidth": 1, "opacity": 0.6}'),
    ('main_boards',         'Main Board Rooms',      20, true,  NULL, '{"fill": "#1565C0", "stroke": "#0D47A1", "strokeWidth": 2}'),
    ('distribution_boards', 'Distribution Boards',   30, true,  1.5,  '{"fill": "#F57C00", "stroke": "#E65100", "strokeWidth": 1}'),
    ('lighting',            'Lighting Zones',        15, false, 2.0,  '{"fill": "#FFF176", "stroke": "#FBC02D", "strokeWidth": 1, "opacity": 0.4}'),
    ('emergency',           'Emergency / Essential',  5, false, NULL, '{"fill": "#FFCDD2", "stroke": "#E53935", "strokeWidth": 1, "strokeDasharray": "6 3"}')
) AS v(code, name, z_order, visible_by_default, min_zoom_visible, style)
WHERE c.code = 'floor_plan';

-- ============================================================
-- 8. Trigger: auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION assets.trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_canvas_updated_at
    BEFORE UPDATE ON assets.canvas
    FOR EACH ROW EXECUTE FUNCTION assets.trigger_set_updated_at();

CREATE TRIGGER trg_canvas_layer_updated_at
    BEFORE UPDATE ON assets.canvas_layer
    FOR EACH ROW EXECUTE FUNCTION assets.trigger_set_updated_at();

CREATE TRIGGER trg_canvas_hotspot_updated_at
    BEFORE UPDATE ON assets.canvas_hotspot
    FOR EACH ROW EXECUTE FUNCTION assets.trigger_set_updated_at();

COMMIT;
