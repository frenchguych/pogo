# -*- coding: utf-8 -*-
#
# Author: Jendrik Seipp (jendrikseipp@web.de)
#         Ingelrest François (Francois.Ingelrest@gmail.com)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import sys, os

import gtk
from gobject import signal_new, TYPE_INT, TYPE_STRING, TYPE_BOOLEAN, TYPE_PYOBJECT, TYPE_NONE, SIGNAL_RUN_LAST

if __name__ == '__main__':
    base_dir = os.path.abspath(os.path.join(os.path.abspath(__file__), '../../'))
    sys.path.insert(0, base_dir)

from extTreeview import ExtTreeView

from tools import consts

# The format of a row in the treeview
(
    ROW_ICO, # Item icon
    ROW_NAME,     # Item name
    ROW_TRK,   # The track object
) = range(3)

# Internal d'n'd (reordering)
DND_REORDERING_ID   = 1024
DND_INTERNAL_TARGET = ('extListview-internal', gtk.TARGET_SAME_WIDGET, DND_REORDERING_ID)

signal_new('tracktreeview-dnd', gtk.TreeView, SIGNAL_RUN_LAST, TYPE_NONE, (gtk.gdk.DragContext, TYPE_INT, TYPE_INT, gtk.SelectionData, TYPE_INT, TYPE_PYOBJECT))



# Positioning constants below:
# POS_CENTER_BELOW: Centers the pop-up window below the button (default).
# POS_CENTER_ABOVE: Centers the pop-up window above the button.
# POS_NW_SW: Positions the pop-up window so that its North West (top right)
#            corner is on the South West corner of the button.
# POS_NW_NE: Positions the pop-up window so that its North West (top right)
#            corner is on the North East corner of the button.
# POS_SW_NW: Positions the pop-up window so that its South West (top right)
#            corner is on the North West corner of the button.
POS_CENTER_BELOW, POS_CENTER_ABOVE, POS_NW_SW, POS_NW_NE, POS_SW_NW = range(5)
# XXX: Add position symbols above as needed and implementation in
#      _update_popup_geometry()

class PopupMenuButton(gtk.ToggleButton):
    """A toggle button that displays a pop-up menu when clicked."""

    # INITIALIZERS #
    def __init__(self, label=None, menu_pos=POS_SW_NW):
        gtk.ToggleButton.__init__(self, label=label)
        self.set_relief(gtk.RELIEF_NONE)
        self.set_menu(gtk.Menu())

        self.menu_pos = menu_pos

        self.connect('toggled', self._on_toggled)


    # ACCESSORS #
    def set_menu(self, menu):
        if getattr(self, '_menu_selection_done_id', None):
            self.menu.disconnect(self._menu_selection_done_id)
        self.menu = menu
        self._menu_selection_done_id = self.menu.connect('selection-done', self._on_menu_selection_done)

    def _get_text(self):
        return unicode(self.get_label())
    def _set_text(self, value):
        self.set_label(value)
    text = property(_get_text, _set_text)


    # METHODS #
    def _calculate_popup_pos(self, menu):
        _w, menu_h = 0, 0
        menu_alloc = menu.get_allocation()
        if menu_alloc.height > 1:
            menu_h = menu_alloc.height
        else:
            _w, menu_h = menu.size_request()

        btn_window_xy = self.window.get_origin()
        btn_alloc = self.get_allocation()

        # Default values are POS_SW_NW
        x = btn_window_xy[0] + btn_alloc.x
        y = btn_window_xy[1] + btn_alloc.y - menu_h
        if self.menu_pos == POS_NW_SW:
            y = btn_window_xy[1] + btn_alloc.y + btn_alloc.height
        elif self.menu_pos == POS_NW_NE:
            x += btn_alloc.width
            y = btn_window_xy[1] + btn_alloc.y
        elif self.menu_pos == 10:
            x += btn_alloc.width
            y = btn_window_xy[1] + btn_alloc.y
        elif self.menu_pos == POS_CENTER_BELOW:
            x -= (menu_alloc.width - btn_alloc.width) / 2
        elif self.menu_pos == POS_CENTER_ABOVE:
            x -= (menu_alloc.width - btn_alloc.width) / 2
            y = btn_window_xy[1] - menu_alloc.height
        return (x, y, True)

    def popdown(self):
        self.menu.popdown()
        return True

    def popup(self):
        self.menu.popup(None, None, self._calculate_popup_pos, 0, 0)


    # EVENT HANDLERS #
    def _on_menu_selection_done(self, menu):
        self.set_active(False)

    def _on_toggled(self, togglebutton):
        assert self is togglebutton

        if self.get_active():
            self.popup()
        else:
            self.popdown()




