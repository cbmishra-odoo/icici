"""Stand-alone tests of the response parsers using the sample responses in ICICI's documents.

Run:  python3 icici_integration/tests/test_parsers.py   (no Odoo needed)
"""
import importlib.util
import os
import unittest

_spec = importlib.util.spec_from_file_location(
    'icici_utils', os.path.join(os.path.dirname(__file__), '..', 'models', 'icici_utils.py'))
u = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(u)


class TestParsers(unittest.TestCase):
    def test_irm_list_success(self):
        r = u.extract('irm_list', {'fetchList': {'irmFetchSuccesful': [{'errorCode': '200', 'message': 'Success', 'irmList': [
            {'remittanceRefNo': 'A1', 'remittanceDate': '16-01-2024'}, {'remittanceRefNo': 'B2', 'remittanceDate': '16-01-2024'}]}]}})
        self.assertTrue(r['ok'])
        self.assertEqual([i['remittanceRefNo'] for i in r['items']], ['A1', 'B2'])

    def test_irm_list_failure(self):
        r = u.extract('irm_list', {'fetchList': {'irmFetchFailure': [{'errorCode': '400ID', 'message': 'Invalid date format', 'params': 'fromRemittanceDate', 'irmList': []}]}})
        self.assertFalse(r['ok'])
        self.assertIn('Invalid date format', r['errors'][0])

    def test_settled_success_and_failure(self):
        ok = u.extract('settled_irm', {'fetchSuccess': {'errorCode': '200', 'irm': [{'remittanceRefNo': 'X'}]}})
        self.assertEqual(len(ok['items']), 1)
        bad = u.extract('settled_irm', {'fetchFailure': {'errorCode': '400', 'errorDescription': 'Invalid Request', 'irmlList': [{'irmNumber': 'Z', 'message': 'Invalid Data Entered'}]}})
        self.assertEqual(len(bad['errors']), 2)

    def test_shipping_list_dict_shape(self):
        r = u.extract('shipping_list', {'fetchList': {'shipBillFetchSuccesful': {'errorCode': '200', 'shippingbillList': [{'shippingBillNo': '6474676'}]}}})
        self.assertEqual(r['items'][0]['shippingBillNo'], '6474676')

    def test_shipping_detail(self):
        r = u.extract('shipping_detail', {'fetchSuccess': {'errorCode': '200', 'params': None, 'shippingbillList': [
            {'shippingBillNo': '6474676', 'invoiceList': [{'invoiceNo': 'I1'}]}]}})
        self.assertTrue(r['ok'])
        self.assertEqual(r['items'][0]['invoiceList'][0]['invoiceNo'], 'I1')

    def test_outstanding_remittance(self):
        r = u.extract('outstanding_remittance', {'status': 'Success', 'CustomerDetails': {'CustomerID': '5', 'CreditAccounts': {'CreditAccount': [{'AccountNo': '1'}]},
            'GSTDetails': {'GSTDetail': [{'GSTNumber': 'G'}]}, 'AssignmentDetails': {'DTAssignment': [{'GRSReferenceNo': 'G1'}]}}})
        self.assertEqual(r['meta']['customer_id'], '5')
        self.assertEqual(r['items'][0]['GRSReferenceNo'], 'G1')

    def test_outstanding_single_assignment_dict(self):
        r = u.extract('outstanding_remittance', {'status': 'Success', 'CustomerDetails': {'AssignmentDetails': {'DTAssignment': {'GRSReferenceNo': 'G1'}}}})
        self.assertEqual(len(r['items']), 1)

    def test_igrs_and_500_errors(self):
        r = u.extract('outstanding_remittance', {'status': 'FAILURE', 'error_code': 'XC00IGRS1E', 'message': 'Business Exception from IGRS',
                                                  'additional_error_info': {'error_code': 'E055', 'error_message': 'No credit account details found for given Customer ID.'}})
        self.assertIn('E055', r['errors'][0])
        r = u.extract('irm_list', {'errorDescription': 'Internal Server Error', 'params': [{'errorCode': '500', 'message': 'Internal system is not available', 'paramName': 'TOL unreachable'}], 'status': 'failure'})
        self.assertIn('500', r['errors'][0])

    def test_dates(self):
        self.assertEqual(str(u.parse_date('16-01-2024')), '2024-01-16')
        self.assertEqual(str(u.parse_date('2017-10-31')), '2017-10-31')
        self.assertEqual(str(u.parse_date('2020-10-30T00:00:00')), '2020-10-30')
        self.assertFalse(u.parse_date(None))
        self.assertEqual(str(u.parse_datetime('2020-10-30T00:00:00')), '2020-10-30 00:00:00')
        self.assertEqual(u.to_float('1323249.9974'), 1323249.9974)


if __name__ == '__main__':
    unittest.main()
