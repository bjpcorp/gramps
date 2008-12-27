# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program - Records plugin
#
# Copyright (C) 2008 Reinhard Müller
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id: $

#------------------------------------------------------------------------
#
# Standard Python modules
#
#------------------------------------------------------------------------
import datetime

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.lib import Date, EventType, Name
import BaseDoc
from BasicUtils import name_displayer
from DataViews import register, Gramplet
from gen.plug.menu import (BooleanOption, EnumeratedListOption, 
                           FilterOption, PersonOption)
from ReportBase import Report, ReportUtils, MenuReportOptions, \
        CATEGORY_TEXT
from gen.plug import PluginManager

MODE_GUI = PluginManager.REPORT_MODE_GUI
MODE_BKI = PluginManager.REPORT_MODE_BKI
MODE_CLI = PluginManager.REPORT_MODE_CLI

# from TransUtils import sgettext as _


#------------------------------------------------------------------------
#
# Global functions
#
#------------------------------------------------------------------------
def _find_records(db, filter, callname):

    today = datetime.date.today()
    today_date = Date(today.year, today.month, today.day)

    # Person records
    person_youngestliving = []
    person_oldestliving = []
    person_youngestdied = []
    person_oldestdied = []
    person_youngestmarried = []
    person_oldestmarried = []
    person_youngestdivorced = []
    person_oldestdivorced = []
    person_youngestfather = []
    person_youngestmother = []
    person_oldestfather = []
    person_oldestmother = []

    person_handle_list = db.get_person_handles(sort_handles=False)

    if filter:
        person_handle_list = filter.apply(db, person_handle_list)

    for person_handle in person_handle_list:
        person = db.get_person_from_handle(person_handle)

        birth_ref = person.get_birth_ref()

        if not birth_ref:
            # No birth event, so we can't calculate any age.
            continue

        birth = db.get_event_from_handle(birth_ref.ref)
        birth_date = birth.get_date_object()

        death_ref = person.get_death_ref()
        if death_ref:
            death = db.get_event_from_handle(death_ref.ref)
            death_date = death.get_date_object()
        else:
            death_date = None

        if not birth_date.is_regular():
            # Birth date unknown or incomplete, so we can't calculate any age.
            continue

        name = _person_get_display_name(person, callname)

        if death_ref is None:
            # Still living, look for age records
            _record(person_youngestliving, person_oldestliving,
                    today_date - birth_date, name, 'Person', person_handle)
        elif death_date.is_regular():
            # Already died, look for age records
            _record(person_youngestdied, person_oldestdied,
                    death_date - birth_date, name, 'Person', person_handle)

        for family_handle in person.get_family_handle_list():
            family = db.get_family_from_handle(family_handle)

            marriage_date = None
            divorce_date = None
            for event_ref in family.get_event_ref_list():
                event = db.get_event_from_handle(event_ref.ref)
                if event.get_type() == EventType.MARRIAGE:
                    marriage_date = event.get_date_object()
                elif event.get_type() == EventType.DIVORCE:
                    divorce_date = event.get_date_object()

            if marriage_date is not None and marriage_date.is_regular():
                _record(person_youngestmarried, person_oldestmarried,
                        marriage_date - birth_date,
                        name, 'Person', person_handle)

            if divorce_date is not None and divorce_date.is_regular():
                _record(person_youngestdivorced, person_oldestdivorced,
                        divorce_date - birth_date,
                        name, 'Person', person_handle)

            for child_ref in family.get_child_ref_list():
                child = db.get_person_from_handle(child_ref.ref)

                child_birth_ref = child.get_birth_ref()
                if not child_birth_ref:
                    continue

                child_birth = db.get_event_from_handle(child_birth_ref.ref)
                child_birth_date = child_birth.get_date_object()

                if not child_birth_date.is_regular():
                    continue

                if person.get_gender() == person.MALE:
                    _record(person_youngestfather, person_oldestfather,
                            child_birth_date - birth_date,
                            name, 'Person', person_handle)
                elif person.get_gender() == person.FEMALE:
                    _record(person_youngestmother, person_oldestmother,
                            child_birth_date - birth_date,
                            name, 'Person', person_handle)


    # Family records
    family_mostchildren = []
    family_youngestmarried = []
    family_oldestmarried = []
    family_shortest = []
    family_longest = []

    for family_handle in db.get_family_handles():
        family = db.get_family_from_handle(family_handle)

        father_handle = family.get_father_handle()
        if not father_handle:
            continue
        mother_handle = family.get_mother_handle()
        if not mother_handle:
            continue

        # Test if either father or mother are in filter
        if filter:
            if not filter.apply(db, [father_handle, mother_handle]):
                continue

        father = db.get_person_from_handle(father_handle)
        mother = db.get_person_from_handle(mother_handle)

        name = _("%s and %s") % (
                _person_get_display_name(father, callname),
                _person_get_display_name(mother, callname))

        _record(None, family_mostchildren,
                len(family.get_child_ref_list()),
                name, 'Family', family_handle)

        marriage = None
        divorce = None
        marriage_date = None
        divorce_date = None
        for event_ref in family.get_event_ref_list():
            event = db.get_event_from_handle(event_ref.ref)
            if event.get_type() == EventType.MARRIAGE:
                marriage = event
                marriage_date = event.get_date_object()
            elif event.get_type() == EventType.DIVORCE:
                divorce = event
                divorce_date = event.get_date_object()

        father_death = None
        father_death_date = None
        father_death_ref = father.get_death_ref()
        if father_death_ref:
            father_death = db.get_event_from_handle(father_death_ref.ref)
            father_death_date = father_death.get_date_object()

        mother_death = None
        mother_death_date = None
        mother_death_ref = mother.get_death_ref()
        if mother_death_ref:
            mother_death = db.get_event_from_handle(mother_death_ref.ref)
            mother_death_date = mother_death.get_date_object()

        if not marriage or not marriage_date.is_regular():
            # Not married or marriage date unknown
            continue

        if divorce and not divorce_date.is_regular():
            # Divorced, but divorce date unknown
            continue

        if father_death and (not father_death_date or not father_death_date.is_regular()):
            # Father dead, but death date unknown
            continue

        if mother_death and (not mother_death_date or not mother_death_date.is_regular()):
            # Mother dead, but death date unknown
            continue

        if not divorce and not father_death and not mother_death:
            # Still married and alive
            _record(family_youngestmarried, family_oldestmarried,
                    today_date - marriage_date,
                    name, 'Family', family_handle)
        else:
            end = None
            if father_death and mother_death:
                end = min(father_death_date, mother_death_date)
            elif father_death:
                end = father_death_date
            elif mother_death:
                end = mother_death_date
            if divorce:
                if end:
                    end = min(end, divorce_date)
                else:
                    end = divorce_date
            duration = end - marriage_date

            _record(family_shortest, family_longest,
                    end - marriage_date, name, 'Family', family_handle)

    return [(text, varname, locals()[varname]) for (text, varname, default) in RECORDS]


