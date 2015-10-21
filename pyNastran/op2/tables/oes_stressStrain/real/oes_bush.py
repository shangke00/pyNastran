from __future__ import (nested_scopes, generators, division, absolute_import,
                        print_function, unicode_literals)
from six import iteritems
from numpy import zeros
from itertools import count

from pyNastran.op2.tables.oes_stressStrain.real.oes_objects import StressObject, StrainObject, OES_Object
from pyNastran.f06.f06_formatting import writeFloats13E, _eigenvalue_header


class RealBushArray(OES_Object):
    def __init__(self, data_code, is_sort1, isubcase, dt):
        OES_Object.__init__(self, data_code, isubcase, apply_data_code=False)
        self.eType = {}
        #self.code = [self.format_code, self.sort_code, self.s_code]
        #self.ntimes = 0  # or frequency/mode
        #self.ntotal = 0
        self.ielement = 0
        self.nelements = 0  # result specific
        print('RealBushArray.nonlinear_factor =', self.nonlinear_factor)
        sfdasdf

    def is_real(self):
        return True

    def is_complex(self):
        return False

    def _reset_indices(self):
        self.itotal = 0
        self.ielement = 0

    def _get_msgs(self):
        raise NotImplementedError('%s needs to implement _get_msgs' % self.__class__.__name__)

    def get_headers(self):
        raise NotImplementedError('%s needs to implement get_headers' % self.__class__.__name__)
        return headers

    def build(self):
        if self.is_built:
            return
        #print("self.ielement =", self.ielement)
        #print('ntimes=%s nelements=%s ntotal=%s' % (self.ntimes, self.nelements, self.ntotal))

        assert self.ntimes > 0, 'ntimes=%s' % self.ntimes
        assert self.nelements > 0, 'nelements=%s' % self.nelements
        assert self.ntotal > 0, 'ntotal=%s' % self.ntotal

        if self.element_type == 102:
            nnodes_per_element = 1
        else:
            raise NotImplementedError(self.element_type)

        self.itime = 0
        self.ielement = 0
        self.itotal = 0
        #self.ntimes = 0
        #self.nelements = 0
        self.is_built = True

        #print("***name=%s type=%s nnodes_per_element=%s ntimes=%s nelements=%s ntotal=%s" % (
            #self.element_name, self.element_type, nnodes_per_element, self.ntimes, self.nelements, self.ntotal))
        dtype = 'float32'
        if isinstance(self.nonlinear_factor, int):
            dtype = 'int32'
        self._times = zeros(self.ntimes, dtype=dtype)
        self.elements = zeros(self.ntotal, dtype='int32')

        # [tx, ty, tz, rx, ry, rz]
        self.data = zeros((self.ntimes, self.ntotal, 6), dtype='float32')

    def add_sort1(self, dt, eid, tx, ty, tz, rx, ry, rz):
        assert isinstance(eid, int)
        self._times[self.itime] = dt
        self.elements[self.itotal] = eid
        self.data[self.itime, self.itotal, :] = [tx, ty, tz, rx, ry, rz]
        self.itotal += 1
        self.ielement += 1

    def get_stats(self):
        if not self.is_built:
            return ['<%s>\n' % self.__class__.__name__,
                    '  ntimes: %i\n' % self.ntimes,
                    '  ntotal: %i\n' % self.ntotal,
                    ]

        nelements = self.ntotal
        ntimes = self.ntimes
        ntotal = self.ntotal
        nelements = self.ntotal

        msg = []
        if self.nonlinear_factor is not None:  # transient
            msg.append('  type=%s ntimes=%i nelements=%i\n'
                       % (self.__class__.__name__, ntimes, nelements))
            ntimes_word = 'ntimes'
        else:
            msg.append('  type=%s nelements=%i\n'
                       % (self.__class__.__name__, nelements))
            ntimes_word = 1
        headers = self.get_headers()

        n = len(headers)
        assert n == self.data.shape[2], 'nheaders=%s shape=%s' % (n, str(self.data.shape))
        msg.append('  data: [%s, ntotal, %i] where %i=[%s]\n' % (ntimes_word, n, n, str(', '.join(headers))))
        msg.append('  data.shape = %s\n' % str(self.data.shape).replace('L', ''))
        msg.append('  element type: %s\n  ' % self.element_name)
        msg += self.get_data_code()
        return msg

    def get_element_index(self, eids):
        # elements are always sorted; nodes are not
        itot = searchsorted(eids, self.elements)  #[0]
        return itot

    def eid_to_element_node_index(self, eids):
        ind = ravel([searchsorted(self.elements == eid) for eid in eids])
        return ind

    def write_f06(self, header, page_stamp, page_num=1, f=None, is_mag_phase=False, is_sort1=True):
        msg = self._get_msgs()
        (ntimes, ntotal) = self.data.shape[:2]
        eids = self.elements

        for itime in range(ntimes):
            dt = self._times[itime]
            header = _eigenvalue_header(self, header, itime, ntimes, dt)
            f.write(''.join(header + msg))

            #[tx, ty, tz, rx, ry, rz]
            tx = self.data[itime, :, 0]
            ty = self.data[itime, :, 1]
            tz = self.data[itime, :, 2]
            rx = self.data[itime, :, 3]
            ry = self.data[itime, :, 4]
            rz = self.data[itime, :, 5]

            # loop over all the elements
            for (i, eid, txi, tyi, tzi, rxi, ryi, rzi) in zip(
                count(), eids, tx, ty, tz, rx, ry, rz):

                vals = [txi, tyi, tzi, rxi, ryi, rzi]
                (vals2, is_all_zeros) = writeFloats13E(vals)
                [txi, tyi, tzi, rxi, ryi, rzi] = vals2
                msg.append('0                   %8i     %-13s %-13s %-13s %-13s %-13s %s\n' % (
                           eid, txi, tyi, tzi, rxi, ryi, rzi))
            f.write(page_stamp % page_num)
            page_num += 1
        if self.nonlinear_factor is None:
            page_num -= 1
        return page_num


