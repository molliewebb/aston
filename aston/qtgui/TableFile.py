# -*- coding: utf-8 -*-

#    Copyright 2011-2013 Roderick Bovee
#
#    This file is part of Aston.
#
#    Aston is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Aston is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Aston.  If not, see <http://www.gnu.org/licenses/>.

"""
Model for handling display of open files.
"""
#pylint: disable=C0103

from __future__ import unicode_literals
import re
import json
from collections import OrderedDict
from PyQt4 import QtGui, QtCore
from aston.ui.QuantDialog import QuantDialog
from aston.ui.resources import resfile
from aston.ui.Fields import aston_fields, aston_groups, aston_field_opts
from aston.ui.MenuOptions import peak_models
from aston.databases.FileDatabase import AstonFileDatabase, LoadFilesThread

peak_models = {str(k): peak_models[k] for k in peak_models}


class FileTree(QtCore.QAbstractItemModel):
    """
    Handles interfacing with QTreeView and other file-related duties.
    """
    def __init__(self, database=None, tree_view=None, master_window=None, \
                 *args):
        QtCore.QAbstractItemModel.__init__(self, *args)

        self.db = database
        self.db._table = self
        self.master_window = master_window
        if type(database) == AstonFileDatabase:
            def_fields = '["name", "vis", "traces", "r-filename"]'
        else:
            def_fields = '["name"]'
        self.fields = json.loads(self.db.get_key('main_cols', dflt=def_fields))

        if tree_view is None:
            return
        else:
            self.tree_view = tree_view

        #set up proxy model
        self.proxyMod = FilterModel()
        self.proxyMod.setSourceModel(self)
        self.proxyMod.setDynamicSortFilter(True)
        self.proxyMod.setFilterKeyColumn(0)
        self.proxyMod.setFilterCaseSensitivity(False)
        tree_view.setModel(self.proxyMod)
        tree_view.setSortingEnabled(True)

        #set up selections
        tree_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        tree_view.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        #TODO: this works, but needs to be detached when opening a new folder
        tree_view.selectionModel().currentChanged.connect(self.itemSelected)
        #tree_view.clicked.connect(self.itemSelected)

        #set up key shortcuts
        delAc = QtGui.QAction("Delete", tree_view, \
            shortcut=QtCore.Qt.Key_Backspace, triggered=self.delItemKey)
        delAc = QtGui.QAction("Delete", tree_view, \
            shortcut=QtCore.Qt.Key_Delete, triggered=self.delItemKey)
        tree_view.addAction(delAc)

        #set up right-clicking
        tree_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree_view.customContextMenuRequested.connect(self.click_main)
        tree_view.header().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tree_view.header().customContextMenuRequested.connect( \
            self.click_head)
        tree_view.header().setStretchLastSection(False)

        #set up drag and drop
        tree_view.setDragEnabled(True)
        tree_view.setAcceptDrops(True)
        tree_view.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        tree_view.dragMoveEvent = self.dragMoveEvent

        #keep us aware of column reordering
        self.tree_view.header().sectionMoved.connect(self.colsChanged)

        #deal with combo boxs in table
        self.cDelegates = {}
        self.enableComboCols()

        #prettify
        tree_view.collapseAll()
        tree_view.setColumnWidth(0, 300)
        tree_view.setColumnWidth(1, 60)

        update_db = self.db.get_key('db_reload_on_open', dflt=True)
        if type(database) == AstonFileDatabase and update_db:
            self.loadthread = LoadFilesThread(self.db)
            self.loadthread.file_updated.connect(self.update_obj)
            self.loadthread.start()

    def dragMoveEvent(self, event):
        #TODO: files shouldn't be able to be under peaks
        #index = self.proxyMod.mapToSource(self.tree_view.indexAt(event.pos()))
        if event.mimeData().hasFormat('application/x-aston-file'):
            QtGui.QTreeView.dragMoveEvent(self.tree_view, event)
        else:
            event.ignore()

    def mimeTypes(self):
        types = QtCore.QStringList()
        types.append('text/plain')
        types.append('application/x-aston-file')
        return types

    def mimeData(self, indexList):
        data = QtCore.QMimeData()
        objs = [i.internalPointer() for i in indexList \
                if i.column() == 0]
        data.setText(self.items_as_csv(objs))

        id_lst = [str(o.db_id) for o in objs]
        data.setData('application/x-aston-file', ','.join(id_lst))
        return data

    def dropMimeData(self, data, action, row, col, parent):
        #TODO: drop files into library?
        #TODO: deal with moving objects between tables
        # i.e. copy from compounds table into file table
        fids = data.data('application/x-aston-file')
        if not parent.isValid():
            new_parent = self.db
        else:
            new_parent = parent.internalPointer()
        for db_id in [int(i) for i in fids.split(',')]:
            obj = self.db.object_from_id(db_id)
            if obj is not None:
                obj.parent = new_parent
        return True

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction

    def enableComboCols(self):
        for c in aston_field_opts.keys():
            if c in self.fields and c not in self.cDelegates:
                #new column, need to add combo support in
                opts = aston_field_opts[c]
                self.cDelegates[c] = (self.fields.index(c), \
                                      ComboDelegate(opts))
                self.tree_view.setItemDelegateForColumn(*self.cDelegates[c])
            elif c not in self.fields and c in self.cDelegates:
                #column has been deleted, remove from delegate list
                self.tree_view.setItemDelegateForColumn( \
                  self.cDelegates[c][0], self.tree_view.itemDelegate())
                del self.cDelegates[c]

    def index(self, row, column, parent):
        if row < 0 or column < 0 or column > len(self.fields):
            return QtCore.QModelIndex()
        elif not parent.isValid() and row < len(self.db.children):
            return self.createIndex(row, column, self.db.children[row])
        elif parent.column() == 0:
            sibs = parent.internalPointer().children
            if row >= len(sibs):
                return QtCore.QModelIndex()
            return self.createIndex(row, column, sibs[row])
        return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        obj = index.internalPointer()
        if obj.parent == self.db or obj is None:
            return QtCore.QModelIndex()
        else:
            row = obj.parent.parent.children.index(obj.parent)
            return self.createIndex(row, 0, obj.parent)

    def rowCount(self, parent):
        if not parent.isValid():
            return len(self.db.children)
        elif parent.column() == 0:
            return len(parent.internalPointer().children)
        else:
            return 0

    def columnCount(self, parent):
        return len(self.fields)

    def data(self, index, role):
        rslt = None
        fld = self.fields[index.column()].lower()
        f = index.internalPointer()
        if f is None:
            rslt = None
        elif fld == 'vis' and f.db_type == 'file':
            if role == QtCore.Qt.CheckStateRole:
                if f.info['vis'] == 'y':
                    rslt = QtCore.Qt.Checked
                else:
                    rslt = QtCore.Qt.Unchecked
        elif role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            if fld == 'p-model' and f.db_type == 'peak':
                rpeakmodels = {peak_models[k]: k for k in peak_models}
                rslt = rpeakmodels.get(f.info[fld], 'None')
            else:
                rslt = f.info[fld]
        elif role == QtCore.Qt.DecorationRole and index.column() == 0:
            #TODO: icon for method, compound
            fname = {'file': 'file.png', 'peak': 'peak.png', \
                    'spectrum': 'spectrum.png'}
            loc = resfile('aston/ui', 'icons/' + fname.get(f.db_type, ''))
            rslt = QtGui.QIcon(loc)
        return rslt

    def headerData(self, col, orientation, role):
        if orientation == QtCore.Qt.Horizontal and \
          role == QtCore.Qt.DisplayRole:
            if self.fields[col] in aston_fields:
                return aston_fields[self.fields[col]]
            else:
                return self.fields[col]
        else:
            return None

    def setData(self, index, data, role):
        data = str(data)
        col = self.fields[index.column()].lower()
        obj = index.internalPointer()
        if col == 'vis':
            obj.info['vis'] = ('y' if data == '2' else 'n')
            #redraw the main plot
            self.master_window.plotData()
        elif col == 'traces' or col[:2] == 't-':
            obj.info[col] = data
            if obj.info['vis'] == 'y':
                self.master_window.plotData()
        elif col == 'p-model':
            obj.update_model(peak_models[data])
            self.master_window.plotData(updateBounds=False)
        else:
            obj.info[col] = data
        obj.save_changes()
        self.dataChanged.emit(index, index)
        return True

    def flags(self, index):
        col = self.fields[index.column()].lower()
        obj = index.internalPointer()
        dflags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        dflags |= QtCore.Qt.ItemIsDropEnabled
        if not index.isValid():
            return dflags
        dflags |= QtCore.Qt.ItemIsDragEnabled
        if col == 'vis' and obj.db_type == 'file':
            dflags |= QtCore.Qt.ItemIsUserCheckable
        elif col in ['r-filename'] or col[:2] == 's-' or col == 'vis':
            pass
        elif obj.db_type == 'file' and (col[:2] == 'p-' or col[:3] == 'sp-'):
            pass
        elif obj.db_type != 'file' and (col[:2] == 't-' or col[:2] == 'r-'):
            pass
        else:
            dflags |= QtCore.Qt.ItemIsEditable
        return dflags

    def itemSelected(self):
        #TODO: update an info window?
        #remove the current spectrum
        self.master_window.plotter.clear_highlight()

        #remove all of the peak patches from the
        #main plot and add new ones in
        sel = self.returnSelFile()
        self.master_window.specplotter.libscans = []
        if sel is not None:
            if sel.db_type == 'file':
            #    self.master_window.plotter.clear_peaks()
            #    if sel.getInfo('vis') == 'y':
            #        self.master_window.plotter.add_peaks( \
            #            sel.getAllChildren('peak'))
                pass
            elif sel.db_type == 'peak':
                if sel.parent_of_type('file').info['vis'] == 'y':
                    self.master_window.plotter.draw_highlight_peak(sel)
            elif sel.db_type == 'spectrum':
                self.master_window.specplotter.libscans = [sel.data]
                self.master_window.specplotter.plot()
        objs_sel = len(self.returnSelFiles())
        self.master_window.show_status(str(objs_sel) + ' items selected')

    def colsChanged(self, *_):  # don't care about the args
        flds = [self.fields[self.tree_view.header().logicalIndex(fld)] \
                    for fld in range(len(self.fields))]
        self.db.set_key('main_cols', json.dumps(flds))

    def click_main(self, point):
        #index = self.proxyMod.mapToSource(self.tree_view.indexAt(point))
        menu = QtGui.QMenu(self.tree_view)
        sel = self.returnSelFiles()

        def _add_menu_opt(self, name, func, objs, menu):
            ac = menu.addAction(name, self.click_handler)
            ac.setData((func, objs))

        #Things we can do with peaks
        fts = [s for s in sel if s.db_type == 'peak']
        if len(fts) > 0:
            self._add_menu_opt(self.tr('Create Spec.'), \
                               self.createSpec, fts, menu)
            self._add_menu_opt(self.tr('Merge Peaks'), \
                               self.merge_peaks, fts, menu)
            self._add_menu_opt(self.tr('Quant'), \
                               self.quant_peaks, fts, menu)

        fts = [s for s in sel if s.db_type in ('spectrum', 'peak')]
        if len(fts) > 0:
            self._add_menu_opt(self.tr('Find in Lib'), \
                               self.find_in_lib, fts, menu)

        ##Things we can do with files
        #fts = [s for s in sel if s.db_type == 'file']
        #if len(fts) > 0:
        #    self._add_menu_opt(self.tr('Copy Method'), \
        #                       self.makeMethod, fts, menu)

        #Things we can do with everything
        if len(sel) > 0:
            self._add_menu_opt(self.tr('Delete Items'), \
                               self.delete_objects, sel, menu)
            #self._add_menu_opt(self.tr('Debug'), self.debug, sel)

        if not menu.isEmpty():
            menu.exec_(self.tree_view.mapToGlobal(point))

    def click_handler(self):
        func, objs = self.sender().data()
        func(objs)

    def delItemKey(self):
        self.delete_objects(self.returnSelFiles())

    def debug(self, objs):
        pks = [o for o in objs if o.db_type == 'peak']
        for pk in pks:
            x = pk.data[:, 0]
            y = pk.as_gaussian()
            plt = self.master_window.plotter.plt
            plt.plot(x, y, '-')
            self.master_window.plotter.canvas.draw()

    def merge_peaks(self, objs):
        from aston.Math.Integrators import merge_ions
        new_objs = merge_ions(objs)
        self.delete_objects([o for o in objs if o not in new_objs])

    def createSpec(self, objs):
        with self.db:
            for obj in objs:
                obj.children += [obj.as_spectrum()]

    def find_in_lib(self, objs):
        for obj in objs:
            if obj.db_type == 'peak':
                spc = obj.as_spectrum().data
            elif obj.db_type == 'spectrum':
                spc = obj.data
            lib_spc = self.master_window.cmpd_tab.db.find_spectrum(spc)
            if lib_spc is not None:
                obj.info['name'] = lib_spc.info['name']
                obj.save_changes()

    def quant_peaks(self, objs):
        self.dlg = QuantDialog(self.master_window, objs)
        self.dlg.show()

    #def makeMethod(self, objs):
    #    self.master_window.cmpd_tab.addObjects(None, objs)

    def click_head(self, point):
        menu = QtGui.QMenu(self.tree_view)
        subs = OrderedDict()
        for n in aston_groups:
            subs[n] = QtGui.QMenu(menu)

        for fld in aston_fields:
            if fld == 'name':
                continue
            grp = fld.split('-')[0]
            if grp in subs:
                ac = subs[grp].addAction(aston_fields[fld], \
                  self.click_head_handler)
            else:
                ac = menu.addAction(aston_fields[fld], \
                  self.click_head_handler)
            ac.setData(fld)
            ac.setCheckable(True)
            if fld in self.fields:
                ac.setChecked(True)

        for grp in subs:
            ac = menu.addAction(aston_groups[grp])
            ac.setMenu(subs[grp])

        menu.exec_(self.tree_view.mapToGlobal(point))

    def click_head_handler(self):
        fld = str(self.sender().data())
        if fld == 'name':
            return
        if fld in self.fields:
            indx = self.fields.index(fld)
            self.beginRemoveColumns(QtCore.QModelIndex(), indx, indx)
            for i in range(len(self.db.children)):
                self.beginRemoveColumns( \
                  self.index(i, 0, QtCore.QModelIndex()), indx, indx)
            self.fields.remove(fld)
            for i in range(len(self.db.children) + 1):
                self.endRemoveColumns()
        else:
            cols = len(self.fields)
            self.beginInsertColumns(QtCore.QModelIndex(), cols, cols)
            for i in range(len(self.db.children)):
                self.beginInsertColumns( \
                  self.index(i, 0, QtCore.QModelIndex()), cols, cols)
            self.tree_view.resizeColumnToContents(len(self.fields) - 1)
            self.fields.append(fld)
            for i in range(len(self.db.children) + 1):
                self.endInsertColumns()
        self.enableComboCols()
        self.colsChanged()
        #FIXME: selection needs to be updated to new col too?
        #self.tree_view.selectionModel().selectionChanged.emit()

    def update_obj(self, dbid, obj):
        if obj is None and dbid is None:
            self.master_window.show_status(self.tr('All Files Loaded'))
        elif obj is None:
            #TODO: delete files if they aren't present
            #c.execute('DELETE FROM files WHERE id=?', (dbid,))
            pass
        else:
            obj.parent = self.db

    def add_objects(self, parent, objs):
        pass

    def delete_objects(self, objs):
        with self.db:
            for obj in objs:
                obj.delete()
        self.master_window.plotData(updateBounds=False)

    def _obj_to_index(self, obj):
        if obj is None or obj == self.db:
            return QtCore.QModelIndex()
        elif obj in self.db.children:
            row = self.db.children.index(obj)
        else:
            row = obj.parent.children.index(obj)
        return self.createIndex(row, 0, obj)

    def active_file(self):
        """
        Returns the file currently selected in the file list.
        If that file is not visible, return the topmost visible file.
        Used for determing which spectra to display on right click, etc.
        """
        dt = self.returnSelFile()
        if dt is not None:
            if dt.db_type == 'file' and dt.info['vis'] == 'y':
                return dt

        dts = self.returnChkFiles()
        if len(dts) == 0:
            return None
        else:
            return dts[0]

    def returnChkFiles(self, node=None):
        """
        Returns the files checked as visible in the file list.
        """
        if node is None:
            node = QtCore.QModelIndex()

        chkFiles = []
        for i in range(self.proxyMod.rowCount(node)):
            prjNode = self.proxyMod.index(i, 0, node)
            f = self.proxyMod.mapToSource(prjNode).internalPointer()
            if f.info['vis'] == 'y':
                chkFiles.append(f)
            if len(f.children) > 0:
                chkFiles += self.returnChkFiles(prjNode)
        return chkFiles

    def returnSelFile(self):
        """
        Returns the file currently selected in the file list.
        Used for determing which spectra to display on right click, etc.
        """
        tab_sel = self.tree_view.selectionModel()
        if not tab_sel.currentIndex().isValid:
            return

        ind = self.proxyMod.mapToSource(tab_sel.currentIndex())
        if ind.internalPointer() is None:
            return  # it doesn't exist
        return ind.internalPointer()

    def returnSelFiles(self, cls=None):
        """
        Returns the files currently selected in the file list.
        Used for displaying the peak list, etc.
        """
        tab_sel = self.tree_view.selectionModel()
        files = []
        for i in tab_sel.selectedRows():
            obj = i.model().mapToSource(i).internalPointer()
            if cls is None or obj.db_type == cls:
                files.append(obj)
        return files

    def items_as_csv(self, itms, delim=',', incHeaders=True):
        flds = [self.fields[self.tree_view.header().logicalIndex(fld)] \
                for fld in range(len(self.fields))]
        row_lst = []
        block_col = ['vis']
        for i in itms:
            col_lst = [i.info[col] for col in flds \
                       if col not in block_col]
            row_lst.append(delim.join(col_lst))

        if incHeaders:
            try:  # for python 2
                flds = [unicode(aston_fields[i]) for i in flds \
                        if i not in ['vis']]
            except:  # for python 3
                flds = [aston_fields[i] for i in flds \
                        if i not in ['vis']]
            header = delim.join(flds) + '\n'
            table = '\n'.join(row_lst)
            return header + table


class FilterModel(QtGui.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(FilterModel, self).__init__(parent)

    def filterAcceptsRow(self, row, index):
        #if index.internalPointer() is not None:
        #    db_type = index.internalPointer().db_type
        #    if db_type == 'file':
        #        return super(FilterModel, self).filterAcceptsRow(row, index)
        #    else:
        #        return True
        #else:
        return super(FilterModel, self).filterAcceptsRow(row, index)

    def lessThan(self, left, right):
        tonum = lambda text: int(text) if text.isdigit() else text.lower()
        breakup = lambda key: [tonum(c) for c in re.split('([0-9]+)', key)]
        return breakup(str(left.data())) < breakup(str(right.data()))


class ComboDelegate(QtGui.QItemDelegate):
    def __init__(self, opts, *args):
        self.opts = opts
        super(ComboDelegate, self).__init__(*args)

    def createEditor(self, parent, option, index):
        cmb = QtGui.QComboBox(parent)
        cmb.addItems(self.opts)
        return cmb

    def setEditorData(self, editor, index):
        txt = index.data(QtCore.Qt.EditRole)
        if txt in self.opts:
            editor.setCurrentIndex(self.opts.index(txt))
        else:
            super(ComboDelegate, self).setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), QtCore.Qt.EditRole)