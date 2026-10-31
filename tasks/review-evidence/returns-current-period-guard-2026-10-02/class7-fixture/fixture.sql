CREATE TABLE companies (id int primary key, cik text, ticker text not null, name text not null);
CREATE TABLE filings (id int primary key, company_id int not null, accession_number text not null, filing_type text not null,
  filing_date timestamptz not null, period_end_date timestamptz, xbrl_data json, created_at timestamptz default now());
CREATE TABLE summaries (id int primary key, filing_id int not null, raw_summary json, schema_version smallint,
  prompt_version text, created_at timestamptz default now(), updated_at timestamptz);
INSERT INTO companies VALUES (1,'1','AAA','A Co'),(2,'2','BBB','B Co'),(3,'3','CCC','C Co');
-- A: pre-#785 latest-financials shape on a 10-Q; the values are the latest 10-K's (2023-12-31) -> mismatch
INSERT INTO filings VALUES (1,1,'0000000001-24-000010','10-Q','2024-08-01','2024-06-30',
 '{"net_income":[{"period":"2023-12-31","value":100,"form":null,"accn":"0000000001-24-000010"},{"period":"2022-12-31","value":90,"form":null,"accn":"0000000001-24-000010"}],
   "total_assets":[{"period":"2023-12-31","value":1000,"form":null,"accn":"0000000001-24-000010"}],"revenue":[]}');
INSERT INTO summaries VALUES (1,1,'{"sections":{"value_drivers":{"returns_on_capital":"Return on assets 10.0%."}}}',2,'summary-2026-09-a');
-- A2: annual 10-K that IS the company's latest 10-K, same pre-#785 shape -> period matches
INSERT INTO filings VALUES (2,1,'0000000001-24-000001','10-K','2024-02-20','2023-12-31',
 '{"net_income":[{"period":"2023-12-31","value":100,"form":null,"accn":"0000000001-24-000001"}]}');
INSERT INTO summaries VALUES (2,2,'{}',2,'summary-2026-09-a');
-- B: companyfacts fallback shape (form set, fact accn; one prior from an older filing)
INSERT INTO filings VALUES (3,2,'0000000002-24-000020','10-Q','2024-08-01','2024-06-30',
 '{"net_income":[{"period":"2024-06-30","value":5,"form":"10-Q","accn":"0000000002-24-000020","period_start":"2024-04-01"},{"period":"2023-06-30","value":4,"form":"10-Q","accn":"0000000002-23-000020","period_start":"2023-04-01"}]}');
INSERT INTO summaries VALUES (3,3,null,null,null);
-- excluded: class 6 (currency present), class 7 without a summary, class 4 (tagged), no snapshot
INSERT INTO filings VALUES (4,3,'0000000003-24-000001','10-K','2024-02-20','2023-12-31',
 '{"net_income":[{"period":"2023-12-31","value":1,"form":"10-K","currency":"USD"}]}');
INSERT INTO summaries VALUES (4,4,null,2,'summary-2026-09-t');
INSERT INTO filings VALUES (5,3,'0000000003-24-000002','10-Q','2024-05-01','2024-03-31',
 '{"net_income":[{"period":"2024-03-31","value":1,"form":null,"accn":"0000000003-24-000002"}]}');
INSERT INTO filings VALUES (6,3,'0000000003-24-000003','10-Q','2024-08-01','2024-06-30',
 '{"net_income":[{"period":"2024-06-30","value":1,"form":"10-Q","currency":"USD","raw_tag":"us-gaap:NetIncomeLoss"}]}');
INSERT INTO summaries VALUES (6,6,null,2,'summary-2026-09-t');
INSERT INTO filings VALUES (7,3,'0000000003-24-000004','10-Q','2024-11-01','2024-09-30',null);
INSERT INTO summaries VALUES (7,7,null,2,'summary-2026-09-t');
