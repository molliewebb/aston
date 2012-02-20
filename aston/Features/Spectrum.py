import math
from aston.Database import DBObject

class Spectrum(DBObject):
    def __init__(self, *args, **kwargs):
        super(Spectrum, self).__init__('spectrum', *args, **kwargs)

    @property
    def data(self):
        return self.rawdata

    
    def _calcInfo(self, fld):
        if fld == 'sp-d13c':
            return self.d13C()
        else:
            return ''
    
    def ion(self, ion):
        lst = dict(self.data)
        for i in lst:
            if math.abs(float(i)-ion) < 1:
                return float(lst[i])
        return None
            
    def d13C(self):
        #TODO: construct corr. factor curve over time from standards
        dt = self.getParentOfType('file')
        if self.getInfo('sp-type') == 'Standard':
            return dt.getInfo('r-d13c-std')
        
        stds = [(o.ion(44), o.ion(45), o.ion(46)) for o in \
          dt.getAllChildren('spectrum') \
          if o.getInfo('sp-type') == 'Standard']
        
        if len(stds) == 0:
            return ''
        i_std = stds[0]

        A, K = 0.5164, 0.0092
        rcpdb, rosmow = 0.011237, 0.002005

        #TODO: construct corr. factor curve over time from standards
        #abundance ratios of the isotope standard
        r45std = i_std[1] / i_std[0]
        r46std = i_std[2] / i_std[0]
        #known delta values for the peak
        r13std = (float(dt.getInfo('r-d13c-std'))/1000.+1)*rcpdb
        r18std = (0/1000.+1)*rosmow #approx. - shouldn't affect results much

        #determine the correction factors
        c45 = (r13std + 2*K*r18std**A)/r45std
        c46 = ((K*r18std**A)**2 + 2*r13std*K*r18std**A + 2*r18std)/r46std

        #correct the voltage ratios to ion ratios
        r45 = (a45/a44) * c45
        r46 = (a46/a44) * c46

        r18 = rosmow #best guess for oxygen ratio (VSMOW value)
        #newton's method to find 18/17O
        for _ in range(4):
            r18 -= (-3*(K*r18**A)**2 + 2*K*r45*r18**A + 2*r18 - r46) / \
                   (-6*A*K**2*r18**(2*A-1) + 2*A*K*r45*r18**(A-1) + 2)
        r13 = r45-2*K*r18**A
        return str(1000*(r13/rcpdb-1))