def _person_get_display_name(person, callname):

    # Make a copy of the name object so we don't mess around with the real
    # data.
    n = Name(source=person.get_primary_name())

    if n.call:
        if callname == RecordsReportOptions.CALLNAME_REPLACE:
            n.first_name = n.call
        elif callname == RecordsReportOptions.CALLNAME_UNDERLINE_ADD:
            if n.call in n.first_name:
                (before, after) = n.first_name.split(n.call)
                n.first_name = "%(before)s<u>%(call)s</u>%(after)s" % {
                        'before': before,
                        'call': n.call,
                        'after': after}
            else:
                n.first_name = "\"%(call)s\" (%(first)s)" % {
                        'call':  n.call,
                        'first': n.first_name}

    return name_displayer.display_name(n)


def _record(lowest, highest, value, text, handle_type, handle):

    if lowest is not None:
        lowest.append((value, text, handle_type, handle))
        lowest.sort(lambda a,b: cmp(a[0], b[0]))
        for i in range(3, len(lowest)):
            if lowest[i-1][0] < lowest[i][0]:
                del lowest[i:]
                break

    if highest is not None:
        highest.append((value, text, handle_type, handle))
        highest.sort(reverse=True)
        for i in range(3, len(highest)):
            if highest[i-1][0] > highest[i][0]:
                del highest[i:]
                break


