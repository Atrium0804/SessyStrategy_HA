SELECT
    starttime,
    ROUND(MAX(CASE WHEN naam = 'discharge' THEN value END), 3) AS discharge,
    ROUND(MAX(CASE WHEN naam = 'import' THEN value END), 3) AS import,
    ROUND(MAX(CASE WHEN naam = 'charge' THEN value END), 3) AS charge,
    ROUND(MAX(CASE WHEN naam = 'pv' THEN value END), 3) AS pv,
    ROUND(MAX(CASE WHEN naam = 'consumption' THEN value END), 3) AS consumption,
    ROUND(MAX(CASE WHEN naam = 'export' THEN value END), 3) AS export,
    ROUND(MAX(CASE WHEN naam = 'inkoop' THEN value END), 3) AS inkoop,
    ROUND(MAX(CASE WHEN naam = 'verkoop' THEN value END), 3) AS verkoop
FROM (
    SELECT DISTINCT
           sm.statistic_id,
           CASE sm.statistic_id
               WHEN 'sensor.netaansluiting_batterij_ontlaad_energie' THEN 'discharge'
               WHEN 'sensor.netaansluiting_import_energie' THEN 'import'
               WHEN 'sensor.netaansluiting_batterij_laad_energie' THEN 'charge'
               WHEN 'sensor.netaansluiting_productie_energie' THEN 'pv'
               WHEN 'sensor.netaansluiting_verbruik_energie' THEN 'consumption'
               WHEN 'sensor.netaansluiting_export_energie' THEN 'export'
               WHEN 'sensor.stroomprijs_inkoop' THEN 'inkoop'
               WHEN 'sensor.stroomprijs_verkoop' THEN 'verkoop'
           END AS naam,
           cast(FROM_UNIXTIME(s.start_ts) as datetime(0)) AS starttime,  # UTC
           s.state - LAG(s.state) OVER (PARTITION BY sm.statistic_id ORDER BY s.start_ts) AS value
    FROM statistics_meta sm
    JOIN statistics s ON sm.id = s.metadata_id
    WHERE sm.statistic_id IN (
        'sensor.netaansluiting_batterij_ontlaad_energie',
        'sensor.netaansluiting_import_energie',
        'sensor.netaansluiting_batterij_laad_energie',
        'sensor.netaansluiting_productie_energie',
        'sensor.netaansluiting_verbruik_energie',
        'sensor.netaansluiting_export_energie',
        'sensor.stroomprijs_inkoop',
        'sensor.stroomprijs_verkoop'
    )

) AS subquery
GROUP BY starttime
ORDER BY starttime ASC;


select sm.statistic_id
     , from_unixtime(s.start_ts) as tijd
     , s.*
from statistics_meta sm
join statistics s on sm.id = s.metadata_id
where sm.statistic_id like '%markt%'
order by s.start_ts desc;