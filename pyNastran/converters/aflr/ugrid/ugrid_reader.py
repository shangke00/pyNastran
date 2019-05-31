"""
Defines the following classes:
    - UGRID

"""
from __future__ import print_function
import os
from struct import Struct, unpack
import sys
from codecs import open

import numpy as np
from numpy import zeros, unique, array
from numpy import arange, hstack, setdiff1d, union1d
from cpylog import get_logger

#from pyNastran.bdf.field_writer_double import print_card_double
#from pyNastran.bdf.field_writer_16 import print_card_16
#from pyNastran.bdf.field_writer_8 import print_card_8

from pyNastran.bdf.field_writer_8 import print_float_8
from pyNastran.bdf.field_writer_16 import print_float_16


def read_ugrid(ugrid_filename=None,
               encoding=None, log=None, debug=True,
               read_shells=True, read_solids=True, check=True):
    """
    Creates the UGRID object

    Parameters
    ----------
    ugrid_filename : str (default=None -> popup)
        the ugrid filename
    debug : bool/None
        used to set the logger if no logger is passed in
            True:  logs debug/info/error messages
            False: logs info/error messages
            None:  logs error messages
    log : logging module object / None
        if log is set, debug is ignored and uses the
        settings the logging object has
    encoding : str; default=None
        is this used?

    Returns
    -------
    model : UGRID()
        an UGRID object
    """
    ugrid_model = UGRID(log=log, debug=debug,
                        read_shells=read_shells, read_solids=read_solids)
    ugrid_model.read_ugrid(ugrid_filename, check=check)
    return ugrid_model


