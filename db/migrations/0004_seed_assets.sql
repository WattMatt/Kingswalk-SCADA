-- Migration: 0004_seed_assets
-- Seeds 9 main boards, all distribution boards, and 104 breakers from sld_per_mb_extract.json
-- Idempotent: ON CONFLICT DO NOTHING on all inserts.

BEGIN;

-- ============================================================
-- 1. Measuring packages
-- ============================================================
INSERT INTO assets.measuring_package (code, description) VALUES
  ('MP2', 'Measuring Package 2 — 8-function (V, I, P, Q, S, PF, f, THD)'),
  ('MP4', 'Measuring Package 4 — 6-function (V, I, P, Q, S, PF)')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 2. Main boards (9 rows)
-- ============================================================
INSERT INTO assets.main_board (code, drawing, vlan_id, subnet, gateway_ip) VALUES
  ('MB-1.1', '643.E.301', 11, '10.10.11.0/24', '10.10.11.1'),
  ('MB-2.1', '643.E.302', 21, '10.10.21.0/24', '10.10.21.1'),
  ('MB-2.2', '643.E.303', 22, '10.10.22.0/24', '10.10.22.1'),
  ('MB-2.3', '643.E.304', 23, '10.10.23.0/24', '10.10.23.1'),
  ('MB-3.1', '643.E.305', 31, '10.10.31.0/24', '10.10.31.1'),
  ('MB-4.1', '643.E.306', 41, '10.10.41.0/24', '10.10.41.1'),
  ('MB-5.1', '643.E.307', 51, '10.10.51.0/24', '10.10.51.1'),
  ('MB-5.2', '643.E.308', 52, '10.10.52.0/24', '10.10.52.1'),
  ('MB-5.3', '643.E.309', 53, '10.10.53.0/24', '10.10.53.1')
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 3. Distribution boards (all unique db_code values)
-- ============================================================
INSERT INTO assets.distribution_board (code, name, area_m2, cable_spec) VALUES
  -- 643.E.301 / MB-1.1
  ('DB-17',    'PEP CELL',                   56.81,   '4C x 25mm² ALU CABLE'),
  ('DB-17A',   'LL KING PIE',                61.03,   '4C x 25mm² ALU CABLE'),
  ('DB-17B',   'PIE MR PRICE CELL',          50.44,   '4C x 25mm² ALU CABLE'),
  ('DB-18',    'SHOPRITE',                   2716.13, '4Cx120mm² ALU CABLES'),
  ('DB-19',    'TRUWORTHS',                  922.22,  '4C x 120mm² ALU CABLE'),
  ('DB-20/21', 'THS IDENTITY / SYNC',        332.36,  '4C x 70mm² ALU CABLE'),
  ('DB-22/23', 'JET',                        842.63,  '4C x 120mm² ALU CABLE'),
  ('DB-24',    'SPORTSCENE',                 401.98,  '4C x 70mm² ALU CABLE'),
  ('DB-24A',   NULL,                         NULL,    NULL),
  ('DB-26',    'EXACT',                      319.09,  NULL),
  -- 643.E.302 / MB-2.1
  ('DB-05',    NULL,                         NULL,    NULL),
  ('DB-08',    NULL,                         NULL,    NULL),
  ('DB-08A',   NULL,                         NULL,    NULL),
  ('DB-09',    NULL,                         NULL,    NULL),
  ('DB-10',    NULL,                         NULL,    NULL),
  ('DB-11',    NULL,                         NULL,    NULL),
  ('DB-11A',   NULL,                         NULL,    NULL),
  ('DB-12',    NULL,                         NULL,    NULL),
  -- 643.E.303 / MB-2.2
  ('DB-01',    'VACANT',                     131.50,  '4C x 35mm² ALU CABLE'),
  ('DB-01A',   'T WATLOO',                   800.25,  '4C x 35mm² ALU CABLE'),
  ('DB-01B',   'KINGSLEY BEVERAGES',         250.67,  '4C x 120mm² ALU CABLE'),
  ('DB-01C',   'KIT KAT',                    472.30,  '4C x 70mm² ALU CABLE'),
  ('DB-01D',   'CAPITEC ATM',                28.52,   '4C x 25mm² ALU CABLE'),
  ('DB-02',    'VACANT',                     150.49,  '4C x 35mm² ALU CABLE'),
  ('DB-03',    'MAX BOX',                    50.20,   '4C x 25mm² ALU CABLE'),
  ('DB-03A',   'ACKERMANS CONNECT',          52.13,   '4C x 25mm² ALU CABLE'),
  ('DB-04',    NULL,                         NULL,    NULL),
  -- 643.E.304 / MB-2.3
  ('DB-13/14', 'VACANT',                     682.41,  '4C x 120mm² ALU CABLE'),
  ('DB-15',    'CLICKS',                     802.76,  '4C x 120mm² ALU CABLE'),
  ('DB-16',    'S SHOPRITE LIQUOR',          252.08,  '4C x 120mm² ALU CABLE'),
  -- 643.E.305 / MB-3.1
  ('DB-74',    'SPUR',                       355.31,  '4C x 95mm² ALU CABLE'),
  ('DB-75',    'KFC',                        201.83,  '4C x 95mm² ALU CABLE'),
  ('DB-76',    'STEERS & DEBONAIRS',         273.55,  '4C x 95mm² ALU CABLE'),
  ('DB-77',    'RS ROCOMAMA''S',             275.80,  '4C x 95mm² ALU CABLE'),
  ('DB-78',    'CONVERSE',                   112.34,  '4C x 35mm² ALU CABLE'),
  ('DB-78A',   'CAPITEC ATM',                10.06,   '4C x 25mm² ALU CABLE'),
  ('DB-80',    'ATM VACANT',                 79.48,   '4C x 25mm² ALU CABLE'),
  ('DB-80A',   'SPECSAVERS',                 74.41,   '4C x 25mm² ALU CABLE'),
  ('DB-81',    'ERS VACANT',                 52.85,   '4C x 25mm² ALU CABLE'),
  ('DB-82',    'SKIPPER BAR',                151.91,  '4C x 35mm² ALU CABLE'),
  ('DB-83',    'VACANT',                     214.78,  '4C x 50mm² ALU CABLE'),
  ('DB-84',    'DUNNS',                      275.71,  '4C x 50mm² ALU CABLE'),
  ('DB-85',    'VICTORY LAB',                191.81,  '4C x 35mm² ALU CABLE'),
  ('DB-86',    'VACANT',                     271.76,  '4C x 50mm² ALU CABLE'),
  ('DB-86A',   'POWER FASHION',              307.18,  '4C x 70mm² ALU CABLE'),
  ('DB-87',    'VACANT',                     204.28,  '4C x 50mm² ALU CABLE'),
  ('DB-88',    'VACANT',                     247.83,  '4C x 50mm² ALU CABLE'),
  ('DB-89',    'VACANT',                     121.88,  '4C x 35mm² ALU CABLE'),
  ('DB-89A',   'NEDBANK ATM',                10.06,   '4C x 25mm² ALU CABLE'),
  ('DB-89B',   'CAKE ZONE',                  56.30,   '4C x 25mm² ALU CABLE'),
  ('DB-89C',   'VACANT',                     55.79,   '4C x 25mm² ALU CABLE'),
  ('DB-90',    NULL,                         NULL,    NULL),
  ('DB-92',    'ABS',                        NULL,    NULL),
  ('DB-SR1',   'TORE ROOM 1',               NULL,    NULL),
  -- 643.E.306 / MB-4.1
  ('DB-46',    'FNB',                        252.38,  '4C x 50mm² ALU CABLE'),
  ('DB-47',    'STANDARD BANK',              221.46,  '4C x 50mm² ALU CABLE'),
  ('DB-48',    'ANK VACANT',                 65.55,   '4C x 50mm² ALU CABLE'),
  ('DB-48A',   'ATM',                        11.71,   '4C x 25mm² ALU CABLE'),
  ('DB-48B',   'VACANT',                     59.95,   '4C x 25mm² ALU CABLE'),
  ('DB-48C',   'VACANT',                     104.72,  '4C x 35mm² ALU CABLE'),
  ('DB-52A',   'PEP HOME',                   271.11,  '4C x 50mm² ALU CABLE'),
  ('DB-53',    'OME MR PRICE & KIDS',        613.09,  '4C x 50mm² ALU CABLE'),
  ('DB-54',    '& KIDS TEKKIE TOWN',         279.70,  '4C x 120mm² ALU CABLE'),
  ('DB-55',    'VACANT',                     426.76,  '4C x 70mm² ALU CABLE'),
  ('DB-57',    'ACKERMANS',                  750.78,  '4C x 120mm² ALU CABLE'),
  ('DB-58/59', 'STUDIO 88',                  402.66,  '4C x 70mm² ALU CABLE'),
  ('DB-60',    'THE FIX',                    313.38,  '4C x 70mm² ALU CABLE'),
  ('DB-62',    'SIDE STEP',                  105.75,  '4C x 35mm² ALU CABLE'),
  ('DB-64',    'VACANT',                     618.94,  '4C x 120mm² ALU CABLE'),
  ('DB-66',    'POLO',                       112.55,  '4C x 35mm² ALU CABLE'),
  ('DB-66A',   'STERNS / VACANT',            57.90,   '4C x 25mm² ALU CABLE'),
  ('DB-67',    'PEDRO',                      154.30,  '4C x 35mm² ALU CABLE'),
  ('DB-67A',   'VACANT',                     NULL,    '4C x 25mm² ALU CABLE'),
  ('DB-68',    'ROMANS PIZZA',               124.91,  '4C x 95mm² ALU CABLE'),
  ('DB-69',    'HUNGRY LION',                145.54,  '4C x 95mm² ALU CABLE'),
  ('DB-70',    NULL,                         NULL,    NULL),
  -- 643.E.307 / MB-5.1
  ('DB-38',    NULL,                         NULL,    NULL),
  ('DB-38A',   NULL,                         NULL,    NULL),
  ('DB-39',    NULL,                         NULL,    NULL),
  ('DB-FIRE',  NULL,                         NULL,    NULL),
  ('DB-DOMESTIC', NULL,                      NULL,    NULL),
  ('DB-SR2',   NULL,                         NULL,    NULL),
  -- 643.E.308 / MB-5.2
  ('DB-40',    'VACANT',                     65.95,   '4C x 25mm² ALU CABLE'),
  ('DB-40A',   'T VACANT',                   65.95,   '4C x 25mm² ALU CABLE'),
  ('DB-41',    'T TORGA OPTICAL',            62.19,   '4C x 25mm² ALU CABLE'),
  ('DB-42',    'AMERICAN SWISS',             60.03,   '4C x 25mm² ALU CABLE'),
  ('DB-43',    'OLD MUTUAL',                 216.94,  '4C x 50mm² ALU CABLE'),
  ('DB-44',    'CAPITEC',                    275.29,  '4C x 50mm² ALU CABLE'),
  ('DB-44A',   'MOJO',                       304.08,  '4C x 70mm² ALU CABLE'),
  ('DB-45',    'BRADLOWS',                   329.93,  '4C x 70mm² ALU CABLE'),
  ('DB-45A',   NULL,                         NULL,    NULL),
  ('DB-93',    'CASHBUILD',                  1416.65, NULL),
  -- 643.E.309 / MB-5.3
  ('DB-27/28', 'TOTALSPORTS',               381.34,  '4C x 70mm² ALU CABLE'),
  ('DB-29',    'S VACANT',                   287.09,  '4C x 50mm² ALU CABLE'),
  ('DB-30',    'T LEGIT',                    251.80,  '4C x 50mm² ALU CABLE'),
  ('DB-31',    'JOHN GRAIG',                 211.80,  '4C x 50mm² ALU CABLE'),
  ('DB-32',    'VACANT',                     187.76,  '4C x 35mm² ALU CABLE'),
  ('DB-32A',   'CODE',                       152.07,  '4C x 35mm² ALU CABLE'),
  ('DB-33',    'REFINERY',                   162.03,  '4C x 35mm² ALU CABLE'),
  ('DB-34',    'VOLPES',                     451.62,  '4C x 70mm² ALU CABLE'),
  ('DB-36',    'ARTHUR FORD',                50.24,   '4C x 25mm² ALU CABLE'),
  ('DB-37',    'DISCHEM',                    900.47,  NULL),
  ('DB-SEC',   'SECURITY',                   NULL,    NULL),
  ('DB-CM',    NULL,                         NULL,    NULL)
