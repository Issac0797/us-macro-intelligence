"""Explain empty chart outputs without changing values, transforms or alignment."""


def availability(native, transformed, displayed, *, source_status='AVAILABLE', has_history=None):
    count = lambda rows: sum(p['value'] is not None for p in rows)
    status = 'AVAILABLE'
    if not count(displayed):
        if source_status != 'AVAILABLE': status = source_status
        elif not native: status = 'NO_OBSERVATIONS_IN_RANGE' if has_history else 'NEEDS_SYNC'
        elif not count(native): status = 'SOURCE_VALUES_MISSING'
        elif not displayed: status = 'NO_CLOSED_PERIODS'
        elif not count(transformed): status = 'INSUFFICIENT_TRANSFORM_DATA'
        else: status = 'NO_OBSERVATIONS_IN_RANGE'
    return dict(status=status, native_count=len(native), native_valid_count=count(native),
                transformed_valid_count=count(transformed), displayed_valid_count=count(displayed))
