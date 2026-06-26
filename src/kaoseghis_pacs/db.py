from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass(frozen=True)
class EGhisDbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    connect_timeout: int = 5
    query_timeout_ms: int = 3000


def _compose_query() -> str:
    return """
WITH t AS (
  SELECT
    m.mwl_key,
    m.eghis_key,
    m.patient_id,
    m.patient_name,
    m.patient_birth_date,
    m.patient_sex,
    m.scheduled_modality,
    m.scheduled_proc_status,
    m.scheduled_dttm,
    m.imaging_request_dttm,
    m.trigger_dttm,
    m.replica_dttm,
    m.accession_no,
    m.scheduled_proc_id,
    m.scheduled_proc_desc,
    m.requested_proc_desc,
    COALESCE(NULLIF(TRIM(m.scheduled_dttm),''),
             NULLIF(TRIM(m.imaging_request_dttm),''),
             NULLIF(TRIM(m.trigger_dttm),''),
             NULLIF(TRIM(m.replica_dttm),'')) AS anchor_dttm,
    split_part(m.eghis_key, '_', 1) AS recept_no_key,
    split_part(m.eghis_key, '_', 2) AS ord_no_key,
    split_part(m.eghis_key, '_', 3) AS ord_seq_no_key
  FROM public.mwl m
  WHERE m.scheduled_proc_status = '100'
)
SELECT
  t.mwl_key,
  t.eghis_key,
  t.patient_id,
  t.patient_name,
  t.patient_birth_date,
  t.patient_sex,
  t.scheduled_modality,
  t.scheduled_proc_status,
  t.scheduled_dttm,
  t.imaging_request_dttm,
  t.trigger_dttm,
  t.replica_dttm,
  t.accession_no,
  t.scheduled_proc_id,
  t.scheduled_proc_desc,
  t.requested_proc_desc,
  t.anchor_dttm,
  o.ord_cd,
  o.ord_ymd,
  o.ord_no,
  o.ord_seq_no,
  o.ord_type,
  o.proc_dept_cd,
  o.dc_yn
FROM t
JOIN public.h2opd_doct_ord o
  ON o.recept_no = t.recept_no_key
 AND CAST(o.ord_no AS text) = t.ord_no_key
 AND CAST(o.ord_seq_no AS text) = t.ord_seq_no_key
WHERE t.anchor_dttm IS NOT NULL
  AND t.anchor_dttm >= %s || '000000'
  AND t.anchor_dttm <= %s || '235959'
  AND o.proc_dept_cd = 'XRAY'
  AND COALESCE(o.dc_yn, 'N') <> 'Y'
ORDER BY t.anchor_dttm, t.mwl_key;
"""


def fetch_active_worklist_rows(cfg: EGhisDbConfig, today_yyyymmdd: str) -> List[dict[str, Any]]:
    query = _compose_query()
    with psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.dbname,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=cfg.connect_timeout,
        cursor_factory=RealDictCursor,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute('SET default_transaction_read_only = on')
            cur.execute('SET statement_timeout = %s', (int(cfg.query_timeout_ms),))
            cur.execute(query, (today_yyyymmdd, today_yyyymmdd))
            return [dict(r) for r in cur.fetchall()]