class UGRID(object):
    """
    Interface to the AFLR UGrid format.
    """
    def __init__(self, log=None, debug=False, read_shells=True, read_solids=True):
        self.log = get_logger(log, 'debug' if debug else 'info')
        self.debug = debug
        self.n = 0

        self.nodes = array([], dtype='float32')
        self.tris = array([], dtype='int32')
        self.quads = array([], dtype='int32')
        self.pids = array([], dtype='int32')

        self.tets = array([], dtype='int32')
        self.penta5s = array([], dtype='int32')
        self.penta6s = array([], dtype='int32')
        self.hexas = array([], dtype='int32')
        self.read_shells = read_shells
        self.read_solids = read_solids

        self.isort = None

    def read_ugrid(self, ugrid_filename, check=True):
        """
        $
        $       NASTRAN INPUT DECK GENERATED BY UG_IO
        $
        BEGIN BULK
        $UG_IO_ Data
        $Number_of_BL_Vol_Tets 2426
        $UG_IO_ Data
        $Number_of_Bnd_Nodes 34350
        $UG_IO_ Data
        $Number_of_Nodes 399036
        $UG_IO_ Data
        $Number_of_Surf_Quads 20665
        $UG_IO_ Data
        $Number_of_Surf_Trias 27870
        $UG_IO_ Data
        $Number_of_Vol_Hexs 163670
        $UG_IO_ Data
        $Number_of_Vol_Pents_5 27875
        $UG_IO_ Data
        $Number_of_Vol_Pents_6 67892
        $UG_IO_ Data
        $Number_of_Vol_Tets 1036480
        """
        out = determine_dytpe_nfloat_endian_from_ugrid_filename(ugrid_filename)
        ndarray_float, float_fmt, nfloat, endian, ugrid_filename = out

        # more for documentation than anything else
        assert ndarray_float in ['float32', 'float64'], ndarray_float
        assert float_fmt in ['f', 'd'], float_fmt
        assert nfloat in [4, 8], nfloat
        assert endian in ['<', '>'], ndarray_float


        with open(ugrid_filename, 'rb') as ugrid_file:
            data = ugrid_file.read(7 * 4)
            self.n += 7 * 4

            nnodes, ntris, nquads, ntets, npenta5s, npenta6s, nhexas = unpack(endian + '7i', data)
            npids = nquads + ntris
            nvol_elements = ntets + npenta5s + npenta6s + nhexas
            self.log.info('nnodes=%.3fm ntris=%s nquads=%s ntets=%.3fm'
                          ' npenta5s=%.3fm npenta6s=%.3fm nhexas=%.3fm' % (
                              nnodes / 1e6, ntris, nquads,
                              ntets / 1e6, npenta5s / 1e6, npenta6s / 1e6, nhexas / 1e6))

            nvolume_elements = ntets + npenta5s + npenta6s + nhexas
            self.log.info('nsurface_elements=%s nvolume_elements=%.3f Million' % (
                npids, nvolume_elements / 1e6))

            # we know the shapes of nodes (e.g. Nx3), but we want to directly
            # unpack the data into the array, so we shape it as N*3, load the
            # data and and then do a reshape
            self.log.debug('ndarray_float=%s' % (ndarray_float))
            #nodes = zeros(nnodes * 3, dtype=ndarray_float)
            tris = array([], dtype='int32')
            quads = array([], dtype='int32')
            #pids = zeros(npids, dtype='int32')
            #nodes = array([], dtype='float32')

            ## NODES
            nbytes_expected = nnodes * 3 * nfloat
            data = ugrid_file.read(nbytes_expected)
            self.n += nbytes_expected
            dtype = endian + float_fmt
            nodes = np.frombuffer(data, dtype=dtype).reshape((nnodes, 3)).copy()
            #print('min xyz value = ' , nodes.min())
            #print('max xyz value = ' , nodes.max())

            ## CTRIA3
            dtype = endian + 'i'
            if ntris:
                data = ugrid_file.read(ntris * 3 * 4)
                tris = np.frombuffer(data, dtype=dtype).reshape((ntris, 3)).copy()
                self.n += ntris * 3 * 4
                #print('min tris value = ' , tris.min())
                #print('max tris value = ' , tris.max())


            ## CQUAD4
            if nquads:
                nbytes_expected = nquads * 4 * 4
                data = ugrid_file.read(nbytes_expected)
                self.n += nbytes_expected
                assert len(data) == nbytes_expected, 'ndata=%s nbytes_expected=%s nquads_actual=%g nquads=%s' % (
                        len(data), nbytes_expected, len(data)/16., nquads)
                quads = np.frombuffer(data, dtype=dtype).reshape((nquads, 4)).copy()
                #print('min quads value = ' , quads.min())
                #print('max quads value = ' , quads.max())

            if npids:
                nbytes_expected = npids * 4
                data = ugrid_file.read(nbytes_expected)
                assert len(data) == nbytes_expected, 'len(data)=%s' % (len(data))
                self.n += nbytes_expected
                pids = np.frombuffer(data, dtype=dtype).copy()
                self.pids = pids
                #print('min pids value = ' , pids.min())
                #print('max pids value = ' , pids.max())

            self.nodes = nodes
            self.tris = tris
            self.quads = quads

            #==========================================
            # solids
            if not self.read_solids:
                #nids = np.unique(np.hstack([self.quads.ravel(), self.tris.ravel()]))
                #inid = np.searchsorted(np.arange(self.nodes.size), nids)
                #self.nodes = self.nodes[inid]
                return

            tets = zeros(ntets * 4, dtype='int32')
            penta5s = zeros(npenta5s * 5, dtype='int32')
            penta6s = zeros(npenta6s * 6, dtype='int32')
            hexas = zeros(nhexas * 8, dtype='int32')

            if ntets:
                ## CTETRA
                nbytes_expected = ntets * 4 * 4
                data = ugrid_file.read(nbytes_expected)
                tets = np.frombuffer(data, dtype=dtype).reshape((ntets, 4)).copy()
                self.n += nbytes_expected
                #print('min tets value = ' , tets.min())
                #print('max tets value = ' , tets.max())

            if npenta5s:
                ## CPYRAM
                nbytes_expected = npenta5s * 5 * 4
                data = ugrid_file.read(nbytes_expected)
                penta5s = np.frombuffer(data, dtype=dtype).reshape((npenta5s, 5)).copy()
                self.n += nbytes_expected
                #print('min penta5s value = ' , penta5s.min())
                #print('max penta5s value = ' , penta5s.max())

            if npenta6s:
                ## CPENTA
                nbytes_expected = npenta6s * 6 * 4
                data = ugrid_file.read(nbytes_expected)
                penta6s = np.frombuffer(data, dtype=dtype).reshape((npenta6s, 6)).copy()
                self.n += nbytes_expected
                #print('min penta6s value = ' , penta6s.min())
                #print('max penta6s value = ' , penta6s.max())

            if nhexas:
                ## CHEXA
                nbytes_expected = nhexas * 8 * 4
                data = ugrid_file.read(nbytes_expected)
                ndata = len(data)
                assert ndata == nbytes_expected, 'ndata=%s nbytes_expected=%s nhexas_actual=%g nhexas=%s' % (
                        ndata, nbytes_expected, ndata/32., nhexas)
                hexas = np.frombuffer(data, dtype=dtype).reshape((nhexas, 8)).copy()
                self.n += nhexas * 8 * 4
                #print('min hexas value = ' , hexas.min())
                #print('max hexas value = ' , hexas.max())

            self.tets = tets
            self.penta5s = penta5s
            self.penta6s = penta6s
            self.hexas = hexas

        if check:
            self.check_hanging_nodes()

    def write_bdf(self, bdf_filename, include_shells=True, include_solids=True,
                  convert_pyram_to_penta=True, write_grids=True, encoding=None,
                  size=16, is_double=False, check=True):
        """
        writes a Nastran BDF

        Parameters
        ----------
        size : int; {8, 16}; default=16
            the bdf write precision
        is_double : bool; default=False
            the field precision to write
        """
        self._check_node_ids()

        if encoding is None:
            encoding = sys.getdefaultencoding()
        #assert encoding.lower() in ['ascii', 'latin1', 'utf8'], encoding

        with open(bdf_filename, 'w', encoding=encoding) as bdf_file:
            #bdf_file.write('CEND\n')
            #bdf_file.write('BEGIN BULK\n')
            bdf_file.write('$ pyNastran: punch=True\n')
            bdf_file.write('$ pyNastran: encoding=utf-8\n')
            mid = 1
            bdf_file.write('MAT1, %i, 1.0e7,, 0.3\n' % mid)


            self.log.debug('writing GRIDs')
            write_grids = True
            if write_grids:
                if not self.read_solids:
                    nids_to_write = np.unique(np.hstack([self.quads.ravel(), self.tris.ravel()]))
                    nnodes = self.nodes.shape[0]
                    all_nids = np.arange(nnodes, dtype='int32')
                    inid = np.searchsorted(all_nids, nids_to_write)
                    unused_nodes = self.nodes[inid, :]

                    if size == 8:
                        for i, nid in enumerate(nids_to_write):
                            if i % 200000:  # pragma: no cover
                                print('  i = %s' % i)
                            node = self.nodes[i, :]
                            bdf_file.write('GRID    %8i%8s%s%s%s\n' % (
                                nid, '',
                                print_float_8(node[0]),
                                print_float_8(node[1]),
                                print_float_8(node[2])))
                    else:
                        for i, nid in enumerate(nids_to_write):
                            if i % 200000:  # pragma: no cover
                                print('  i = %s' % i)
                            node = self.nodes[i, :]
                            bdf_file.write('GRID*   %16i%16s%16s%16s\n'
                                           '*       %16s\n' % (
                                               nid,
                                               '',
                                               print_float_16(node[0]),
                                               print_float_16(node[1]),
                                               print_float_16(node[2])))
                else:
                    if check:
                        self.check_hanging_nodes()
                    if size == 8:
                        for i, node in enumerate(self.nodes):
                            node = self.nodes[i, :]
                            bdf_file.write('GRID    %8i%8s%s%s%s\n' % (
                                i + 1, '',
                                print_float_8(node[0]),
                                print_float_8(node[1]),
                                print_float_8(node[2])))
                    else:
                        for i, node in enumerate(self.nodes):
                            node = self.nodes[i, :]
                            bdf_file.write('GRID*   %16i%16s%16s%16s\n'
                                           '*       %16s\n' % (
                                               i + 1,
                                               '',
                                               print_float_16(node[0]),
                                               print_float_16(node[1]),
                                               print_float_16(node[2])))

                self.log.debug('finished writing GRIDs')

            eid = 1
            pids = self.pids #+ 1
            if include_shells:
                upids = unique(pids)  # auto-sorts
                for pid in upids:
                    bdf_file.write('PSHELL,%i,%i, 0.1\n' % (pid, mid))
                self.log.debug('writing CTRIA3')
                for element in self.tris:
                    assert len(np.unique(element)) == 3, element
                    bdf_file.write('CTRIA3  %-8i%-8i%-8i%-8i%-8i\n' % (
                        eid, pids[eid-1], element[0], element[1], element[2]))
                    eid += 1

                self.log.debug('writing CQUAD4')
                for element in self.quads:
                    assert len(np.unique(element)) == 4, element
                    bdf_file.write('CQUAD4  %-8i%-8i%-8i%-8i%-8i%-8i\n' % (
                        eid, pids[eid-1], element[0], element[1], element[2], element[3]))
                    eid += 1
            else:
                ntris = self.tris.shape[0]
                nquads = self.quads.shape[0]
                eid += ntris + nquads

            if len(pids) == 0:
                max_pid = 1
            else:
                max_pid = pids.max()
            #==========================================
            # solids
            if include_solids:
                pid = max_pid + 1
                eid, pid = self._write_bdf_solids(
                    bdf_file, eid, pid, convert_pyram_to_penta=convert_pyram_to_penta)
            bdf_file.write('ENDDATA\n')

    def check_hanging_nodes(self, stop_on_diff=True):
        """verifies that all nodes are used"""
        self.log.debug('checking hanging nodes')
        self._check_node_ids()

        tris = self.tris
        quads = self.quads
        unused_pids = self.pids

        nnodes = self.nodes.shape[0]
        ntris = tris.shape[0]
        nquads = quads.shape[0]

        if self.read_solids:
            tets = self.tets
            pyrams = self.penta5s
            pentas = self.penta6s
            hexas = self.hexas

            ntets = tets.shape[0]
            npyramids = pyrams.shape[0]
            npentas = pentas.shape[0]
            nhexas = hexas.shape[0]
        else:
            ntets = 0
            npyramids = 0
            npentas = 0
            nhexas = 0

        nids = []
        if ntris:
            nids.append(unique(tris.ravel()))
        if nquads:
            nids.append(unique(quads.ravel()))

        if ntets:
            nids.append(unique(tets.ravel()))
        if npyramids:
            nids.append(unique(pyrams.ravel()))
        if npentas:
            nids.append(unique(pentas.ravel()))
        if nhexas:
            nids.append(unique(hexas.ravel()))

        if len(nids) == 0:
            raise RuntimeError('there are no solid nodes; nids=%s' % nids)
        elif len(nids) == 1:
            nids = nids[0]
        else:
            nids = unique(hstack(nids))

        diff = []
        if nnodes != len(nids):
            expected = arange(1, nnodes + 1, dtype='int32')
            print('expected = %s' % expected)
            print('actual   = %s' % nids)

            diff = setdiff1d(expected, nids)
            diff2 = setdiff1d(nids, expected)
            diff = union1d(diff, diff2)
            msg = 'nnodes=%i len(actual)=%s expected-actual=%s (n=%s) actual-expected=%s (n=%s)' % (
                nnodes, len(nids),
                diff, len(diff),
                diff2, len(diff),
            )
            print(msg)
            print('nids = %s' % nids)
            if stop_on_diff:
                raise RuntimeError(msg)

        # check unique node ids
        for tri in tris:
            assert len(unique(tri)) == 3, tri
        for quad in quads:
            # assert len(unique(quad)) == 4, quad
            if len(unique(quad)) != 4:
                print(quad)
        for tet in tets:
            assert len(unique(tet)) == 4, tet
        for pyram in pyrams:
            assert len(unique(pyram)) == 5, pyram
        for penta in pentas:
            assert len(unique(penta)) == 6, penta
        for hexa in hexas:
            assert len(unique(hexa)) == 8, hexa
        return diff

    def _check_node_ids(self):
        tris = self.tris
        quads = self.quads
        pids = self.pids
        tets = self.tets
        pyrams = self.penta5s
        pentas = self.penta6s
        hexas = self.hexas
        if len(tris):
            assert tris.min() >= 1, tris.min()
        if len(quads):
            assert quads.min() >= 1, quads.min()
        if len(tets):
            assert tets.min() >= 1, tets.min()
        if len(pyrams):
            assert pyrams.min() >= 1, pyrams.min()
        if len(pentas):
            assert pentas.min() >= 1, pentas.min()
        if len(hexas):
            assert hexas.min() >= 1, hexas.min()

    def write_ugrid(self, ugrid_filename_out, check_shells=True, check_solids=True, check=True):
        """writes a UGrid model"""
        outi = determine_dytpe_nfloat_endian_from_ugrid_filename(ugrid_filename_out)
        unused_ndarray_float, float_fmt, unused_nfloat, endian, ugrid_filename = outi

        nodes = self.nodes
        nnodes = nodes.shape[0]

        tris = self.tris
        quads = self.quads
        pids = self.pids

        if len(pids):
            self.log.info('nupids=%s min=%s max=%s' % (np.unique(pids), pids.min(), pids.max()))
        else:
            self.log.warning('no surface_ids were found')
        tets = self.tets
        pyrams = self.penta5s
        pentas = self.penta6s
        hexas = self.hexas

        self._check_node_ids()

        ntris = tris.shape[0]
        nquads = quads.shape[0]
        npids = pids.shape[0]
        #print('ntris=%s nquads=%s' % (ntris, nquads))
        ntets = tets.shape[0]
        npyramids = pyrams.shape[0]
        npentas = pentas.shape[0]
        nhexas = hexas.shape[0]

        nshells = ntris + nquads
        assert nshells == npids, 'ntris=%s nquads=%s nshells=%s npids=%s' % (ntris, nquads, nshells, npids)
        if ntris:
            assert tris.shape[1] == 3, tris.shape
        if nquads:
            assert quads.shape[1] == 4, quads.shape

        nsolids = ntets + npyramids + npentas + nhexas
        if check_shells:
            assert nshells > 0, 'nquads=%s ntris=%s' % (nquads, ntris)
        if nsolids == 0 and check_solids:
            msg = 'ntets=%s npyramids=%s npentas=%s nhexas=%s' % (
                ntets, npyramids, npentas, nhexas)
            raise RuntimeError(msg)

        self.log.debug('writing ugrid=%r' % ugrid_filename)
        with open(ugrid_filename, 'wb') as f_ugrid:
            sfmt = Struct(endian + '7i')
            f_ugrid.write(sfmt.pack(nnodes, ntris, nquads, ntets, npyramids, npentas, nhexas))

            #def _write(f_ugrid, nodes_array, endian):
                #if endian == '<':
                    #f_ugrid.write(nodes_array.ravel().tobytes())
                #else:
                    #nodes_array = nodes_array.byteswap()
                    #f_ugrid.write(nodes_array.ravel().tobytes())

            #_write(f_ugrid, nodes, endian)
            #_write(f_ugrid, nodes, endian)
            #_write(f_ugrid, tris, endian)
            #_write(f_ugrid, quads, endian)
            #_write(f_ugrid, pids, endian)
            #_write(f_ugrid, tets, endian)
            #_write(f_ugrid, pyrams, endian)
            #_write(f_ugrid, pentas, endian)
            #_write(f_ugrid, hexas, endian)

            # %3f or %3d
            fmt = endian + '%i%s' % (nnodes * 3, float_fmt) # len(x,y,z) = 3
            sfmt = Struct(fmt)
            f_ugrid.write(sfmt.pack(*nodes.ravel()))

            # TODO: speed up with numpy
            if ntris:
                # CTRIA3
                fmt = endian + '%ii' % (ntris * 3)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*tris.ravel()))

            if nquads:
                # QUAD4
                fmt = endian + '%ii' % (nquads * 4)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*quads.ravel()))

            # PSHELL
            if nshells:
                fmt = endian + '%ii' % (nshells)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*pids.ravel()))

            if ntets:
                # CTETRA
                fmt = endian + '%ii' % (ntets * 4)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*tets.ravel()))

            if npyramids:
                # CPYRAM
                fmt = endian + '%ii' % (npyramids * 5)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*pyrams.ravel()))

            if npentas:
                # CPENTA
                fmt = endian + '%ii' % (npentas * 6)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*pentas.ravel()))

            if nhexas:
                # CHEXA
                fmt = endian + '%ii' % (nhexas * 8)
                sfmt = Struct(fmt)
                f_ugrid.write(sfmt.pack(*hexas.ravel()))
        if check:
            self.check_hanging_nodes()

    def _write_bdf_solids(self, bdf_file, eid, pid, convert_pyram_to_penta=True):
        """writes the Nastran BDF solid elements"""
        #pid = 0
        bdf_file.write('PSOLID,%i,1\n' % pid)
        self.log.debug('writing CTETRA')
        bdf_file.write('$ CTETRA\n')
        for element in self.tets:
            #card = ['CTETRA', eid, pid] + list(element)
            #f.write(print_int_card(card))
            bdf_file.write('CTETRA  %-8i%-8i%-8i%-8i%-8i%-8i\n' % (
                eid, pid, element[0], element[1], element[2], element[3]))
            eid += 1

        if convert_pyram_to_penta:
            # skipping the penta5s
            self.log.debug('writing CPYRAM as CPENTA with node6=node5')
            bdf_file.write('$ CPYRAM - CPENTA5\n')
            for element in self.penta5s:
                bdf_file.write('CPENTA  %-8i%-8i%-8i%-8i%-8i%-8i%-8i%-8i\n' % (
                    eid, pid, element[0], element[1], element[2], element[3],
                    element[4], element[4]))
                eid += 1
        else:
            self.log.debug('writing CPYRAM')
            bdf_file.write('$ CPYRAM - CPENTA5\n')
            for element in self.penta5s:
                bdf_file.write('CPYRAM  %-8i%-8i%-8i%-8i%-8i%-8i%-8i\n' % (
                    eid, pid, element[0], element[1], element[2], element[3], element[4]))
                eid += 1

        self.log.debug('writing CPENTA')
        bdf_file.write('$ CPENTA6\n')
        for element in self.penta6s:
            #card = ['CPENTA', eid, pid] + list(element)
            #f.write(print_int_card(card))
            bdf_file.write('CPENTA  %-8i%-8i%-8i%-8i%-8i%-8i%-8i%-8i\n' % (
                eid, pid, element[0], element[1], element[2], element[3], element[4], element[5]))
            eid += 1

        self.log.debug('writing CHEXA')
        bdf_file.write('$ CHEXA\n')
        for element in self.hexas:
            #card = ['CHEXA', eid, pid] + list(element)
            bdf_file.write('CHEXA   %-8i%-8i%-8i%-8i%-8i%-8i%-8i%-8i\n        %-8i%-8i\n' % (
                eid, pid, element[0], element[1], element[2], element[3],
                element[4], element[5], element[6], element[7]))
            #f.write(print_int_card(card))
            eid += 1
        return eid, pid

    def skin_solids(self):
        """Finds the CTRIA3s and CQUAD4 elements on the surface of the solid"""
        tris = []
        quads = []
        nhexas = self.hexas.shape[0]
        npenta6s = self.penta6s.shape[0]
        npenta5s = self.penta5s.shape[0]
        ntets = self.tets.shape[0]

        nquads = nhexas * 6 + npenta5s + 3 * npenta6s
        ntris = npenta5s * 4 + npenta6s * 2 + ntets * 4
        self.log.info('ntris=%s nquads=%s' % (ntris, nquads))
        if ntris:
            tris = zeros((ntris, 3), dtype='int32')
        if nquads:
            quads = zeros((nquads, 4), dtype='int32')

        print('ntris=%s nquads=%s' % (ntris, nquads))
        ntri_start = 0
        nquad_start = 0
        if ntets:
            faces1 = self.tets[:, [0, 1, 2]]
            faces2 = self.tets[:, [0, 1, 3]]
            faces3 = self.tets[:, [1, 2, 3]]
            faces4 = self.tets[:, [0, 2, 3]]
            tris[:ntets] = faces1
            tris[ntets:2*ntets] = faces2
            tris[2*ntets:3*ntets] = faces3
            tris[3*ntets:4*ntets] = faces4
            ntri_start += 4*ntets

        if nhexas:
            # btm (1-2-3-4)
            # top (5-6-7-8)
            # left (1-4-8-5
            # right (2-3-7-6)
            # front (1-2-6-5)
            # back (4-3-7-8)
            faces1 = self.hexas[:, [0, 1, 2, 3]] # 1,2,3,4
            faces2 = self.hexas[:, [4, 5, 6, 7]] # 5,6,7,8
            faces3 = self.hexas[:, [0, 3, 7, 4]]
            faces4 = self.hexas[:, [1, 2, 6, 5]]
            faces5 = self.hexas[:, [0, 1, 5, 4]]
            faces6 = self.hexas[:, [3, 2, 6, 7]]
            quads[: nhexas] = faces1
            quads[nhexas:2*nhexas] = faces2
            quads[2*nhexas:3*nhexas] = faces3
            quads[3*nhexas:4*nhexas] = faces4
            quads[4*nhexas:5*nhexas] = faces5
            quads[5*nhexas:6*nhexas] = faces6
            nquad_start += 6*nhexas

        if npenta5s:
            faces1 = self.penta5s[:, [0, 1, 2, 3]] # 1,2,3,4
            quads[nquad_start:nquad_start+npenta5s] = faces1

            faces2 = self.penta5s[:, [0, 1, 4]]
            faces3 = self.penta5s[:, [1, 2, 4]]
            faces4 = self.penta5s[:, [2, 3, 4]]
            faces5 = self.penta5s[:, [3, 0, 4]]
            tris[ntri_start           :ntri_start+  npenta5s] = faces2
            tris[ntri_start+  npenta5s:ntri_start+2*npenta5s] = faces3
            tris[ntri_start+2*npenta5s:ntri_start+3*npenta5s] = faces4
            tris[ntri_start+3*npenta5s:ntri_start+4*npenta5s] = faces5
            ntri_start += 4*npenta5s

        if npenta6s:
            faces1 = self.penta5s[:, [0, 1, 2]]
            faces2 = self.penta5s[:, [3, 4, 5]]
            quads[nquad_start         :nquad_start+  npenta5s] = faces1
            quads[nquad_start+npenta5s:nquad_start+2*npenta5s] = faces2

            faces3 = self.penta5s[:, [1, 4, 5, 3]]
            faces4 = self.penta5s[:, [0, 1, 4, 3]]
            faces5 = self.penta5s[:, [5, 3, 0, 2]]
            tris[ntri_start           :ntri_start+  npenta6s] = faces3
            tris[ntri_start+  npenta6s:ntri_start+2*npenta6s] = faces4
            tris[ntri_start+2*npenta6s:ntri_start+3*npenta6s] = faces5
        #from numpy.lib.arraysetops import unique
        #from numpy import lexsort

        #-----------------------------------------
        # we have two merged triangle faces of two neighboring TETRAs
        # and we need to merge them
        #
        # this could likely be much, much more efficient

        tri_array = np.array(tris)
        quad_array = np.array(quads)
        if 0:
            if ntris:
                #print(tris)
                #tris = tris.sort()
                #print(tris)
                tri_set = set()
                #tris = tris.sort()
                for tri in tris:
                    tri_set.add(tuple(tri))
                tri_array = array(list(tri_set))
            else:
                tri_array = np.array([])

            if nquads:
                quads.sort()
                unused_quad_set = set()
                # if tris:
                    # tris = vstack(tris)
                    # tris.sort(axis=0)
                    # tris = unique_rows(tris)
                # if quads:
                    # quads = vstack(quads)
                    # quads.sort(axis=0)
                    # quads = unique_rows(tris)
                raise NotImplementedError()
            else:
                quad_array = np.array(quads)

        #print(tris)
        #print(quads)
        return tris, quad_array