def _output(value):

    if isinstance(value, tuple) and len(value) == 3:
        # time span as years, months, days
        (years, months, days) = value
        result = []
        if years == 1:
            result.append(_("1 year"))
        elif years != 0:
            result.append(_("%s years") % years)
        if months == 1:
            result.append(_("1 month"))
        elif months != 0:
            result.append(_("%s months") % months)
        if days == 1:
            result.append(_("1 day"))
        elif days != 0:
            result.append(_("%s days") % days)
        if not result:
            result.append(_("0 days"))
        return ", ".join(result)
    else:
        return str(value)


#------------------------------------------------------------------------
#
# The Gramplet
#
#------------------------------------------------------------------------
class RecordsGramplet(Gramplet):

    def init(self):
        self.set_use_markup(True)
        self.tooltip = _("Double-click name for details")
        self.set_text(_("No Family Tree loaded."))


    def db_changed(self):

        self.dbstate.db.connect('person-add', self.update)
        self.dbstate.db.connect('person-delete', self.update)
        self.dbstate.db.connect('person-update', self.update)
        self.dbstate.db.connect('family-add', self.update)
        self.dbstate.db.connect('family-delete', self.update)
        self.dbstate.db.connect('family-update', self.update)


    def main(self):

        self.set_text(_("Processing...") + "\n")
        records = _find_records(self.dbstate.db, None,
                RecordsReportOptions.CALLNAME_DONTUSE)
        self.set_text("")
        for (text, varname, top3) in records:
            self.render_text("<b>%s</b>" % text)
            last_value = None
            rank = 0
            for (number, (value, name, handletype, handle)) in enumerate(top3):
                if value != last_value:
                    last_value = value
                    rank = number
                self.append_text("\n  %s. " % (rank+1))
                # TODO: When linktype 'Family' is introduced, use this:
                # self.link(name, handletype, handle)
                # TODO: instead of this:
                if handletype == 'Family':
                    family = self.dbstate.db.get_family_from_handle(handle)
                    father_handle = family.get_father_handle()
                    father = self.dbstate.db.get_person_from_handle(father_handle)
                    father_name = _person_get_display_name(father, RecordsReportOptions.CALLNAME_DONTUSE)
                    self.link(father_name, 'Person', father_handle)
                    self.append_text(_(" and "))
                    mother_handle = family.get_mother_handle()
                    mother = self.dbstate.db.get_person_from_handle(mother_handle)
                    mother_name = _person_get_display_name(mother, RecordsReportOptions.CALLNAME_DONTUSE)
                    self.link(mother_name, 'Person', mother_handle)
                else:
                    self.link(name, handletype, handle)
                # TODO: end.
                self.append_text(" (%s)" % _output(value))
            self.append_text("\n")
        self.append_text("", scroll_to='begin')


#------------------------------------------------------------------------
#
# The Report
#
#------------------------------------------------------------------------
class RecordsReport(Report):

    def __init__(self, database, options_class):

        Report.__init__(self, database, options_class)
        menu = options_class.menu

        self.filter_option =  menu.get_option_by_name('filter')
        self.filter = self.filter_option.get_filter()

        self.callname = menu.get_option_by_name('callname').get_value()

        self.include = {}
        for (text, varname, default) in RECORDS:
            self.include[varname] = menu.get_option_by_name(varname).get_value()


    def write_report(self):
        """
        Build the actual report.
        """

        records = _find_records(self.database, self.filter, self.callname)

        self.doc.start_paragraph('REC-Title')
        self.doc.write_text(_("Records"))
        self.doc.end_paragraph()

        for (text, varname, top3) in records:
            if not self.include[varname]:
                continue

            self.doc.start_paragraph('REC-Heading')
            self.doc.write_text(text)
            self.doc.end_paragraph()

            last_value = None
            rank = 0
            for (number, (value, name, handletype, handle)) in enumerate(top3):
                if value != last_value:
                    last_value = value
                    rank = number
                self.doc.start_paragraph('REC-Normal')
                self.doc.write_text(_("%(number)s. %(name)s (%(value)s)") % {
                    'number': rank+1,
                    'name': name,
                    'value': _output(value)})
                self.doc.end_paragraph()