class RealBushStressArray(RealBushArray, StressObject):
    def __init__(self, data_code, is_sort1, isubcase, dt):
        RealBushArray.__init__(self, data_code, is_sort1, isubcase, dt)
        StressObject.__init__(self, data_code, isubcase)

    def get_headers(self):
        headers = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
        return headers

    def _get_msgs(self):
        if self.element_type == 102:
            pass
        else:
            raise NotImplementedError(self.element_type)

        msg = [
            '                                  S T R E S S E S   I N   B U S H   E L E M E N T S        ( C B U S H )\n \n',
            '                  ELEMENT-ID        STRESS-TX     STRESS-TY     STRESS-TZ    STRESS-RX     STRESS-RY     STRESS-RZ \n',
        ]
        return msg

class RealBushStrainArray(RealBushArray, StrainObject):
    def __init__(self, data_code, is_sort1, isubcase, dt):
        RealBushArray.__init__(self, data_code, is_sort1, isubcase, dt)
        StrainObject.__init__(self, data_code, isubcase)

    def get_headers(self):
        headers = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']
        return headers

    def _get_msgs(self):
        if self.element_type == 102:
            pass
        else:
            raise NotImplementedError(self.element_type)

        msg = [
            '                                    S T R A I N S   I N   B U S H   E L E M E N T S        ( C B U S H )\n'
            ' \n'
            '                  ELEMENT-ID        STRAIN-TX     STRAIN-TY     STRAIN-TZ    STRAIN-RX     STRAIN-RY     STRAIN-RZ \n'
        ]
        return msg