ON CONFLICT (code) DO NOTHING;

-- ============================================================
-- 4. Breakers
-- Naming convention: device_ip = 10.10.{VLAN}.{11 + offset}
-- Each MB section assigns IPs sequentially starting at .11
-- ============================================================

-- ---- MB-1.1 (VLAN 11, drawing 643.E.301, 10 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-1.1')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-17',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.11.11'::inet),
  ('DB-17A',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.11.12'::inet),
  ('DB-17B',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.11.13'::inet),
  ('DB-18',   'TS2', 'Tmax XT', 800, 'TP', 'MP2', '10.10.11.14'::inet),
  ('DB-19',   'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.11.15'::inet),
  ('DB-20/21','TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.11.16'::inet),
  ('DB-22/23','TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.11.17'::inet),
  ('DB-24',   'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.11.18'::inet),
  ('DB-24A',  'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.11.19'::inet),
  ('DB-26',   'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.11.20'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-2.1 (VLAN 21, drawing 643.E.302, 8 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-2.1')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-05',  'TS2', 'Tmax XT', 600, 'TP', 'MP2', '10.10.21.11'::inet),
  ('DB-08',  'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.21.12'::inet),
  ('DB-08A', 'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.21.13'::inet),
  ('DB-09',  'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.21.14'::inet),
  ('DB-10',  'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.21.15'::inet),
  ('DB-11',  'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.21.16'::inet),
  ('DB-11A', 'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.21.17'::inet),
  ('DB-12',  'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.21.18'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-2.2 (VLAN 22, drawing 643.E.303, 9 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-2.2')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-01',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.22.11'::inet),
  ('DB-01A',  'TS2', 'Tmax XT', 200, 'TP', 'MP2', '10.10.22.12'::inet),
  ('DB-01B',  'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.22.13'::inet),
  ('DB-01C',  'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.22.14'::inet),
  ('DB-01D',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.22.15'::inet),
  ('DB-02',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.22.16'::inet),
  ('DB-03',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.22.17'::inet),
  ('DB-03A',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.22.18'::inet),
  ('DB-04',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.22.19'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-2.3 (VLAN 23, drawing 643.E.304, 3 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-2.3')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-13/14', 'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.23.11'::inet),
  ('DB-15',    'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.23.12'::inet),
  ('DB-16',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.23.13'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-3.1 (VLAN 31, drawing 643.E.305, 24 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-3.1')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-74',   'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.31.11'::inet),
  ('DB-75',   'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.31.12'::inet),
  ('DB-76',   'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.31.13'::inet),
  ('DB-77',   'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.31.14'::inet),
  ('DB-78',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.31.15'::inet),
  ('DB-78A',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.16'::inet),
  ('DB-80',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.17'::inet),
  ('DB-80A',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.18'::inet),
  ('DB-81',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.19'::inet),
  ('DB-82',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.31.20'::inet),
  ('DB-83',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.21'::inet),
  ('DB-84',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.22'::inet),
  ('DB-85',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.31.23'::inet),
  ('DB-86',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.24'::inet),
  ('DB-86A',  'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.31.25'::inet),
  ('DB-87',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.26'::inet),
  ('DB-88',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.27'::inet),
  ('DB-89',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.31.28'::inet),
  ('DB-89A',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.29'::inet),
  ('DB-89B',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.30'::inet),
  ('DB-89C',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.31'::inet),
  ('DB-90',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.32'::inet),
  ('DB-92',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.31.33'::inet),
  ('DB-SR1',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.31.34'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-4.1 (VLAN 41, drawing 643.E.306, 22 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-4.1')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-46',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.41.11'::inet),
  ('DB-47',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.41.12'::inet),
  ('DB-48',    'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.41.13'::inet),
  ('DB-48A',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.41.14'::inet),
  ('DB-48B',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.41.15'::inet),
  ('DB-48C',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.41.16'::inet),
  ('DB-52A',   'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.41.17'::inet),
  ('DB-53',    'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.41.18'::inet),
  ('DB-54',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.41.19'::inet),
  ('DB-55',    'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.41.20'::inet),
  ('DB-57',    'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.41.21'::inet),
  ('DB-58/59', 'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.41.22'::inet),
  ('DB-60',    'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.41.23'::inet),
  ('DB-62',    'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.41.24'::inet),
  ('DB-64',    'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.41.25'::inet),
  ('DB-66',    'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.41.26'::inet),
  ('DB-66A',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.41.27'::inet),
  ('DB-67',    'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.41.28'::inet),
  ('DB-67A',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.41.29'::inet),
  ('DB-68',    'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.41.30'::inet),
  ('DB-69',    'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.41.31'::inet),
  ('DB-70',    'TM3', 'Tmax XT', 150, 'TP', 'MP2', '10.10.41.32'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-5.1 (VLAN 51, drawing 643.E.307, 6 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-5.1')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-38',      'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.51.11'::inet),
  ('DB-38A',     'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.51.12'::inet),
  ('DB-39',      'TS1', 'Tmax XT', 200, 'TP', 'MP2', '10.10.51.13'::inet),
  ('DB-FIRE',    'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.51.14'::inet),
  ('DB-DOMESTIC','TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.51.15'::inet),
  ('DB-SR2',     'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.51.16'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-5.2 (VLAN 52, drawing 643.E.308, 10 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-5.2')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-40',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.52.11'::inet),
  ('DB-40A', 'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.52.12'::inet),
  ('DB-41',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.52.13'::inet),
  ('DB-42',  'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.52.14'::inet),
  ('DB-43',  'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.52.15'::inet),
  ('DB-44',  'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.52.16'::inet),
  ('DB-44A', 'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.52.17'::inet),
  ('DB-45',  'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.52.18'::inet),
  ('DB-45A', 'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.52.19'::inet),
  ('DB-93',  'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.52.20'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

-- ---- MB-5.3 (VLAN 53, drawing 643.E.309, 12 breakers) ----
WITH mb AS (SELECT id FROM assets.main_board WHERE code = 'MB-5.3')
INSERT INTO assets.breaker
  (main_board_id, label, breaker_code, abb_family, rating_amp, poles, mp_code, feeds_db_id, device_ip, protocol)
SELECT
  mb.id,
  b.label,
  b.breaker_code,
  b.abb_family,
  b.rating_amp,
  b.poles,
  b.mp_code,
  db.id,
  b.device_ip,
  'modbus_tcp'
FROM mb,
LATERAL (VALUES
  ('DB-27/28', 'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.53.11'::inet),
  ('DB-29',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.53.12'::inet),
  ('DB-30',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.53.13'::inet),
  ('DB-31',    'TM3', 'Tmax XT', 100, 'TP', 'MP2', '10.10.53.14'::inet),
  ('DB-32',    'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.53.15'::inet),
  ('DB-32A',   'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.53.16'::inet),
  ('DB-33',    'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.53.17'::inet),
  ('DB-34',    'TM3', 'Tmax XT', 120, 'TP', 'MP2', '10.10.53.18'::inet),
  ('DB-36',    'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.53.19'::inet),
  ('DB-37',    'TM3', 'Tmax XT', 200, 'TP', 'MP2', '10.10.53.20'::inet),
  ('DB-SEC',   'TM3', 'Tmax XT', 60,  'TP', 'MP2', '10.10.53.21'::inet),
  ('DB-CM',    'TM3', 'Tmax XT', 80,  'TP', 'MP2', '10.10.53.22'::inet)
) AS b(label, breaker_code, abb_family, rating_amp, poles, mp_code, device_ip)
JOIN assets.distribution_board db ON db.code = b.label
ON CONFLICT DO NOTHING;

COMMIT;
