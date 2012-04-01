# -*- coding: utf-8 -*-
#
# Copyright (c) 2010  Jendrik Seipp (jendrikseipp@web.de)
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

import os
import subprocess
import sys
import logging
from gettext import gettext as _

import gtk
import gobject

import tools
import modules
import media
from tools import consts

search_text = _('Search in your music folders')

# Module information
MOD_INFO = ('Search', ('Search'), search_text, [], True, False)
MOD_NAME = MOD_INFO[modules.MODINFO_NAME]

MIN_CHARS = 1
CACHE_QUERY = "Caching files"



class Search(modules.ThreadedModule):

    def __init__(self):
        """ Constructor """
        handlers = {
                        consts.MSG_EVT_APP_STARTED:         self.onAppStarted,
                        consts.MSG_EVT_SEARCH_START:        self.onSearch,
                        consts.MSG_EVT_MUSIC_PATHS_CHANGED: self.onPathsChanged,
                   }

        modules.ThreadedModule.__init__(self, handlers)


    def search_dir(self, dir, query):
        cmd = ['find', dir]
        for part in query.split():
            cmd.extend(['-iwholename', '*%s*' % part])
        search = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        if query == CACHE_QUERY:
            logging.info('Caching "%s"' % dir)
            return []
        logging.info('Searching with command: %s' % ' '.join(cmd))
        self.searches.append(search)
        output, errors = search.communicate()
        if search.returncode < 0:
            # Process was killed
            return None
        output = sorted(output.splitlines(), key=str.lower)
        logging.info('Results for %s in %s: %s' % (query, dir, len(output)))
        return output


    def stop_searches(self):
        logging.info('Stopping all searches')
        # The kill() method was introduced in python2.6
        self.should_stop = True

        if not hasattr(subprocess.Popen, 'kill'):
            self.searches = []
            return

        for search in self.searches:
            if search.returncode is None:
                logging.debug('Killing process %d' % search.pid)
                search.kill()
        self.searches = []


    def filter_results(self, results, search_path, regexes):
        '''
        Remove subpaths of parent directories
        '''
        def same_case_bold(match):
            return 'STARTBOLD%sENDBOLD' % match.group(0)

        def get_name(path):
            # Remove the search path from the name
            if path == search_path:
                name = tools.dirname(path)
            else:
                name = path.replace(search_path, '')
            name = name.strip('/')

            for regex in regexes:
                name = regex.sub(same_case_bold, unicode(name))

            name = tools.htmlEscape(name)
            name = name.replace('STARTBOLD', '<b>').replace('ENDBOLD', '</b>')
            return name

        dirs = []
        files = []
        for path in results:
            if self.should_stop:
                return ([], [])

            # Check if this is only a subpath of a directory already handled
            is_subpath = False
            for dir in dirs:
                if path.startswith(dir):
                    is_subpath = True
                    break

            if not is_subpath:
                name = get_name(path)

                if os.path.isdir(path):
                    dirs.append((path, name))
                elif media.isSupported(path):
                    files.append((path, name))

        return (dirs, files)


    def cache_dirs(self, keep_caching):
        for index, path in enumerate(self.paths):
            # Cache dirs one by one after a small timeout
            gobject.timeout_add_seconds(3 * index, self.search_dir, path,
                                        CACHE_QUERY)
        # Keep caching in regular intervals
        return keep_caching


    def get_search_paths(self):
        """Do not search in subdirectories if we already search in parent dir.

        If path1 is a prefix of path2, return only path1. Always search in the
        user's home directory.
        """
        paths = set(self.paths)
        search_paths = []
        for path1 in paths:
            if not any(path1.startswith(path2) and not path1 == path2
                       for path2 in paths):
                search_paths.append(path1)
        logging.info('Searching at %s' % search_paths)
        return search_paths


    # --== Message handlers ==--


    def onAppStarted(self):
        """ The module has been loaded """
        wTree = tools.prefs.getWidgetsTree()
        self.searchbox = gtk.Entry()
        self.searchbox.set_size_request(210, -1)
        self.searchbox.set_tooltip_text(search_text)

        search_container = gtk.HBox()
        search_container.pack_start(self.searchbox, False)
        search_container.show_all()

        hbox3 = wTree.get_object('hbox3')
        hbox3.pack_start(search_container)
        hbox3.set_property('homogeneous', True)
        hbox3.reorder_child(search_container, 0)

        if hasattr(self.searchbox, 'set_icon_from_stock'):
            #self.searchbox.set_icon_from_stock(0, gtk.STOCK_FIND)
            #self.searchbox.set_icon_sensitive(0, False)
            self.searchbox.set_icon_from_stock(1, gtk.STOCK_CLEAR)
            self.searchbox.connect('icon-press', self.on_searchbox_clear)

        self.searchbox.connect('activate', self.on_searchbox_activate)
        self.searchbox.connect('changed', self.on_searchbox_changed)

        # Add search shortcut
        main_win = wTree.get_object('win-main')
        main_win.connect('key-press-event', self.on_key_pressed)
        self.searchbox.grab_focus()

        self.paths = []

        self.searches = []

        self.allow_caching = not '--multiple-instances' in sys.argv

        if self.allow_caching:
            # Cache the music folders regularly for faster searches
            gobject.timeout_add_seconds(100, self.cache_dirs, True)


    def onSearch(self, query):
        self.should_stop = False

        regexes = [tools.get_regex(part) for part in query.split()]

        for dir in self.get_search_paths():
            # Check if search has been aborted during filtering
            if self.should_stop:
                return

            results = self.search_dir(dir, query)

            # Check if search has been aborted during searching
            if results is None or self.should_stop:
                return

            dirs, files = self.filter_results(results, dir, regexes)
            if not self.should_stop:
                modules.postMsg(consts.MSG_EVT_SEARCH_APPEND,
                            {'results': (dirs, files), 'query': query})

        modules.postMsg(consts.MSG_EVT_SEARCH_END)


    def onPathsChanged(self, paths):
        self.paths = paths
        if self.allow_caching:
            # Cache the new paths once
            gobject.timeout_add_seconds(5, self.cache_dirs, False)


    #------- GTK handlers ----------------

    def on_key_pressed(self, widget, event):
        """
        Let search box grab the focus when "Ctrl-F" is hit
        """
        key_name = gtk.gdk.keyval_name(event.keyval)
        modifiers = event.get_state()
        ctrl_pressed = modifiers & gtk.gdk.CONTROL_MASK
        if key_name == 'f' and ctrl_pressed:
            self.searchbox.grab_focus()
            return True


    def on_searchbox_activate(self, entry):
        self.stop_searches()
        query = self.searchbox.get_text().strip()
        if len(query) < MIN_CHARS:
            msg = 'Search term has to have at least %d characters' % MIN_CHARS
            logging.info(msg)
            return
        query = self.searchbox.get_text().decode('utf-8')
        logging.info('Query: %s' % query)
        modules.postMsg(consts.MSG_EVT_SEARCH_START, {'query': query})


    def on_searchbox_changed(self, entry):
        if self.searchbox.get_text().strip() == '':
            self.stop_searches()
            modules.postMsg(consts.MSG_EVT_SEARCH_RESET, {})


    def on_searchbox_clear(self, entry, icon_pos, event):
        '''
        An icon has been pressed
        '''
        if icon_pos == 1:
            self.searchbox.set_text('')