class RealBushStress(StressObject):

    def __init__(self, data_code, is_sort1, isubcase, dt):
        StressObject.__init__(self, data_code, isubcase)
        self.eType = {}

        self.code = [self.format_code, self.sort_code, self.s_code]
        self.translations = {}
        self.rotations = {}

        self.dt = dt
        if is_sort1:
            if dt is not None:
                self.add_new_eid = self.add_new_eid_sort1
        else:
            assert dt is not None
            self.add_new_eid = self.add_new_eid_sort2

    def get_stats(self):
        nelements = len(self.eType)

        msg = self.get_data_code()
        if self.dt is not None:  # transient
            ntimes = len(self.translations)
            msg.append('  type=%s ntimes=%s nelements=%s\n'
                       % (self.__class__.__name__, ntimes, nelements))
        else:
            msg.append('  imaginary type=%s nelements=%s\n' % (self.__class__.__name__,
                                                               nelements))
        msg.append('  eType, translations, rotations\n')
        return msg

    def add_f06_data(self, data, transient):
        if transient is None:
            for line in data:
                (eType, eid, tx, ty, tz, rx, ry, rz) = line
                self.eType[eid] = 'CBUSH'
                self.translations[eid] = [tx, ty, tz]
                self.rotations[eid] = [rx, ry, rz]
            return

        (dtName, dt) = transient
        self.data_code['name'] = dtName

        if dt not in self.translations:
            self.update_dt(self.data_code, dt)

        for line in data:
            (eType, eid, tx, ty, tz, rx, ry, rz) = line
            self.eType[eid] = 'CBUSH'
            self.translations[dt][eid] = [tx, ty, tz]
            self.rotations[dt][eid] = [rx, ry, rz]

    def delete_transient(self, dt):
        del self.translations[dt]
        del self.rotations[dt]

    def get_transients(self):
        k = self.translations.keys()
        k.sort()
        return k

    def add_new_transient(self, dt):
        """
        initializes the transient variables
        """
        self.dt = dt
        self.translations[dt] = {}
        self.rotations[dt] = {}

    def add_new_eid(self, eType, dt, eid, tx, ty, tz, rx, ry, rz):
        self.eType[eid] = eType
        self.translations[eid] = [tx, ty, tz]
        self.rotations[eid] = [rx, ry, rz]

    def add_new_eid_sort1(self, eType, dt, eid, tx, ty, tz, rx, ry, rz):
        if dt not in self.translations:
            self.add_new_transient(dt)
        self.eType[eid] = eType
        self.translations[dt][eid] = [tx, ty, tz]
        self.rotations[dt][eid] = [rx, ry, rz]

    def write_f06(self, header, page_stamp, page_num=1, f=None, is_mag_phase=False, is_sort1=True):
        if self.nonlinear_factor is not None:
            return self._write_f06_transient(header, page_stamp, page_num, f, is_mag_phase=is_mag_phase, is_sort1=is_sort1)

        msg = header + [
            '                                  S T R E S S E S   I N   B U S H   E L E M E N T S        ( C B U S H )\n \n',
            '                  ELEMENT-ID        STRESS-TX     STRESS-TY     STRESS-TZ    STRESS-RX     STRESS-RY     STRESS-RZ \n',
        ]

        for eid, (tx, ty, tz) in sorted(iteritems(self.translations)):
            eType = self.eType[eid]
            (rx, ry, rz) = self.rotations[eid]

            vals = [tx, ty, tz, rx, ry, rz]
            (vals2, is_all_zeros) = writeFloats13E(vals)
            [tx, ty, tz, rx, ry, rz] = vals2
            msg.append('0                   %8i     %-13s %-13s %-13s %-13s %-13s %s\n' % (eid, tx, ty, tz, rx, ry, rz))

        msg.append(page_stamp % page_num)
        f.write(''.join(msg))
        return page_num

    def _write_f06_transient(self, header, page_stamp, page_num=1, f=None, is_mag_phase=False, is_sort1=True):
        words = [
            '                                  S T R E S S E S   I N   B U S H   E L E M E N T S        ( C B U S H )\n \n',
            '                  ELEMENT-ID        STRESS-TX     STRESS-TY     STRESS-TZ    STRESS-RX     STRESS-RY     STRESS-RZ \n',
        ]
        msg = []
        for dt, translations in sorted(iteritems(self.translations)):
            header[1] = ' %s = %10.4E\n' % (self.data_code['name'], dt)
            msg += header + words
            for eid, (tx, ty, tz) in sorted(iteritems(translations)):
                eType = self.eType[eid]
                (rx, ry, rz) = self.rotations[dt][eid]

                vals = [tx, ty, tz, rx, ry, rz]
                (vals2, is_all_zeros) = writeFloats13E(vals)
                [tx, ty, tz, rx, ry, rz] = vals2
                msg.append('0%8i   %-13s  %-13s  %-13s  %-13s  %-13s  %s\n' % (eid, tx, ty, tz, rx, ry, rz))

            msg.append(page_stamp % page_num)
            f.write(''.join(msg))
            page_num += 1
        return page_num - 1


