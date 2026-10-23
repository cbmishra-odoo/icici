"""Pure-Python helpers: date parsing and normalising ICICI response shapes.

No Odoo imports here so the parsers can be unit-tested stand-alone.
"""
import json
from datetime import datetime

DATE_FORMATS = ('%d-%m-%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S')


def parse_date(value):
    if not value:
        return False
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text[:19] if 'T' in text else text[:10], fmt).date()
        except ValueError:
            continue
    return False


def parse_datetime(value):
    if not value:
        return False
    text = str(value).strip()
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(text[:19] if len(text) > 10 else text[:10], fmt)
        except ValueError:
            continue
    return False


def to_float(value):
    try:
        return float(str(value).replace(',', '')) if value not in (None, '') else 0.0
    except ValueError:
        return 0.0


def as_list(value):
    if value is None or value == '':
        return []
    return value if isinstance(value, list) else [value]


def generic_errors(resp):
    """Messages from the 500-style and IGRS-style failure shapes."""
    if not isinstance(resp, dict):
        return [str(resp)]
    errors = []
    for param in as_list(resp.get('params')):
        if isinstance(param, dict) and (param.get('message') or param.get('errorCode')):
            errors.append(' '.join(filter(None, [
                str(param.get('errorCode') or ''), param.get('message') or '',
                '(%s)' % param['paramName'] if param.get('paramName') else '',
            ])))
    if not errors and str(resp.get('status', '')).lower() in ('failure', 'failed'):
        info = resp.get('additional_error_info') or {}
        errors.append(' | '.join(filter(None, [
            resp.get('error_code'), resp.get('message'),
            info.get('error_code'), info.get('error_message'),
        ])))
    if not errors and resp.get('errorDescription') and resp.get('errorDescription') != 'Success':
        errors.append(resp['errorDescription'])
    return errors


def _irm_list(resp, out):
    fetch = resp.get('fetchList') or {}
    for ok in as_list(fetch.get('irmFetchSuccesful')):
        out['ok'] = True
        out['items'] += as_list(ok.get('irmList'))
    for bad in as_list(fetch.get('irmFetchFailure')):
        out['errors'].append('%s: %s %s' % (bad.get('errorCode'), bad.get('message'), bad.get('params') or ''))


def _settled_irm(resp, out):
    success = resp.get('fetchSuccess')
    if success is not None:
        out['ok'] = True
        out['items'] += as_list(success.get('irm'))
    failure = resp.get('fetchFailure')
    if failure:
        out['errors'].append('%s: %s' % (failure.get('errorCode'), failure.get('errorDescription')))
        for bad in as_list(failure.get('irmlList') or failure.get('irmList')):
            out['errors'].append('%s: %s' % (bad.get('irmNumber'), bad.get('message')))


def _shipping_list(resp, out):
    fetch = resp.get('fetchList') or {}
    for key, value in fetch.items():
        if 'succes' in key.lower():
            for ok in as_list(value):
                out['ok'] = True
                out['items'] += as_list(ok.get('shippingbillList'))
        elif 'fail' in key.lower():
            for bad in as_list(value):
                out['errors'].append('%s: %s' % (bad.get('errorCode'), bad.get('message')))


def _shipping_detail(resp, out):
    success = resp.get('fetchSuccess')
    if success is not None:
        out['ok'] = True
        out['items'] += as_list(success.get('shippingbillList'))
    failure = resp.get('fetchFailure')
    if failure:
        out['errors'].append('%s: %s' % (failure.get('errorCode'), failure.get('errorDescription')))
        for bad in as_list(failure.get('shippingbillList')):
            out['errors'].append('%s %s: %s' % (bad.get('shippingBillNo') or '', bad.get('formNo') or '', bad.get('message')))


def _outstanding(resp, out):
    if str(resp.get('status', '')).lower() != 'success':
        return
    out['ok'] = True
    customer = resp.get('CustomerDetails') or {}
    out['meta'] = {
        'customer_id': customer.get('CustomerID') or '',
        'credit_accounts': json.dumps((customer.get('CreditAccounts') or {}).get('CreditAccount'), indent=2),
        'gst_details': json.dumps((customer.get('GSTDetails') or {}).get('GSTDetail'), indent=2),
    }
    out['items'] += as_list((customer.get('AssignmentDetails') or {}).get('DTAssignment'))


HANDLERS = {
    'irm_list': _irm_list,
    'settled_irm': _settled_irm,
    'shipping_list': _shipping_list,
    'shipping_detail': _shipping_detail,
    'outstanding_remittance': _outstanding,
}


def extract(api_code, resp):
    """Normalise a response into {'ok', 'items', 'errors', 'meta'}."""
    out = {'ok': False, 'items': [], 'errors': [], 'meta': {}}
    if not isinstance(resp, dict):
        out['errors'] = ['Unexpected response: %r' % (resp,)]
        return out
    HANDLERS[api_code](resp, out)
    if not out['ok'] and not out['errors']:
        out['errors'] = generic_errors(resp) or ['Unrecognised response from ICICI.']
    return out