class TrackTreeView(ExtTreeView):
    def __init__(self, colums, use_markup=True):
        ExtTreeView.__init__(self, colums, use_markup)
        
        #self.set_level_indentation(30)
        
        # Drag'n'drop management
        self.dndContext    = None
        self.dndSources    = None
        self.dndTargets    = consts.DND_TARGETS.values()
        self.motionEvtId   = None
        self.dndStartPos   = None
        self.dndReordering = False

        self.dndStartPos     = None
        self.isDraggableFunc = lambda: True
        
        if len(self.dndTargets) != 0:
            # Move one name around while dragging
            # self.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, \
            #        self.dndTargets+[DND_INTERNAL_TARGET], gtk.gdk.ACTION_MOVE)
            self.enable_model_drag_dest(self.dndTargets, gtk.gdk.ACTION_DEFAULT)
        
        #self.connect('drag-begin', self.onDragBegin)
        self.connect('drag-motion', self.onDragMotion)
        self.connect('drag-data-received', self.onDragDataReceived)
        
        #self.connect('button-press-event', self.onButtonPressed)
        
        self.mark = None
        
    def insert(self, target, source_row, drop_mode=None):
        model = self.store
        if drop_mode == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
            new = model.prepend(target, source_row)
        elif drop_mode == gtk.TREE_VIEW_DROP_INTO_OR_AFTER or drop_mode is None:
            new = model.append(target, source_row)
        elif drop_mode == gtk.TREE_VIEW_DROP_BEFORE:
            new = model.insert_before(None, target, source_row)
        elif drop_mode == gtk.TREE_VIEW_DROP_AFTER:
            new = model.insert_after(None, target, source_row)
        return new
        
    def appendRow(self, row, parent_iter=None):
        """ Append a row to the tree """
        return self.store.append(parent_iter, row)
        
    def removeRow(self, iter):
        """ Remove the given row """
        self.store.remove(iter)
        
    def getSelectedRows(self):
        sel_paths = self.selection.get_selected_rows()[1]
        return [self.store.get_iter(path) for path in sel_paths]
        
    def getFirstSelectedRow(self):
        sel_rows = self.getSelectedRows()
        if sel_rows:
            return sel_rows[0]
        return None
        
    def iterSelectedRows(self):
        """ Iterate on selected rows """
        for iter in self.getSelectedRows():
            yield iter
            
    def removeSelectedRows(self):
        '''
        Remove the rows in reverse order.
        Otherwise we remove the wrong rows, 
        because the paths will have changed
        '''
        for iter in reversed(self.getSelectedRows()):
            self.removeRow(iter)
        
    def setItem(self, iter, colIndex, value):
        """ Change the value of the given item """
        self.store.set_value(iter, colIndex, value)
        
    def getItem(self, iter, colIndex):
        """ Return the value of the given item """
        return self.store.get_value(iter, colIndex)
        
    def getTrack(self, iter):
        return self.getItem(iter, ROW_TRK)
        
    def getLabel(self, iter):
        label = self.getItem(iter, ROW_NAME)
        from xml.sax.saxutils import unescape
        label = unescape(label)
        return label
        
    def setLabel(self, iter, label):
        label = label.replace('_', ' ')
        return self.setItem(iter, ROW_NAME, label)
        
    def scroll(self, iter):
        self.scroll_to_cell(self.store.get_path(iter))
        
    def expand(self, iter):
        self.expand_to_path(self.store.get_path(iter))
        
    def get_nodename(self, iter):
        if not iter:
            return 'NoneValue'
        return self.store.get_value(iter, 1)
        
    def get_first_iter(self):
        return self.store.get_iter_root()
        
    def get_last_iter(self):
        return self.get_lowest_descendant(self.get_lowest_root())
        
    def get_lowest_root(self):
        root_nodes = len(self.store)
        if root_nodes == 0:
            return None
        return self.store.iter_nth_child(None, root_nodes-1)
        
    def get_all_parents(self, iter):
        ''' Returns a list of parent, grandparent, greatgrandparent, etc. '''
        parent = self.store.iter_parent(iter)
        while parent:
            yield parent
            parent = self.store.iter_parent(parent)
        
    def iter_prev(self, iter):
        path = self.store.get_path(iter)
        position = path[-1]
        if position == 0:
            return None
        prev_path = list(path)[:-1]
        prev_path.append(position - 1)
        prev = self.store.get_iter(tuple(prev_path))
        return prev
        
    def get_prev_iter(self, iter=None):
        '''
        Look for the previous iter in the tree
        '''
        #assert self.mark
        if iter is None:
            iter = self.getMark()
            if iter is None:
                return None
            
        # Check for a sibling or its children
        prev_iter = self.iter_prev(iter)
        if prev_iter:
            return self.get_lowest_descendant(prev_iter)
            
        # Check for the parent
        parent_iter = self.store.iter_parent(iter)
        if parent_iter:
            return parent_iter
        return None
        
    def get_next_iter(self, iter=None):
        '''
        Look for the next iter in the tree
        '''
        #assert self.mark
        if iter is None:
            iter = self.getMark()
            if iter is None:
                return self.get_first_iter()
            
        # Check for a child
        if self.store.iter_has_child(iter):
            first_child = self.store.iter_nth_child(iter, 0)
            return first_child
            
        # Check for a sibling
        next_iter = self.store.iter_next(iter)
        if next_iter:
            return next_iter
            
        # iter has no following siblings -> return uncle
        return self.get_uncle(iter)
            
    def get_uncle(self, iter):
        while True:
            parent = self.store.iter_parent(iter)
            if parent is None:
                # We have reached the top of the tree
                return None
            uncle = self.store.iter_next(parent)
            if uncle:
                return uncle
            iter = parent
            
    def get_lowest_descendant(self, iter):
        '''
        Find lowest descendant or return iter
        - a    -> c
          - b  -> b
          - c  -> c
        - d    -> d
        '''
        descendant = None
        if self.store.iter_has_child(iter):
            last_child = self.get_last_child_iter(iter)
            descendant = self.get_lowest_descendant(last_child)
        return descendant or iter
        
    def get_last_child_iter(self, iter):
        ''''''
        if not self.store.iter_has_child(iter):
            return None
        children = self.store.iter_n_children(iter)
        return self.store.iter_nth_child(iter, children-1)
        
    def get_last_iter_on_same_level(self, iter):
        ''''''
        parent = self.store.iter_parent(iter)
        if parent:
            return self.get_last_child_iter(parent)
        while True:
            sibling = self.store.iter_next(iter)
            if not sibling:
                return iter
            iter = sibling
            
    def iter_children(self, parent=None):
        """ Iterate on the children of the given iter """
        iter = self.store.iter_children(parent)

        while iter is not None:
            #print 'RETURNING', self.getLabel(iter), 'PARENT', parent, self.getLabel(self.store.get_iter_first())
            yield iter
            iter = self.store.iter_next(iter)
    
        
    # --== Mark management ==--


    def hasMark(self):
        """ True if a mark has been set """
        return self.mark is not None and self.mark.valid()


    def clearMark(self):
        """ Remove the mark """
        #if self.mark is not None:
            ##self.setItem(self.mark, self.markColumn, False)
        self.mark = None


    def getMark(self):
        """ Return the iter of the marked row """
        #if not self.hasMark():
        #    self.setMark(self.store.get_iter_root())
        if self.mark is None or not self.mark.valid():
            return None
        return self.store.get_iter(self.mark.get_path())


    def setMark(self, iter):
        """ Put the mark on the given row, it will move with the row itself (e.g., D'n'D) """
        #self.clearMark()
        self.mark = gtk.TreeRowReference(self.store, self.store.get_path(iter))
        
    
    def isAtMark(self, iter):
        '''
        Compare the marker path and the path of iter, because the iters alone
        will not predict equality
        '''
        if not self.hasMark():
            return False
        #print 'EQUALS', self.store.get_path(self.getMark()), self.store.get_path(iter), self.store.get_path(self.getMark()) == self.store.get_path(iter)
        return self.store.get_path(self.getMark()) == self.store.get_path(iter)
    
        
    
    # DRAG AND DROP
    
    def move_selected_rows(self, x, y):
        '''
        Method called when dnd happens inside the treeview
        '''
        drop = self.get_dest_row_at_pos(int(x), int(y))
        selection = self.getSelectedRows()
        
        model = self.store
        
        if drop:
            dest, drop_mode = drop
            dest = model.get_iter(dest)
        else:
            # Dropped on free space -> append
            dest, drop_mode = self.get_last_iter(), gtk.TREE_VIEW_DROP_AFTER
            
        self.freeze_child_notify()
        
        # filter selected tracks whose directories have been selected too
        iters = []
        for iter in selection:
            add = True
            for checked_iter in iters:
                if model.is_ancestor(checked_iter, iter):
                    add = False
            if model.is_ancestor(iter, dest):
                # Do not drop ancestors into children
                add = False
            if add:
                iters.append(iter)
        
        # Move the iters
        for index, iter in enumerate(iters):
            if index > 0:
                drop_mode = gtk.TREE_VIEW_DROP_AFTER
            
            track = self.getTrack(iter)
            if track:
                row = model[iter]
                dest = self.insert(dest, row, drop_mode)
                
                # adjust track label to __new__ parent
                parent = self.store.iter_parent(dest)
                parent_label = self.getLabel(parent) if parent else None
                self.setLabel(dest, track.get_label(parent_label))
                
                # Handle Mark
                if self.isAtMark(iter):
                    self.setMark(dest)
            else:
                dest = self.move_dir(iter, dest, drop_mode)
            
        for iter in iters:
            model.remove(iter)
        
        self.thaw_child_notify()
        
        
    def move_dir(self, dir_iter, target, drop_mode):
        '''
        Recursive Method that moves a dir to target
        '''
        children = self.store[dir_iter].iterchildren()
        dir_row = self.store[dir_iter]
        new_target = self.insert(target, dir_row, drop_mode)
        for child in children:
            child = child.iter
            track = self.getTrack(child)
            row = self.store[child]
            if track:
                dest = self.insert(new_target, row, gtk.TREE_VIEW_DROP_INTO_OR_AFTER)
                # Handle Mark
                if self.isAtMark(child):
                    self.setMark(dest)
            else:
                self.move_dir(child, new_target, gtk.TREE_VIEW_DROP_INTO_OR_AFTER)
        return new_target
            
        
    def enableDNDReordering(self):
        """ Enable the use of Drag'n'Drop to reorder the list """
        self.dndReordering = True
        self.dndTargets.append(DND_INTERNAL_TARGET)
        self.enable_model_drag_dest(self.dndTargets, gtk.gdk.ACTION_DEFAULT)


    def onDragDataReceived(self, tree, context, x, y, selection, dndId, time):
        """ Some data has been dropped into the list """
        if dndId == DND_REORDERING_ID:
            self.move_selected_rows(x, y)
        else:
            self.emit('tracktreeview-dnd', context, int(x), int(y), selection, dndId, time)


    def onDragMotion(self, tree, context, x, y, time):
        """
        Allow the following drops:
        - tracks onto and into dir
        - tracks between dirs
        - dir between dirs
        
        -> Prevent the drops:
        - dir into dir
        - anything into track
        """
        drop = self.get_dest_row_at_pos(int(x), int(y))

        if drop is not None:
            iter = self.store.get_iter(drop[0])
            #self.setItem(self.get_first_iter(), 1, str(drop[1])[1:-1])
            track = self.getTrack(iter)
            if track and (drop[1] == gtk.TREE_VIEW_DROP_INTO_OR_AFTER or drop[1] == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                # do not let the user drop anything here
                self.enable_model_drag_dest([('invalid-position', 0, -1)], gtk.gdk.ACTION_DEFAULT)
                return
        # Everything ok, enable dnd
        self.enable_model_drag_dest(self.dndTargets, gtk.gdk.ACTION_DEFAULT)
        
        
if __name__ == '__main__':    
    from gobject import TYPE_STRING, TYPE_INT, TYPE_PYOBJECT
    
    from tools import icons
    from media import getTracks
    
    tracks = getTracks(['/home/jendrik/Musik/Clearlake - Amber'])
    #print tracks
    
    columns = (('',   [(gtk.CellRendererPixbuf(), gtk.gdk.Pixbuf), (gtk.CellRendererText(), TYPE_STRING)], True),
                   (None, [(None, TYPE_INT)],                                                                 False),
                   (None, [(None, TYPE_STRING)],                                                               False),
                   (None, [(None, TYPE_PYOBJECT)], False),
                  )
                  
    tree = TrackTreeView(columns, True)
    
    track = None
    
    
    
    a = tree.appendRow((icons.nullMenuIcon(), 'a', 1, 'something', track), None)
    b = tree.appendRow((icons.nullMenuIcon(), 'b', 1, 'something', track), a)
    c = tree.appendRow((icons.nullMenuIcon(), 'c', 1, 'something', track), a)
    d = tree.appendRow((icons.nullMenuIcon(), 'd', 1, 'something', track), None)
    
    for iter in [a, b, c, d]:
        next = tree.get_next_iter(iter)
        print tree.get_nodename(iter), '->', tree.get_nodename(next)
        
    for iter in [a, b, c, d]:
        uncle = tree.get_uncle(iter)
        print 'Uncle(%s) = %s' % (tree.get_nodename(iter), tree.get_nodename(uncle))
        
    for iter in [a, b, c, d]:
        prev = tree.get_prev_iter(iter)
        print tree.get_nodename(prev), '<-', tree.get_nodename(iter)
        
    for iter in [a, b, c, d]:
        res = tree.get_last_iter_on_same_level(iter)
        print 'Last Sibling(%s) = %s' % (tree.get_nodename(iter), tree.get_nodename(res))
        
    for iter in [a, b, c, d]:
        res = tree.get_lowest_descendant(iter)
        print 'Lowest Descendant(%s) = %s' % (tree.get_nodename(iter), tree.get_nodename(res))
        
    res = tree.get_last_iter()
    print 'Last node: %s' % tree.get_nodename(res)
    
    res = list(tree.iter_children())
    print 'Children of root:', [tree.getLabel(iter) for iter in res]
    
    res = list(tree.iter_children(a))
    print 'Children of a:', [tree.getLabel(iter) for iter in res]
    
    win = gtk.Window()
    win.set_size_request(400,300)
    win.connect('destroy', lambda x: sys.exit())
    win.add(tree)
    tree.expand_all()
    
    win.show_all()
    gtk.main()