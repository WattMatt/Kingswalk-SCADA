-- Kingswalk SCADA — continuous aggregates
-- Must run OUTSIDE a transaction block (TimescaleDB requirement).
-- Run AFTER 0001_initial.sql has committed.

-- Continuous aggregates (1-min, 15-min, hourly, daily) for pq_sample
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry.pq_1min
WITH (timescaledb.continuous) AS
SELECT device_id,
       time_bucket('1 minute', ts) AS bucket,
       avg(v_l1_n) AS v_l1_n, avg(v_l2_n) AS v_l2_n, avg(v_l3_n) AS v_l3_n,
       avg(i_l1) AS i_l1, avg(i_l2) AS i_l2, avg(i_l3) AS i_l3,
       avg(p_total) AS p_avg, max(p_total) AS p_max,
       avg(pf_total) AS pf_avg,
       avg(freq_hz) AS freq_avg,
       avg(thd_v) AS thd_v_avg, avg(thd_i) AS thd_i_avg
FROM telemetry.pq_sample
GROUP BY device_id, bucket;

SELECT add_continuous_aggregate_policy('telemetry.pq_1min',
    start_offset => INTERVAL '1 hour',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