#------------------------------------------------------------------------
#
# MenuReportOptions
#
#------------------------------------------------------------------------
class RecordsReportOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.
    """

    CALLNAME_DONTUSE = 0
    CALLNAME_REPLACE = 1
    CALLNAME_UNDERLINE_ADD = 2

    def __init__(self, name, dbase):

        self.__pid = None
        self.__filter = None
        self.__db = dbase
        MenuReportOptions.__init__(self, name, dbase)


    def add_menu_options(self, menu):

        category_name = _("Report Options")

        self.__filter = FilterOption(_("Filter"), 0)
        self.__filter.set_help(
                         _("Determines what people are included in the report"))
        menu.add_option(category_name, "filter", self.__filter)
        self.__filter.connect('value-changed', self.__filter_changed)
        
        self.__pid = PersonOption(_("Filter Person"))
        self.__pid.set_help(_("The center person for the filter"))
        menu.add_option(category_name, "pid", self.__pid)
        self.__pid.connect('value-changed', self.__update_filters)
        
        self.__update_filters()

        callname = EnumeratedListOption(_("Use call name"), self.CALLNAME_DONTUSE)
        callname.set_items([
            (self.CALLNAME_DONTUSE, _("Don't use call name")),
            (self.CALLNAME_REPLACE, _("Replace first name with call name")),
            (self.CALLNAME_UNDERLINE_ADD, _("Underline call name in first name / add call name to first name"))])
        menu.add_option(category_name, "callname", callname)

        for (text, varname, default) in RECORDS:
            option = BooleanOption(text, default)
            if varname.startswith('person'):
                category_name = _("Person Records")
            elif varname.startswith('family'):
                category_name = _("Family Records")
            menu.add_option(category_name, varname, option)


    def __update_filters(self):
        """
        Update the filter list based on the selected person
        """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        filter_list = ReportUtils.get_person_filters(person, False)
        self.__filter.set_filters(filter_list)


    def __filter_changed(self):
        """
        Handle filter change. If the filter is not specific to a person,
        disable the person option
        """
        filter_value = self.__filter.get_value()
        if filter_value in [1, 2, 3, 4]:
            # Filters 1, 2, 3 and 4 rely on the center person
            self.__pid.set_available(True)
        else:
            # The rest don't
            self.__pid.set_available(False)


    def make_default_style(self, default_style):

        #Paragraph Styles
        font = BaseDoc.FontStyle()
        font.set_type_face(BaseDoc.FONT_SANS_SERIF)
        font.set_size(10)
        font.set_bold(0)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The basic style used for the text display.'))
        default_style.add_paragraph_style('REC-Normal', para)

        font = BaseDoc.FontStyle()
        font.set_type_face(BaseDoc.FONT_SANS_SERIF)
        font.set_size(10)
        font.set_bold(1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The style used for headings.'))
        default_style.add_paragraph_style('REC-Heading', para)

        font = BaseDoc.FontStyle()
        font.set_type_face(BaseDoc.FONT_SANS_SERIF)
        font.set_size(12)
        font.set_bold(1)
        para = BaseDoc.ParagraphStyle()
        para.set_font(font)
        para.set_description(_("The style used for the report title"))
        default_style.add_paragraph_style('REC-Title', para)


#------------------------------------------------------------------------
#
# Translation hack
#
#------------------------------------------------------------------------
mytranslation = {
        u"Records"                        : u"Rekorde",
        u"%s and %s"                      : u"%s und %s",
        u" and "                          : u" und ",
        u"1 year"                         : u"1 Jahr",
        u"%s years"                       : u"%s Jahre",
        u"1 month"                        : u"1 Monat",
        u"%s months"                      : u"%s Monate",
        u"1 day"                          : u"1 Tag",
        u"%s days"                        : u"%s Tage",
        u"0 days"                         : u"0 Tage",
        u"Youngest living person"         : u"Nesthäkchen",
        u"Oldest living person"           : u"Älteste lebende Person",
        u"Person died at youngest age"    : u"Am jüngsten gestorbene Person",
        u"Person died at oldest age"      : u"Im höchsten Alter gestorbene Person",
        u"Person married at youngest age" : u"Am jüngsten geheiratete Person",
        u"Person married at oldest age"   : u"Am ältesten geheiratete Person",
        u"Person divorced at youngest age": u"Am jüngsten geschiedene Person",
        u"Person divorced at oldest age"  : u"Am ältesten geschiedene Person",
        u"Youngest father"                : u"Jüngster Vater",
        u"Youngest mother"                : u"Jüngste Mutter",
        u"Oldest father"                  : u"Ältester Vater",
        u"Oldest mother"                  : u"Älteste Mutter",
        u"Couple with most children"      : u"Familie mit den meisten Kindern",
        u"Couple married most recently"   : u"Zuletzt geheiratetes Paar",
        u"Couple married most long ago"   : u"Am längsten verheiratetes Paar",
        u"Shortest marriage"              : u"Kürzeste Ehe",
        u"Longest marriage"               : u"Längste Ehe"}

from gettext import gettext
import locale
lang = locale.getdefaultlocale()[0]
if lang:
    lang = lang.split('_')[0]
def _(string):
    if lang == 'de':
        print string
        return mytranslation.get(string, gettext(string))
    else:
        return gettext(string)


#------------------------------------------------------------------------
#
# List of records (must be defined after declaration of _())
#
#------------------------------------------------------------------------
RECORDS = [
        (_("Youngest living person"),          'person_youngestliving',   True),
        (_("Oldest living person"),            'person_oldestliving',     True),
        (_("Person died at youngest age"),     'person_youngestdied',     False),
        (_("Person died at oldest age"),       'person_oldestdied',       True),
        (_("Person married at youngest age"),  'person_youngestmarried',  True),
        (_("Person married at oldest age"),    'person_oldestmarried',    True),
        (_("Person divorced at youngest age"), 'person_youngestdivorced', False),
        (_("Person divorced at oldest age"),   'person_oldestdivorced',   False),
        (_("Youngest father"),                 'person_youngestfather',   True),
        (_("Youngest mother"),                 'person_youngestmother',   True),
        (_("Oldest father"),                   'person_oldestfather',     True),
        (_("Oldest mother"),                   'person_oldestmother',     True),
        (_("Couple with most children"),       'family_mostchildren',     True),
        (_("Couple married most recently"),    'family_youngestmarried',  True),
        (_("Couple married most long ago"),    'family_oldestmarried',    True),
        (_("Shortest marriage"),               'family_shortest',         False),
        (_("Longest marriage"),                'family_longest',          True)]


#------------------------------------------------------------------------
#
# Register the gramplet and the report
#
#------------------------------------------------------------------------
pmgr = PluginManager.get_instance()
register(
        type="gramplet", 
        name= "Records Gramplet", 
        tname=_("Records Gramplet"), 
        height=230,
        expand=True,
        content = RecordsGramplet,
        title=_("Records"))

pmgr.register_report(
        name = 'records',
        category = CATEGORY_TEXT,
        report_class = RecordsReport,
        options_class = RecordsReportOptions,
        modes = MODE_GUI | MODE_BKI | MODE_CLI,
        translated_name = _("Records Report"),
        status = _("Stable"),
        author_name = u"Reinhard Müller",
        author_email = "reinhard.mueller@bytewise.at",
        description = _(
            "Shows some interesting records about people and families"))
