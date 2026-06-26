import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from kaoseghis_pacs import cfind, payload


class TestUtf8CFindOutput(unittest.TestCase):
    def setUp(self):
        self.manual_payload = [
            {
                'patient_id': '7435',
                'patient_name': '이진성',
                'patient_birth_date': '19830210',
                'patient_sex': 'M',
                'modality': 'CR',
                'station_aet': 'INNOVISION',
                'accession_no': 'UTF8TEST001',
                'scheduled_procedure_step_description': '흉부 X선',
                'requested_procedure_description': '흉부 X선',
                'order_code': 'XRAY01',
                'route': 'INNOVISION',
            },
        ]

    def test_specific_character_set_is_utf8(self):
        dataset = cfind.to_mwl_dataset(self.manual_payload[0])
        self.assertEqual(dataset.SpecificCharacterSet, 'ISO_IR 192')

    def test_korean_patient_name_survives_json_load(self):
        with tempfile.TemporaryDirectory() as workdir:
            path = os.path.join(workdir, 'current_worklist.json')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(json.dumps({'entries': self.manual_payload}, ensure_ascii=False, indent=2))
            rows = cfind.load_current_worklist(path)
        self.assertEqual(rows[0]['patient_name'], '이진성')

    def test_korean_patient_name_in_dataset(self):
        dataset = cfind.to_mwl_dataset(self.manual_payload[0])
        self.assertEqual(dataset.PatientName, '이진성')

    def test_korean_procedure_description_in_dataset(self):
        dataset = cfind.to_mwl_dataset(self.manual_payload[0])
        self.assertEqual(dataset.RequestedProcedureDescription, '흉부 X선')
        self.assertEqual(
            dataset.ScheduledProcedureStepSequence[0].ScheduledProcedureStepDescription,
            '흉부 X선',
        )

    def test_modality_filtering_still_works(self):
        routed = cfind.filter_by_modality(self.manual_payload, modality='CR')
        self.assertEqual(len(routed), 1)
        self.assertEqual(routed[0]['patient_name'], '이진성')
        self.assertEqual(routed[0]['modality'], 'CR')

    def test_every_dataset_has_iso_ir_192(self):
        datasets = cfind.build_mwl_datasets(self.manual_payload)
        self.assertEqual(datasets[0].SpecificCharacterSet, 'ISO_IR 192')

    def test_payload_shape_still_holds_existing_fields(self):
        row = {
            'mwl_key': 7,
            'eghis_key': '261864_1_0',
            'patient_id': '7435',
            'patient_name': '이진성',
            'patient_birth_date': '19830210',
            'patient_sex': 'M',
            'scheduled_dttm': '20260625080000',
            'anchor_dttm': '20260625080000',
            'accession_no': 'UTF8TEST001',
            'ord_cd': 'XRAY01',
            'route_name': 'INNOVISION',
            'scheduled_proc_desc': '흉부 X선',
            'requested_proc_desc': '흉부 X선',
        }
        entries = payload.build_payload_entries(
            [row],
            {
                'BMD': {'modality': 'BMD', 'station_aet': 'BMD', 'description': 'BMD'},
                'INNOVISION': {'modality': 'CR', 'station_aet': 'INNOVISION', 'description': '흉부 X선'},
            },
            'Asia/Seoul',
        )
        dataset = cfind.to_mwl_dataset(entries[0])
        self.assertEqual(dataset.SpecificCharacterSet, 'ISO_IR 192')
        self.assertEqual(dataset.PatientName, '이진성')
        self.assertEqual(dataset.Modality, 'CR')
        self.assertEqual(dataset.RequestedProcedureDescription, '흉부 X선')
        self.assertEqual(
            dataset.ScheduledProcedureStepSequence[0].ScheduledProcedureStepDescription,
            '흉부 X선',
        )


if __name__ == '__main__':
    unittest.main()
