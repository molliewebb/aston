import numpy as np
from aston.Features import Peak
from aston.TimeSeries import TimeSeries
from aston.Math.Peak import time
from aston.Math.PeakModels import peak_models
from aston.Math.PeakFitting import guess_initc, fit


def simple_integrate(ts, peak_list):
    """
    Integrate each peak naively; without regard to overlap.
    """
    peaks = []
    for t0, t1, hints in peak_list:
        pk_ts = ts.trace('!', twin=(t0, t1))
        if 'y0' in hints and 'y1' in hints:
            d = np.vstack([hints['y0'], ts.data, hints['y1']])
            t = np.hstack([t0, ts.times, t1])
            pk_ts = TimeSeries(d, t, ts.ions)
        info = {'name': '{:.2f}-{:.2f}'.format(t0, t1)}
        info['p-create'] = hints.get('pf', '') + ',simple_integrate'
        pk = Peak(None, None, None, info, pk_ts)
        peaks.append(pk)
    return peaks


def _get_windows(peak_list):
    """
    Given a list of peaks, bin them into windows.
    """
    win_list = []
    for t0, t1, hints in peak_list:
        p_w = (t0, t1)
        for w in win_list:
            if p_w[0] <= w[0][1] and p_w[1] >= w[0][0]:
                w[0] = (min(p_w[0], w[0][0]), \
                        max(p_w[1], w[0][1]))
                w[1].append((t0, t1, hints))
                break
        else:
            win_list.append([p_w, [(t0, t1, hints)]])
    return win_list


def drop_integrate(ts, peak_list):
    """
    Resolves overlap by breaking at the minimum value.
    """
    peaks = []
    for _, pks in _get_windows(peak_list):
        temp_pks = []
        pks = sorted(pks, key=lambda p: p[0])
        # go through list of peaks to make sure there's no overlap
        for t0, t1, hints in pks:
            # if this peak totally overlaps with an existing one, don't add
            if sum(1 for p in temp_pks if t1 <= p[1]) > 0:
                continue
            overlap_pks = [p for p in temp_pks if t0 <= p[1]]
            if len(overlap_pks) > 0:
                # find the last of the overlapping peaks
                overlap_pk = max(overlap_pks, key=lambda p: p[0])
                # get the section of trace and find the lowest point
                over_ts = ts.trace('!', twin=(t0, overlap_pk[1]))
                min_t = over_ts.times[over_ts.y.argmin()]

                # delete the existing overlaping peak
                for i, p in enumerate(temp_pks):
                    if p == overlap_pk:
                        del temp_pks[i]
                        break

                # if there are y-values, interpolate a new one
                if 'y0' in overlap_pk[2] and 'y1' in hints:
                    xs = np.array([overlap_pk[0], t1])
                    ys = np.array([overlap_pk[2]['y0'], hints['y1']])
                    y_val = np.interp(min_t, xs, ys)
                    overlap_pk[2]['y1'] = y_val
                    hints['y0'] = y_val

                # add the old and new peak in
                temp_pks.append((overlap_pk[0], min_t, overlap_pk[2]))
                temp_pks.append((min_t, t1, hints))
            else:
                temp_pks.append((t0, t1, hints))

        # none of our peaks should overlap, so we can just use
        # simple_integrate now
        peaks += simple_integrate(ts, temp_pks)
        for p in peaks:
            p.info['p-create'] = p.info['p-create'].split(',')[0] + \
                    ',drop_integrate'

    return peaks


def leastsq_integrate(ts, peak_list, f='gaussian'):
    win_list = _get_windows(peak_list)

    # lookup the peak model function to use for fitting
    f = {f.__name__: f for f in peak_models}[f]

    peaks = []
    for w, peak_list in win_list:
        tr = ts.trace(twin=w)
        # if there's location info, we can use this for
        # our inital params
        if 'x' in peak_list[0][2]:
            #TODO: should fill in other values?
            #TODO: should do something with y0 and y1?
            initc = [i[2] for i in peak_list]
        else:
            #TODO: should find peak maxima for rts?
            rts = [0.5 * (i[0] + i[1]) for i in peak_list]
            initc = guess_initc(tr, f, rts)
        params, _ = fit(tr, [f] * len(initc), initc)
        for p in params:
            pk_ts = TimeSeries(f(tr.times, **p), tr.times)
            info = {'name': '{:.2f}'.format(p['x'])}
            info['p-create'] = peak_list[0][2].get('pf', '') + \
                    ',' + 'leastsq_integrate'
            pk = Peak(None, None, None, info, pk_ts)
            peaks.append(pk)
    return peaks


def periodic_integrate(ts, peak_list, offset=0., period=1.):
    pass


def merge_ions(pks):
    cleaned_pks = []
    sort_pks = sorted(pks, key=lambda pk: time(pk.as_poly()))
    cur_t = np.nan
    for pk in sort_pks:
        if np.abs(cur_t - time(pk.as_poly())) < 0.01:
            c_pk = cleaned_pks[-1]
            if c_pk.data.ions[0] != pk.data.ions[0]:
                c_pk.rawdata = c_pk.rawdata & pk.rawdata
                if 's-mzs' in c_pk.info:
                    del c_pk.info['s-mzs']
            else:
                cleaned_pks.append(pk)
        else:
            cleaned_pks.append(pk)
        cur_t = time(pk.as_poly())

    return cleaned_pks