def determine_dytpe_nfloat_endian_from_ugrid_filename(ugrid_filename=None):
    """figures out what the format of the binary data is based on the filename"""
    if ugrid_filename is None:
        from pyNastran.utils.gui_io import load_file_dialog
        wildcard_wx = "AFLR3 UGRID (*.ugrid)|" \
            "*.ugrid|" \
            "All files (*.*)|*.*"
        wildcard_qt = "AFLR3 UGRID (*.ugrid);;All files (*)"
        title = 'Please select an AFLR3 UGRID to load'
        ugrid_filename = load_file_dialog(title, wildcard_wx, wildcard_qt)[0]
        assert ugrid_filename is not None, ugrid_filename

    try:
        unused_base, file_format, ext = os.path.basename(ugrid_filename).split('.')
    except ValueError:
        msg = ('expected file of the form "model.b8.ugrid" '
               'or "model.lb4.ugrid"; actual=%r' % ugrid_filename)
        raise ValueError(msg)
    assert ext == 'ugrid', 'extension=%r' % ext

    if '8' in file_format:
        ndarray_float = 'float64'
        float_fmt = 'd'
        nfloat = 8
    elif '4' in file_format:
        ndarray_float = 'float32'
        float_fmt = 'f'
        nfloat = 4
    else:  # ???
        msg = 'file_format=%r ugrid_filename=%s' % (file_format, ugrid_filename)
        raise NotImplementedError(msg)

    if 'lb' in file_format:  # C binary, little endian
        endian = '<'
    elif 'b' in file_format: # C binary, big endian
        endian = '>'
    #elif 'lr' in file_format: # Fortran unformatted binary, little endian
        #endian = '>'
    #elif 'r' in file_format:  # Fortran unformatted binary, big endian
        #endian = '>'
    else:  # fortran unformatted
        msg = 'file_format=%r ugrid_filename=%s' % (file_format, ugrid_filename)
        raise NotImplementedError(msg)
    return ndarray_float, float_fmt, nfloat, endian, ugrid_filename