class RealBushStrain(StrainObject):
    """
    """
    def __init__(self, data_code, is_sort1, isubcase, dt):
        StrainObject.__init__(self, data_code, isubcase)
        self.eType = {}

        self.code = [self.format_code, self.sort_code, self.s_code]
        self.translations = {}
        self.rotations = {}

        if is_sort1:
            if dt is not None:
                self.add_new_eid = self.add_new_eid_sort1
        else:
            assert dt is not None
            #self.add_new_eid = self.add_new_eid_sort2

    def get_stats(self):
        nelements = len(self.eType)

        msg = self.get_data_code()
        if self.dt is not None:  # transient
            ntimes = len(self.translations)
            msg.append('  type=%s ntimes=%s nelements=%s\n' % (self.__class__.__name__, ntimes, nelements))
        else:
            msg.append('  imaginary type=%s nelements=%s\n' % (self.__class__.__name__, nelements))
        msg.append('  eType, translations, rotations\n')
        return msg

    def add_f06_data(self, data, transient):
        if transient is None:
            for line in data:
                (eType, eid, tx, ty, tz, rx, ry, rz) = line
                self.eType[eid] = 'CBUSH'
                self.translations[eid] = [tx, ty, tz]
                self.rotations[eid] = [rx, ry, rz]
            return

        (dtName, dt) = transient
        self.data_code['name'] = dtName

        if dt not in self.translations:
            self.update_dt(self.data_code, dt)

        for line in data:
            (eType, eid, tx, ty, tz, rx, ry, rz) = line
            self.eType[eid] = 'CBUSH'
            self.translations[dt][eid] = [tx, ty, tz]
            self.rotations[dt][eid] = [rx, ry, rz]

    def delete_transient(self, dt):
        del self.translations[dt]
        del self.rotations[dt]

    def get_transients(self):
        k = self.translations.keys()
        k.sort()
        return k

    def add_new_transient(self, dt):
        """
        initializes the transient variables
        """
        self.dt = dt
        self.translations[dt] = {}
        self.rotations[dt] = {}

    def add_new_eid(self, eType, dt, eid, tx, ty, tz, rx, ry, rz):
        self.eType[eid] = eType
        self.translations[eid] = [tx, ty, tz]
        self.rotations[eid] = [rx, ry, rz]

    def add_new_eid_sort1(self, eType, dt, eid, tx, ty, tz, rx, ry, rz):
        if dt not in self.translations:
            self.add_new_transient(dt)
        self.eType[eid] = eType
        self.translations[dt][eid] = [tx, ty, tz]
        self.rotations[dt][eid] = [rx, ry, rz]

    def write_f06(self, header, page_stamp, page_num=1, f=None, is_mag_phase=False, is_sort1=True):
        if self.nonlinear_factor is not None:
            return self._write_f06_transient(header, page_stamp, page_num, f, is_mag_phase=is_mag_phase, is_sort1=is_sort1)

        msg = header + [
            '                                    S T R A I N S   I N   B U S H   E L E M E N T S        ( C B U S H )\n'
            ' \n'
            '                  ELEMENT-ID        STRAIN-TX     STRAIN-TY     STRAIN-TZ    STRAIN-RX     STRAIN-RY     STRAIN-RZ \n'
        ]
        for eid, (tx, ty, tz) in sorted(iteritems(self.translations)):
            eType = self.eType[eid]
            (rx, ry, rz) = self.rotations[eid]
            vals = [tx, ty, tz, rx, ry, rz]
            (vals2, is_all_zeros) = writeFloats13E(vals)
            [tx, ty, tz, rx, ry, rz] = vals2
            msg.append('0                   %8i     %-13s %-13s %-13s %-13s %-13s %s\n' % (eid, tx, ty, tz, rx, ry, rz))

        msg.append(page_stamp % page_num)
        f.write(''.join(msg))
        return page_num

    def __write_f06_transient(self, header, page_stamp, page_num=1, f=None, is_mag_phase=False, is_sort1=True):
        f.write('%s _write_f06_transient not implemented...\n' % self.__class__.__name__)
        raise NotImplementedError('CBUSH')
        return page_num - 1
