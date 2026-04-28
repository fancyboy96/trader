-- Setup CSV export settings
.headers on
.mode csv
.output scyne_contracts_export.csv

SELECT 
    c.id,
    c.contract_number,
    c.title,
    c.contracting_agency,
    c.status,
    c.category,
    c.value_aud,
    c.value_display,
    c.awarded_date,
    c.start_date,
    c.end_date,
    c.procurement_method,
    b.name AS contractor_name,
    b.abn AS contractor_abn
FROM contracts c
JOIN businesses b ON c.prime_contractor_id = b.id
WHERE 
    b.name LIKE '%Scyne%' 
    OR b.name LIKE '%PricewaterhouseCoopers%'
    OR b.abn = '20607773295'
ORDER BY c.awarded_date DESC;

-- Reset output to terminal (optional)
.output stdout
